# Written by TheGurke 2011
"""GUI for the client program"""

import random
import math
import os
import re
from gettext import gettext as _
import logging

import gtk
import glib

from progenitus import *
from progenitus.db import cards
from progenitus.db import semantics
from progenitus.editor import decks
import network
import players
import desktop
import muc


class Interface(uiloader.Interface):
	
	isfullscreen = False
	_deck_load_async_handle = None
	_browser_cardlist = None
	_last_untapped = []
	_entrybar_task = "" # current task for the entry bar
	my_player = None # this client's player
	network_manager = None # the network manager instance
	players = [] # all players
	users = dict() # all users that joined the chat room
	
	def __init__(self, solitaire):
		super(self.__class__, self).__init__()
		self.load(config.GTKBUILDER_CLIENT)
		self.main_win.set_title(config.APP_NAME_CLIENT)
		self.main_win.maximize()
		glib.idle_add(cards.connect)
		
		# Insert a CairoDesktop
		self.cd = desktop.CairoDesktop(self, self.eventbox)
		self.eventbox.add(self.cd)
		self.hscale_zoom.set_value(2) # sync initial zoom level
		self.zoom_change()
		
		# Set CairoDesktop callbacks
		self.cd.prop_callback = self.call_properties
		self.cd.hover_callback = self.hover
		
		# Check if running in solitaire mode
		self.solitaire = solitaire
		if solitaire:
			self.solitaire_mode(None)
		else:
			self.network_manager = network.NetworkManager()
			self.network_manager.logger.log_callback = self.add_log_line
			self.network_manager.exception_handler = self.handle_exception
			
			# Set default login entries
			self.entry_username.set_text(settings.username)
			self.entry_pwd.set_text(settings.userpwd)
			self.checkbutton_save_pwd.set_active(settings.userpwd != "")
			self.entry_server.set_text(settings.server)
			self.entry_gamename.set_text(settings.gamename)
			self.entry_gamepwd.set_text(settings.gamepwd)
			if settings.userpwd != "":
				glib.idle_add(self.button_login.grab_focus)
			elif settings.username != "":
				glib.idle_add(self.entry_pwd.grab_focus)
			else:
				glib.idle_add(self.entry_username.grab_focus)
		
		# Initialize tokens
		self.init_counters_autocomplete()
		glib.idle_add(self.init_token_autocomplete)
	
	
	def show_about(self, widget):
		"""Display information about this program"""
		dialog = gtk.AboutDialog()
		dialog.set_name(config.APP_NAME_EDITOR)
		dialog.set_version(str(config.VERSION))
		dialog.set_copyright(_("Copyright by TheGurke 2011"))
		dialog.set_website(config.APP_WEBSITE)
		dialog.set_comments(_("This program is Free Software by the GPL3."))
		dialog.run()
		dialog.destroy()
	
	def init_token_autocomplete(self):
		"""Load the tokens into the autocompleting combobox"""
		cards.load_tokens()
		for token in cards.tokens:
			if token.power != "":
				desc = "%s %s/%s (%s)" % (token.subtype, token.power,
					token.toughness, token.setname)
			else:
				desc = "%s (%s)" % (token.subtype, token.setname)
			self.liststore_tokens.append((token.id, desc, token.setname,
				token.releasedate))
		
		# Complete the entry_tokens widget
		completion = gtk.EntryCompletion()
		completion.set_model(self.liststore_tokens)
		completion.set_text_column(1)
		completion.set_inline_completion(True)
		completion.set_minimum_key_length(2)
		completion.connect("match-selected", self.token_autocomplete_pick)
		self.entry_tokens.set_completion(completion)
	
	def init_counters_autocomplete(self):
		completion = gtk.EntryCompletion()
		completion.set_model(self.liststore_counters)
		completion.set_text_column(0)
		completion.set_inline_completion(False)
		completion.connect("match-selected", self.update_counter_num)
		self.entry_counters.set_completion(completion)
	
	
	# Network methods
	
	def solitaire_mode(self, widget):
		"""Go into solitaire mode"""
		self.label_gamename.set_text(_("Solitaire game"))
		self.hpaned_desktop.set_position(0)
		self.hpaned_desktop.set_property("position-set", True)
		self.notebook.set_page(2)
		
		self.my_player = self.create_player(None, "", config.VERSION)
		glib.idle_add(self.my_player.create_tray, None, (0.8, 0.8, 1.0))
	
	def start_connecting(self, widget):
		"""Login to the jabber account"""
		username = self.entry_username.get_text()
		pwd = self.entry_pwd.get_text()
		self.server = self.entry_server.get_text()
		
		# Save login details to settings
		settings.username = username
		settings.userpwd = pwd if self.checkbutton_save_pwd.get_active() else ""
		settings.server = self.server
		settings.save()
		
		# Set interface
		self.hbox_login_status.show()
		self.spinner_login.start()
		for widget in (self.entry_username, self.entry_pwd, self.entry_server,
			self.checkbutton_save_pwd, self.button_login,
			self.button_solitaire_mode
		):
			widget.set_sensitive(False)
		self.label_servername.set_text(self.server)
		
		# Connect
		self.network_manager.connect(username, pwd)
		self.network_manager.client.connection_established = \
			self._connection_established
	
	def _join_lobby(self):
		"""Join the lobby room"""
		nick = self.network_manager.get_my_jid().user
		room = config.
		self.lobby = muc.Room(self.network_manager.client, room, None, nick)
	
	def _show_lobby(self):
		self.hbox_login_status.hide()
		self.spinner_login.stop()
		self.notebook.set_page(1)
		self.button_join.grab_focus()
	
	def join_game(self, widget):
		"""Join a game room"""
		gamename = (config.DEFAULT_GAME_PREFIX + self.entry_gamename.get_text()
			+ "@conference." + self.server)
		self.label_gamename.set_text("%s@%s" %
			(self.entry_gamename.get_text(), self.entry_server.get_text()))
		gamepwd = self.entry_gamepwd.get_text()
		
		settings.gamename = self.entry_gamename.get_text()
		settings.gamepwd = gamepwd
		settings.save()
		
		self.notebook.set_page(2)
		
		nick = self.network_manager.get_my_jid().user
		self.game = self.network_manager.join_game(gamename, gamepwd, nick)
		self.game.joined = self._game_joined
		self.game.incoming_commands = self._incoming_cmds
		self.game.incoming_chat = self.add_chat_line
		self.game.user_joined = self.user_joined
		self.game.user_left = self.user_left
		self.game.user_nick_changed = self.user_nick_changed
	
	def _game_joined(self):
		"""A game room has sucessfully been joined"""
		logging.info(_("Game '%s' joined successfully."), self.game.jid)
		self.hpaned_desktop.set_sensitive(True)
		
		# Create player
		jid = self.game.get_my_jid()
		self.my_player = self.create_player(self.game, jid, config.VERSION)
		self.my_player.send_network_cmds([("hello", (config.VERSION,))])
		
		# Create tray
		glib.timeout_add(
			config.JOIN_DELAY,
			self.my_player.create_tray,
			None,
			(0.8, 0.8, 1.0)
		)
	
	def create_player(self, game, jid, version=""):
		"""Create a player object for a user"""
		jid = muc.JID(jid)
		for player in self.players:
			# Check that the player has not yet been created
			assert(jid != player.jid)
		player = players.Player(game, jid)
		player.version = version
		if self.network_manager is not None:
			if jid == self.game.get_my_jid():
				player.send_network_cmds = game.send_commands
				player.updated_hand = self.cd.repaint_hand
		else:
			player.updated_hand = self.cd.repaint_hand
		player.new_item = self.new_item
		player.new_tray = self.new_tray
		player.delete_item = self.delete_item
		player.exception_handler = self.handle_exception
		self.players.append(player)
		
		# Update a user's version information
		userid = self.get_userid(jid)
		for i in range(len(self.liststore_users)):
			if self.liststore_users[i][0] == userid:
				self.liststore_users[i][3] = version
		
		return player
	
	def _incoming_cmds(self, game, sender, cmdlist):
		"""Pass incoming network commands on to the player instances"""
		# Check if a new player entered
		cmd1, args1 = cmdlist[0]
		if cmd1 == "hello":
			player = self.create_player(game, sender, args1[0])
			player.has_been_welcomed = True
			self.my_player.handle_network_cmds(sender, cmdlist)
		if cmd1 == "welcome":
			for player in self.players:
				if player.jid == sender:
					break # user found
			else:
				player = self.create_player(game, sender, args1[0])
		
		# Pass on the commands
		for player in self.players:
			if player is not self.my_player:
				player.handle_network_cmds(sender, cmdlist)
	
	def get_userid(self, jid):
		"""Get the id corresponding to a room user"""
		userid = None
		for i, u in self.users.items():
			if jid == u:
				userid = i
				break
		return userid
	
	def user_joined(self, user):
		"""A user joined the game"""
		# Create new user id
		userid = 0
		while userid in self.users.keys():
			userid += 1
		self.users[userid] = user
		self.liststore_users.append((userid, user.user, unicode(user.full),
			None, True))
	
	def user_left(self, user):
		"""A user left the game"""
		# Remove the user
		userid = self.get_userid(user)
		del self.users[userid]
		for i in range(len(self.liststore_users)):
			if self.liststore_users[i][0] == userid:
				del self.liststore_users[i]
				break
		
		# Find the corresponding player
		player = None
		for pl in self.players:
			if pl.user == user:
				player = pl
				break
		if player is None:
			return # Player did not join the game
		self.players.remove(player)
		if player.tray is not None:
			player.remove_tray()
	
	def user_nick_changed(self, user):
		"""A user changed their nick name"""
		# Update liststore_users
		userid = self.get_userid(user)
		for i in range(len(self.liststore_users)):
			if self.liststore_users[i][0] == userid:
				self.liststore_users[i][1] = user.user
				self.liststore_users[i][2] = unicode(user.full)
	
	def add_log_line(self, message):
		"""Add a line to the game log"""
		buf = self.logview.get_buffer()
		if message[0] != "\n" and buf.get_char_count() > 0:
			message = "\n" + message
		buf.insert(buf.get_end_iter(), message, -1)
		mark = buf.get_mark("insert")
		self.logview.scroll_to_mark(mark, 0)
	
	def add_chat_line(self, game, sender, message):
		"""Recieved a chat message"""
		self.add_log_line(_("%s: %s") % (sender.user, message))
	
	def send_chat_message(self, widget):
		"""Send a chat message"""
		text = self.entry_chat.get_text()
		if text == "":
			return
		if text[0] == "/":
			# Handle special commands
			match = re.match(r'/life\s+([-0-9]*)', text)
			if match is not None:
				self.my_player.set_life(int(match.groups()[0]))
			match = re.match(r'/draw\s+([0-9]*)', text)
			if match is not None:
				self.my_player.draw_x_cards(int(match.groups()[0]))
			match = re.match(r'/nick\s+(.+)', text)
			if match is not None and self.network_manager is not None:
				self.network_manager.change_nick(match.groups()[0])
			if text[:5] == "/flip":
				# Flip a coin
				result = (_("heads"), _("tails"))[random.randint(0, 1)]
				msg = _("The coin came up %s.") % result
				self.network_manager.send_chat(msg, self.game)
				self.add_log_line(msg)
			if text[:5] == "/roll":
				# Roll a die
				result = random.randint(1, 6)
				msg = _("Rolled a %d.") % result
				self.network_manager.send_chat(msg, self.game)
				self.add_log_line(msg)
		
		else:
			if self.network_manager is not None:
				self.network_manager.send_chat(text, self.game)
			self.add_log_line(_("You: %s") % text)
		self.entry_chat.set_text("")
	
	
	# Global methods
	
	def toggle_fullscreen(self, widget):
		"""Change the fullscreen state"""
		if self.isfullscreen:
			self.main_win.unfullscreen()
		else:
			self.main_win.fullscreen()
		self.isfullscreen = not self.isfullscreen
	
	def keypress(self, widget, event):
		"""Keypress on the main window"""
		if event.type == gtk.gdk.KEY_PRESS:
#			print("Key:", event.keyval, gtk.gdk.keyval_name(event.keyval))
			if event.keyval == 65480: # F11
				self.toggle_fullscreen(None)
	
	def untap_all(self, widget=None):
		"""Untap all cards"""
		self._last_untapped = []
		for carditem in self.cd._items:
			if (isinstance(carditem, desktop.CardItem)
					and not carditem.does_not_untap and carditem.mine):
				if carditem.tapped:
					self._last_untapped.append(carditem)
				carditem.set_tapped(False)
	
	def load_deck(self, widget):
		"""Let the user pick a deck to load"""
		dialog = gtk.FileChooserDialog(_("Load a deck..."),
			self.main_win, gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL,
			gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		dialog.set_default_response(gtk.RESPONSE_OK)
		dialog.set_current_folder(settings.deck_dir)
		
		# Set filename filters
		f = gtk.FileFilter()
		f.set_name(_("Decks"))
		f.add_pattern("*.deck")
		dialog.add_filter(f)
		f = gtk.FileFilter()
		f.set_name(_("All files"))
		f.add_pattern("*")
		dialog.add_filter(f)
		
		response = dialog.run()
		if response == gtk.RESPONSE_OK:
			self._load_deck(dialog.get_filename())
		dialog.destroy()
	
	def _load_deck(self, filename):
		"""Load a deck by filename"""
		logging.info(_("loading %s..."), filename)
		if self._deck_load_async_handle is not None:
			# Cancel the current loading process
			self._deck_load_async_handle.cancel()
		self.status_label.set_text(_("Loading deck..."))
		self.progressbar.show()
		
		# progress callback
		def progresscallback(fraction):
			self.progressbar.set_fraction(fraction)
		
		# return callback
		def finish_deckload(deck):
			self._deck_load_async_handle = None
			self.my_player.load_deck(deck)
			self.progressbar.hide()
			self.status_label.set_text(_("Deck load complete."))
		
		self._deck_load_async_handle = \
			async.start(decks.load(filename, progresscallback, finish_deckload))
	
	
	# Entry bar
	
	def reset_entrybar(self):
		self.spinbutton_life.hide()
		self.spinbutton_num.hide()
		self.spinbutton_num.set_value(0)
		self.entry.hide()
		self.button_accept.hide()
		self.label_entrybar2.hide()
		self.combobox_counters.hide()
		self.combobox_tokens.hide()
	
	def entrybar_size_allocation(self, widget, rect):
		self.cd.y_offset = rect.height
	
	def create_token(self, widget):
		self.reset_entrybar()
		self._entrybar_task = "token"
		self.combobox_tokens.show()
		self.label_entrybar.set_text(_("Choose a token:"))
		self.hbox_entrybar.show()
		self.entry_tokens.grab_focus()
	
	def token_pick(self, widget):
		i = self.combobox_tokens.get_active()
		if 0 <= i < len(cards.tokens):
			self.selected_token(cards.tokens[i].id)
	
	def token_autocomplete_pick(self, widget, model, it):
		"""Picked a token from the autocompletion"""
		self.selected_token(model[it][0])
	
	def tokens_activate(self, widget):
		text = self.entry_tokens.get_text()
		for row in self.liststore_tokens:
			if text == row[1]:
				self.selected_token(row[0])
				break
		else:
			logging.info(_("Token '%s' is invalid."), text)
	
	def selected_token(self, tokenid):
		self.entrybar_unfocus()
		token = cards.get(tokenid)
		item = self.my_player.create_carditem(token.id, str(token))
		item.istoken = True
	
	def set_life(self, widget):
		self.reset_entrybar()
		self.spinbutton_life.set_value(self.my_player.life)
		self.spinbutton_life.show()
		self.label_entrybar.set_text(_("Set your life total to:"))
		self._entrybar_task = "life"
		self.hbox_entrybar.show()
		self.spinbutton_life.grab_focus()
	
	def ask_for_reset(self):
		self.reset_entrybar()
		self.button_accept.show()
		self._entrybar_task = "reset"
		self.hbox_entrybar.show()
		self.button_accept.grab_focus()
		self.label_entrybar.set_text(_("Reset all cards and life?"))
	
	def card_set_counters(self, widget):
		item = self._popup
		self.reset_entrybar()
		self.spinbutton_num.show()
		self.combobox_counters.show()
		self.label_entrybar.set_text(_("Set"))
		self.label_entrybar2.set_text(_("counters."))
		self.label_entrybar2.show()
		# Set default entry
		if len(item.counters) > 0:
			counter, num = item.counters.items()[0]
			self.entry_counters.set_text(counter)
			self.spinbutton_num.set_value(num)
		elif item.default_counters != []:
			counter = item.default_counters[0]
			self.entry_counters.set_text(counter)
			if counter in item.counters:
				self.spinbutton_num.set_value(item.counters[counter])
		else:
			self.entry_counters.set_text("")
		self.liststore_counters.clear()
		for counter in item.default_counters:
			self.liststore_counters.append((counter,))
		for counter in item.counters:
			for row in self.liststore_counters:
				if row[0] == counter:
					break
			else:
				self.liststore_counters.append((counter,))
		self._entrybar_task = "counters"
		self.hbox_entrybar.show()
		if len(item.counters) == 0:
			self.spinbutton_num.set_value(1)
			self.entry_counters.grab_focus()
		else:
			self.spinbutton_num.grab_focus()
	
	def counter_pick(self, widget):
		update_counter_num()
	
	def counter_autocomplete_pick(self, widget, model, it):
		update_counter_num()
	
	def counter_entry_change(self, widget):
		pass
	
	def update_counter_num(self, *args):
		counter = self.entry_counters.get_text()
		item = self._popup
		if counter in item.counters:
			self.spinbutton_num.set_value(item.counters[counter])
		else:
			self.spinbutton_num.set_value(1)
	
	def entrybar_unfocus(self, *args):
		if not self.hbox_entrybar.get_visible():
			return # entrybar wasn't shown
		self.hbox_entrybar.hide()
		self.cd.y_offset = 0
		if self._entrybar_task == "life":
			life = int(self.spinbutton_life.get_value())
			if life != self.my_player.life:
				self.my_player.set_life(life)
		elif self._entrybar_task == "counters":
			if self.entry_counters.get_text() != "":
				counter = self.entry_counters.get_text()
				num = int(self.spinbutton_num.get_value())
				self.my_player.set_counters(self._popup, num, counter)
		self._entrybar_task = ""
	
	def entrybar_accept(self, widget):
		if not self.hbox_entrybar.get_visible():
			return # entrybar wasn't shown
		if self._entrybar_task in ("reset", "spectate"):
			self.my_player.reset()
			if self._entrybar_task == "spectate":
				self.my_player.remove_tray()
		self.entrybar_unfocus()
	
	
	# Interface callbacks
	
	def zoom_in(self, widget):
		self.cd.zoom *= 1.2
		self.cd.queue_draw()
	
	def zoom_out(self, widget):
		self.cd.zoom *= 0.8
		self.cd.queue_draw()
	
	def reset_game(self, widget):
		if self.my_player.entered_play():
			self.ask_for_reset()
		else:
			self.my_player.reset()
	
	def spectate(self, widget):
		if self.my_player.entered_play():
			self.ask_for_reset()
			self._entrybar_task = "spectate"
		else:
			self.my_player.remove_tray()
	
	def shuffle_library(self, widget):
		self.my_player.shuffle_library()
	
	def draw_a_card(self, widget):
		self.my_player.draw_card()
	
	def draw_7_cards(self, widget):
		self.my_player.draw_x_cards(7)
	
	def lib_top_to_bottom(self, widget):
		self.my_player.library.insert(0, self.my_player.library.pop())
	
	def discard_this(self, widget):
		self.my_player.discard(self._popup)
	
	def exile_this(self, widget):
		pl = self.my_player
		pl.move_card(self._popup, pl.hand, pl.exile)
	
	def hand_to_library(self, widget):
		pl = self.my_player
		pl.move_card(self._popup, pl.hand, pl.library)
	
	def discard_random(self, widget):
		self.my_player.discard_random()
	
	def shuffle_hand(self, widget):
		self.my_player.shuffle_hand()
	
	def discard_all(self, widget):
		self.my_player.discard_all()
	
	def mulligan(self, widget):
		self.my_player.mulligan()
	
	def shuffle_graveyard_into_library(self, widget):
		self.my_player.shuffle_graveyard_into_library()
	
	def return_to_hand_from_graveyard(self, widget):
		self.my_player.graveyard_top_to_hand()
	
	def exile_from_graveyard(self, widget):
		pl = self.my_player
		pl.move_card(pl.graveyard[-1], pl.graveyard, pl.exile)
	
	def switch_sides(self, widget):
		self.cd.flip_y = not self.cd.flip_y
		self.cd.repaint()
	
	def card_to_hand(self, widget):
		pl = self.my_player
		pl.move_card(self._popup, pl.battlefield, pl.hand)
	
	def card_to_library(self, widget):
		pl = self.my_player
		pl.move_card(self._popup, pl.battlefield, pl.library)
	
	def card_to_graveyard(self, widget):
		pl = self.my_player
		pl.move_card(self._popup, pl.battlefield, pl.graveyard)
	
	def exile_card(self, widget):
		pl = self.my_player
		pl.move_card(self._popup, pl.battlefield, pl.exile)
	
	def clone_card(self, widget):
		pl = self.my_player
		item = self._popup
		name = str(item.token) if item.card is None else item.card.name
		x, y = item.x + 1, item.y + 1
		item2 = pl.create_carditem(item.cardid, name, None, x, y)
		item2.istoken = True
		item2.card = item.card
		item2.token = item.token
	
	def flip_card(self, widget):
		self._popup.set_flipped(self.menuitem_flipped.get_active())
		self._popup.repaint()
	
	def turn_card_over(self, widget):
		self._popup.set_faceup(not self.menuitem_faceup.get_active())
		self._popup.repaint()
	
	def card_set_no_untap(self, widget):
		self._popup.does_not_untap = self.menuitem_does_not_untap.get_active()
	
	def card_give_to(self, widget):
		pass # TODO
	
	def card_show_details(self, widget):
		pass # TODO
	
	def browse_exile(self, widget):
		self.show_cardbrowser(self.my_player.exile, None)
		# Hide useless buttons
		self.button_to_top.hide()
		self.button_to_bottom.hide()
		self.button_exile.hide()
	
	def browse_graveyard(self, widget):
		# Find the graveyard's owner
		player = self._popup.parent.player
		self.show_cardbrowser(player.graveyard, None, self.my_player is player)
		self.button_to_graveyard.hide()
	
	def browse_library(self, widget):
		self.show_cardbrowser(self.my_player.library, True)
		self.button_to_library.hide()
	
	def zoom_change(self, *args):
		value = self.hscale_zoom.get_value()
		self.cd.zoom = 35 / math.sqrt(value + 1)
		self.cd.queue_draw()
	
	
	# CarioDesktop's callbacks
	
	def hover(self, item):
		"""The user hovers the mouse over an item or handcard"""
		if isinstance(item, desktop.CardItem):
			self.status_label.set_text(item.get_description())
		if isinstance(item, cards.Card):
			self.status_label.set_text(item.name)
		if isinstance(item, desktop.Graveyard):
			graveyard = item.parent.player.graveyard
			self.status_label.set_text(_("%s's graveyard: %d cards") %
				(item.parent.player.name, len(graveyard)))
			if len(graveyard) > 0:
				self.cd.show_enlarged_card(graveyard[-1].id)
		if isinstance(item, desktop.Library):
			self.status_label.set_text(_("%s's library: %d cards") %
				(item.parent.player.name, len(item.parent.player.library)))
		if isinstance(item, desktop.Tray):
			self.status_label.set_text(item.player.name)
	
	def call_properties(self, item, event):
		"""Display the popup menu for an item or handcard"""
		self._popup = item
		if item is None:
			self._popup = event.x, event.y
			if self.my_player.tray is not None:
				self.menuitem_browse_exile.set_sensitive(
					len(self.my_player.exile) > 0)
				self.menuitem_browse_exile.set_label(
					_("browse exile (%d)...") % len(self.my_player.exile))
				self.menu_desktop.popup(None, None, None, event.button,
					event.time)
		if isinstance(item, desktop.CardItem):
			self.menuitem_flipped.set_active(item.flipped)
			self.menuitem_faceup.set_active(not item.faceup)
			self.menuitem_does_not_untap.set_active(item.does_not_untap)
			for widgetname in ("to_hand", "to_lib", "to_graveyard", "exile",
				"attack", "block", "use_effect", "cardsep2", "does_not_untap",
				"set_counters", "give_to"):
				getattr(self, "menuitem_" + widgetname).set_visible(item.mine)
			for widgetname in ("flipped", "faceup"):
				getattr(self, "menuitem_" + widgetname).set_sensitive(item.mine)
			self.menu_card.popup(None, None, None, event.button, event.time)
		if isinstance(item, desktop.Tray):
			if item.mine:
				self.menu_tray.popup(None, None, None, event.button, event.time)
		if isinstance(item, desktop.Library):
			if item.mine:
				self.menuitem_draw_7_from_lib.set_sensitive(
					len(self.my_player.library) >= 7)
				self.menuitem_draw_from_lib.set_sensitive(
					len(self.my_player.library) >= 1)
				self.menuitem_lib_top_to_bottom.set_sensitive(
					len(self.my_player.library) >= 1)
				self.menu_library.popup(None, None, None, event.button,
					event.time)
		if isinstance(item, desktop.Graveyard):
			self.menuitem_graveyard_to_hand.set_visible(item.mine)
			self.menuitem_graveyard_shuffle_lib.set_visible(item.mine)
			self.menu_graveyard.popup(None, None, None, event.button,
				event.time)
		if isinstance(item, cards.Card):
			self.menu_hand.popup(None, None, None, event.button, event.time)
	
	
	# Player callbacks
	
	def new_item(self, cardortoken, player, x, y):
		"""Create a new item from a cardid"""
		assert(cardortoken is not None)
		assert(player is not None)
		mine = player is self.my_player
		item = desktop.CardItem(cardortoken, player, mine)
		item.x = x
		item.y = y
		if player == self.my_player:
			glib.idle_add(semantics.init_carditem, item) # Parse card semantics
		
		self.cd.add_item(item)
		item.clamp_coords()
		item.repaint()
		return item
	
	def new_tray(self, player):
		"""Create a new tray item"""
		mine = player is self.my_player
		tray = desktop.Tray(player, mine)
		if len(self.players) == 1:
			tray.x = -22
			tray.y = 8
		elif len(self.players) == 2:
			tray.x = 22 - tray.w
			tray.y = -8 - tray.h
		elif len(self.players) == 3:
			tray.x = 22 - tray.w
			tray.y = 8
		elif len(self.players) == 4:
			tray.x = -22
			tray.y = -8 - tray.h
		self.cd.add_item(tray, None if mine else 0)
		tray.repaint()
		
		# append redraw call-backs
		player.updated_library   = tray.repaint
		player.updated_graveyard = tray.repaint
		player.updated_life      = tray.repaint
		
		return tray
	
	def delete_item(self, item):
		"""Delete a card item"""
		self.cd.remove_item(item)
	
	# Card browser
	
	def show_cardbrowser(self, cardlist, shuffle=True, mine=True):
		"""Show the cardbrowser"""
		assert(cardlist is not None)
		if shuffle is None:
			self.checkbutton_shuffle.hide()
			self.checkbutton_shuffle.set_active(False)
		else:
			self.checkbutton_shuffle.show()
			self.checkbutton_shuffle.set_active(shuffle)
		# Show buttons
		for widget in [self.button_to_graveyard, self.button_to_library,
				self.button_exile, self.button_to_hand, self.button_to_top,
				self.button_to_bottom]:
			widget.show()
		for widget in [self.button_to_graveyard, self.button_to_library,
				self.button_exile, self.button_to_hand,
				self.checkbutton_shuffle]:
			widget.set_sensitive(mine)
		self._browser_cardlist = cardlist
		self.update_cardlist()
		self.win_browse.show()
	
	def update_cardlist(self):
		"""Update the card browser list"""
		if len(self._browser_cardlist) == 0:
			self.hide_cardbrowser()
			return
		self.liststore_browse.clear()
		for i in range(len(self._browser_cardlist)):
			card = self._browser_cardlist[i]
			self.liststore_browse.append((i, card.name, card.manacost,
				card.get_composed_type(), card.power, card.toughness,
				card.text)
			)
	
	def hide_cardbrowser(self, *args):
		"""Hide the card browser"""
		self.win_browse.hide()
		if self.checkbutton_shuffle.get_active():
			self.my_player.shuffle_library()
		self._browser_cardlist = None
		return True
	
	def browser_to_top(self, widget):
		"""Move the selected card to the top of the list"""
		assert(self._browser_cardlist is not None)
		# TODO
	
	def browser_to_bottom(self, widget):
		"""Move the selected card to the bottom of the list"""
		assert(self._browser_cardlist is not None)
		# TODO
	
	def browser_to_graveyard(self, widget):
		"""Move the selected card to the graveyard"""
		assert(self._browser_cardlist is not None)
		model, it = self.treeview_browse.get_selection().get_selected()
		if it is None:
			return # Nothing selected
		card = self._browser_cardlist[model.get_value(it, 0)]
		self.my_player.move_card(card, self._browser_cardlist,
			self.my_player.graveyard)
		model.remove(it)
		self.update_cardlist()
	
	def browser_to_library(self, widget):
		"""Move the selected card to the library"""
		assert(self._browser_cardlist is not None)
		model, it = self.treeview_browse.get_selection().get_selected()
		if it is None:
			return # Nothing selected
		card = self._browser_cardlist[model.get_value(it, 0)]
		self.my_player.move_card(card, self._browser_cardlist,
			self.my_player.library)
		model.remove(it)
		self.update_cardlist()
	
	def browser_exile(self, widget):
		"""Move the selected card to the exile"""
		assert(self._browser_cardlist is not None)
		model, it = self.treeview_browse.get_selection().get_selected()
		if it is None:
			return # Nothing selected
		card = self._browser_cardlist[model.get_value(it, 0)]
		self.my_player.move_card(card, self._browser_cardlist,
			self.my_player.exile)
		model.remove(it)
		self.update_cardlist()
	
	def browser_to_hand(self, widget):
		"""Move the selected card to the hand"""
		assert(self._browser_cardlist is not None)
		model, it = self.treeview_browse.get_selection().get_selected()
		if it is None:
			return # Nothing selected
		card = self._browser_cardlist[model.get_value(it, 0)]
		self.my_player.move_card(card, self._browser_cardlist,
			self.my_player.hand)
		model.remove(it)
		self.update_cardlist()
	
	
	# Debug
	
	def handle_exception(self, exception):
		"""Display a message to the user about the exception"""
		self.show_dialog(self.main_win, str(exception), dialog_type="error")
	
	def create_random_card(self, widget=None):
		"""Create a random card on the desktop"""
		cardid = "tsp." + str(random.randint(1, 301))
		w, h = self.cd.get_wh()
		x = (random.random() - 0.5) * (w - 2.5)
		y = random.random() * (h - 3.5) / 2
		self.my_player.move_card(cards.get(cardid), None,
			self.my_player.battlefield, x, y)




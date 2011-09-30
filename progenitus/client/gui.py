# Written by TheGurke 2011
"""GUI for the client program"""

import random
import math
import os
import re
import gtk
import glib
from gettext import gettext as _

from progenitus import *
from progenitus.db import cards
from progenitus.editor import decks
import network
import players
import desktop


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
			self.main_win.set_sensitive(True)
			self.label_gamename.set_text(_("Solitaire game"))
			
			# Use a fake user class
			class FakeUser(object):
				nick = ""
				def same_as(self, other):
					return self is other
			self.my_player = self.create_player(FakeUser(), config.VERSION)
			glib.idle_add(self.my_player.create_tray, None, (0.8, 0.8, 1.0))
		else:
			self.network_manager = network.NetworkManager()
			self.network_manager.logger.log_callback = self.add_log_line
			self.network_manager.incoming_commands = self._incoming_cmds
			self.network_manager.incoming_chat = self.add_chat_line
			self.network_manager.user_joined = self.user_joined
			self.network_manager.user_left = self.user_left
			self.network_manager.user_nick_changed = self.user_nick_changed
			self.network_manager.exception_handler = self.handle_exception
			
			# Set default login entries
			self.entry_username.set_text(settings.username)
			self.entry_server.set_text(settings.server)
			self.entry_gamename.set_text(settings.gamename)
			self.entry_gamepwd.set_text(settings.gamepwd)
			if settings.username != "":
				glib.idle_add(self.entry_pwd.grab_focus)
		
		# Initialize tokens
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
			self.liststore_tokens.append((token.id, token.get_description(),
				token.setname, token.releasedate))
	
	
	# Network methods
	
	def _incoming_cmds(self, user, cmdlist):
		"""Pass incoming network commands on to the player instances"""
		# Check if a new player entered
		cmd1, args1 = cmdlist[0]
		if cmd1 == "hello":
			player = self.create_player(user, args1[0])
			player.has_been_welcomed = True
			self.my_player.handle_network_cmds(user, cmdlist)
		if cmd1 == "welcome":
			user_known = False
			for player in self.players:
				if player.user.same_as(user):
					user_known = True
			if not user_known:
				player = self.create_player(user)
				player.version = args1[0]
		
		# Pass on the commands
		for player in self.players:
			if player is not self.my_player:
				player.handle_network_cmds(user, cmdlist)
	
	def get_userid(self, user):
		"""Get the id corresponding to a room user"""
		userid = None
		for i, u in self.users.items():
			if user.same_as(u):
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
		self.liststore_users.append((userid, user.nick, unicode(user.real_jid),
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
			if pl.user.same_as(user):
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
				self.liststore_users[i][1] = user.nick
				self.liststore_users[i][2] = unicode(user.real_jid)
	
	def create_player(self, user, version=""):
		"""Create a player object for a user"""
		for player in self.players:
			# Check that the player has not yet been created
			assert(not player.user.same_as(user))
		player = players.Player(user)
		player.version = version
		if self.network_manager is not None:
			if user.same_as(self.network_manager.get_my_user()):
				player.send_network_cmds = self.network_manager.send_commands
				player.updated_hand = self.cd.repaint_hand
		else:
			player.updated_hand = self.cd.repaint_hand
		player.new_item = self.new_item
		player.new_tray = self.new_tray
		player.delete_item = self.delete_item
		player.exception_handler = self.handle_exception
		self.players.append(player)
		
		# Update a user's version information
		userid = self.get_userid(user)
		for i in range(len(self.liststore_users)):
			if self.liststore_users[i][0] == userid:
				self.liststore_users[i][3] = version
		
		return player
	
	def start_connecting(self, widget):
		"""Start connecting to the jabber room"""
		self.login_win.hide()
		username = self.entry_username.get_text()
		pwd = self.entry_pwd.get_text()
		gamename = (config.DEFAULT_GAME_PREFIX + self.entry_gamename.get_text()
			+ "@conference." + self.entry_server.get_text())
		self.label_gamename.set_text("%s@%s" %
			(self.entry_gamename.get_text(), self.entry_server.get_text()))
		gamepwd = self.entry_gamepwd.get_text()
		self.network_manager.connect(username, pwd, gamename, username, gamepwd)
		# FIXME: async!
		glib.timeout_add(100, self.check_login_status)
	
	def check_login_status(self):
		"""Check if the connection has been established yet"""
		if self.network_manager.is_connected():
			self.main_win.set_sensitive(True)
			self.progressbar.hide()
			
			# Set nick
			user = self.network_manager.get_my_user()
			self.network_manager.change_nick(user.nick.split('@')[0])
			
			# Create player
			assert(user is not None)
			self.my_player = self.create_player(user, config.VERSION)
			
			# Initialize handshake
			self.network_manager.send_commands([("hello", (config.VERSION,))])
			
			# Create tray
			glib.timeout_add(config.JOIN_DELAY, self.my_player.create_tray,
				None, (0.8, 0.8, 1.0))
			
			return False
		self.progressbar.pulse()
		return True	
	
	def add_log_line(self, message):
		"""Add a line to the game log"""
		buf = self.logview.get_buffer()
		if message[0] != "\n" and buf.get_char_count() > 0:
			message = "\n" + message
		buf.insert(buf.get_end_iter(), message, -1)
		mark = buf.get_mark("insert")
		self.logview.scroll_to_mark(mark, 0)
	
	def add_chat_line(self, user, message):
		"""Recieved a chat message"""
		self.add_log_line(_("%s: %s") % (user.nick, message))
	
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
		else:
			if self.network_manager is not None:
				self.network_manager.send_chat(text)
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
		print(_("loading %s...") % filename)
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
		self.entry.hide()
		self.label_entrybar2.hide()
		self.combobox_tokens.hide()
	
	def create_token(self, widget):
		self.reset_entrybar()
		self._entrybar_task = "token"
		self.combobox_tokens.show()
		self.label_entrybar.set_text(_("Choose a token:"))
		self.hbox_entrybar.show()
		self.combobox_tokens.grab_focus()
	
	def selected_token(self, widget):
		i = self.combobox_tokens.get_active()
		if 0 <= i < len(cards.tokens):
			self.hbox_entrybar.hide()
			token = cards.tokens[i]
			item = self.my_player.create_carditem(token.id,
				token.get_description())
			item.istoken = True
	
	def set_life(self, widget):
		self.reset_entrybar()
		self.spinbutton_life.set_value(self.my_player.life)
		self.spinbutton_life.show()
		self.label_entrybar.set_text(_("Set your life total to:"))
		self._entrybar_task = "life"
		self.hbox_entrybar.show()
		self.spinbutton_life.grab_focus()
	
	def card_set_counter(self, widget):
		self.reset_entrybar()
		self.spinbutton_num.show()
		self.spinbutton_num.set_value(1)
		self.entry.show()
		self.label_entrybar.set_text(_("Set"))
		self.label_entrybar2.set_text(_("counter."))
		self.label_entrybar2.show()
		if self._popup.default_counter is not None:
			counter = self._popup.default_counter
			self.entry.set_text(counter)
			if counter in self._popup.counters:
				self.spinbutton_num.set_value(self._popup.counters[counter])
		elif len(self._popup.counters.keys()) > 0:
			counter, num = self._popup.counters.items()[0]
			self.entry.set_text(counter)
			self.spinbutton_num.set_value(num)
		elif "Creature" in self._popup.card.cardtype:
			self.entry.set_text("+1/+1")
		else:
			self.entry.set_text("")
		self._entrybar_task = "counter"
		self.hbox_entrybar.show()
		self.entry.grab_focus()
	
	def entrybar_unfocused(self, widget, event):
		if not self.hbox_entrybar.get_visible():
			return # entrybar wasn't shown
		self.hbox_entrybar.hide()
		if self._entrybar_task == "life":
			life = int(self.spinbutton_life.get_value())
			if life != self.my_player.life:
				self.my_player.set_life(life)
		elif self._entrybar_task == "counter" and self.entry.get_text() != "":
			counter = self.entry.get_text()
			num = self.spinbutton_num.get_value()
			self.my_player.set_counter(self._popup, num, counter)
		self._entrybar_task = ""
	
	
	# Interface callbacks
	
	def zoom_in(self, widget):
		self.cd.zoom *= 1.2
		self.cd.queue_draw()
	
	def zoom_out(self, widget):
		self.cd.zoom *= 0.8
		self.cd.queue_draw()
	
	def reset_game(self, widget):
		self.my_player.reset()
	
	def spectate(self, widget):
		self.my_player.reset()
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
		item2 = pl.create_carditem(item.cardid, None, item.x + 1, item.y + 1)
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
	
	def zoom_change(self, widget=None, scroll=None, value=None):
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
				"set_counter", "give_to"):
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
	
	def new_item(self, cardid, player, x, y):
		"""Create a new item from a cardid"""
		mine = player is self.my_player
		item = desktop.CardItem(cards.get(cardid), player, mine)
		item.x = x
		item.y = y
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
			self.liststore_browse.append((i, card.name, card.manacost))
	
	def hide_cardbrowser(self, widget=None, stuff=None):
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




# Written by TheGurke 2011
"""GUI for the deck editor"""

import os
import sqlite3
from gettext import gettext as _

import glib
import gtk

from progenitus import *
from progenitus.db import cards
from progenitus.db import pics
import decks



class Interface(uiloader.Interface):
	
	isfullscreen = False
	
	def __init__(self):
		super(self.__class__, self).__init__()
		self.load(config.GTKBUILDER_DECKEDITOR)
		self.main_win.set_title(config.APP_NAME_EDITOR)
		self.main_win.maximize()
		cards.connect()
		self.textview_deckdesc.get_buffer().connect("changed",
			self.deckdesc_changed)
		self.quicksearch_entry.grab_focus()
		self.cardview.get_model().set_sort_func(3, self.sort_by_type, 3)
		self.resultview.get_model().set_sort_func(3, self.sort_by_type, 3)
		self.cardview.get_model().set_sort_func(2, self.sort_by_cost, 2)
		self.resultview.get_model().set_sort_func(2, self.sort_by_cost, 2)
		self.cardview.get_model().set_sort_column_id(3, gtk.SORT_ASCENDING)
		self.resultview.get_model().set_sort_column_id(10, gtk.SORT_DESCENDING)
		gtk.quit_add(0, self.save_deck) # one extra decksave just to be sure
		def refresh_once():
			self.refresh_decklist()
			return False
		glib.idle_add(refresh_once) # delayed decklist refresh
		glib.timeout_add(settings.decklist_refreshtime, self.refresh_decklist)
			# check periodically if the deck files on the disk have changed
	
	#
	# Interface callbacks
	#
	
	def about_click(self, widget):
		"""Display information about this program"""
		dialog = gtk.AboutDialog()
		dialog.set_name(config.APP_NAME_EDITOR)
		dialog.set_version(str(config.VERSION))
		dialog.set_copyright(_("Copyright by TheGurke 2011"))
		dialog.set_website(config.APP_WEBSITE)
		dialog.set_comments(_("This program is Free Software by the GPL3."))
		dialog.run()
		dialog.destroy()
	
	def show_preferences(self, widget):
		"""Show the program's preferences"""
		self.notebook_search.set_current_page(5)
	
	# Search
	
	def quicksearch(self, widget):
		"""Pressed enter on the quicksearch field"""
		query = self.quicksearch_entry.get_text()
		i = 0
		for q in ['"id" == ?', '"manacost" == ?',
				'"name" LIKE ? OR "type" LIKE ? OR "subtype" LIKE ?',
				'"set" LIKE ?', '"artist" LIKE ?', '"text" LIKE ?']:
			l = cards.search(q, (query,) * q.count("?"))
			if l != []:
				break
			i += 1
			if i >= 2:
				query = "%" + _replace_chars(query) + "%"
		self._show_results(l)
	
	def extended_search(self, widget):
		"""Clicked on the extended search button"""
		self.notebook_search.set_current_page(1)
		self.entry_text.grab_focus()
	
	def clear_search(self, widget):
		"""Clear the extended search fields"""
		self.entry_name.set_text("")
		self.entry_text.set_text("")
		self.entry_types.set_text("")
		self.entry_sets.set_text("")
		for c in [self.checkbutton_white, self.checkbutton_blue,
			self.checkbutton_black, self.checkbutton_red,
			self.checkbutton_green, self.checkbutton_colorless,
			self.checkbutton_lands, self.checkbutton_multicolor]:
			c.set_active(False)
		self.checkbutton_exclude.set_active(False)
		self.combobox_eq_manacost.set_active(-1)
		self.entry_manacost.set_text("")
		self.combobox_eq_price.set_active(-1)
		self.spinbutton_price.set_value(0)
		self.combobox_eq_converted_cost.set_active(-1)
		self.spinbutton_converted_cost.set_value(0)
		self.combobox_eq_power.set_active(-1)
		self.spinbutton_power.set_value(0)
		self.combobox_eq_toughness.set_active(-1)
		self.spinbutton_toughness.set_value(0)
		self.entry_rarity.set_text("")
		self.entry_artist.set_text("")
		self.entry_flavor.set_text("")
	
	def search(self, widget):
		"""Execute the extended search"""
		
		# Construct query
		query = ''
		args = []
		name = self.entry_name.get_text()
		if name != "":
			query += ' "name" LIKE ? AND'
			args.append("%" + _replace_chars(name) + "%")
		text = self.entry_text.get_text()
		if text != "":
			query += ' "text" LIKE ? AND'
			args.append("%" + _replace_chars(text) + "%")
		cardtypes = self.entry_types.get_text()
		if cardtypes != "":
			query += ' ("type" LIKE ? OR "subtype" LIKE ?) AND'
			args.extend(2 * ["%" + _replace_chars(cardtypes) + "%"])
		artist = self.entry_artist.get_text()
		if artist != "":
			query += ' "artist" LIKE ? AND'
			args.append("%" + _replace_chars(artist) + "%")
		flavor = self.entry_flavor.get_text()
		if flavor != "":
			query += ' "flavor" LIKE ? AND'
			args.append("%" + _replace_chars(flavor) + "%")
		cardsets = self.entry_sets.get_text()
		if cardsets != "":
			cardsets = cardsets.replace(",", "") # remove commas
			cl = _replace_chars(cardsets).split("%")
			if cl != []:
				query += ' ('
				for cset in cl:
					query += ' "set" LIKE ? OR'
					args.append("%" + cset + "%")
				query = query[:-2]
				query += ') AND'
		rarities = self.entry_rarity.get_text()
		if rarities != "":
			rarities = rarities.replace(",", "") # remove commas
			r = _replace_chars(rarities).split("%")
			if r != []:
				query += ' ('
				for rarity in r:
					query += ' "rarity" LIKE ? OR'
					args.append("%" + rarity + "%")
				query = query[:-2]
				query += ') AND'
		
		exact_color = self.checkbutton_exclude.get_active()
		clist = ["white", "blue", "black", "red", "green", "colorless"]
		if any(map(lambda c: getattr(self, "checkbutton_" + c).get_active(),
				clist)):
			if not exact_color:
				query += '('
			for c in clist:
				cb = getattr(self, "checkbutton_" + c).get_active()
				if cb or exact_color:
					query += ' "is%s" == ? %s' % (c,
						'AND' if exact_color else 'OR')
					args.append(cb)
			if not exact_color:
				query = query[:-2] + ') AND'
		if self.checkbutton_multicolor.get_active():
			query += ' "iswhite" + "isblue" + "isblack" + "isred" + "isgreen"' \
				' >= 2 AND'
		if self.checkbutton_lands.get_active():
			query += ' "type" LIKE "%Land%" AND'
		# FIXME can't or type land!
		eq = ["", "=", "<=", ">="]
		price_eq = self.combobox_eq_price.get_active()
		if price_eq > 0:
			query += ' "price" %s ? AND "price" >= 0 AND' % eq[price_eq]
			args.append(int(self.spinbutton_price.get_value() * 100))
		converted_eq = self.combobox_eq_converted_cost.get_active()
		if converted_eq > 0:
			query += ' "converted" %s ? AND' % eq[converted_eq]
			args.append(self.spinbutton_converted_cost.get_value_as_int())
		power_eq = self.combobox_eq_power.get_active()
		if power_eq > 0:
			query += ' "power" %s ? AND' % eq[power_eq]
			args.append(self.spinbutton_power.get_value_as_int())
		toughness_eq = self.combobox_eq_toughness.get_active()
		if toughness_eq > 0:
			query += ' "toughness" %s ? AND' % eq[toughness_eq]
			args.append(self.spinbutton_toughness.get_value_as_int())
		mana_eq = self.combobox_eq_manacost.get_active()
		manacost = self.entry_manacost.get_text()
		if mana_eq == 1 and manacost != "":
			query += ' "manacost" == ? AND'
			args.append(manacost)
		if mana_eq == 2 and manacost != "":
			total = 0
			mana_cl = manacost
			for c in "WUBRGXYZP":
				query += ' "manacost" LIKE ? AND'
				args.append("%" + manacost.count(c) * c + "%")
				if c not in "XYZP":
					total += manacost.count(c)
				mana_cl = mana_cl.replace(c, "")
			try:
				i = int(mana_cl)
			except:
				pass
			else:
				query += ' "converted" >= ? AND'
				args.append(total + i)
		# Execute query
		if self._execute_search(query[:-3], args) != []:
			self.no_results.hide()
		else:
			self.no_results.show()
	
	def custom_search(self, widget):
		"""Clicked on the custom search button"""
		self.notebook_search.set_current_page(2)
	
	def more_results(self, widget):
		"""Get more results to the previously executed search query"""
		self._show_results(cards.more_results())
	
	def sqlquery_keypress(self, widget, event):
		"""Keypress on the textview_sqlquery"""
		if event.type == gtk.gdk.KEY_PRESS and event.keyval == 65293 and \
				event.state & gtk.gdk.SHIFT_MASK: # shift + enter
			self.execute_custom_search(self.textview_sqlquery)
			return True
	
	def execute_custom_search(self, widget):
		"""Execute the custom search"""
		bfr = self.textview_sqlquery.get_buffer()
		query = bfr.get_text(bfr.get_start_iter(), bfr.get_end_iter())
		self._execute_search(query)
	
	def search_lands(self, widget):
		"""Find lands matching a deck's colors"""
		if self.deck is None:
			return
		query = '"type" LIKE "%Land%" AND NOT "type" = "Basic Land" AND ' + \
			'NOT "type" = "Basic Snow Land" AND '
		mana = {"white":"W", "blue":"U", "black":"B", "red":"R", "green":"G"}
		basic = {"white":"Plains", "blue":"Island", "black":"Swamp",
			"red":"Mountain", "green":"Forest"}
		if len(self.deck.color) >= 1:
			query += '('
		for c in self.deck.color:
			query += '"text" LIKE "%%{%s}%%" OR ' % mana[c]
			query += '"text" LIKE "%%%s%%" OR ' % basic[c]
		query = query[:-4]
		if len(self.deck.color) >= 1:
			query += ')'
		query += ' AND '
		for c in ["white", "blue", "black", "red", "green"]:
			if c not in self.deck.color:
				query += 'NOT "text" LIKE "%%{%s}%%" AND ' % mana[c]
				query += 'NOT "text" LIKE "%%%s%%" AND ' % basic[c]
		query = query[:-5]
		self._execute_search(query)
	
	def view_new_cards_show_query(self, widget):
		self.win_set_query.show()
		self.entry_set_query.set_text("")
		self.entry_set_query.grab_focus()
	
	def view_set_new(self, widget):
		"""Sent search query for the set view"""
		self.win_set_query.hide()
		self.view_new_cards(self.entry_set_query.get_text())
	
	def view_new_cards(self, setname):
		"""View all cards that where introduced in a particular set"""
		query = ('"set" LIKE ? AND "name" IN '
			+ '(SELECT "name" FROM "cards" WHERE "set" LIKE ? EXCEPT '
			+ 'SELECT "name" FROM "cards" WHERE "releasedate" < '
			+ '(SELECT "releasedate" FROM "cards" WHERE "set" LIKE ? LIMIT 1))')
		al = cards.search('"set" LIKE ?', (setname,))
		l = self._execute_search(query, (setname,) * 3)
		text = _("showing %d of %d cards") % (len(l), len(al))
		self.label_results.set_text(text)
	
	
	# Select
	
	def select_all(self, widget, event):
		"""Selects all text in an entry"""
		if isinstance(widget, gtk.Editable):
			widget.select_region(0, -1)
	
	def select_deck(self, widfget):
		"""Click on a deck"""
		filename = self.get_selected_deck()
		if filename is not None and os.path.isfile(filename):
			self.load_deck(filename)
	
	def select_card(self, widget):
		"""Click on the deck card list"""
		if self.deck is not None:
			cardid = self.get_selected_card()[0]
			if cardid is not None:
				self.show_card(cardid)
	
	def select_result(self, widget):
		"""Click on the search view"""
		cardid = self.get_selected_result()
		self.show_card(cardid)
	
	def doubleclick_result(self, *args):
		"""Double ckick on the search view"""
		if self.deck is not None:
			cardid = self.get_selected_result()
			self.add_to_deck(cardid, False)
			# TODO: shift determines sb
	
	def doubleclick_card(self, *args):
		"""Double click on the card view"""
		cardid, sb, removed = self.get_selected_card()
		if cardid is not None:
			if removed:
				self.add_to_deck(cardid, sb)
			else:
				self.toggle_sideboard()
	
	def cardview_click(self, widget, event):
		"""Clicked on the card view"""
		if event.button == 3:
			# show popup menu
			cardid, sb, removed = self.get_selected_card()
			if cardid is not None:
				text = "to deck" if sb else "to sideboard"
				self.menuitem3.get_child().set_text(text)
				self.cardview_menu.popup(None, None, None, event.button,
					event.time)
	
	def searchview_keypress(self, widget, event):
		"""A key has been pressed on the searchview"""
		if event.type == gtk.gdk.KEY_PRESS:
			if event.keyval == 65379: # insert, shift for sideboard
				if self.deck is not None:
					cardid = self.get_selected_result()
					self.add_to_deck(cardid, event.state & gtk.gdk.SHIFT_MASK)
	
	def cardview_keypress(self, widget, event):
		"""A key has been pressed on the cardview"""
		if event.type == gtk.gdk.KEY_PRESS:
			if event.keyval == 65535: # delete
				cardid, sb, removed = self.get_selected_card()
				if cardid is not None and not removed:
					self.remove_from_deck(cardid, sb)
			if event.keyval == 65379: # insert, shift for sideboard
				cardid = self.get_selected_card()[0]
				if cardid is not None:
					self.add_to_deck(cardid, event.state & gtk.gdk.SHIFT_MASK)
	
	def keypress(self, widget, event):
		"""Global keypress handler"""
		if event.type == gtk.gdk.KEY_PRESS:
			if event.keyval == ord('f') and event.state & gtk.gdk.CONTROL_MASK:
				self.quicksearch_entry.grab_focus()
			if event.keyval == ord('q') and event.state & gtk.gdk.CONTROL_MASK:
				self.extended_search(None)
			if event.keyval == ord('n') and event.state & gtk.gdk.CONTROL_MASK:
				self.new_deck()
			if event.keyval == ord('s') and event.state & gtk.gdk.CONTROL_MASK:
				self.export_deck()
			if event.keyval == ord('C') and event.state & gtk.gdk.CONTROL_MASK:
				self.clear_search(None)
			if event.keyval == ord('e') and event.state & gtk.gdk.CONTROL_MASK:
				self.edit_deck(None)
			if event.keyval == 65480: # F11
				self.toggle_fullscreen(None)
	
	# Other
	
	def toggle_fullscreen(self, widget):
		"""Change the fullscreen state"""
		if self.isfullscreen:
			self.main_win.unfullscreen()
		else:
			self.main_win.fullscreen()
		self.isfullscreen = not self.isfullscreen
	
	def deckname_changed(self, widget):
		"""The deckname has been changed"""
		if not self._is_loading and self.deck is not None:
			self.deck.name = self.deckname_entry.get_text()
			model, it = self.decklistview.get_selection().get_selected()
			model.set_value(it, 1, self.deckname_entry.get_text())
			self.delayed_decksave()
	
	def author_changed(self, widget):
		"""The author has been changed"""
		if not self._is_loading and self.deck is not None:
			self.deck.author = self.entry_author.get_text()
			self.delayed_decksave()
	
	def deckdesc_changed(self, widget):
		"""The deck description has been changed"""
		if not self._is_loading and self.deck is not None:
			buf = self.textview_deckdesc.get_buffer()
			self.deck.description = buf.get_text(buf.get_start_iter(),
				buf.get_end_iter())
			self.delayed_decksave()
	
	# Sort functions
	
	def sort_by_type(self, model, it1, it2, column):
		"""Sort function for the resultview/cardview"""
		types = ["Plainswalker", "Creature", "Enchantment", "Artifact",
			"Instant", "Sorcery", "Land", ""]
		v1 = model.get_value(it1, column)
		v1 = "" if v1 is None else v1
		v2 = model.get_value(it2, column)
		v2 = "" if v2 is None else v2
		i, j = 0, 0
		while v1.find(types[i]) < 0:
			i += 1
		while v2.find(types[j]) < 0:
			j += 1		
		return cmp(i, j)
	
	def sort_by_cost(self, model, it1, it2, column):
		"""Sort function for the resultview/cardview"""
		v1 = model.get_value(it1, column)
		v2 = model.get_value(it2, column)
		t1 = model.get_value(it1, 3) # type of card at it1
		t1 = "" if t1 is None else t1
		t2 = model.get_value(it2, 3) # type of card at it2
		t2 = "" if t2 is None else t2
		# Lands sort last
		c1 = 1000 if t1.find("Land") >= 0 else cards.convert_mana(v1)
		c2 = 1000 if t2.find("Land") >= 0 else cards.convert_mana(v2)
		if c1 == c2:
			pass # TODO
		return cmp(c1, c2)
	
	# Popup menu
	
	def insert_one(self, *args):
		"""Insert an additional card of this kind to the deck"""
		cardid, sb, removed = self.get_selected_card()
		if cardid is not None:
			self.add_to_deck(cardid, sb)
	
	def remove_one(self, *args):
		"""Remove currently selected card from the deck"""
		cardid, sb, removed = self.get_selected_card()
		if cardid is not None:
			self.remove_from_deck(cardid, sb)
	
	#
	# Interface methods
	#
	
	def show_card(self, cardid):
		"""Show a card picture and information"""
		if cardid is not None:
			self.cardpic.set_from_pixbuf(pics.get(cardid))
			card = cards.get(cardid)
			self.carddetails.set_markup(card.markup())
	
	def get_selected_result(self):
		model, it = self.resultview.get_selection().get_selected()
		if it is None:
			return None
		cardid = model.get_value(it, 0)
		return cardid
	
	def get_selected_card(self):
		"""Get the currently selected card in the deck"""
		model, it = self.cardview.get_selection().get_selected()
		if it is None:
			return None, None, None
		cardid = model.get_value(it, 0)
		sb = model.get_value(it, 8)
		removed = model.get_value(it, 9)
		return cardid, sb, removed
	
	def get_selected_deck(self):
		"""Get the currently selected deck"""
		model, it = self.decklistview.get_selection().get_selected()
		if it is None:
			return None
		filename = model.get_value(it, 0)
		return filename
	
	#
	# Card handling
	#
	
	def add_to_deck(self, cardid, sideboard=False):
		"""Add a card to the deck"""
		if self.deck.readonly:
			self.show_dialog(None, _("This deck is read-only."),
				dialog_type="error")
			return
		card = cards.get(cardid)
		(self.deck.sideboard if sideboard else self.deck.decklist).append(card)
		# Look if the card has recently been deleted
		for row in self.cards:
			if row[0] == cardid and row[8] == sideboard and row[9]:
				row[9] = False
				break
		else:
			it = self.cards.append((card.cardid, card.name, card.manacost,
				card.get_composed_type(), card.power, card.toughness,
				card.rarity, card.cardset, sideboard, False, card.price,
				_price_to_text(card.price), card.releasedate))
			self.cardview.get_selection().select_iter(it)
			self.cardview.scroll_to_cell(self.cardview.get_model().get_path(it))
		self.delayed_decksave()
		self.update_cardcount()
	
	def remove_from_deck(self, cardid, sideboard=False):
		"""Remove a card from the deck"""
		if self.deck.readonly:
			self.show_dialog(None, _("This deck is read-only."),
				dialog_type="error")
			return
		cardid, sb, removed = self.get_selected_card()
		if cardid is not None and not removed:
			l = self.deck.sideboard if sb else self.deck.decklist
			c = filter(lambda c: c.cardid == cardid, l)[0]
			l.remove(c)
			model, it = self.cardview.get_selection().get_selected()
			model.set_value(it, 9, True)
			
			# select next card
			it = model.iter_next(it)
			if it is not None:
				self.cardview.get_selection().select_iter(it)
				self.cardview.scroll_to_cell(model.get_path(it))
			
			self.delayed_decksave()
			self.update_cardcount()
	
	def toggle_sideboard(self, *args):
		if self.deck.readonly:
			self.show_dialog(None, _("This deck is read-only."),
				dialog_type="error")
			return
		cardid, sb, removed = self.get_selected_card()
		if cardid is not None and not removed:
			old = self.deck.sideboard if sb else self.deck.decklist
			new = self.deck.decklist if sb else self.deck.sideboard
			card = filter(lambda c: c.cardid == cardid, old)[0]
			old.remove(card)
			new.append(card)
			model, it = self.cardview.get_selection().get_selected()
			model.set_value(it, 8, not sb)
			self.delayed_decksave()
			self.update_cardcount()
	
	def refresh_deck(self):
		"""Refresh the deck card list"""
		if self.deck is None:
			return
		self.cards.clear()
		for sb in [True, False]:
			l = self.deck.sideboard if sb else self.deck.decklist
			for card in l:
				self.cards.append((card.cardid, card.name, card.manacost,
					card.get_composed_type(), card.power, card.toughness,
					card.rarity[0], card.cardset, sb, False, card.price,
					_price_to_text(card.price), card.releasedate))
		self.cardview.set_sensitive(True)
		self.deckname_entry.set_sensitive(True)
		self.update_cardcount()
	
	def sort_deck(self, *args):
		"""Sort the cards in the card view according to the settings"""
		pass
	
	#
	# Deck handling
	#
	
	deck = None
	_deck_load_async_handle = None
	_is_loading = False
	_waiting_for_decksave = False
	_parents = {}
	
	def _expand_dirs(self, path):
		l = []
		while path != "":
			l.append(path)
			path, name = os.path.split(path)
		l.reverse()
		return l
	
	def refresh_decklist(self):
		"""Refresh the list of decks"""
		
		folder_icon = self.main_win.render_icon(gtk.STOCK_DIRECTORY,
			gtk.ICON_SIZE_MENU, None)
		deck_icon = self.main_win.render_icon(gtk.STOCK_FILE,
			gtk.ICON_SIZE_MENU, None)
		
		for root, dirs, files in os.walk(settings.deck_dir, followlinks=True):
			# sort by name
			for l in [dirs, files]:
				if l is not None:
					l.sort()
			
			# create subfolders
			for subdir in dirs:
				path = os.path.join(root, subdir)
				if path not in self._parents:
					self._parents[path] = self.decks.append(
						self._parents.get(root, None),
							(path, subdir, True, folder_icon))
			
			# add ".deck"-files
			files = filter(lambda s: s[-5:] == ".deck", files)
			for filename in files:
				filename = os.path.join(root, filename)
				# File already in the list?
				found = [False]
				def check_for_file(model, path, it, found):
					if not self.decks.get_value(it, 2) and \
						self.decks.get_value(it, 0) == filename:
						found[0] = True
						return True
				self.decks.foreach(check_for_file, found)
				if not found[0]:
					deckname = decks.Deck("").derive_name(filename)
					self.decks.append(self._parents.get(root, None),
						(filename, deckname, False, deck_icon))
		
		# Any files/folders removed since the last check?
		def check_deep(it):
			if it is None:
				return # recursion stopreturn True
			
			filename = self.decks.get_value(it, 0)
			isdir = self.decks.get_value(it, 2)
			if not os.path.exists(filename) or \
				os.path.isfile(filename) == isdir:
				if not self.decks.remove(it):
					it = None
			else:
				check_deep(self.decks.iter_children(it)) # check children
				it = self.decks.iter_next(it)
			check_deep(it) # check siblings
		check_deep(self.decks.get_iter_first())
		return True
	
	def new_folder(self, *args):
		"""Create a new subfolder"""
		pass # TODO
	
	def enable_deck(self):
		"""Make all deck-related widgets sensitive"""
		self.cards.clear()
		self._is_loading = True
		self.deckname_entry.set_text(self.deck.name)
		if self.deck.author != "":
			self.deckname_entry.set_tooltip_text(_("Author: %s") 
				% self.deck.author)
		else:
			self.deckname_entry.set_tooltip_text("")
		self.entry_author.set_text(self.deck.author)
		self.textview_deckdesc.get_buffer().set_text(self.deck.description)
		self.cardview.set_sensitive(True)
		self.deckname_entry.set_sensitive(True)
		self.button_deckedit.set_sensitive(True)
		self.toolbutton_copy_deck.set_sensitive(True)
		self.toolbutton_delete_deck.set_sensitive(True)
		self.toolbutton_export_deck.set_sensitive(True)
		self.toolbutton_deckedit.set_sensitive(True)
		self.toolbutton_stats.set_sensitive(True)
		self.toolbutton_search_lands.set_sensitive(True)
		self._is_loading = False
		self.cardview.grab_focus()
	
	def new_deck(self, *args):
		"""Create a new empty deck"""
		model, it = self.decklistview.get_selection().get_selected()
		# TODO: model.iter_parent(it)
		newname = _("new")
		icon = self.main_win.render_icon(gtk.STOCK_FILE,
			gtk.ICON_SIZE_MENU, None)
		filename = os.path.join(settings.deck_dir, newname + ".deck")
		i = 2
		while os.path.exists(filename):
			newname = _("new (%d)") % i
			filename = os.path.join(settings.deck_dir, newname + ".deck")
			i += 1
		it = self.decks.append(None, (filename, newname, False, icon))
		self.decklistview.get_selection().select_iter(it)
		self.deck = decks.Deck(filename)
		self.enable_deck()
		with open(filename, 'w') as f:
			pass # create file
		self.deckname_entry.grab_focus()
	
	def copy_deck(self, *args):
		"""Copy the currently selected deck"""
		if self.deck is not None:
			icon = self.main_win.render_icon(gtk.STOCK_FILE,
				gtk.ICON_SIZE_MENU, None)
			new_name = self.deck.name + _(" (copy)")
			filename = os.path.join(os.path.dirname(self.deck.filename),
				new_name + ".deck")
			i = 2
			while os.path.exists(filename):
				new_name = self.deck.name + (_(" (copy %d)") % i)
				filename = os.path.join(os.path.dirname(self.deck.filename),
					new_name + ".deck")
				i += 1
			self.deck.name = new_name
			self.deck.filename = filename
			it = self.decklistview.get_selection().get_selected()[1]
			parent = self.decks.iter_parent(it)
			it = self.decks.insert_after(parent, it,
				(self.deck.filename, self.deck.name, False, icon))
			self.decklistview.get_selection().select_iter(it)
			self._waiting_for_decksave = True
			self.save_deck() # save deck instantly
	
	def delete_deck(self, *args):
		"""Delete the currently selected deck"""
		if self.deck is not None:
			modified = (len(self.deck.decklist) > 0 or
				len(self.deck.sideboard) > 0 or self.deck.description != "")
			if (modified):
				deckname = self.deckname_entry.get_text()
				text = (_("Are you sure you want to delete the deck '%s'?\n" +
					"(This cannot be undone.)")) % deckname
				md = gtk.MessageDialog(self.main_win,
					gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_WARNING,
					gtk.BUTTONS_YES_NO, text)
				md.set_default_response(gtk.RESPONSE_NO)
				result = md.run()
				md.destroy()
			if not modified or result == gtk.RESPONSE_YES:
				filename = self.deck.filename
				it = self.decklistview.get_selection().get_selected()[1]
				self.decks.remove(it)
				self.unload_deck()
				os.remove(filename)
	
	def load_deck(self, filename):
		"""Load a deck from a file"""
		# Save old deck before proceeding
		if self._waiting_for_decksave:
			self.save_deck()
		
		self.unload_deck()
		self.progressbar_deckload.show()
		
		# progress callback
		def progresscallback(fraction):
			self.progressbar_deckload.set_fraction(fraction)
		# return callback
		def finish_deckload(deck):
			self.deck = deck
			self.enable_deck()
			self.refresh_deck()
			self.progressbar_deckload.hide()
		
		self._deck_load_async_handle = \
			async.start(decks.load(filename, progresscallback, finish_deckload))
	
	def unload_deck(self):
		"""Unload the current deck"""
		if self._deck_load_async_handle is not None:
			# Currently loading a deck
			self._deck_load_async_handle.cancel()
			self._deck_load_async_handle = None
		if self._waiting_for_decksave:
			self.save_deck()
		self.deck = None
		self.cardview.set_sensitive(False)
		self.cards.clear()
		self.deckname_entry.set_sensitive(False)
		self.deckname_entry.set_text("")
		self.entry_author.set_text("")
		self.textview_deckdesc.get_buffer().set_text("")
		self.button_deckedit.set_sensitive(False)
		self.toolbutton_copy_deck.set_sensitive(False)
		self.toolbutton_delete_deck.set_sensitive(False)
		self.toolbutton_export_deck.set_sensitive(False)
		self.toolbutton_deckedit.set_sensitive(False)
		self.toolbutton_stats.set_sensitive(False)
		self.toolbutton_search_lands.set_sensitive(False)
		self.update_cardcount()
	
	def save_deck(self):
		"""Save the currently edited deck to disk"""
		if not self._waiting_for_decksave:
			return # deck has been saved in the meantime
		self._waiting_for_decksave = False
		filename = self.deck.filename
		old_filename = None
		if self.deck.name != self.deck.derive_name(filename):
			# Deck name has changed
			old_filename = filename
			self.deck.filename = \
				os.path.join(os.path.dirname(old_filename),
					self.deck.name + u".deck")
		self.except_safe(self.deck.save)
		print(_("Deck saved: %s") % self.deck.filename)
		if old_filename is not None and os.path.exists(old_filename):
			os.remove(old_filename)
	
	def export_deck(self, *args):
		"""Export a deck to a file"""
		dialog = gtk.FileChooserDialog(_("Export deck..."), self.main_win,
			gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL,
				gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
		dialog.set_default_response(gtk.RESPONSE_CANCEL)
		dialog.set_do_overwrite_confirmation(True)
		dialog.set_current_folder(settings.deck_dir)
		dialog.set_current_name(self.deck.name + u".deck")
		
		response = dialog.run()
		if response == gtk.RESPONSE_ACCEPT:
			old_filename = self.deck.filename
			self.deck.filename = dialog.get_filename()
			self.except_safe(self.deck.save)
			print(_("Deck exported as: %s") % self.deck.filename)
			self.deck.filename = old_filename
		dialog.destroy()
	
	def edit_deck(self, *args):
		"""Edit the deck description and author"""
		if self.deck is not None:
			self.notebook_search.set_current_page(3)
			self.textview_deckdesc.grab_focus()
	
	def show_deckstats(self, widget):
		"""Show statistics about the deck"""
		if self.deck is not None:
			self.notebook_search.set_current_page(4)
	
	def delayed_decksave(self):
		if not self._waiting_for_decksave:
			self._waiting_for_decksave = True
			glib.timeout_add(settings.decksave_timeout, self.save_deck)
	
	def update_cardcount(self):
		"""Update the decklist and sideboard card count display"""
		if self.deck is not None:
			lands = 0
			for c in self.deck.decklist:
				if c.cardtype.find("Land") >= 0:
					lands += 1
			self.decksummary.set_text(_("Deck: %d (Lands: %d), Sideboard: %d") %
				(len(self.deck.decklist), lands, len(self.deck.sideboard)))
			self.deck.derive_color()
			for c in ["white", "blue", "black", "red", "green"]:
				if c in self.deck.color:
					getattr(self, "mana_" + c).show()
				else:
					getattr(self, "mana_" + c).hide()
		else:
			self.decksummary.set_text("")
			for c in ["white", "blue", "black", "red", "green"]:
				getattr(self, "mana_" + c).hide()
	
	#
	# Database access
	#
	
	def _execute_search(self, query, args=()):
		if query == "":
			return # Don't execute an empty query
		# Protect against SQL injection
		if query.find(";") >= 0:
			self.show_dialog(self.main_win,
				_("The query must not contain ';'."), "error")
			return
		try:
			l = cards.search(query, args)
		except sqlite3.OperationalError as e:
			message = "SQL error:\n" + str(e)
			self.show_dialog(self.main_win, message, "error")
		else:
			self._show_results(l)
			return l
	
	def _show_results(self, cardlist):
		# Insert results into the TreeStore
		self.results.clear()
		i = -1
		while i + 1 < len(cardlist):
			i += 1
			# Group cards with the same name
			versions = filter(lambda c: c.name == cardlist[i].name, cardlist)
			if versions.index(cardlist[i]) > 0:
				# This card has been handled
				continue
			if len(versions) <= 1:
				it = None
			else:
				# Insert a parent card
				card = max(versions, key=lambda card: card.releasedate)
				versions_ = filter(lambda card: card.price >= 0, versions)
				if len(versions_) == 0:
					minprice = -1
				else:
					minprice = min(versions_, key=lambda card: card.price).price
				it = self.results.append(None, (card.cardid, card.name,
					card.manacost, card.get_composed_type(), card.power,
					card.toughness, card.rarity[0], "...", minprice,
					_price_to_text(minprice), card.releasedate))
			# Insert all child cards
			for card in versions:
				self.results.append(it, (card.cardid, card.name, card.manacost,
					card.get_composed_type(), card.power, card.toughness,
					card.rarity[0], card.cardset, card.price,
					_price_to_text(card.price), card.releasedate))
		
		# Handle gui
		if len(cardlist) == 0:
			text = _("no results")
		elif len(cardlist) == 1:
			text = _("one result")
		elif len(cardlist) >= settings.results_limit:
			text = _("at least %d results") % len(cardlist)
#			self.button_more_results.show() # FIXME
		else:
			text = _("%d results") % len(cardlist)
		self.label_results.set_text(text)
		if len(cardlist) > 0:
			self.notebook_search.set_current_page(0)
			it = self.resultview.get_model().get_iter_first()
			self.resultview.get_selection().select_iter(it)
			self.resultview.grab_focus()
			self.select_result(None)
		if len(cardlist) < settings.results_limit:
			self.button_more_results.hide()


def _price_to_text(price):
	assert(isinstance(price, int))
	if price < 0:
		return _("N/A")
	else:
		return _("$%.2f") % (float(price) / 100)


def _replace_chars(s):
	"""Replace every space not enclosed in quotes by %"""
	t = s.split("\"")
	for i in range(len(t)):
		if i % 2 == 0:
			t[i] = t[i].replace(" ", "%")
	return "".join(t)




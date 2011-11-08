# Written by TheGurke 2011
"""GUI for the deck editor"""

import os
import sqlite3
import re
from gettext import gettext as _
import logging

import glib
import gio
import gtk

from progenitus import *
from progenitus.db import cards
from progenitus.db import pics
import decks


_query_new_in_set = ('"setname" = ? AND "name" IN '
	'(SELECT "name" FROM "cards" WHERE "setname" = ? EXCEPT '
		'SELECT "name" FROM "cards" WHERE "releasedate" < '
			'(SELECT "releasedate" FROM "cards" WHERE "setname" = ? LIMIT 1))'
)



class Interface(uiloader.Interface):
	
	isfullscreen = False
	_enlarged_card = None
	
	def __init__(self):
		super(self.__class__, self).__init__()
		self.load(config.GTKBUILDER_DECKEDITOR)
		self.main_win.set_title(config.APP_NAME_EDITOR)
		self.main_win.maximize()
		self.textview_deckdesc.get_buffer().connect("changed",
			self.deckdesc_changed)
		self.quicksearch_entry.grab_focus()
		self.cardview.get_model().set_sort_func(3, self.sort_by_type, 3)
		self.resultview.get_model().set_sort_func(3, self.sort_by_type, 3)
		self.cardview.get_model().set_sort_func(2, self.sort_by_cost, 2)
		self.resultview.get_model().set_sort_func(2, self.sort_by_cost, 2)
		self.treestore_files.set_sort_func(2, self.sort_files)
		self.treestore_files.set_sort_column_id(2, gtk.SORT_ASCENDING)
		self.cardview.get_model().set_sort_column_id(3, gtk.SORT_ASCENDING)
		self.resultview.get_model().set_sort_column_id(10, gtk.SORT_DESCENDING)
		gtk.quit_add(0, self.save_deck) # one extra decksave just to be sure
		
		# Init the file view
		async.start(self._update_dir(settings.deck_dir))
		self._create_monitor(settings.deck_dir)
		
		# Render folder and deck icons
		self._folder_icon = self.main_win.render_icon(gtk.STOCK_DIRECTORY,
			gtk.ICON_SIZE_MENU, None)
		self._deck_icon = self.main_win.render_icon(gtk.STOCK_FILE,
			gtk.ICON_SIZE_MENU, None)
		
		# Check if the database is accessable
		db_file = os.path.join(settings.cache_dir, config.DB_FILE)
		if not os.path.exists(db_file):
			self.warn_about_empty_db()
			return
		
		cards.connect()
		num = cards.count()
		if num == 0:
			self.warn_about_empty_db()
			return
		else:
			self.label_results.set_text("%d cards available" % num)
		
		# Create deck directory if it doesn't exist
		if not os.path.exists(settings.deck_dir):
			os.mkdir(settings.deck_dir)
			if os.name == 'posix':
				os.symlink(os.path.abspath(config.DEFAULT_DECKS_PATH),
					os.path.join(settings.deck_dir, _("default decks")))
		
		# Initialize the quicksearch autocompletion
		async.start(self.init_qs_autocomplete())
	
	def init_qs_autocomplete(self):
		"""Initialize the quicksearch entry autocompletion"""
		completion = gtk.EntryCompletion()
		completion.set_model(self.liststore_qs_autocomplete)
		completion.set_property("text-column", 0)
		completion.set_inline_completion(False)
		completion.set_minimum_key_length(3)
		completion.set_popup_set_width(False)
		completion.connect("match-selected", self.qs_autocomplete_pick)
		renderer = gtk.CellRendererText()
		completion.pack_start(renderer, True)
		completion.set_attributes(renderer, markup=1)
		
		descrenderer = gtk.CellRendererText()
		completion.pack_end(descrenderer)
		self.quicksearch_entry.set_completion(completion)
		
		# Populate quicksearch autocomplete
		for setname in cards.sets:
			desc1 = setname + " <span size=\"x-small\">" \
				"(Card set - all in set)</span>"
			desc2 = setname + " <span size=\"x-small\">" \
				"(Card set - new in that set)</span>"
			self.liststore_qs_autocomplete.append((setname, desc1,
				'"setname" = ?', setname))
			self.liststore_qs_autocomplete.append((setname, desc2,
				_query_new_in_set, setname))
		if not settings.save_ram:
			# Because it requires a lot of RAM, the card and card type
			# autocomplete feature is not available in the reduced RAM mode
			subtypes = dict()
			for card in cards.cards:
				for subtype in card.subtype.split(" "):
					yield
					if subtype in subtypes:
						subtypes[subtype] += 1
					else:
						subtypes[subtype] = 1
			for subtype in subtypes:
				if subtypes[subtype] >= 3:
					# Only use subtypes that occur more than 3 times on cards
					desc = (subtype +
						" <span size=\"x-small\">(Creature type)</span>")
					self.liststore_qs_autocomplete.append((subtype, desc,
						'"subtype" LIKE ?', "%" + subtype + "%"))
					cardnames = yield set(card.name for card in cards.cards)
			for cardname in cardnames:
				card = yield cards.find_by_name(cardname)[0]
				desc = card.name + " <span size=\"x-small\">" + card.cardtype
				if card.subtype != "":
					desc += " - " + card.subtype
				if card.manacost != "":
					desc += " (%s)" % card.manacost
				desc += "</span>"
				self.liststore_qs_autocomplete.append((cardname, desc,
					'"name" = ?', card.name))
	
	
	#
	# Interface callbacks
	#
	
	def warn_about_empty_db(self):
		"""Display a warning that there are no cards in the database"""
		dialog = self.show_dialog(self.main_win,
			_("The card database is empty. Please run the updater."), "warning")
		dialog.connect("destroy", self.quit)
	
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
	
	def select_all(self, widget, event):
		"""Selects all text in an entry"""
		if isinstance(widget, gtk.Editable):
			widget.select_region(0, -1)
	
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
			cardid, sb, removed = self.get_selected_card()
			if event.keyval == 65535: # delete
				if cardid is not None and not removed:
					self.remove_from_deck(cardid, sb)
			if event.keyval == 65379: # insert, shift for sideboard
				if cardid is not None:
					self.add_to_deck(cardid, event.state & gtk.gdk.SHIFT_MASK)
#			if event.keyval == ord('c') and event.state & gtk.gdk.CONTROL_MASK:
#				c = gtk.Clipboard()
#				card = cards.get(cardid)
#				c.set_text("%s (%s)" % (card.name, card.setname))
#			if event.keyval == ord('v') and event.state & gtk.gdk.CONTROL_MASK:
#				c = gtk.Clipboard()
#				text = c.wait_for_text()
#				match = re.match(r'(.+?) \(([^)]+)\)', text)
#				if match is not None:
#					cardname, setname = match.groups()
#					l = cards.find_by_name(cardname, setname)
#					if l != []:
#						card = l[0]
#						self.add_to_deck(card.id, False)
	
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
	
	def toggle_fullscreen(self, widget):
		"""Change the fullscreen state"""
		if self.isfullscreen:
			self.main_win.unfullscreen()
		else:
			self.main_win.fullscreen()
		self.isfullscreen = not self.isfullscreen
	
	def qs_autocomplete_pick(self, widget, model, it):
		"""Picked a suggested autocompletion item"""
		row = model[it]
		self._execute_search(row[2], (row[3],) * row[2].count("?"))
	
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
	
	
	#
	# Sort functions
	#
	
	def sort_files(self, model, it1, it2):
		"""Sort the files first by type (folder or file) and then by name"""
		isdir1, name1 = model.get(it1, 0, 2)
		isdir2, name2 = model.get(it2, 0, 2)
		if isdir1 == isdir2:
			return cmp(name1, name2)
		else:
			return -cmp(isdir1, isdir2)
	
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
		if i != j:	
			return cmp(i, j)
		n1 = model.get_value(it1, 1) # name of card at it1
		n1 = "" if n1 is None else n1
		n2 = model.get_value(it2, 1) # name of card at it2
		n2 = "" if n2 is None else n2
		return cmp(n1, n2)
	
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
			return cmp(v1[::-1], v2[::-1])
		return cmp(c1, c2)
	
	
	#
	# Preferences
	#
	
	def show_preferences(self, widget):
		"""Show the program's preferences"""
		self.filechooserbutton_cache.set_filename(settings.cache_dir)
		self.filechooserbutton_decks.set_filename(settings.deck_dir)
		self.checkbutton_save_ram.set_active(settings.save_ram)
		#self.spinbutton_decksave_interval.set_value(settings.decksave_timeout
		#	/ 1000)
		self.notebook_search.set_current_page(5)
	
	def save_preferences(self, widget, nothing=None):
		"""Save the changed settings to disk"""
		#settings.decksave_timeout = \
		#	int(self.spinbutton_decksave_interval.get_value()) * 1000
		settings.save_ram = self.checkbutton_save_ram.get_active()
		new_cache_dir = unicode(self.filechooserbutton_cache.get_filename())
		if new_cache_dir != "None":
			settings.cache_dir = new_cache_dir
		old_deck_dir = settings.deck_dir
		new_deck_dir = unicode(self.filechooserbutton_decks.get_filename())
		if new_deck_dir != "None" and new_deck_dir != old_deck_dir:
			settings.deck_dir = new_deck_dir
			self.treestore_files.clear()
			async.start(self.refresh_files())
		settings.save()
		logging.info(_("Settings saved."))
	
	
	#
	# Deck files and folders
	#
	
	_it_by_path = dict()
	_filemonitors = dict()
	_folder_icon = None
	_deck_icon = None
	
	def _create_monitor(self, path):
		"""Create a file monitor for a directory"""
		logging.debug(_("Monitoring '%s' for updates."), path)
		filemonitor = gio.File(path).monitor_directory()
		filemonitor.connect("changed", self.update_files)
		self._filemonitors[path] = filemonitor
	
	def _expand_dirs(self, path):
		"""Extract a list of folders from a path"""
		l = []
		while path != "":
			l.append(path)
			path, name = os.path.split(path)
		l.reverse()
		return l
	
	def _get_path(self, it):
		"""Derive the file path from the tree structure"""
		assert(it is not None)
		isdir, path, name = self.treestore_files.get(it, 0, 1, 2)
		path = name + ("" if isdir else config.DECKFILE_SUFFIX)
		while it is not None:
			it = self.treestore_files.iter_parent(it)
			if it is not None:
				os.path.join(self.treestore_files.get_value(it, 2), path)
		path = os.path.join(settings.deck_dir, path)
		return path
	
	def _update_dir(self, path):
		"""Recursively add a directory to the files view"""
		assert(path == settings.deck_dir or path in self._it_by_path)
		for filename in os.listdir(path):
			yield self._add_file(os.path.join(path, filename))
	
	def _add_file(self, path):
		"""Add a path to the file view"""
		root, filename = os.path.split(path)
		
		suffix = config.DECKFILE_SUFFIX
		if os.path.isfile(path) and filename[-len(suffix):] != suffix:
			return # ignore non-deck files
		
		it_root = self._it_by_path.get(root, None)
		
		# File already in the tree?
		it = self.treestore_files.iter_children(it_root)
		while it is not None:
			if self.treestore_files.get_value(it, 1) == path:
				break # entry found
			it = self.treestore_files.iter_next(it)
		else:
			if os.path.isdir(path):
				self._it_by_path[path] = self.treestore_files.append(it_root,
					(True, path, filename, self._folder_icon))
				self._create_monitor(path) # Monitor subfolder for changes
				async.start(self._update_dir(path))
				return self._it_by_path[path]
			else:
				name = decks.Deck("").derive_name(path)
				return self.treestore_files.append(it_root,
					(False, path, name, self._deck_icon))
	
	def _remove_file(self, path):
		"""Remove a path from the file view"""
		root, filename = os.path.split(path)
		it_root = self._it_by_path.get(root, None)
		
		it = self.treestore_files.iter_children(it_root)
		while it is not None:
			if self.treestore_files.get_value(it, 1) == path:
				isdir = self.treestore_files.get_value(it, 0)
				self.treestore_files.remove(it)
				if isdir:
					del self._it_by_path[path]
					del self._filemonitors[path]
				break
			it = self.treestore_files.iter_next(it)
		else:
			logging.debug(_("Recieved a file delete event for '%s', "
				"but the file was not found in the files view."), path)
	
	def update_files(self, filemonitor, gfile1, gfile2, event):
		"""Filemonitor callback if something changed in the deck dir"""
		if event == gio.FILE_MONITOR_EVENT_CREATED:
			self._add_file(gfile1.get_path())
		if event == gio.FILE_MONITOR_EVENT_DELETED:
			self._remove_file(gfile1.get_path())
	
	def move_deckorfolder(self, model, modelpath, it):
		"""Moved a deck or folder in the decklistview using drag and drop"""
		# This is also triggered by the insertions from refresh_files()
		assert(model is self.treestore_files)
		
#		# Check if row is fully populated
#		isdir, path, name = model.get(it, 0, 1, 2)
#		if name is None:
#			return
#		
#		# Calculate the new path
#		it_parent = model.iter_parent(it)
#		while it_parent is not None and not model.get_value(it_parent, 0):
#			it_parent = model.iter_parent(it_parent)
#		new_dirname = model.get_value(it_parent, 1)
##		if it_parent is None:
##			new_dirname = settings.deck_dir
##		else:
##			new_dirname = self._get_path(it_parent)
#		new_path = os.path.join(new_dirname, name +
#			("" if isdir else config.DECKFILE_SUFFIX))
#		
#		# Check if file/folder needs to be moved
#		if new_path != path:
#			# File/folder has been moved
#			try:
#				pass
#				print "rename", path, new_path
##				os.rename(path, new_path)
#			except:
#				# TODO: undo move in the treemodel
#				raise
	
	def rename_file(self, cellrenderer, modelpath, new_name):
		"""Renamed a file or folder in treeview_files"""
		it = self.treestore_files.get_iter(modelpath)
		isdir, old_path, old_name = self.treestore_files.get(it, 0, 1, 2)
		new_path = os.path.join(os.path.dirname(old_path), new_name)
		if not isdir:
			new_path += config.DECKFILE_SUFFIX
		if os.path.exists(new_path):
			self.show_dialog(self, self.main_win,
				(_("Cannot rename '%s' to '%s': a file with that name exists.")
					if os.path.isfile(new_path) else
					_("Cannot rename '%s' to '%s': a folder with that name "
					"exists.")) % (old_name, new_name), 'error')
		try:
			os.rename(old_path, new_path)
			self.treestore_files.set(it, 1, new_path, 2, new_name)
		except OSError as e:
			logging.warning(_("Could not rename '%s' to '%s': %s"), old_path,
				new_path, str(e))
			self.show_dialog(self, self.main_win,
				_("Cannot rename '%s' to '%s': %s.")
					% (old_name, new_name, str(e)), 'error')
	
	def remove_file(self, *args):
		"""Delete the currently selected file or directory"""
		if self.deck is not None:
			modified = (len(self.deck.decklist) > 0 or
				len(self.deck.sideboard) > 0 or self.deck.description != "")
			if modified:
				deckname = self.deck.name
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
				it = self.treeview_files.get_selection().get_selected()[1]
				self.treestore_files.remove(it)
				self.unload_deck()
				os.remove(filename)
	
	def new_folder(self, *args):
		"""Create a new subfolder"""
		model, it = self.treeview_files.get_selection().get_selected()
		if it is None:
			isdir = True
			path = settings.deck_dir
		else:
			isdir, path = model.get(it, 0, 1)
		root = path if isdir else os.path.basename(path)
		
		name = _("new folder")
		i = 1
		while os.path.exists(os.path.join(root, name)):
			i += 1
			name = _("new folder (%d)") % i
		path = os.path.join(root, name)
		
		os.mkdir(path)
		it = self._add_file(path)
		self.treeview_files.expand_to_path(self.treestore_files.get_path(it))
		self.treeview_files.get_selection().select_iter(it)
	
	
	#
	# Deck save/load and display
	#
	
	deck = None
	_deck_load_async_handle = None
	_is_loading = False
	_waiting_for_decksave = False
	
	def enable_deck(self):
		"""Make all deck-related widgets sensitive"""
		# Opposite: unload_deck
		self.cards.clear()
		self._is_loading = True
		self.entry_author.set_text(self.deck.author)
		self.textview_deckdesc.get_buffer().set_text(self.deck.description)
		self.cardview.set_sensitive(True)
		self.entry_author.set_sensitive(True)
		self.textview_deckdesc.set_sensitive(True)
		self.toolbutton_copy_deck.set_sensitive(True)
		self.toolbutton_delete_deck.set_sensitive(True)
		self.toolbutton_export_deck.set_sensitive(True)
		self.toolbutton_deckedit.set_sensitive(True)
		self.toolbutton_stats.set_sensitive(True)
		self.toolbutton_search_lands.set_sensitive(True)
		self._is_loading = False
		self.cardview.grab_focus()
	
	def unload_deck(self):
		"""Unload the current deck"""
		# Opposite: enable_deck
		if self._deck_load_async_handle is not None:
			# Currently loading a deck
			self._deck_load_async_handle.cancel()
			self._deck_load_async_handle = None
		if self._waiting_for_decksave:
			self.save_deck()
		self.deck = None
		self.cardview.set_sensitive(False)
		self.cards.clear()
		self.entry_author.set_text("")
		self.textview_deckdesc.get_buffer().set_text("")
		self.toolbutton_copy_deck.set_sensitive(False)
		self.toolbutton_delete_deck.set_sensitive(False)
		self.toolbutton_export_deck.set_sensitive(False)
		self.toolbutton_deckedit.set_sensitive(False)
		self.toolbutton_stats.set_sensitive(False)
		self.toolbutton_search_lands.set_sensitive(False)
		self.entry_author.set_sensitive(False)
		self.textview_deckdesc.set_sensitive(False)
		for c in ["white", "blue", "black", "red", "green"]:
			getattr(self, "mana_" + c).hide()
		self.update_cardcount()
	
	def refresh_deck(self):
		"""Refresh the deck card list"""
		if self.deck is None:
			return
		self.cards.clear()
		for sb in [True, False]:
			l = self.deck.sideboard if sb else self.deck.decklist
			for card in l:
				self.cards.append((card.id, card.name, card.manacost,
					card.get_composed_type(), card.power, card.toughness,
					card.rarity[0], card.setname, sb, False, card.price,
					_price_to_text(card.price), card.releasedate))
		self.update_cardcount()
	
	def new_deck(self, *args):
		"""Create a new empty deck"""
		self.unload_deck()
		
		# Find the parent directory
		model, it = self.treeview_files.get_selection().get_selected()
		while it is not None and not self.treestore_files.get_value(it, 0):
			it = model.iter_parent(it)
		
		if it is None:
			parent_dir = settings.deck_dir
		else:
			parent_dir = self.treestore_files.get_value(it, 1)
		
		# Find the new file name
		name = _("new")
		path = os.path.join(parent_dir, name + config.DECKFILE_SUFFIX)
		i = 2
		while os.path.exists(path):
			name = _("new (%d)") % i
			path = os.path.join(parent_dir, name + config.DECKFILE_SUFFIX)
			i += 1
		
		# Enter the deck to the decks treestore
		icon = self.main_win.render_icon(gtk.STOCK_FILE, gtk.ICON_SIZE_MENU,
			None)
		it = self.treestore_files.append(it, (False, path, name, icon))
		self.treeview_files.expand_to_path(model.get_path(it))
		self.treeview_files.set_cursor(model.get_path(it))
		
		# Initialize deck
		self.deck = decks.Deck(path)
		self.enable_deck()
		with open(path, 'w') as f:
			pass # touch file
	
	def copy_deck(self, *args):
		"""Copy the currently selected deck"""
		if self.deck is not None:
			icon = self.main_win.render_icon(gtk.STOCK_FILE,
				gtk.ICON_SIZE_MENU, None)
			new_name = self.deck.name + _(" (copy)")
			filename = os.path.join(os.path.dirname(self.deck.filename),
				new_name + config.DECKFILE_SUFFIX)
			i = 2
			while os.path.exists(filename):
				new_name = self.deck.name + (_(" (copy %d)") % i)
				filename = os.path.join(os.path.dirname(self.deck.filename),
					new_name + config.DECKFILE_SUFFIX)
				i += 1
			self.deck.name = new_name
			self.deck.filename = filename
			it = self.treeview_files.get_selection().get_selected()[1]
			if it is None:
				return # no deck selected
			parent = self.treestore_files.iter_parent(it)
			it = self.treestore_files.insert_after(parent, it,
				(self.deck.filename, self.deck.name, False, icon))
			self.treeview_files.set_cursor(self.treestore_files.get_path(it))
			self._waiting_for_decksave = True
			self.save_deck() # save deck instantly
	
	def load_deck(self, filename):
		"""Load a deck from a file"""
		# Save old deck before proceeding
		if self._waiting_for_decksave:
			self.save_deck()
		
		self.unload_deck()
		if settings.save_ram:
			# In reduced RAM mode the loading will take much longer
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
				async.start(decks.load(filename, progresscallback,
					finish_deckload))
		else:
			# No need to display any progress bar here
			def finish_deckload(deck):
				self.deck = deck
				logging.info(_("Deck '%s' loaded."), deck.filename)
				self.enable_deck()
				self.refresh_deck()
			async.run(decks.load(filename, None, finish_deckload))
	
	def save_deck(self):
		"""Save the currently edited deck to disk"""
		if not self._waiting_for_decksave:
			return # deck has been saved in the meantime
		self._waiting_for_decksave = False
		old_filename = None
		if self.deck.name != self.deck.derive_name():
			new_filename = self.deck.derive_filename()
			if not os.path.exists(new_filename):
				old_filename = self.deck.filename
				self.deck.filename = new_filename
		self.except_safe(self.deck.save)
		logging.info(_("Deck saved: %s"), self.deck.filename)
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
		dialog.set_current_name(self.deck.name + config.DECKFILE_SUFFIX)
		
		response = dialog.run()
		if response == gtk.RESPONSE_ACCEPT:
			old_filename = self.deck.filename
			self.deck.filename = dialog.get_filename()
			self.except_safe(self.deck.save)
			logging.info(_("Deck exported as: %s"), self.deck.filename)
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
	# Select a card / deck
	#
	
	def select_deck(self, widget):
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
#			else:
#				self.toggle_sideboard()
	
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
	
	def show_card(self, cardid):
		"""Show a card picture and information"""
		self.hbuttonbox_transform.hide()
		if cardid is not None:
			try:
				self.cardpic.set_from_pixbuf(pics.get(cardid))
			except RuntimeError:
				pass # If there is not picture, continue anyways
			card = cards.get(cardid)
			self._enlarged_card = card
			self.carddetails.set_markup(card.markup())
			if cardid[-1] in ("a", "b"):
				self.hbuttonbox_transform.show()
		else:
			self.cardpic.set_from_pixbuf(pics.get("deckmaster"))
	
	def transform_card(self, widget):
		"""View the respective transformed card"""
		card = self._enlarged_card
		if card is not None and card.id[-1] in ("a", "b"):
			self.show_card(card.id[:-1] + ("b" if card.id[-1] == "a" else "a"))
	
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
		model, it = self.treeview_files.get_selection().get_selected()
		if it is None:
			return None
		filename = model.get_value(it, 1)
		return filename
	
	
	#
	# Deck editing
	# 
	
	def deckname_changed(self, widget):
		"""The deckname has been changed"""
		if self._is_loading or self.deck is None:
			return
		new_name = self.deckname_entry.get_text()
		new_filename = self.deck.derive_filename(new_name)
		if new_name != "" and not os.path.exists(new_filename):
			self.deckname_entry.set_property("secondary-icon-stock", None)
			self.deck.name = new_name
			model, it = self.treeview_files.get_selection().get_selected()
			model.set_value(it, 0, new_filename)
			model.set_value(it, 1, new_name)
			self.delayed_decksave()
		else:
			self.deckname_entry.set_property("secondary-icon-stock",
				gtk.STOCK_STOP)
			if new_name == "":
				tooltip = _("A deck's name cannot be empty.")
			elif os.path.isdir(new_filename):
				tooltip = _("A directory with that name exists.")
			else:
				tooltip = _("A deck with that name already exists.")
			self.deckname_entry.set_property("secondary-icon-tooltip-text",
				tooltip)
	
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
			it = self.cards.append((card.id, card.name, card.manacost,
				card.get_composed_type(), card.power, card.toughness,
				card.rarity, card.setname, sideboard, False, card.price,
				_price_to_text(card.price), card.releasedate))
			self.cardview.set_cursor(self.cards.get_path(it))
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
			c = filter(lambda c: c.id == cardid, l)[0]
			l.remove(c)
			model, it = self.cardview.get_selection().get_selected()
			model.set_value(it, 9, True)
			
			# select next card
			it = model.iter_next(it)
			if it is not None:
				self.cardview.set_cursor(model.get_path(it))
				self.cardview.scroll_to_cell(model.get_path(it))
			
			self.delayed_decksave()
			self.update_cardcount()
	
	def toggle_sideboard(self, *args):
		if self.deck.readonly:
			self.show_dialog(None, _("This deck is read-only."),
				dialog_type="error")
			return
		if isinstance(args[0], gtk.CellRendererToggle):
			path = args[1]
			cardid = self.cards[path][0]
			sb = self.cards[path][8]
			removed = self.cards[path][9]
			self.cards[path][8] = not sb
		else:
			cardid, sb, removed = self.get_selected_card()
			model, it = self.cardview.get_selection().get_selected()
			model.set_value(it, 8, not sb)
		if cardid is not None and not removed:
			old = self.deck.sideboard if sb else self.deck.decklist
			new = self.deck.decklist if sb else self.deck.sideboard
			card = filter(lambda c: c.id == cardid, old)[0]
			old.remove(card)
			new.append(card)
			self.delayed_decksave()
			self.update_cardcount()
	
	
	#
	# Card search
	#
	
	def quicksearch(self, widget):
		"""Pressed enter on the quicksearch field"""
		query = self.quicksearch_entry.get_text()
		i = 0
		for q in ['"id" == ?', '"manacost" == ?',
				'"name" LIKE ? OR "type" LIKE ? OR "subtype" LIKE ?',
				'"setname" LIKE ?', '"artist" LIKE ?', '"text" LIKE ?']:
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
			words = _replace_chars(cardtypes).split("%")
			for word in words:
				query += ' ("type" LIKE ? OR "subtype" LIKE ?) AND'
				args.extend(2 * ["%" + word + "%"])
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
					query += ' "setname" LIKE ? OR'
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
				clist)) or self.checkbutton_lands.get_active():
			if not exact_color:
				query += '('
			for c in clist:
				cb = getattr(self, "checkbutton_" + c).get_active()
				if cb or exact_color:
					query += ' "is%s" == ? %s' % (c,
						'AND' if exact_color else 'OR')
					args.append(cb)
			if self.checkbutton_lands.get_active():
				query += '"type" LIKE "%Land%" '
				query += 'AND' if exact_color else 'OR'
			if not exact_color:
				query = query[:-2] + ') AND'
		if self.checkbutton_multicolor.get_active():
			query += ' "iswhite" + "isblue" + "isblack" + "isred" + "isgreen"' \
				' >= 2 AND'
		
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
			query += ' CAST("power" AS INTEGER) %s ? AND' % eq[power_eq]
			args.append(self.spinbutton_power.get_value_as_int())
		toughness_eq = self.combobox_eq_toughness.get_active()
		if toughness_eq > 0:
			query += ' CAST("toughness" AS INTEGER) %s ? AND' % eq[toughness_eq]
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
	
	def execute_custom_search(self, widget):
		"""Execute the custom search"""
		bfr = self.textview_sqlquery.get_buffer()
		query = bfr.get_text(bfr.get_start_iter(), bfr.get_end_iter())
		self._execute_search(query)
	
	def search_lands(self, widget):
		"""Find lands matching a deck's colors"""
		if self.deck is None:
			return
		query = '"type" LIKE "%Land%" AND '
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
				it = self.results.append(None, (card.id, card.name,
					card.manacost, card.get_composed_type(), card.power,
					card.toughness, card.rarity[0], "...", minprice,
					_price_to_text(minprice), card.releasedate))
			# Insert all child cards
			for card in versions:
				self.results.append(it, (card.id, card.name, card.manacost,
					card.get_composed_type(), card.power, card.toughness,
					card.rarity[0], card.setname, card.price,
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
			it = self.results.get_iter_first()
			self.resultview.set_cursor(self.results.get_path(it))
			self.resultview.grab_focus()
			self.select_result(None)
			# If there is only one card result, expand the versions
			if self.results.iter_next(it) is None:
				self.resultview.expand_all()
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




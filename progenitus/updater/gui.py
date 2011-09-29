# Written by TheGurke 2011
"""GUI for the database/image updater"""

import os
import datetime
import urllib

from gettext import gettext as _
import sqlite3
import glib
import gtk

from progenitus import *
from progenitus.db import *
from progenitus.miner import *



class Interface(uiloader.Interface):
	
	downloadlist = None
	
	def __init__(self):
		super(self.__class__, self).__init__()
		self.load(config.GTKBUILDER_UPDATER)
		
		# Insert download servers
		self.liststore_data_servers.append(("magiccards.info",))
		self.combobox_data_servers.set_active(0)
		self.liststore_pic_servers.append(("magiccards.info",))
		self.combobox_pic_servers.set_active(0)
		self.liststore_price_servers.append(("tcgplayer.com",))
		self.combobox_price_servers.set_active(0)
		
		if not settings.disclaimer_agreed:
			self.disclaimer_win.show()
			self.checkbutton_confirm.grab_focus()
		else:
			self.main_win.show()
			self.button_start.grab_focus()
	
	def toggle_confirm(self, widget):
		"""The user toggles the 'I confirm' checkbutton"""
		self.button_agree.set_sensitive(self.checkbutton_confirm.get_active())
	
	def agree(self, widget):
		"""The user agreed to the disclaimer"""
		self.disclaimer_win.hide()
		self.main_win.show()
		
		# Save to settings
		settings.disclaimer_agreed = True
		glib.idle_add(settings.save)
	
	def toggle_download_pics(self, widget):
		self.combobox_pic_servers.set_sensitive(
			self.checkbutton_download_pics.get_active())
	
	def toggle_download_prices(self, widget):
		self.combobox_price_servers.set_sensitive(
			self.checkbutton_download_prices.get_active())
	
	def log(self, message):
		"""Print a status log message"""
		buf = self.logview.get_buffer()
		if message[0] != "\n" and buf.get_char_count() > 0:
			message = "\n" + message
		buf.insert(buf.get_end_iter(), message, -1)
		mark = buf.get_mark("insert")
		self.logview.scroll_to_mark(mark, 0)
		
	def start_download(self, widget=None):
		"""Interface callback to start the download"""
		self.vbox_settings.set_sensitive(False)
		self.hbox_progress.show()
		self.expander_details.show()
		self.button_start.hide()
		self.button_stop.show()
		async.run_threaded(self._run_download(), self.show_exception)
#		async.run(self._run_download()) # For debugging; prints traceback
	
	def _prepare_download(self):
		"""Prepare everything for the download"""
		
		# Get download list
		self.log(_("Getting downloadlist..."))
		data = miner.fetch_downloadlist(settings.list_url)
		downloadlist = miner.parse_downloadlist(data)
		
		# Establish database access
		if not os.path.isfile(settings.cards_db):
			self.log(_("Creating a new database file..."))
			cards.create_db(settings.cards_db)
		
		cards.connect()
		self.sqlconn = sqlite3.connect(settings.cards_db)
		self.cursor = self.sqlconn.cursor()
		
		# Create directories
		if not os.path.exists(settings.cache_path):
			os.mkdir(settings.cache_path)
		if self.checkbutton_download_pics.get_active():
			if not os.path.exists(os.path.join(settings.cache_path, "cards")):
				os.mkdir(os.path.join(settings.cache_path, "cards"))
		
		self.log(_("Starting download."))
		return downloadlist
	
	def _run_download(self):
		"""Threaded download function"""
		
		downloadlist = yield self._prepare_download()
		assert(downloadlist is not None)
		assert(len(downloadlist) > 0)
		
		# Download every card set
		for set_num in range(len(downloadlist)):
			setcode, releasedate, mcinfosetcode, setname = downloadlist[set_num]
			
			# Update gui
			self.progressbar1.set_fraction(float(set_num)
				/ len(downloadlist))
			self.progressbar1.set_text(setname)
			self.progressbar2.set_fraction(0)
			self.progressbar2.set_text(" ")
			
			# Check if the set has already been downloaded
			self.cursor.execute('SELECT * FROM "sets" WHERE "id" = ?',
				(setcode,))
			cardlist = None
			if self.cursor.fetchone() is not None:
				cardlist = cards.search('"setid" = ?', (setcode,))
			else:
				self.log(_("Downloading '%s'...") % setname)
				self.progressbar2.set_text(_("Getting card information..."))
				
				# Get full spoilers information
				setname, cardlist = yield magiccardsinfo.mine_set(
					*downloadlist[set_num][:3])
				
				# Insert into the database
				self.cursor.execute(u'INSERT INTO "sets" VALUES (?,?,?,?)',
					(setcode, setname, len(cardlist), releasedate.toordinal()))
				for i in range(len(cardlist)):
					self.progressbar2.set_fraction(float(i) / len(cardlist))
					self.cursor.execute(u'INSERT INTO "cards" VALUES (' +
						23 * '?,' + '?)', cardlist[i].as_tuple())
				self.sqlconn.commit()
			assert(cardlist is not None)
			
			# Download pricing information
			if self.checkbutton_download_prices.get_active():
				self.progressbar2.set_text(_("Getting card prices..."))
				
				pricelist = yield tcgplayercom.mine_pricelist(setname)
				for i in range(len(pricelist)):
					name, price = pricelist[i]
					self.progressbar2.set_fraction(float(i) / len(pricelist))
					self.cursor.execute('UPDATE "cards" SET "price" = ? '
						'WHERE "name" = ? AND "setname" = ?',
						(price, name, setname)
					)
				self.sqlconn.commit()
			
			# Download card pictures
			if self.checkbutton_download_pics.get_active():
				self.progressbar2.set_text(_("Getting card pictures..."))
				# Create picture directory
				pic_dir = os.path.dirname(pics._get_path(setcode + "." + "000"))
				if not os.path.exists(pic_dir):
					os.mkdir(pic_dir)
				
				# Get pics
				for i in range(len(cardlist)):
					self.progressbar2.set_fraction(float(i) / len(cardlist))
					card = cardlist[i]
					pic_filename = pics._get_path(card.id)
					if not os.path.exists(pic_filename):
						yield magiccardsinfo.mine_pic(magiccardsinfo.url_pic
							% (mcinfosetcode, card.collectorsid), pic_filename)
		
		# Download tokens
		if self.checkbutton_download_tokens.get_active():
			self.progressbar1.set_text(_("Tokens"))
			self.log(_("Downloading tokens..."))
			
			# Create token pic directory
			if not os.path.exists(os.path.join(settings.cache_path, "tokens")):
				os.mkdir(os.path.join(settings.cache_path, "tokens"))
			
			# Get token information
			tokens = magiccardsinfo.mine_tokens()
			for i in range(len(tokens)):
				pic_url, token = tokens[i]
				self.progressbar2.set_fraction(float(i) / len(tokens))
				
				# Get token picture
				pic_filename = pics._get_path(token.id)
				if not os.path.exists(pic_filename):
					yield magiccardsinfo.mine_pic(pic_url, pic_filename)
				
				# Insert database entry
				try:
					yield cards.get(token.id)
				except RuntimeError:
					self.cursor.execute(u'INSERT INTO "tokens" VALUES (' +
						17 * '?,' + '?)', token.as_tuple())
					self.sqlconn.commit()
		
		glib.idle_add(self.download_complete)
	
	def download_complete(self):
		self.progressbar1.set_fraction(1)
		self.progressbar2.set_fraction(1)
		self.log(_("Update complete."))
		md = gtk.MessageDialog(self.main_win, gtk.DIALOG_DESTROY_WITH_PARENT,
			gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, _("Update complete."))
		md.connect("response", self.quit)
		md.show()
	
	def show_exception(self, exception):
		"""Show the exception and then quit"""
		text = "An exception occured:\n%s" % str(exception)
		md = gtk.MessageDialog(self.main_win, gtk.DIALOG_DESTROY_WITH_PARENT,
			gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, text)
		md.connect("response", self.quit)
		md.show()




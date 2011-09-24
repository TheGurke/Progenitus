# Written by TheGurke 2011
"""GUI for the database/image updater"""

import os
import datetime
import urllib

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
			self.download_win.show()
			self.button_start.grab_focus()
	
	def toggle_confirm(self, widget):
		"""The user toggles the 'I confirm' checkbutton"""
		self.button_agree.set_sensitive(self.checkbutton_confirm.get_active())
	
	def agree(self, widget):
		"""The user agreed to the disclaimer"""
		self.disclaimer_win.hide()
		self.download_win.show()
		
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
		self.table_progress.show()
		self.expander_details.show()
		self.button_start.hide()
		self.button_stop.show()
		async.run_threaded(self._run_download(), self.show_exception)
	
	def _run_download(self):
		"""Threaded download function"""
		
		# Get download list
		if self.downloadlist is None:
			self.log("Getting downloadlist...")
			data = yield miner.fetch_downloadlist(settings.list_url)
			self.downloadlist = miner.parse_downloadlist(data)
		
		# Establish database access
		if not os.path.isfile(settings.cards_db):
			self.log("Creating a new database file...")
			cards.create_db(settings.cards_db)
		
		cards.connect()
		self.sqlconn = sqlite3.connect(settings.cards_db)
		self.cursor = self.sqlconn.cursor()
		
		# Create directories
		if not os.path.exists(settings.pics_path):
			os.mkdir(settings.pics_path)
		
		self.log("Starting download.")
		
		# Establish connections
		magiccardsinfo.connect()
		tcgplayercom.connect()
		
		# Download every card set
		for set_num in range(len(self.downloadlist)):
			setcode, releasedate = self.downloadlist[set_num]
			
			# Get set information
			setname, cardlist = yield magiccardsinfo.mine_set(setcode)
			
			# Update gui
			self.progressbar_expansion.set_fraction(float(set_num)
				/ len(self.downloadlist))
			self.progressbar_expansion.set_text(setname)
			self.progressbar_cards.set_fraction(0)
			self.progressbar_cards.set_text("0 / %d" % len(cardlist))
			
			# Check if expansion has already been downloaded
			l = yield cards.search('"set" == ?', (setname,), 1)
			if len(l) > 0:
				self.log("'%s' was found in the database." % setname)
				continue
			self.log("Downloading '%s'..." % setname)
			
			# Insert set information
			self.cursor.execute(u'INSERT INTO "sets" VALUES (?,?,?,?,?)',
				(set_num, setname, setcode, len(cardlist),
				releasedate.toordinal()))
			
			# Create picture directory
			pic_dir = os.path.dirname(pics._get_path(int(
				releasedate.strftime("%y%m%d") + "000")))
			if not os.path.exists(pic_dir):
				os.mkdir(pic_dir)
			
			# Download individual cards
			for i in range(len(cardlist)):
				collectorsid = cardlist[i]
				card = yield magiccardsinfo.mine_card(setcode, collectorsid)
				
				# Set id and release date
				card.releasedate = releasedate.toordinal()
				card.cardid = card.derive_id()
				
				# Download pricing information
				if self.checkbutton_download_prices.get_active():
					card.price = yield tcgplayercom.mine_price(setcode,
						collectorsid)
				
				# Download picture
				pic_filename = pics._get_path(int(card.cardid))
				if (not os.path.exists(pic_filename) and
						self.checkbutton_download_pics.get_active()):
					yield magiccardsinfo.mine_pic(setcode, collectorsid,
						pic_filename)
				
				# Insert into the database
				self.cursor.execute(u'INSERT INTO "cards" VALUES (' +
					22 * '?,' + '?)', card.as_tuple())
				self.progressbar_cards.set_fraction(float(i) / len(cardlist))
				self.progressbar_cards.set_text("%d / %d" % (i, len(cardlist)))
			
			# Save db to disk
			self.sqlconn.commit()
		glib.idle_add(self.download_complete)
	
	def download_complete(self):
		self.log("Download complete.")
		md = gtk.MessageDialog(self.download_win,
			gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO,
			gtk.BUTTONS_CLOSE, "Download complete.")
		md.connect("response", self.quit)
		md.show()




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


def fetch_downloadlist(url):
	"""Fetch the download list from an url"""
	f = urllib.urlopen(url)
	data = f.read()
	f.close()
	return data


def parse_downloadlist(data):
	"""Fetch the download list from a file"""
	downloadlist = []
	for line in data.split('\n'):
		if line != "" and line[0] not in ("#", "%"):
			code, num, idprefix = line.strip().split()[0:3]
			downloadlist.append((code, int(num), idprefix))
	return downloadlist



class Interface(uiloader.Interface):
	
	downloadlist = None
	
	def __init__(self):
		super(self.__class__, self).__init__()
		self.load(config.GTKBUILDER_UPDATER)
		
		# Insert download servers
		self.liststore_servers.append(("magiccards.info",))
		self.combobox_servers.set_active(0)
		
		if not settings.disclaimer_agreed:
			self.disclaimer_win.show()
			self.checkbutton_confirm.grab_focus()
		else:
			self.download_win.show()
	
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
			data = yield fetch_downloadlist(settings.list_url)
			self.downloadlist = parse_downloadlist(data)
		
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
		
		# Download every expansion
		for expansion_num in range(len(self.downloadlist)):
			code, num, idprefix = self.downloadlist[expansion_num]
			
			# Update gui
			self.progressbar_expansion.set_fraction(float(expansion_num) \
				/ len(self.downloadlist))
			self.progressbar_cards.set_fraction(0)
			self.progressbar_cards.set_text("0 / %d" % num)
			
			# Download first card to get further expansion information
			card = yield miner.mine(code, 1)
			self.progressbar_expansion.set_text(card.cardset)
			
			# Check if expansion has already been downloaded
			l = yield cards.search('"set" == ?', (card.cardset,))
			if len(l) == num:
				self.log(card.cardset + " was found in the database.")
				continue
			self.log("Downloading %s..." % card.cardset)
			
			# Calculate release date
			year = int(idprefix[:2])
			year += 1900 if year > 80 else 2000
			month = int(idprefix[2:4])
			day = int(idprefix[4:6])
			date = datetime.date(year, month, day)
			
			# Create picture directory
			pic_dir = os.path.dirname(pics._get_path(int(idprefix + "000")))
			if not os.path.exists(pic_dir):
				os.mkdir(pic_dir)
			
			# Download individual cards
			for card_num in range(1, num + 1):
				# Download data
				if card_num > 1: # first card has already been downloaded
					card = yield miner.mine(code, card_num)
				
				# Set id and release date
				card.cardid = idprefix + str(card_num).rjust(3, "0")
				card.releasedate = date.toordinal()
				
				# Download pricing information
				if self.checkbutton_download_prices.get_active():
					card.price = yield miner.mine_price(code, card_num)
				
				# Download picture
				if self.checkbutton_download_pics.get_active():
					pic_filename = pics._get_path(int(card.cardid))
					yield miner.getpic(code, card_num, pic_filename)
				
				# Insert into the database
				self.cursor.execute(u'INSERT INTO "cards" VALUES (' +
					20 * '?,' + '?)', card.as_tuple())
				self.progressbar_cards.set_fraction(float(card_num) / num)
				self.progressbar_cards.set_text("%d / %d" % (card_num, num))
			
			self.sqlconn.commit() # Save db to disk
		glib.idle_add(self.download_complete)
	
	def download_complete(self):
		self.log("Download complete.")
		md = gtk.MessageDialog(self.download_win,
			gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO,
			gtk.BUTTONS_CLOSE, "Download complete.")
		md.run()
		md.destroy()
		glib.idle_add(self.quit)




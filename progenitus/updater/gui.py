# Written by TheGurke 2011
"""GUI for the database/image downloader"""

import os
import datetime
import sqlite3

import glib
import gtk

from progenitus import *
from progenitus.db import *



DOWNLOADLIST_FILE = "downloadlist.txt"
DOWNLOAD_PICS = True

downloadlist = []

gtk.gdk.threads_init()
async.method_queuer = glib.idle_add


class Interface(uiloader.Interface):
	def __init__(self):
		super(self.__class__, self).__init__()
		self.load(config.GTKBUILDER_UPDATER)
	
	def toggle_confirm(self, widget):
		"""The user toggles the 'I confirm' checkbutton"""
		self.button_start.set_sensitive(self.checkbutton_confirm.get_active())
	
	def log(self, message):
		"""Print a status log message"""
		buf = self.logview.get_buffer()
		if message[0] != "\n" and buf.get_char_count() > 0:
			message = "\n" + message
		buf.insert(buf.get_end_iter(), message, -1)
		mark = buf.get_mark("insert")
		self.logview.scroll_to_mark(mark, 0)
	
	def show_except(self, exc):
		text = "Exception %s:\n%s" % (type(exc), str(exc))
		self.show_dialog(self.download_win, text, dialog_type="error")
	
	def start_download(self, widget):
		"""Interface callback to start the download"""
		self.disclaimer_win.hide()
		self.download_win.show()
		async.run_threaded(self._run_download(), self.show_except)
		
	def _run_download(self):
		"""Run the download"""
		
		# Initialize
		self.log("Getting downloadlist...")
		yield load_downloadlist()
	
		if not os.path.isfile(settings.cards_db):
			self.log("Creating a new database file...")
			cards.create_db(settings.cards_db)
	
		cards.connect()
		self.sqlconn = sqlite3.connect(settings.cards_db)
		self.cursor = self.sqlconn.cursor()
		
		self.log("Starting download.")
		
		# Download every expansion
		for expansion_num in range(len(downloadlist)):
			code, num, idprefix = downloadlist[expansion_num]
			
			# Update gui
			self.progressbar_expansion.set_fraction(float(expansion_num) \
				/ len(downloadlist))
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
				card.price = yield miner.mine_price(code, card_num)
				
				# Download picture
				if DOWNLOAD_PICS:
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


def load_downloadlist():
	"""Fetch the download list from a file"""
	global downloadlist
	downloadlist = []
	with open(DOWNLOADLIST_FILE, 'r') as f:
		for line in f:
			if line != "\n" and line[0] not in ("#", "%"):
				code, num, idprefix = line.strip().split()[0:3]
				downloadlist.append((code, int(num), idprefix))




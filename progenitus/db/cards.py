# Written by TheGurke 2011
"""Card class and database access"""

import os
import glib
import sqlite3
from gettext import gettext as _

from progenitus import settings
import pics


_cursor = None # The database cursor
_last_search = None # The last query executed

def connect():
	"""Establish database connection"""
	assert(os.path.isfile(settings.cards_db))
	global sqlconn, _cursor
	sqlconn = sqlite3.connect(settings.cards_db)
	_cursor = sqlconn.cursor()

connect()

class Card(object):
	"""Magic card instance"""
	
	def __init__(self, *args):
		if args == ():
			args = (0, "", "", "", "", "", "", "", "", "", "", "", "", "", "",
				"", "", "", "", 0, 0)
		assert(isinstance(args[0], int))
		(self.cardid, self.name, self.cardset, self.manacost,
			self.converted_cost, self.iswhite, self.isblue, self.isblack,
			self.isred, self.isgreen, self.iscolorless, self.cardtype,
			self.subtype, self.text, self.flavor, self.artist,
			self.rarity, self.power, self.toughness, self.price,
			self.releasedate) = args
	
	def __eq__(self, other):
		return self.cardid == other.cardid
	
	def __str__(self):
		return "%s (%s)" % (self.name, self.cardset)
	
	def markup(self):
		"""Return the card details as a gtk markup text"""
		esc = glib.markup_escape_text # escape function
		if self.manacost != "":
			text = "<b>%s  (%s)</b>\n" % (esc(self.name), self.manacost)
		else:
			text = "<b>%s</b>\n" % esc(self.name)
		text += "%s - %s" % (esc(self.cardtype), esc(self.subtype)) if \
			self.subtype != "" else esc(self.cardtype)
		if self.text != "":
			text += "\n\n%s" % esc(self.text)
		if self.flavor != "":
			text += "\n\n<i>%s</i>" % esc(self.flavor)
		text += "\n\n\n<small>%s #%d" % (self.cardset, self.cardid % 1000)
		if self.price >= 0:
			text += "    $%.2f</small>" % (float(self.price) / 100,)
		else:
			text += "</small>"
		return text
	
	def get_price(self):
		"""Get the pricing of a card with the same name"""
		if self.price >= 0:
			return self.price
		# search for a card with the same name and pricing information
		query = '"name" = ? AND "price" >= 0 ORDER BY "price" ASC'
		l = search(query, (self.name,), 1)
		if len(l) >= 1:
			return l[0].price
		else:
			return None
	
	def get_composed_type(self):
		if self.subtype == "":
			return self.cardtype
		else:
			return self.cardtype + " - " + self.subtype
	
	def as_tuple(self):
		"""Return the magic card as a tuple"""
		return self.cardid, self.name, self.cardset, self.manacost, \
			self.converted_cost, self.iswhite, self.isblue, self.isblack, \
			self.isred, self.isgreen, self.iscolorless, self.cardtype, \
			self.subtype, self.text, self.flavor, self.artist, self.rarity, \
			self.power, self.toughness, self.price, self.releasedate
	
	def get_pic(self):
		"""Returns the pixmap containing the card picture"""
		return pics.get(self.cardid)


def convert_mana(manacost):
	if manacost is None:
		return 0
	cc = manacost
	for z in "WUBRGXYZP{/}":
		cc = cc.replace(z, "")
	cc = "0" if cc == "" else cc
	return sum(map(lambda s: manacost.count(s), "WUBRGP")) + int(cc) - \
		manacost.count("}")
			# alternative colors e.g. {W/G} have 1 less than counted


def create_db(filename):
	"""Create the sqlite database file"""
	assert(not os.path.exists(filename))
	conn = sqlite3.connect(filename)
	c = conn.cursor()
	c.execute(u'CREATE TABLE "cards" ("id" INTEGER PRIMARY KEY, "name" TEXT, ' \
		'"set" TEXT, "manacost" TEXT, "converted" INTEGER, '\
		'"iswhite" INTEGER, "isblue" INTEGER, "isblack" INTEGER, ' \
		'"isred" INTEGER, "isgreen" INTEGER, "iscolorless" INTEGER, ' \
		'"type" TEXT, "subtype" TEXT, "text" TEXT, "flavor" TEXT, ' \
		'"artist" TEXT, "rarity" TEXT, "power" TEXT, "toughness" TEXT, ' \
		'"price" INTEGER, "releasedate" INTEGER)')
	conn.commit()


def get(cardid):
	"""Get a card by id"""
	assert(isinstance(cardid, int))
	l = search('"id" = ?', (cardid,), 1)
	if l == []:
		raise RuntimeError(_("Card with id %d not found.") % cardid)
	if len(l) > 1:
		# SQL will see to that this never happends
		raise RuntimeError(_("Card id %d is ambiguous.") % cardid)
	return l[0]


def search(query, args=(), limit=settings.results_limit):
	"""Get a list of cards by sql query"""
	global _cursor, _limit, _last_search
	_limit = limit
	_last_search = 'SELECT * FROM "cards" WHERE ' + query, args
	_cursor.execute(*_last_search)
	l = []
	i = 0
	for row in _cursor:
		card = Card(*row)
		l.append(card)
		i += 1
		if i >= _limit:
			break
	return l


def more_results(limit=None):
	"""Get more results to the last executed sql query"""
	# FIXME: broken!
	global _cursor, _limit, _last_search
	if limit is None:
		_limit += settings.results_limit
	else:
		_limit = limit
	print _limit
	_cursor.execute(*_last_search)
	l = []
	i = 0
	for row in _cursor:
		card = Card(*row)
		l.append(card)
		i += 1
		if i >= _limit:
			print "Limit reached"
			break
	return l




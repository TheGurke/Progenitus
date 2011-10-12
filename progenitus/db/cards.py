# Written by TheGurke 2011
"""Manage card instances and access to the card database"""

import datetime
import os
import glib
import sqlite3
from gettext import gettext as _

from progenitus import config
from progenitus import settings

#
# Every card has a unique id string; tokens and cards have different ids.
# Use the function cards.is_token(cardid) to tell them apart.
#

_cursor = None # The database cursor
_last_search = None # The last query executed
tokens = None # A list of all tokens
cards = None # A list of all cards
sets = None # A list of all card sets
_by_id = None # A dict mapping id to card or token instance
_by_name = None # A dict mapping a name to a list of card instances


def connect():
	"""Establish database connection"""
	db_file = os.path.join(settings.cache_dir, config.DB_FILE)
	assert(os.path.isfile(db_file))
	global sqlconn, _cursor
	sqlconn = sqlite3.connect(db_file)
	_cursor = sqlconn.cursor()
	load_tokens()
	load_cards()
	load_sets()
	build_datastructures()


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


def is_token(cardid):
	"""Determine if something is a token by its card id"""
	return cardid.find('.T.') >= 0



class Card(object):
	"""Magic card instance"""
	
	def __init__(self, *args):
		if len(args) == 0:
			args = ("", "", "", "", "", 0, 0, 0, 0, 0, 0, 0, "", "", "", "", "",
				"", "", "", -1, 0, "", 0)
		(self.id, self.name, self.setid, self.setname, self.manacost,
			self.converted_cost, self.iswhite, self.isblue, self.isblack,
			self.isred, self.isgreen, self.iscolorless, self.cardtype,
			self.subtype, self.text, self.flavor, self.artist,
			self.rarity, self.power, self.toughness, self.price,
			self.releasedate, self.collectorsid, self.linkedto) = args
	
	def __eq__(self, other):
		return self.id == other.id
	
	def __str__(self):
		return self.name
	
	def derive_id(self):
		"""Derive the card id based on collectors id and setid"""
		self.id = "%s.%s" % (self.setid, self.collectorsid)
	
	def derive_colors(self):
		"""Derive this card's color"""
		for c in ("white", "blue", "black", "red", "green", "colorless"):
			setattr(self, "is" + c, False)
		for c in ("white", "blue", "black", "red", "green", "colorless"):
			if self.text.find("%s is %s." % (self.name, c)) >= 0:
				setattr(self, "is" + c, True)
				return
		iscolorless = True
		for c, z in (("white", "W"), ("blue", "U"), ("black", "B"),
			("red", "R"), ("green", "G")):
			setattr(self, "is" + c, z in self.manacost)
			iscolorless = iscolorless and not z in self.manacost
		self.iscolorless = False if self.cardtype.find("Land") >= 0 else \
			iscolorless # Lands do not count as colorless
	
	def markup(self):
		"""Return the card details as a gtk markup text"""
		esc = glib.markup_escape_text # escape function
		if self.manacost != "":
			text = "<b>%s  (%s)</b>\n" % (esc(self.name), self.manacost)
		else:
			text = "<b>%s</b>\n" % esc(self.name)
		text += "<small>%s %s #%s" % (self.setname, self.rarity,
			self.collectorsid)
		if self.price >= 0:
			text += "  $%.2f</small>\n" % (float(self.price) / 100,)
		else:
			text += "</small>\n"
		text += "%s - %s" % (esc(self.cardtype), esc(self.subtype)) if \
			self.subtype != "" else esc(self.cardtype)
		if self.text != "":
			text += "\n\n%s" % esc(self.text)
		if self.flavor != "":
			text += "\n\n<i>%s</i>" % esc(self.flavor)
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
		return (self.id, self.name, self.setid, self.setname, self.manacost,
			self.converted_cost, self.iswhite, self.isblue, self.isblack,
			self.isred, self.isgreen, self.iscolorless, self.cardtype,
			self.subtype, self.text, self.flavor, self.artist, self.rarity,
			self.power, self.toughness, self.price, self.releasedate,
			self.collectorsid, self.linkedto)



class Token(object):
	"""A token instance"""
	
	def __init__(self, *args):
		if args == ():
			args = ("", "", "", 0, 0, 0, 0, 0, 0, "", "", "", "", "", "", "",
				0, "")
		(self.id, self.setid, self.setname, self.iswhite, self.isblue,
			self.isblack, self.isred, self.isgreen, self.iscolorless,
			self.cardtype, self.subtype, self.text, self.flavor, self.artist,
			self.power, self.toughness, self.releasedate, self.collectorsid) \
				= args
	
	def __eq__(self, other):
		return self.id == other.id
	
	def __str__(self):
		if self.power != "" and self.toughness != "":
			return "%s/%s %s" % (self.power, self.toughness, self.subtype)
		return self.subtype
	
	def derive_id(self):
		"""Derive the card id based on collectors id and setid"""
		self.id = "%s.T.%s" % (self.setid, self.collectorsid)
	
	def get_description(self):
		"""Get a token description"""
		if self.power == "" and self.toughness == "":
			return "%s (%s)" % (self.subtype, self.setname)
		return "%s/%s %s (%s)" % (self.power, self.toughness, self.subtype,
			self.setname)
	
	def markup(self):
		"""Return the card details as a gtk markup text"""
		esc = glib.markup_escape_text # escape function
		text = "%s - %s" % (esc(self.cardtype), esc(self.subtype)) if \
			self.subtype != "" else esc(self.cardtype)
		if self.text != "":
			text += "\n\n%s" % esc(self.text)
		if self.flavor != "":
			text += "\n\n<i>%s</i>" % esc(self.flavor)
		text += "\n\n\n<small>%s #%d" % (self.cardset, self.collectorsid)
		text += "</small>"
		return text
	
	def as_tuple(self):
		"""Return the token as a tuple"""
		return (self.id, self.setid, self.setname, self.iswhite, self.isblue,
			self.isblack, self.isred, self.isgreen, self.iscolorless,
			self.cardtype, self.subtype, self.text, self.flavor, self.artist,
			self.power, self.toughness, self.releasedate, self.collectorsid)


def create_db(filename):
	"""Create the sqlite database file"""
	assert(not os.path.exists(filename))
	conn = sqlite3.connect(filename)
	c = conn.cursor()
	c.execute(u'CREATE TABLE "sets" ("id" TEXT PRIMART KEY, "name" TEXT, ' \
		'"cards" INTEGER, "releasedate" INTEGER)')
	c.execute(u'CREATE TABLE "cards" ("id" TEXT PRIMARY KEY, "name" TEXT, ' \
		'"setid" TEXT, "setname" TEXT, "manacost" TEXT, "converted" INTEGER, '\
		'"iswhite" INTEGER, "isblue" INTEGER, "isblack" INTEGER, ' \
		'"isred" INTEGER, "isgreen" INTEGER, "iscolorless" INTEGER, ' \
		'"type" TEXT, "subtype" TEXT, "text" TEXT, "flavor" TEXT, ' \
		'"artist" TEXT, "rarity" TEXT, "power" TEXT, "toughness" TEXT, ' \
		'"price" INTEGER, "releasedate" INTEGER, "collectorsid" TEXT, ' \
		'"linkedto" INTEGER)')
	c.execute(u'CREATE TABLE "tokens" ("id" TEXT PRIMARY KEY, ' \
		'"setid" TEXT, "setname" TEXT, "iswhite" INTEGER, "isblue" INTEGER, ' \
		'"isblack" INTEGER, "isred" INTEGER, "isgreen" INTEGER, ' \
		'"iscolorless" INTEGER, "type" TEXT, "subtype" TEXT, "text" TEXT, ' \
		'"flavor" TEXT, "artist" TEXT, "power" TEXT, "toughness" TEXT, ' \
		'"releasedate" INTEGER, "collectorsid" TEXT)')
	conn.commit()


def get(cardid):
	"""Get a card or token by id"""
	assert(_by_id is not None) # must be initialized
	if cardid not in _by_id:
		raise RuntimeError(_("Card id %s not found in database.") % cardid)
	return _by_id[cardid]


def find_by_name(cardname):
	"""Return a list of versions of a card by the English name"""
	assert(_by_name is not None) # must be initialized
	if cardname not in _by_name:
		raise RuntimeError(_("Card '%s' not found in database.") % cardname)
	return _by_name[cardname]


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


def count():
	"""Count the number of available cards"""
	_cursor.execute('SELECT COUNT(*) FROM "cards"')
	for row in _cursor:
		return row[0]


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


def load_tokens():
	"""Load all tokens from the database to memory"""
	global tokens
	_cursor.execute('SELECT * FROM "tokens"')
	tokens = []
	for row in _cursor:
		token = Token(*row)
		tokens.append(token)


def load_cards():
	"""Load all cards from the database to memory"""
	global cards
	_cursor.execute('SELECT * FROM "cards"')
	cards = []
	for row in _cursor:
		card = Card(*row)
		cards.append(card)


def load_sets():
	"""Load all cards from the database to memory"""
	global sets
	_cursor.execute('SELECT "name" FROM "sets"')
	sets = []
	for row in _cursor:
		sets.append(row[0])


def build_datastructures():
	"""refresh _by_id and _by_name"""
	global _by_id, _by_name, cards, tokens
	_by_id = dict()
	_by_name = dict()
	for card in cards:
		_by_id[card.id] = card
		if card.name in _by_name:
			_by_name[card.name].append(card)
		else:
			_by_name[card.name] = [card]
	for token in tokens:
		_by_id[token.id] = token




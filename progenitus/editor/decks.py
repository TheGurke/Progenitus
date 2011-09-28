# Written by TheGurke 2011
"""Load and save decks"""

import random
import copy
import codecs
import re
import os

from gettext import gettext as _

from progenitus import settings
from progenitus.db import cards

#
# About the deck format:
# The deck is a plain text file consisting of lines of cards
# No pathenthesis may be used in card names, instead just the text inside the
# pathenthesis should be used to indetify the card.
# If a card from a specific set is desired, the set name may be added in
# parenthesis after the card name.
#


# Regular expressions used by _parse_file
_re1 = re.compile(r'\s*(?:#|%)([^\n]*)') # comment with # or %
_re2 = re.compile(
	r'\s*(?:(\d+)x?\s|)\s*([^\(\r\n]+)\s+(?:\(\s*([^\)\r\n]*)\)|)')
_re3 = re.compile(r'\s*(?:#|%)\s*@author:\s*([^\r\n]+)')
_re4 = re.compile(r'\s*\n') # empty line


def get_decklist():
	"""Get a list of all available decks"""
	decklist = []
	# find all files in settings.deck_dir with suffix ".deck"
	for root, dirs, files in os.walk(settings.deck_dir):
		files = filter(lambda s: os.path.isfile(os.path.join(root, s)) \
			and s[-5:] == ".deck", files)
		decklist.extend(map(lambda s: os.path.join(root, s), files))
	return decklist


class Deck(object):
	def __init__(self, filename):
		self.filename = filename
		self.name = self.derive_name()
		self.description = ""
		self.author = ""
		self.decklist = []
		self.sideboard = []
		self.readonly = False
		self.color = []
	
	def derive_name(self, filename=None):
		"""The deckname is the filename without path and extension"""
		if filename is None:
			filename = self.filename
		name = os.path.basename(filename)
		if name[-5:] == u".deck":
			name = name[:-5]
		return name
	
	def derive_filename(self, deckname=None):
		"""Suggest a path based on the decks name and previous location"""
		if deckname is None:
			deckname = self.name
		filename = os.path.join(os.path.dirname(self.filename), deckname +
			u".deck")
		return filename
	
	def derive_color(self):
		"""List a deck's color"""
		self.color = []
		for c in ["white", "blue", "black", "red", "green"]:
			l = filter(lambda card: getattr(card, "is" + c), self.decklist)
			if len(l) > 3:
				self.color.append(c)
	
	def get_price(self):
		"""Get the estimated price of all the cards in this deck"""
		price = 0
		for card in self.deck + self.sideboard:
			if card.price >= 0:
				price += card.price
		return price
	
	def add(self, cardid, sideboard=False):
		"""Add a card by id to the deck"""
		card = cards.get(cardid)
		if card is not None:
			(self.sideboard if sideboard else self.deck).append(card)
	
	def remove(self, cardid, sideboard=False):
		"""Remove a card by id from the deck"""
		l = self.sideboard if sideboard else self.decklist
		card = filter(lambda c: c.id == cardid, l)[0]
		l.remove(card)
	
	def save(self):
		"""Save a magic deck to a file"""
		with codecs.open(self.filename, 'w', 'utf-8') as f:
			# Write author and description
			if self.author != "":
				f.write("# @author: %s\n" % self.author)
			if self.description != "":
				for line in self.description.split('\n'):
					f.write("#%s\n" % line)
			f.write("\n");
			
			# Write cardlist
			for l in (self.decklist, self.sideboard):
				for i in range(len(l)):
					card = l[i]
					assert(isinstance(card, cards.Card))
					if card in l[:i]:
						continue # already processed
					num = len([c for c in l[i:] if c == card])
					name = card.name
					if name.find("(") >= 0:
						# Workaround for cards with '(' in their name
						assert(name.find(")") >= 0)
						name = name.split('(')[1].split(')')[0]
					f.write("%d %s (%s)\n" % (num, name, card.setname))
				if len(self.sideboard) > 0 and l == self.decklist:
					f.write("\nSideboard:\n")


def _parse_file(filename):
	"""Parse a deck file into a list of card names"""
	deck = Deck(filename)
	cardlist = []
	
	with codecs.open(filename, 'r', 'utf-8') as f:
		atsideboard = False
		for line in f:
			if _re4.match(line):
				# empty line
				continue
			if _re3.match(line):
				# author
				match = _re3.match(line)
				deck.author = match.group(1)
				continue
			if _re1.match(line):
				# comment
				match = _re1.match(line)
				deck.description += match.group(1) + "\n"
				continue
			if line.lower().find("sideboard") >= 0:
				atsideboard = True # sideboard cards from now on
				continue
			# card
			match = _re2.match(line)
			if match:
				num, name, setname = match.group(1, 2, 3)
				num = int(num) if num is not None else 1
				cardlist.append((num, name, setname, atsideboard))
	
	deck.description = deck.description[:-1] # remove the last newline
	return deck, cardlist


def load(filename, progresscallback=None, returncallback=None):
	"""Load a magic deck from a file; asynchronious method"""
	
	deck, cardlist = yield _parse_file(filename)
	
	# check for write-protection
	if not os.access(filename, os.W_OK):
		deck.readonly = True
	
	# lookup in the db
	for i in range(len(cardlist)):
		num, name, setname, sb = cardlist[i]
		if setname is not None:
			l = yield cards.search('"setname" = ? AND "name" = ?' +
				' ORDER BY "releasedate" DESC', (setname, name))
		if setname is None or l == []:
			print _("Card '%s' in set '%s' not found.") % (name, setname)
			l = yield cards.search('"name" = ? ORDER BY "releasedate" DESC',
				(name,))
		if l == []:
			# try to find card by adding parenthesis
			name = "%(" + name + ")%"
			if setname is not None:
				l = yield cards.search('"setname" LIKE ? AND "name" = ?' +
					' ORDER BY "releasedate" DESC', (setname, name))
			if setname is None or l == []:
				l = yield cards.search('"name" LIKE ?' +
					' ORDER BY "releasedate" DESC', (name,))
			if l == []:
				print("Card \"" + name[2:-2] + "\" not found.")
				continue
		card = random.choice(l)
		assert(0 <= num < 1000)
		for j in range(num):
			(deck.sideboard if sb else deck.decklist).append(copy.copy(card))
		if progresscallback is not None:
			progresscallback(float(i) / len(cardlist))
	if returncallback is not None:
		returncallback(deck)




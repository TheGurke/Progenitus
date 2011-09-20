#!/usr/bin/python
#
# This script converts octgn type decks to the new format
# Usage:
#
# ./ocgtnconvert.py octgndeck.xml
#

import sys
import xml.dom.minidom
from gettext import gettext as _

import lang
import settings
import cards
import decks



def getText(node):
	"""Get the text content of a node"""
	rc = []
	for node in node.childNodes:
		if node.nodeType == node.TEXT_NODE:
			rc.append(node.data)
	return ''.join(rc)


def parse_info(node, deck):
	"""Extract the deck's meta information"""
	for child in node.childNodes:
		if child.localName == "creator":
			deck.author = getText(child)
		if child.localName == "description":
			deck.description == getText(child)


def parse_list(node):
	"""Extract the cards from a list"""
	cardlist = []
	for child in node.childNodes:
		if child.localName == "card":
			octgnid = int(child.getAttribute("id"))
			name = getText(child)
			l = cards.search('"name" == ? ORDER BY "releasedate" DESC', (name,))
			if l == []:
				print(_("Card not found: %s (%d)") % (name, octgnid))
			else:
				cardlist.append(l[0])
	return cardlist


def parse(dom, deck):
	"""Parse an xml dom to into a deck instance"""
	# Get root and check file
	l = dom.getElementsByTagName("OCTGNDeck")
	if len(l) == 0:
		raise RuntimeError("Source file is not an OCTGN1 deck file.")
	root = l[0]
	version = root.getAttribute("Version")
	assert(version == u"1.0")
	
	# Parse the data
	parse_info(dom.getElementsByTagName("deckinfo")[0], deck)
	deck.decklist = parse_list(dom.getElementsByTagName("maindeck")[0])
	deck.sideboard = parse_list(dom.getElementsByTagName("sideboard")[0])


if __name__ == "__main__":
	# Get source and target filename
	targetfile = sourcefile = sys.argv[1]
	if targetfile[-4:] == ".xml":
		targetfile = targetfile[:-4]
	targetfile += ".deck"
	
	# Initialization
	print("Converting %s..." % sourcefile)
	cards.connect()
	
	# Parse!
	dom = xml.dom.minidom.parse(sourcefile) # parse the xml
	deck = decks.Deck(targetfile)
	parse(dom, deck)
	deck.save()




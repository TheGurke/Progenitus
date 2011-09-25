# Written by TheGurke 2011
"""Extract data from magiccards.info"""


import re
import httplib
import urllib

from progenitus.db import cards
import miner



lang = "en"

server = "magiccards.info"

url_search = "/query?q=%s&v=card&s=cname"
url_set = "/%s/" + lang + ".html"
url_card = "/%s/" + lang + "/%s.html"
url_pic = "/scans/" + lang + "/%s/%s.jpg"


# Regular expressions to be used on the query
re_set = re.compile(r'<h1>([^<]*)<small[^>]*>([^<]*)</small>\s*</h1>')
#re_set2 = re.compile(r'<td[^>]*>\s*(\d+)\s+cards\s*</td>')
re_set2 = re.compile(r'<td align="right">([^<]*)</td>\s*'
	'<td>\s*<a\s+href="[^"]*"\s*>')
re_card = re.compile(r'<a href="[^"]*">([^<]+)</a>\s*<[^<]*</span>\s*<p>(.*?)'
	'(?:\s([\d\*X]+)/|)([\d\*X]+|)(?:,\s+([\d\{\}/WUBRGXYZP]+)\s*'
	'(?:\(\d+\)|)|)</p>\s*<p\s+class="ctext"><b>(.*?)</b></p>\s*'
	'<p><i>(.*?)</i></p>\s*<p>Illus. ([^<]*)</p>')
re_card2 = re.compile(r'<br><u><b>Editions:</b></u><br>(?:.|\n)*'
	'<b>(.*?) \((.+?)\)</b><br>(?:.|\n)*'
	'<br><u><b>Languages:</b></u><br>')


con = None # httplib.HTTPConnection


def connect():
	global con
	con = miner.new_connection(server)


def mine_set(setcode):
	"""Mine the date for a magic set"""
	html = miner.download(con, url_set % setcode)
	
	# Get set name
	result = re_set.search(html)
	if result is None:
		raise RuntimeError("Pattern match failed at '%s'." % magicset)
	name, code = result.groups()
	
	# Get set cards
	result = re_set2.findall(html)
	return name.strip(), result


def mine_card(setcode, collectorsid):
	"""Mine the data for one card of a magic set"""
	html = miner.download(con, url_card % (setcode, collectorsid))
	
	# Extract data
	res = re_card.search(html)
	if res is None:
		raise RuntimeError("Pattern match failed at the card %s:%s."
			% (setcode, collectorsid))
	
	card = cards.Card()
	card.collectorsid = collectorsid
	card.name, cardtype, card.power, card.toughness, card.manacost, \
		card.text, card.flavor, card.artist = res.groups()
	if card.manacost is None:
		card.manacost = ""
	card.text = card.text.replace("<br>", "\n")
	card.flavor = card.flavor.replace("<br>", "\n")
	card.flavor = card.flavor.replace("<i>", "").replace("</i>", "")
	t = cardtype.split(" - ")
	card.cardtype = t[0].strip()
	card.subtype = "" if len(t) <= 1 else t[1].strip()
	iscolorless = True
	for c, z in [("white", "W"), ("blue", "U"), ("black", "B"), ("red", "R"),
		("green", "G")]:
		setattr(card, "is" + c, z in card.manacost)
		iscolorless = iscolorless and not z in card.manacost
	card.iscolorless = False if card.cardtype.find("Land") >= 0 else iscolorless
		# Lands do not count as colorless
	card.converted_cost = cards.convert_mana(card.manacost)
	
	res = re_card2.search(html)
	if res is None:
		raise RuntimeError("Pattern (2) match failed at the card %s:%s."
			% (setcode, collectorsid))
	card.cardset = res.group(1)
	card.rarity = res.group(2)
	return card


def mine_pic(setcode, collectorsid, filename):
	"""Download the card jpg"""
	pic = miner.download(con, url_pic % (setcode, collectorsid), False)
	with open(filename, 'wb') as f:
		f.write(pic)




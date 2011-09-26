# Written by TheGurke 2011
"""Extract data from magiccards.info"""


import re
import httplib
import urllib

from gettext import gettext as _

from progenitus.db import cards
import miner



lang = "en"

server = "magiccards.info"

url_set = "/%s/" + lang + ".html"
url_pic = "/scans/" + lang + "/%s/%s.jpg"
url_tokens = "/extras.html"

url_spoiler = "/query?q=%%2B%%2Be%%3A%s%%2F" + lang + "&v=spoiler"

# Regular expressions to be used on the query
re_set = re.compile(r'<h1>([^<]*)' # set name
	'<small[^>]*>([^<]*)</small>\s*</h1>' # magiccards.info set code
)
re_set2 = re.compile(r'<td\s+align="right">([^<]+)</td>\s*' # collector's id
	'<td>\s*<a\s+href="[^"]*"\s*>([^<]+)</a>\s*</td>' # card name
)
re_set3 = re.compile(r'<span[^>]*>\s*<a\s+href="[^"]*">([^<]+)</a>\s*</span>'
	'\s*<p>\s*<img[^>]*>[^<]*<i>([^<]*)</i>\s*</p>\s*'
	'<p>(.*?)(?:\s([\d\*X]+)/|)([\d\*X]+|),(?:\s+([\d\{\}/WUBRGXYZP]+)\s*'
	'(?:\(\d+\)|)|)\s*</p>\s*<p\s+class="ctext">\s*<b>(.*?)</b>\s*</p>\s*'
	'<p>\s*<i>([\d\D]*?)</i>\s*</p>\s*<p>Illus.\s+([^<]*)</p>')
re_token = re.compile(r'<h2>([^<]*)</h2>') # set name
re_token2 = re.compile(r'<tr[^>]*>\s*'
	'<td>\s*<a\s+href="([^"]*)">(.*?)' # link and name
	'(?:\s+([\d\*X]+)/([\d\*X]+)|)</a>\s*</td>\s*' # power and toughness
	'<td>Token</td>\s*' # token description
	'<td>(?:([\d\*X]+)/[\d\*X]+|-)</td>\s*' # number
	'<td>([^<]*)</td>\s*' # artist
	'</tr>'
)

con = None # httplib.HTTPConnection


def connect():
	global con
	con = miner.new_connection(server)


def mine_set(setcode, releasedate, magiccardsinfocode):
	"""Mine the date for a magic set"""
	html = miner.download(con, url_set % magiccardsinfocode)
	
	# Get set name
	result = re_set.search(html)
	if result is None:
		raise RuntimeError(_("Pattern match failed."))
	setname, code = result.groups()
	
	# Get set cards
	cids = re_set2.findall(html)
	if cids is None:
		raise RuntimeError(_("Pattern (2) match failed."))
	
	# Get full spoilers
	html = miner.download(con, url_spoiler % magiccardsinfocode)
	spoilers = re_set3.findall(html)
	if spoilers is None:
		raise RuntimeError(_("Pattern (3) match failed."))
	if len(cids) != len(spoilers):
		missing = []
		for cid, name in cids:
			for spoiler in spoilers:
				if name == spoiler[0]:
					break
			else:
				missing.append(name)
		raise RuntimeError(_("Missing cards: " + ", ".join(missing)))
				
	
	cardlist = []
	for i in range(len(cids)):
		card = cards.Card()
		card.name, card.rarity, cardtype, card.power, card.toughness, \
			card.manacost, card.text, card.flavor, card.artist = spoilers[i]
		for i in range(len(cids)):
			collectorsid, name = cids[i]
			if name == card.name:
				card.collectorsid = collectorsid
				cids[i:i+1] = []
				break
		else:
			raise RuntimeError(_("Missing card: '%s'") % card.name)
		if card.manacost is None:
			card.manacost = ""
		card.text = card.text.replace("<br>", "\n")
		card.flavor = card.flavor.replace("<br>", "\n")
		card.flavor = card.flavor.replace("<i>", "").replace("</i>", "")
		t = cardtype.split(" - ")
		card.cardtype = t[0].strip()
		card.subtype = "" if len(t) <= 1 else t[1].strip()
		card.converted_cost = cards.convert_mana(card.manacost)
		card.setid = setcode
		card.setname = setname
		card.releasedate = releasedate.toordinal()
		card.derive_id()
		card.derive_colors()
		cardlist.append(card)
	return setname.strip(), cardlist


def mine_tokens():
	"""Mine all tokens"""
	html = miner.download(con, url_tokens)
	tokens = []
	for part in html.split('<table>'):
		setname = re_token.search(part).group(1)
		tokens_ = re_token2.findall(part)
		if tokens_ is None:
			continue
		for link, name, power, toughness, number, artist in tokens_:
			tokens.append((link[:-4] + "jpg", name, setname, power, toughness,
				number, artist))
	if len(tokens) == 0:
		raise RuntimeError(_("Pattern (4) match failed."))
	return tokens


def mine_pic(url, filename):
	"""Download the card jpg"""
	pic = miner.download(con, url, False)
	with open(filename, 'wb') as f:
		f.write(pic)




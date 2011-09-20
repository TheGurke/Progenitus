# Written by TheGurke 2011
"""Miner program to extract card information for the Magic the Gathering trading
card game from the online platform magiccards.info"""

import re
import httplib

import cards



# url settings
lang = "en"
url_search = "/query?q=%s&v=card&s=cname"
url_base = "magiccards.info"
card_url_location = "/%s/" + lang + "/%d.html"
pic_url_location = "/scans/" + lang + "/%s/%d.jpg"
price_url_base = "partner.tcgplayer.com"
price_url_location = "/syn/Synidcate.ashx?pk=MAGCINFO&pi=%s-%d"


# Regular expressions to be used on the query
re2 = re.compile(r'<a href="[^"]*">[^<]+</a>\s*<[^<]*</span>\s*<p>(.*?)'
	'(?:\s([\d\*X]+)/|)([\d\*X]+|)(?:,\s+([\d\{\}/WUBRGXYZP]+)\s*'
	'(?:\(\d+\)|)|)</p>\s*<p\s+class="ctext"><b>(.*?)</b></p>\s*'
	'<p><i>(.*?)</i></p>\s*<p>Illus. ([^<]*)</p>')
re3 = re.compile(r'<br><u><b>Editions:</b></u><br>(?:.|\n)*'
	'<b>(.*?) \((.+?)\)</b><br>(?:.|\n)*'
	'<br><u><b>Languages:</b></u><br>')
re_price = re.compile(r'>\$(\d+.\d\d)<')


def download(host, url, convert_to_unicode=True):
	"""Download data from a web address"""
	con = httplib.HTTPConnection(host)
	con.request("GET", url)
	res = con.getresponse()
	if res.status != 200:
		raise RuntimeError(str(res.status) + res.reason + ": " + url)
	code = res.read()
	con.close()
	if convert_to_unicode:
		code = unicode(code, 'utf-8')
	return code


def mine_price(magicset, n):
	"""Get the average price for a card"""
	url = price_url_location % (magicset, n)
	js = download(price_url_base, url)
	prices = re_price.findall(js)
	if len(prices) < 3:
		return -1
	lowest_price = prices[0]
	average_price = prices[1]
	highest_price = prices[2]
	return int(100*float(average_price))


def mine(magicset, n):
	"""Mine the data for one card of a magic set"""
	# Retrieve html
	url = card_url_location % (magicset, n)
	html = download(url_base, url)
	
	# Extract data
	res = re.search(r'<a href="' + url + '">([^<]+)</a>', html)
	if res is None:
		raise RuntimeError("Pattern match failed at card #%d." % n)
	card = cards.Card()
	card.name = res.group(1)
	
	res = re2.search(html)
	if res is None:
		raise RuntimeError("Pattern match failed at the card \"%s\"." \
			% card.name)
	cardtype, card.power, card.toughness, card.manacost, \
		card.text, card.flavor, card.artist = res.group(1, 2, 3, 4, 5, 6, 7)
	if card.manacost is None:
		card.manacost = ""
	card.text = card.text.replace("<br>", "\n")
	card.flavor = card.flavor.replace("<br>", "\n")
	t = cardtype.split(" - ")
	card.cardtype = t[0]
	card.subtype = "" if len(t) <= 1 else t[1]
	iscolorless = True
	for c, z in [("white", "W"), ("blue", "U"), ("black", "B"), ("red", "R"),
		("green", "G")]:
		setattr(card, "is" + c, z in card.manacost)
		iscolorless = iscolorless and not z in card.manacost
	card.iscolorless = False if card.cardtype.find("Land") >= 0 else iscolorless
		# Lands do not count as colorless
	card.converted_cost = cards.convert_mana(card.manacost)
	
	res = re3.search(html)
	if res is None:
		raise RuntimeError("Pattern2 match failed at the card \"%s\"." \
			% card.name)
	card.cardset = res.group(1)
	card.rarity = res.group(2)
	return card


def getpic(magicset, n, filename):
	"""Download the card jpg"""
	url = pic_url_location % (magicset, n)
	pic = download(url_base, url, convert_to_unicode=False)
	with open(filename, 'wb') as f:
		f.write(pic)




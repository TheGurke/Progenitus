# Written by TheGurke 2011
"""Extract pricing information from tcgplayer.com"""


import re

import miner


server = "partner.tcgplayer.com"
url_price = "/syn/Synidcate.ashx?pk=MAGCINFO&pi=%s-%s"

re_price = re.compile(r'>\$(\d+.\d\d)<')


con = None # httplib.HTTPConnection


def connect():
	global con
	con = miner.new_connection(server)


def mine_price(magicset, n):
	"""Get the average price for a card"""
	js = miner.download(con, url_price % (magicset, n))
	prices = re_price.findall(js)
	if len(prices) < 3:
		return -1
	lowest_price = prices[0]
	average_price = prices[1]
	highest_price = prices[2]
	return int(100*float(average_price))




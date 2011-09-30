# Written by TheGurke 2011
"""Extract pricing information from tcgplayer.com"""


import re
import urllib

import miner


server = "magic.tcgplayer.com"
url_price = "/db/price_guide.asp?setname=%s"

re_name = re.compile(r'<font\s+class=default_7>&nbsp;([^<]*?)</font>')
re_price = re.compile(r'<font\s+class=default_7>\$(\d+\.\d+)&nbsp;</font>')

con = miner.new_connection(server)


def mine_pricelist(setname):
	"""Get the average price for a card"""
	url = urllib.quote(url_price % setname, '/?=')
	html = miner.download(con, url, convert_to_unicode=False)
	pricelist = []
	for part in html.split("<TR height=20>"):
		match = re_name.search(part)
		if match is None:
			continue
		cardname = unicode(match.group(1), errors="ignore")
		cardname = cardname.replace(u'AE', u'\xc3')
		prices = re_price.findall(part)
		if prices is None or len(prices) < 3:
			continue
		lowest_price, average_price, highest_price = map(float, prices)
		pricelist.append((cardname, int(100 * average_price)))
	return pricelist




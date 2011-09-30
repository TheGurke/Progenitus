# Written by TheGurke 2011
"""Miner program to extract card information for the Magic the Gathering trading
card game from a web page"""

import datetime
import re
import httplib
import urllib

from progenitus.db import cards


MAX_TRIES = 10 # number of tries until the process is aborted



def fetch_downloadlist(url):
	"""Fetch the download list from an url"""
	f = urllib.urlopen(url)
	data = f.read()
	f.close()
	return data


def parse_downloadlist(data):
	"""Fetch the download list from a file"""
	downloadlist = []
	for line in data.split('\n'):
		if line != "" and line[0] not in ("#", "%"):
			code, rd, mccode, name, tcgplayername = line.split('\t')[:5]
			releasedt = datetime.date(int(rd[0:4]), int(rd[5:7]), int(rd[8:10]))
			downloadlist.append((code, releasedt, mccode, name, tcgplayername))
	return downloadlist


def download(con, url, convert_to_unicode=True):
	"""Download data from a web address"""
	assert(isinstance(con, httplib.HTTPConnection))
	tries = 0
	while True: # Try to connect a couple of times
		try:
			con.request("GET", url)
			res = con.getresponse()
			data = res.read()
		except httplib.HTTPException:
			tries += 1
			if tries >= MAX_TRIES:
				raise # Let the exception fall through
			continue
		break
	
	if convert_to_unicode:
		data = unicode(data, 'utf-8')
	return data

def new_connection(server):
	"""Create a new httplib.HTTPConnection object and remember to destroy it"""
	return httplib.HTTPConnection(server)



# Written by TheGurke 2011
"""Miner program to extract card information for the Magic the Gathering trading
card game from a web page"""

import datetime
import re
import httplib
import urllib

from progenitus.db import cards



connections = [] # List of all established connections


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
			code, rd, mccode, name = line.split('\t')[:4]
			releasedt = datetime.date(int(rd[0:4]), int(rd[5:7]), int(rd[8:10]))
			downloadlist.append((code, releasedt, mccode, name))
	return downloadlist


def download(con, url, convert_to_unicode=True):
	"""Download data from a web address"""
	assert(isinstance(con, httplib.HTTPConnection))
	con.request("GET", url)
	res = con.getresponse()
	if res.status != 200:
		raise RuntimeError(str(res.status) + res.reason + ": " + url)
	data = res.read()
	con.close()
	if convert_to_unicode:
		data = unicode(data, 'utf-8')
	return data

def new_connection(server):
	"""Create a new httplib.HTTPConnection object and remember to destroy it"""
	global connections
	con = httplib.HTTPConnection(server)
	connections.append(con)
	return con


def disconnect():
	"""Disconnect all open http connections"""
	global connections
	for con in connections:
		con.close()
	connections = []



# Written by TheGurke 2012
"""Singleton program instance enforcing"""

import os
import fcntl
import atexit


fd = None

def check(lockfile):
	"""Check the lockfile and return whether this is the first instance"""
	global fd
	fd = open(lockfile, 'w')
	try:
		fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
		atexit.register(cleanup, lockfile)
		return True
	except:
		return False

def cleanup(lockfile):
	global fd
	fd.close()
	os.remove(lockfile)

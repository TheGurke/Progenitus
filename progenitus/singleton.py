# Written by TheGurke 2012
"""Singleton program instance enforcing"""

import os
if os.name == 'posix':
	import fcntl
import atexit


fd = None

def check(lockfile):
	"""Check the lockfile and return whether this is the first instance"""
	global fd
	try:
		if os.name == 'posix':
			# In unix, fcntl is available and enables file locking.
			fd = open(lockfile, 'w')
			fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
		elif os.name == 'nt':
			# In windows, files cannot be removed while they are opened.
			if os.path.exists(lockfile):
				os.remove(lockfile)
			fd = open(lockfile, 'w')
		else:
			assert(False) # unknown os
		atexit.register(cleanup, lockfile)
		return True
	except:
		return False

def cleanup(lockfile):
	global fd
	fd.close()
	os.remove(lockfile)

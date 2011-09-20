# Written by TheGurke 2011
"""Setup script for the py2exe windows compilation"""

#
# Do not run!
#
# On windows, invoke:
# python win32compile.py py2exe
#


from distutils.core import setup
import py2exe

from progenitus import config


#
# Notes for compiling on windows:
# - install python 2.7
# - install pygtk all-in-one installer
# - make sure you don't have conflicting versions of gtk installed
# - do not copy the redistributable to C:\windows\system32 as instructed
#   on some webpages!
#


setup(
	name=config.APP_NAME,
	version=config.VERSION,
	windows=["progenitus.py"],
	options={"py2exe":{
		"optimize": 2,
		'packages':'encodings',
		"includes": ["gobject", "gio", "cairo", "pango", "pangocairo", "gtk",
			"atk", "glib"]}},
	data_files=["client.glade", "deckeditor.glade", "updater.glade",
		"mtg.sqlite", "README.txt"]
)





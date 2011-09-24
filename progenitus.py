#!/usr/bin/python
# Written by TheGurke 2011
"""Deck editor and network client for Wizard of the Coast's Magic the Gathering
trading card game"""


import os
import sys

from progenitus import *
from progenitus.client import gui as clientgui
from progenitus.editor import gui as editorgui
from progenitus.updater import gui as updatergui

import glib
import gtk


# Change current directory to this script's location
if os.name == 'posix':
	os.chdir(os.path.dirname(os.path.realpath(__file__)))

async.method_queuer = glib.idle_add
gtk.gdk.threads_init()


if len(sys.argv) > 1 and sys.argv[1] == "--client":
	iface = clientgui.Interface()
	iface.main_win.show()
	iface.login_win.show()
	try:
		iface.main()
	finally:
		iface.main_win.hide()
		iface.network_manager.disconnect()
elif len(sys.argv) > 1 and sys.argv[1] == "--updater":
	iface = updatergui.Interface()
	iface.main()
	updatergui.miner.disconnect()
else:
	iface = editorgui.Interface()
	iface.main_win.show()
	iface.main()



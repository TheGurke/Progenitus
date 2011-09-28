#!/usr/bin/python
# Written by TheGurke 2011
"""Deck editor and network client for Wizard of the Coast's Magic the Gathering
trading card game"""


import os
import optparse
from gettext import gettext as _

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


# Command line argument parser
optparser = optparse.OptionParser(
	version=config.VERSION,
	description=_("Deck editor and network client for "
		"Wizard of the Coast's Magic the Gathering trading card game"),
	add_help_option=True,
	epilog=_("Written by TheGurke 2011, GPL3-licenced.")
)
optparser.add_option("--editor", action="store_const", const="editor",
	dest="run", help=_("run the deck editor"))
optparser.add_option("--client", action="store_const", const="client",
	dest="run", help=_("run the network client"))
optparser.add_option("--solitaire", action="store_true", dest="solitaire",
	default=False, help=_("run the network client in single user mode "
		"(requires --client)"))
optparser.add_option("--updater", action="store_const", const="updater",
	dest="run", help=_("run the database updater"))
optparser.set_defaults(run="editor") # by default run the editor


# Parse arguments
options, args = optparser.parse_args()

if options.run == "editor":
	iface = editorgui.Interface()
	iface.main_win.show()
	iface.main()
elif options.run == "client":
	iface = clientgui.Interface(options.solitaire)
	iface.main_win.show()
	if not options.solitaire:
		iface.login_win.show()
	try:
		iface.main()
	finally:
		iface.main_win.hide()
		if not options.solitaire:
			iface.network_manager.disconnect()
elif options.run == "updater":
	iface = updatergui.Interface()
	iface.main()
	updatergui.miner.disconnect()
else:
	assert(False) # Should specify either editor, client or updater to run



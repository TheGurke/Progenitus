#!/usr/bin/python
# Written by TheGurke 2011
"""
Deck editor and network client for Wizard of the Coast's Magic the Gathering
trading card game

This is the startup script. It parses command line arguments and initializes the
interfaces.
"""


import os
import optparse
from gettext import gettext as _
import logging

# Import everything explicitly
from progenitus import async, config, settings, lang, uiloader
from progenitus.client import desktop, muc, network, players
from progenitus.db import cards, pics, semantics
from progenitus.editor import decks
from progenitus.miner import magiccardsinfo, miner, tcgplayercom
from progenitus.client import gui as clientgui
from progenitus.editor import gui as editorgui
from progenitus.updater import gui as updatergui

import glib
import gio
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
optparser.add_option("--log", action="store", dest="log_level",
	default="WARNING",
	help=_("Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"))
optparser.add_option("--logfile", action="store", dest="logfile",
	default=config.LOG_FILE, help=_("External file to write the log to"))
optparser.add_option("--settings", action="store", dest="settings_file",
	default=config.SETTINGS_FILE, help=_("Settings file"))
optparser.set_defaults(run="editor") # by default run the editor


# Parse arguments
options, args = optparser.parse_args()

# Load the settings file
config.SETTINGS_FILE = options.settings_file
settings.load()


# Initialize the logger
level = getattr(logging, options.log_level.upper(), None)
warn_about_invalid_level = False
if not isinstance(level, int):
	level = logging.DEBUG
	warn_about_invalid_level = True
logging.basicConfig(
	filename=options.logfile,
	level=level,
	format="%(asctime)s %(levelname)s: %(message)s",
	datefmt='%Y-%m-%d %H:%M:%S'
)
if hasattr(logging, "captureWarnings"):
	logging.captureWarnings(True)
if warn_about_invalid_level:
	logging.warning("'%s' is not a valid logging level.", options.log_level)

# Run the program
if options.run == "editor":
	iface = editorgui.Interface()
	iface.main()
elif options.run == "client":
	iface = clientgui.Interface(options.solitaire)
	try:
		iface.main()
	finally:
		iface.main_win.hide()
		iface.logout()
elif options.run == "updater":
	iface = updatergui.Interface()
	iface.main()
else:
	assert(False) # Should specify either editor, client or updater to run


# Disable the logger
logging.shutdown()




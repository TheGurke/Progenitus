# Written by TheGurke 2011
"""Provides access to the user changed program parameters"""

import ConfigParser
import sys
import os

import config

#
# The _settings list defines all settings. These are loaded from/saved to a file
# by the module and are accessible as a global variable (in the module
# settings).
# The settings file is stored at config.SETTINGS_FILE.
#
# Note: variable names must be unique.
#


_settings = [
	# section, variable name, type, default value, description
	("DEFAULT", "cache_dir", "dir", "/var/cache/progenitus" if
		os.path.exists("/var/cache/progenitus") else "cache/",
		"Path to picture cache folder"),
	("DEFAULT", "deck_dir", "dir",
		"$HOME/Progenitus decks" if os.name == 'posix' else "decks",
		"Path to deck folder"),
	("DEFAULT", "save_ram", "bool", False,
		"The program should reduce memory footprint even at the cost of speed "
		"or features"),
	("Updater", "disclaimer_agreed", "bool", False,
		"The user has agreed to the disclaimer"),
	("Updater", "list_url", "str",
		"https://raw.github.com/TheGurke/Progenitus/master/downloadlist.txt",
		"URL to the set download list"),
	("Editor", "results_limit", "int", 500, "Maximum number of search results"),
	("Editor", "decksave_timeout", "int", 10000,
		"The deck is saved automatically in this interval (milliseconds)"),
	("Editor", "decklist_refreshtime", "int", 60000, "The decklist is " + 		"refreshed automatically in this interval (milliseconds)"),
	("Client", "username", "str", "", "Jabber login username"),
	("Client", "userpwd", "str", "", "Jabber login password"),
	("Client", "server", "str", "", "Jabber server"),
	("Client", "gamename", "str", "", "Last joined game's name"),
	("Client", "gamepwd", "str", "", "Last game's password")
]


# Parse settings assertions
for section, var, t, default, desc in _settings:
	assert(var not in ("_settings", "_defaults", "load", "save"))
_defaults = dict([(var, str(default)) for section, var, t, default, desc in
	_settings])


def load():
	"""Load the settings from disk"""
	cparser = ConfigParser.SafeConfigParser(_defaults)
	cparser.read(os.path.expandvars(config.SETTINGS_FILE))
	for section, var, t, default, desc in _settings:
		if section != "DEFAULT" and not cparser.has_section(section):
			cparser.add_section(section)
		value = cparser.get(section, var)
		# type casting
		if t == "bool":
			value = value.lower() == "true"
		elif t == "int":
			value = int(value)
		elif t == "file" or t == "dir":
			value = os.path.expandvars(value)
		
		# Check for path existance
		if t == "file":
			if not os.path.exists(value) or not os.path.isfile(value):
				print("File not found: %s" % value)
		elif t == "dir":
			if not os.path.exists(value) or not os.path.isdir(value):
				print("Directory not found: %s" % value)
		setattr(sys.modules[__name__], var, value)


def save():
	"""Write the settings to disk"""
	cparser = ConfigParser.SafeConfigParser()
	for section, var, t, default, desc in _settings:
		if section != "DEFAULT" and not cparser.has_section(section):
			cparser.add_section(section)
		if hasattr(sys.modules[__name__], var):
			value = getattr(sys.modules[__name__], var)
			if value != default: # only save non-default values
				cparser.set(section, var, str(value))
	
	# save to disk
	with open(os.path.expandvars(config.SETTINGS_FILE), 'wt') as f:
		cparser.write(f)


# Initially load the settings
load()



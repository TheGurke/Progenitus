# Written by TheGurke 2011
"""Contains various program parameters that will not be changed by the user"""



import os


# Program name
APP_NAME = "Progenitus"
APP_NAME_EDITOR = APP_NAME + " Editor"
APP_NAME_CLIENT = APP_NAME + " Client"

# Program version
VERSION = "0.40-beta"

# Program website
APP_WEBSITE = "http://progenitus.org/"

# Path to the settings file
if os.name == 'posix':
	SETTINGS_FILE = "$HOME/.progenitus.cfg"
else:
	SETTINGS_FILE = "settings.ini"

# Path to the log file
LOG_FILE = None

# Path to the translation directory
TRANSLATIONS_PATH = "po"

# Gettext domain
GETTEXT_DOMAIN = APP_NAME

# Path to the GTKBuilder files
GTKBUILDER_CLIENT = "client.ui"
GTKBUILDER_DECKEDITOR = "editor.ui"
GTKBUILDER_UPDATER = "updater.ui"

# Path structure in the picture directory
def CARD_PICS_PATH(cid):
	setname = cid.split(".")[0]
	if os.name == 'nt' and setname is ("con", "prn", "aux", "nul"):
		# On windows, there is a number of illegal file 
		setname += "_"  # BEWARE: DIRTY HACK!
	return("cards/%s/%s.jpg" % (setname, cid))
TOKEN_PICS_PATH = lambda tid: ("tokens/%s.jpg" % tid)
DB_FILE = "mtg.sqlite"
DECKMASTER_PATH = "media/deckmaster.png"
DEFAULT_DECKS_PATH = "default decks"

# Suffix for the deck files
DECKFILE_SUFFIX = ".deck"

# Network options
JOIN_DELAY = 1000 # time to wait for tray creation
MAX_ITEMID = 2**16 - 1

# Lobby room name
LOBBY_ROOM = "progenituslobby"

# Default prefix for network games
DEFAULT_GAME_PREFIX = "progenitus-"

# Game specific constants
DEFAULT_LIFE = 20
DEFAULT_HANDCARDS = 7
MIN_LIBRARY = 60




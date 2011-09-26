# Written by TheGurke 2011
"""Contains various program parameters that will not be changed by the user"""

# Program name
APP_NAME = "Progenitus"
APP_NAME_EDITOR = APP_NAME + " Editor"
APP_NAME_CLIENT = APP_NAME + " Client"

# Program version
VERSION = "0.30-beta"

# Program website
APP_WEBSITE = "http://progenitus.org/"

# Path to the settings file
SETTINGS_FILE = "$HOME/.progenitus.cfg"

# Path to the translation directory
TRANSLATIONS_PATH = "po"

# Gettext domain
GETTEXT_DOMAIN = APP_NAME

# Path to the GTKBuilder files
GTKBUILDER_CLIENT = "client.glade"
GTKBUILDER_DECKEDITOR = "deckeditor.glade"
GTKBUILDER_UPDATER = "updater.glade"

# Path structure in the picture directory
CARD_PICS_PATH = lambda cid: ("cards/%s/%s.jpg" % (cid.split(".")[0], cid))
TOKEN_PICS_PATH = lambda tid: ("tokens/%s.jpg" % tid)
DECKMASTER_PATH = "media/deckmaster.png"

# Network options
JOIN_DELAY = 1000 # time to wait for tray creation
MAX_ITEMID = 2**16 - 1

# Default card dimensions
CARD_WIDTH = 312
CARD_HEIGHT = 445

# Default prefix for network games
DEFAULT_GAME_PREFIX = "progenitus-"

# Game specific constants
DEFAULT_LIFE = 20
DEFAULT_HANDCARDS = 7
MIN_LIBRARY = 60




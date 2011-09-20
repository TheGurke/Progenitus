# Written by TheGurke 2011
"""Initialize gettext"""


import config
import gettext

gettext.bindtextdomain(config.GETTEXT_DOMAIN, config.TRANSLATIONS_PATH)
gettext.textdomain(config.GETTEXT_DOMAIN)




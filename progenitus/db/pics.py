# Written by TheGurke 2011
"""Manage access to the cached card pictures"""

import math
import os.path
import datetime
from gettext import gettext as _
import logging

import gtk.gdk
import cairo

from progenitus import config
from progenitus import settings
import cards

#
# Given a card id it returns the corresponding picture as a gdk.Pixbuf
#


_map = dict() # data structure to hold the pics


def _get_path(cardid):
	"""Returns the file path for the card picture"""
	if cardid == "deckmaster":
		return config.DECKMASTER_PATH
	if cards.is_token(cardid):
		return os.path.join(settings.cache_dir, config.TOKEN_PICS_PATH(cardid))
	else:
		return os.path.join(settings.cache_dir, config.CARD_PICS_PATH(cardid))


def _load(cardid):
	"""Load a card picture from the disk"""
	filename = _get_path(cardid)
	if not os.path.isfile(filename):
		if cards.is_token(cardid):
			logging.error(_("Picture for token %s not found."), cardid)
		else:
			logging.error(_("Picture for card %s not found."), cardid)
	pixbuf = gtk.gdk.pixbuf_new_from_file(filename).add_alpha(False, 0, 0, 0)
	global _map
	if not settings.save_ram:
		_map[cardid] = pixbuf
	return pixbuf



def get(cardid):
	"""Get the pixmap for a card or token"""
	global _map
	if cardid not in _map:
		return _load(cardid)
	return _map[cardid]



class PicFactory(object):
	"""Data structure managing scaled images"""
	
	def __init__(self):
		self._map = dict()
	
	def _update(self, cardid, width):
		"""Update the entry at cardid"""
		pixbuf = get(cardid)
		width = math.ceil(width)
		zoom = width * (1. / pixbuf.get_width())
		surface, w, h = surface_from_pixbuf(pixbuf, zoom)
		#assert(w == int(width)) # might fail due to flop errors
		self._map[cardid] = surface, int(width), datetime.datetime.now()
	
	def get(self, cardid, width):
		"""Get the scaled cairo surface for a card"""
		if cardid not in self._map:
			self._update(cardid, width)
		surface, w, creation_time = self._map[cardid]
		if w != width:
			self._update(cardid, width)
		return self._map[cardid][0]


def surface_from_pixbuf(pixbuf, zoom=1., antialiasing=True):
	"""Create a (scaled) cairo surface from an gdk pixbuffer"""
	w = pixbuf.get_width()
	h = pixbuf.get_height()
	w_, h_ = int(math.ceil(zoom * w)), int(math.ceil(zoom * h))
	surface = cairo.ImageSurface(0, w_, h_)
	cr = gtk.gdk.CairoContext(cairo.Context(surface))
	if antialiasing:
		cr.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
	if zoom != 1:
		cr.scale(zoom, zoom)
	cr.set_source_pixbuf(pixbuf, 0, 0)
	cr.paint()
	return surface, w_, h_




# Written by TheGurke 2011
"""Manage access to the picture files"""

import math
import os.path
import gtk.gdk
import cairo

from progenitus import config
from progenitus import settings

#
# Handles card picture access. Given a card id it returns the corresponding
# picture as a gdk.Pixbuf.
# 0  = deckmaster
# -1 = empty card
#

_map = dict() # data structure to hold the pics


def _get_path(cardid):
	"""The the file path for the card picture"""
	assert(isinstance(cardid, int))
	if cardid == 0: # Deckmaster has id 0
		return config.DECKMASTER_PATH
	if cardid == -1: # Empty card has id -1
		return config.EMPTY_CARD_PATH
	idstr = str(cardid).rjust(9, "0")
	return os.path.join(settings.pics_path, config.PICS_PATH(idstr))


def _load(cardid):
	"""Load a magic card picture from the disk"""
	assert(isinstance(cardid, int))
	filename = _get_path(cardid)
	if not os.path.isfile(filename):
		print("Picture for card #%d not found." % cardid)
	pixbuf = gtk.gdk.pixbuf_new_from_file(filename).add_alpha(False, 0, 0, 0)
	global _map
	_map[cardid] = pixbuf
	return pixbuf


def get(cardid):
	"""Get the pixmap for a card"""
	assert(isinstance(cardid, int))
	global _map
	if cardid not in _map:
		_load(cardid)
	return _map[cardid]


class PicFactory(object):
	"""A data structure managing the image data"""
	
	_map = dict()
	_zoom = 0
	
	def __init__(self, zoom):
		assert(zoom > 0)
		self._zoom = zoom
	
	def get(self, cardid, zoom):
		"""Get the scaled cairo surface for a card"""
		if zoom == self._zoom and cardid in self._map:
			return self._map[cardid]
		if zoom != self._zoom:
			# clear database
			self._zoom = zoom
			self._map = dict()
		surface = surface_from_pixbuf(get(cardid), zoom)[0]
		self._map[cardid] = surface
		return surface


def surface_from_pixbuf(pixbuf, zoom=1., antialiasing=True):
	"""Create a (scaled) cairo surface from an gdk pixbuffer"""
	w = pixbuf.get_width()
	h = pixbuf.get_height()
	w_, h_ = int(math.ceil(w / zoom)), int(math.ceil(h / zoom))
	surface = cairo.ImageSurface(0, w_, h_)
	cr = gtk.gdk.CairoContext(cairo.Context(surface))
	if antialiasing:
		cr.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
	cr.scale(1. / zoom, 1. / zoom)
	cr.set_source_pixbuf(pixbuf, 0, 0)
	cr.paint()
	return surface, w_, h_




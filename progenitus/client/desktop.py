# Written by TheGurke 2011
"""Vector graphics engine for the card table as a gtk.Widget"""

import math
import random

from gettext import gettext as _
import cairo
import gtk

from progenitus import config
from progenitus.db import cards
from progenitus.db import pics



class DragNDrop(object):
	"""An object to save drag and drop information"""
	
	def __init__(self, item, start_x, start_y):
		assert(isinstance(item, Item))
		self.item = item
		self.start_x = start_x
		self.start_y = start_y
		self.item_x = item.x # the item's x and y coordinates at the time the
		self.item_y = item.y # dragging started
		self.set_hand_index(start_x, start_y)
		desktop = self.item.widget
		if desktop.is_over_hand(start_x, start_y):
			self.initial_hand_index = desktop.get_hand_card_index(start_x,
				start_y)
			# There is a difference to set_hand_index!
		else:
			self.initial_hand_index = None
	
	def set_hand_index(self, x ,y):
		"""Set the current hand index of hovering over the hand area"""
		desktop = self.item.widget
		if desktop.is_over_hand(x, y):
			self.hand_index = desktop.get_hand_index(x, y)
		else:
			self.hand_index = None
	
	def update_pos(self, x, y):
		"""Update the item's position"""
		dx = x - self.start_x
		dy = y - self.start_y
		self.item.x = dx * self.item.widget.zoom + self.item_x
		self.item.y = dy * self.item.widget.zoom + self.item_y
		self.set_hand_index(x, y)


class CairoDesktop(gtk.DrawingArea):
	"""A Widget for drawing on using cairo"""
	
	__gsignals__ = {"expose-event": "override"}
	
	enlarged_card = None
	enlarged_card_last_pos = None # Last x, y position of the enlarged card
	bg_color = 1, 1, 1
	zoom = 5.7 # initial zoom factor
	# position is always centered around (0,0)
	flip_y = False
	
	_items = [] # Cards and other stuff
	_dragndrop = None
	
	# Callbacks to be filled
	movement_callback = None
	hover_callback = None
	prop_callback = None
	
	# Initialize
	
	def __init__(self, interface, eventbox=None):
		super(self.__class__, self).__init__()
		self.picfactory = pics.PicFactory(self.zoom)
		if eventbox is not None:
			self.setup_eventbox(eventbox)
		self.show() # Visible by default
		self.interface = interface
	
	def setup_eventbox(self, eventbox):
		"""Configure and eventbox so it sends events to this widget"""
		assert(isinstance(eventbox, gtk.Widget))
		eventbox.connect("button-press-event", self.mouse_down)
		eventbox.connect("button-release-event", self.mouse_up)
		eventbox.connect("motion-notify-event", self.mouse_motion)
		eventbox.connect("scroll-event", self.mouse_scroll)
		eventbox.set_events(eventbox.get_events() | gtk.gdk.POINTER_MOTION_MASK)
	
	def do_expose_event(self, event):
		# Handle the expose-event by painting
		cr = self.window.cairo_create()
		a = event.area
		cr.rectangle(a.x, a.y, a.width, a.height)
		cr.clip()
		self.paint(cr)
	
	# Coordinates
	
	def get_screen_coords(self):
		"""Get the screen coordinates of this widget"""
		w, h = self.window.get_size()
		return 0, 0, w, h - self.get_hand_height()
	
	def get_wh(self):
		"""Return the size (w, h) of the currently visible playing area"""
		w, h = self.window.get_size()
		return w * self.zoom, (h - self.get_hand_height()) * self.zoom
	
	def get_hand_height(self):
		"""Get the height of the bottom area reserved for the cards in hand"""
		return int(1.2 * config.CARD_HEIGHT / self.zoom)
	
	# Item container
	
	def add_item(self, item, position_hint=None):
		assert(isinstance(item, Item))
		if self._items.count(item) < 1:
			if position_hint is None:
				self._items.append(item)
			else:
				self._items.insert(position_hint, item)
			item.parent = self
			item.widget = self
			if item.visible:
				item.repaint()
			if isinstance(item, Container):
				for item_ in item:
					item_.widget = self
	
	def remove_item(self, item):
		if self._items.count(item) > 0:
			self._items.remove(item)
			item.repaint()
			item.parent = None
			item.widget = None
	
	def get_item_at(self, x, y):
		"""Find an item by its screen coordinates"""
		items_reversed = self._items[:]
		items_reversed.reverse()
		for item in items_reversed:
			if item.match_pixel(x, y):
				while hasattr(item, "get_item_at"):
					item_ = item.get_item_at(x, y)
					if item_ is None:
						return item
					else:
						item = item_
				return item
		return None
	
	# Hand
	
	def get_hand(self):
		"""Get the hand card list"""
		if self.interface.my_player is None:
			return []
		hand = self.interface.my_player.hand[:]
		# If dragging apply dragging information
		if (self._dragndrop is not None
				and isinstance(self._dragndrop.item, CardItem)):
			if self._dragndrop.initial_hand_index is not None:
				i = self._dragndrop.initial_hand_index
				hand = hand[:i] + hand[i+1:]
			if self._dragndrop.hand_index is not None:
				hand.insert(self._dragndrop.hand_index,
					self._dragndrop.item.card)
		return hand
	
	def get_hand_index(self, x, y):
		"""Get the list index where the position suggests insertion"""
		# Note the difference to get_hand_card_index
		hand = self.get_hand()
		w, h = self.get_wh()
		cw = int(config.CARD_WIDTH / self.zoom)
		x = x - w / self.zoom / 2 + int(1.1 * cw) * (len(hand) + 1) / 2
		i = int(x) / int(1.1 * cw)
		if i < 0:
			i = 0
		if i > len(hand):
			i = len(hand)
		return i
	
	def is_over_hand(self, x, y):
		"""Determine whether an pointer position is over the hand area"""
		return y > self.get_screen_coords()[3]
	
	def get_hand_card_index(self, x, y):
		# Note the difference to get_hand_index
		"""Get a card in the hand by its x and y-coordinate"""
		hand = self.get_hand()
		if hand is None:
			return
		w, h = self.get_wh()
		if y < h / self.zoom or y > h / self.zoom + self.get_hand_height():
			return None
		cw = int(config.CARD_WIDTH / self.zoom)
		x = x - w / self.zoom / 2 + int(1.1 * cw) * len(hand) / 2
		if x % int(1.1 * cw) > cw:
			return None
		i = int(x) / int(1.1 * cw)
		if 0 <= i < len(hand):
			return i
		return None
	
	def get_hand_card(self, x, y):
		"""If there is a hand card at (x, y) then return the card, else None"""
		hand = self.get_hand()
		i = self.get_hand_card_index(x, y)
		if i is None:
			return None
		return hand[i]
	
	def repaint_hand(self):
		w, h = self.window.get_size()
		hh = self.get_hand_height()
		self.queue_draw_area(0, h - hh, w, hh)
	
	def _paint_hand(self, cr, width, height):
		hand = self.get_hand()
		if hand is None:
			return
		w = int(config.CARD_WIDTH / self.zoom)
		h = int(config.CARD_HEIGHT / self.zoom)
		x = width / 2 - int(1.1 * w) * len(hand) / 2
		y = height - int(1.1 * h)
		
		# Divider line
		cr.save()
		cr.set_line_width(1)
		cr.set_source_rgb(0.5, 0.5, 0.5)
		cr.move_to(int(0.1 * width), y - int(0.05 * h))
		cr.line_to(int(0.9 * width), y - int(0.05 * h))
		cr.stroke()
		cr.restore()
		
		for card in hand:
			cr.save()
			cr.rectangle(x, y, w, h)
			cr.translate(x, y)
			cr.clip()
			surface = self.picfactory.get(card.cardid, self.zoom)
			assert isinstance(surface, cairo.Surface)
			cr.set_source_surface(surface)
			cr.paint()
			cr.restore()
			x += int(1.1 * w)
	
	
	# Enlarged card
	
	def _get_enlarged_card_pos(self):
		"""Get the x, y coordinates of the enlarged card"""
		px, py, mask = self.get_parent_window().get_pointer()
		_x, _y, w, h, bd = self.get_parent_window().get_geometry()
		# Display card on the left or on the right?
		x = w - self.enlarged_card.get_width() if px < w / 2 else 0
		y = int((h - self.enlarged_card.get_height()) / 2)
		return x, y
	
	def repaint_enlarged_card(self):
		"""Repaint the area where the enlarged card is"""
		if self.enlarged_card_last_pos is not None:
			x, y = self.enlarged_card_last_pos
			w = self.enlarged_card.get_width()
			h = self.enlarged_card.get_height()
			self.queue_draw_area(x, y, w, h)
	
	def show_enlarged_card(self, cardid=None):
		"""Show the large version of a card"""
		if cardid is None:
			if self.enlarged_card is not None:
				self.repaint_enlarged_card()
				self.enlarged_card = None
				self.enlarged_card_last_pos = None
		else:
			self.repaint_enlarged_card()
			self.enlarged_card = pics.surface_from_pixbuf(pics.get(cardid))[0]
			self.enlarged_card_last_pos = self._get_enlarged_card_pos()
			self.repaint_enlarged_card()
	
	def _paint_enlarged_card(self, cr, width, height):
		if self.enlarged_card is not None:
			cr.translate(*self._get_enlarged_card_pos())
			cr.set_source_surface(self.enlarged_card)
			cr.paint()
	
	
	# Painting
	
	def repaint(self):
		self.queue_draw()
	
	def paint(self, cr):
		"""Use Cairo to paint the widget"""
		assert isinstance(cr, cairo.Context)
		width, height = self.window.get_size()
		
		# Background fill
		cr.set_source_rgb(*self.bg_color)
		cr.rectangle(0, 0, width, height)
		cr.fill()
		
		# Set viewport
		height_ = height - self.get_hand_height()
		cr.save()
		cr.rectangle(0, 0, width, height_)
		cr.clip()
		
		# Paint items
		for item in self._items:
			if item.visible:
				cr.save()
				cr.rectangle(*item.get_screen_coords())
				cr.clip()
				cr.translate(*item.get_screen_coords()[:2])
				item.paint(self, cr)
				cr.restore()
		cr.restore()
		
		# Paint hand and enlarged cards
		self._paint_hand(cr, width, height)
		self._paint_enlarged_card(cr, width, height_)
	
	
	# Mouse input
	
	def mouse_down(self, widget, event):
		item = self.get_item_at(event.x, event.y)
		handcard = self.get_hand_card(event.x, event.y)
		if item is not None and item.mine:
			if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
				item.double_click(event)
			elif event.button == 1 and item.dragable:
				# Start dragging
				self._dragndrop = DragNDrop(item, event.x, event.y)
				self._dragndrop.started = self.interface.my_player.battlefield
				# Raise the item to be on top of all others
				self.remove_item(item)
				self.add_item(item)
				self.show_enlarged_card(None)
		elif handcard is not None:
			if event.button == 1:
				# Create new card item
				width, height = self.window.get_size()
				item = CardItem(handcard, self.interface.my_player, True)
				item.x = ((event.x - width / 2) * self.zoom -
					config.CARD_WIDTH / 2)
				item.y = (event.y - height / 2) * self.zoom
				item.visible = False
				self.add_item(item)
				item.clamp_coords()
				# Start dragging
				self._dragndrop = DragNDrop(item, event.x, event.y)
				self._dragndrop.started = self.interface.my_player.hand
				assert(self._dragndrop.initial_hand_index is not None)
				self.show_enlarged_card(None)
		elif (item is None and event.button == 1
				and event.type == gtk.gdk._2BUTTON_PRESS):
			# Double click on the desktop
			self.interface.untap_all()
		if event.button == 3 and self.prop_callback is not None:
			self.show_enlarged_card(None)
			self.prop_callback(item if item is not None else handcard, event)
	
	def mouse_up(self, widget, event):
		if event.button == 1 and self._dragndrop is not None:
			item = self._dragndrop.item
			# If the dragged distance was 0, do nothing
			if (event.x == self._dragndrop.start_x
					and event.y == self._dragndrop.start_y):
				self._dragndrop = None
				return
			
			# Stop dragging
			if isinstance(item, CardItem) or isinstance(item, Tray):
				player = self.interface.my_player
				started = self._dragndrop.started
				finished = (player.hand if self.is_over_hand(event.x, event.y)
					else player.battlefield)
				if started is not player.battlefield:
					self.remove_item(item)
					item_ = item.card
				else:
					item_ = item
				if started is player.hand and finished is player.hand:
					# Moved within the hand
					ii = self._dragndrop.initial_hand_index
					i  = self._dragndrop.hand_index
					player.hand[ii:ii+1] = []
					player.hand.insert(i, item.card)
				elif finished is player.battlefield:
					player.move_card(item_, started, finished, item.x, item.y)
				else:
					player.move_card(item_, self._dragndrop.started, finished)
			self._dragndrop = None
	
	def mouse_motion(self, widget, event):
		hand = self.get_hand()
		if self._dragndrop is not None: # Dragging something
			item = self._dragndrop.item
			item.repaint()
			
			# Update movement coordinates
			i = self._dragndrop.hand_index
			self._dragndrop.update_pos(event.x, event.y)
			if isinstance(item, CardItem):
				# Card items can be moved to the hand
				item.visible = not self.is_over_hand(event.x, event.y)
			if i is not self._dragndrop.hand_index:
				self.repaint_hand()
			item.clamp_coords()
			item.repaint()
			
			# Update drag status
			self._dragndrop.last_x = event.x
			self._dragndrop.last_y = event.y
		else: # Not dragging
			item = self.get_item_at(event.x, event.y)
			handcard = self.get_hand_card(event.x, event.y)
			if handcard is not None:
				self.show_enlarged_card(handcard.cardid)
				if self.hover_callback is not None:
					self.hover_callback(handcard)
			elif (item is not None and item.visible
				and isinstance(item, CardItem) and (item.mine or item.face)):
				self.show_enlarged_card(item.cardid)
			else:
				self.show_enlarged_card(None)
			if item is not None and self.hover_callback is not None:
				self.hover_callback(item)
	
	def mouse_scroll(self, widget, event):
		pass
#		if event.direction == gtk.gdk.SCROLL_UP:
#			self.zoom /= 1.2
#			self.repaint()
#		if event.direction == gtk.gdk.SCROLL_DOWN:
#			self.zoom *= 1.2
#			self.repaint()


#
# Item
#

class Item(object):
	"""Abstract class for everything that will be painted by CairoDesktop"""
	
	x, y, w, h = 0, 0, 0, 0 # dimensions
	itemid = None
	dragable = False
	mine = False
	parent = None # the immediate parent item
	widget = None # The CairoDesktop widget this item is associated with
	network_sync = True
	visible = True
	
	def __eq__(self, other):
		if self.itemid is not None:
			return self.itemid == other.itemid
		else:
			return self is other
	
	def get_wh(self):
		return self.w, self.h
	
	def paint(self, desktop, cr):
		"""Paint on the cairo context"""
		pass
	
	def show_tooltip(self):
		pass
	
	def double_click(self, event):
		pass
	
	def match_pixel(self, x, y):
		"""Is this pixel part of this item?"""
		coords = self.get_screen_coords()
		if x < coords[0] or x >= coords[0] + coords[2]:
			return False
		if y < coords[1] or y >= coords[1] + coords[3]:
			return False
		return True
	
	def get_screen_coords(self):
		"""Get the on-screen-coordinates of this item"""
		x, y, w, h = self.parent.get_screen_coords()
		ix = int(math.floor(self.x / self.widget.zoom + w / 2))
		iy = int(math.floor(self.y / self.widget.zoom + h / 2))
		iw = int(self.w / self.widget.zoom) + 2
		ih = int(self.h / self.widget.zoom) + 2
		return ix, iy, iw, ih
	
	def clamp_coords(self):
		"""Make sure that this card never leaves the playing area"""
		w, h = self.parent.get_wh()
		self.x = self.x if self.x >= -(w + self.w) / 2 else -(w + self.w) / 2
		self.y = self.y if self.y >= -(h + self.h) / 2 else -(h + self.h) / 2
		self.x = self.x if self.x <= (w - self.w) / 2 else (w - self.w) / 2
		self.y = self.y if self.y <= (h - self.h) / 2 else (h - self.h) / 2
	
	def repaint(self):
		"""Queue a repaint of this item"""
		self.widget.queue_draw_area(*self.get_screen_coords())


class Container(Item):
	"""A Container holds a multitude of items and passes paint and other events
	on to them"""
	
	background = 1, 1, 1
	
	def __init__(self):
		self._items = []
	
	def add(self, item):
		"""Add an item to this container"""
		self._items.append(item)
		item.parent = self
		item.widget = self.widget
	
	def remove(self, item):
		"""Remove an item from this container"""
		self._items.remove(item)
		item.parent = None
		item.widget = None
	
	def paint(self, desktop, cr):
		w = int(self.w / desktop.zoom)
		h = int(self.h / desktop.zoom)
		
		# Background fill
		cr.set_source_rgb(*self.bg_color)
		cr.rectangle(0, 0, w, h)
		cr.fill()
		
		# Paint items
		for item in self._items:
			if item.visible:
				cr.save()
				cr.rectangle(*item.get_screen_coords())
				cr.clip()
				cr.translate(*item.get_screen_coords()[:2])
				item.paint(desktop, cr)
				cr.restore()
	
	def get_item_at(self, x, y):
		"""Get an item at a point on the screen"""
		dx, dy, dw, dh  = self.get_screen_coords()
		x -= dx
		y -= dy
		for item in self._items:
			if item.match_pixel(x, y):
				return item
		return None
	
	def show_tooltip(self, x, y):
		dx, dy, dw, dh  = self.get_screen_coords()
		x -= dx
		y -= dy
		item = self.get_item_at(self, x, y)
		if item is None:
			self.show_own_tooltip(x, y)
		else:
			item.show_tooltip(x, y)
	
	def show_own_tooltip(self, x, y):
		pass
	
	def double_click(self, event):
		dx, dy, dw, dh  = self.get_screen_coords()
		x = event.x - dx
		y = event.y - dy
		item = self.get_item_at(x, y)
		if item is not None:
			item.double_click(event)
	
	# Emulate container type
	
	def __len__(self):
		return len(self._items)
	
	def __contains__(self, item):
		return item in self._items
	
	def __iter__(self):
		return self._items.__iter__()


class TextItem(Item):
	
	color = 0, 0, 0
	font_face = "sans-serif"
	fontsize = 0
	update = None
	
	def __init__(self, text=""):
		self.text = text
	
	def get_wh(self):
		"""Get the expected width of the text"""
		surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 0, 0)
		cr = cairo.Context(surface)
		cr.select_font_face(self.font_face)
		cr.set_font_size(self.fontsize / self.widget.zoom)
		xb, yb, w, h, xa, ya = cr.text_extents(self.text)
		return w * self.widget.zoom + 2, h * self.widget.zoom + 2
	
	def set_text(self, text):
		"""Update the text and item width"""
		self.text = text
		self.w, self.h = self.get_wh()
	
	def paint(self, desktop, cr):
		if self.update is not None:
			self.update()
		cr.set_source_rgb(*self.color)
		cr.select_font_face(self.font_face)
		cr.set_font_size(self.fontsize / self.widget.zoom)
		cr.move_to(0, self.fontsize / self.widget.zoom)
		cr.show_text(self.text)


#
# CardItem
#

class CardItem(Item):
	"""A magic card or token"""
	
	w = config.CARD_WIDTH
	h = config.CARD_HEIGHT
	
	tapped = False
	flipped = False
	face = True # True is face up
	does_not_untap = False
	token = False # Is this card only a token / copy?
	
	border_color = None
	dragable = True
	
	def __init__(self, card, owner, mine=False):
		self.card = card
		self.cardid = card.cardid
		self.owner = owner
		self.controller = owner
		self.mine = mine
		
		# Check if the card does not untap by default
		if self.card.text.find("doesn't untap during your untap step.") >= 0:
			self.does_not_untap = True
	
	def paint(self, desktop, cr):
		surface = desktop.picfactory.get(self.cardid if self.face else 0,
			desktop.zoom)
		assert(isinstance(surface, cairo.Surface))
		
		# rotate image
		phi = math.pi / 2 if self.tapped else 0
		phi += math.pi if self.flipped else 0
		if self.tapped:
			cr.translate(surface.get_height() / 2, surface.get_width() / 2)
		else:
			cr.translate(surface.get_width() / 2, surface.get_height() / 2)
		cr.rotate(phi)
		cr.translate(-surface.get_width() / 2, -surface.get_height() / 2)
		cr.set_source_surface(surface)
		cr.paint()
	
	def get_description(self):
		"""Get a one line description of this card item"""
		text = self.card.name if self.mine or self.face else _("face down card")
		if self.token:
			text += " (clone)"
		if not self.mine:
			text = _("{0}'s {1}").format(self.controller.name, text)
		return text
	
	def double_click(self, event):
		self.toggle_tapped()
	
	def toggle_tapped(self):
		self.set_tapped(not self.tapped)
	
	def set_tapped(self, tapped):
		"""Set the tapped status of this card"""
		assert(isinstance(tapped, bool))
		if self.tapped != tapped:
			self.repaint()
			self.w, self.h = self.h, self.w
			self.repaint()
			self.tapped = tapped
			if self.mine:
				self.widget.interface.network_manager.send_commands([
					("tap", (self.itemid,))
				])
	
	def toggle_flipped(self):
		self.set_flipped(not self.flipped)
	
	def set_flipped(self, flipped):
		"""Set the flipped status of this card"""
		assert(isinstance(flipped, bool))
		if self.flipped != flipped:
			self.repaint()
			self.flipped = flipped
			if self.mine:
				self.widget.interface.network_manager.send_commands([
					("flip", (self.itemid,))
				])
	
	def turn_over(self):
		self.set_face(not self.face)
	
	def set_face(self, face=True):
		"""Set the direction the card is facing: up (True) or down (False)"""
		assert(isinstance(face, bool))
		if self.face != face:
			self.repaint()
			self.face = face
			if self.mine:
				self.widget.interface.network_manager.send_commands([
					("face", (self.itemid,))
				])


#
# Tray
#

class Tray(Container):
	"""The tray is composed of the library, the graveyard, the player name,
	a life counter and a hand card counter (for other players)"""
	
	w = int(config.CARD_WIDTH * 3.4)
	h = int(config.CARD_HEIGHT * 1.4)
	bg_color = 0.9, 0.9, 0.9
	dragable = True
	
	def __init__(self, player, mine=False):
		super(self.__class__, self).__init__()
		self.player = player
		self.mine = mine
		
		# Populate the container
		self.library_item = Library()
		self.library_item.x = int(config.CARD_WIDTH * 0.05)
		self.library_item.y = -int(config.CARD_HEIGHT * 0.35)
		self.add(self.library_item)
		self.graveyard_item = Graveyard()
		self.graveyard_item.x = -int(config.CARD_WIDTH * 1.05)
		self.graveyard_item.y = -int(config.CARD_HEIGHT * 0.35)
		self.add(self.graveyard_item)
		self.name_item = TextItem()
		self.name_item.x = -self.w / 2
		self.name_item.y = -self.h / 2
		self.name_item.fontsize = config.CARD_HEIGHT * 0.2
		self.name_item.update = \
			lambda: self.name_item.set_text(self.player.user.nick)
		self.add(self.name_item)
		self.life_item = TextItem()
		self.life_item.color = 0.5, 0, 0
		self.life_item.x = config.CARD_WIDTH * 1.1
		self.life_item.y = self.name_item.y
		self.life_item.fontsize = config.CARD_HEIGHT * 0.14
		self.life_item.update = \
			lambda: self.life_item.set_text(str(self.player.life))
		self.add(self.life_item)
		self.card_count_item = TextItem()
		self.card_count_item.color = 0.5, 0.5, 0
		self.card_count_item.x = config.CARD_WIDTH * 1.5
		self.card_count_item.y = self.name_item.y
		self.card_count_item.fontsize = config.CARD_HEIGHT * 0.14
		self.card_count_item.update = \
			lambda: self.card_count_item.set_text(str(len(self.player.hand)))
		self.add(self.card_count_item)
		for item in self:
			item.mine = self.mine


class Library(Item):
	
	w = config.CARD_WIDTH
	h = config.CARD_HEIGHT
	
	def double_click(self, event):
		self.parent.player.draw_card()
	
	def paint(self, desktop, cr):
		if len(self.parent.player.library) > 0:
			surface = desktop.picfactory.get(0, desktop.zoom)
			assert(isinstance(surface, cairo.Surface))
			cr.set_source_surface(surface)
			cr.paint()


class Graveyard(Item):
	
	w = config.CARD_WIDTH
	h = config.CARD_HEIGHT
	
	def paint(self, desktop, cr):
		if len(self.parent.player.graveyard) > 0:
			card = self.parent.player.graveyard[-1]
			surface = desktop.picfactory.get(card.cardid, desktop.zoom)
			assert(isinstance(surface, cairo.Surface))
			cr.set_source_surface(surface)
			cr.paint()




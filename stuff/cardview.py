# Written by TheGurke 2011
"""Draw a visual card list using cairo"""

import gtk
import cairo
import pics

CARD_ASPECT = 0.701123595506
SKEW = 0.3
DEPTH = 0.8

class CardView(gtk.DrawingArea):
	"""A Widget for drawing on using cairo"""	
	
	mouse_x = 100 # last position of the mouse pointer
	selected_card = None
	
	last_width = 0
	last_height = 0
	
	card_change = None # callback when the selected card changed
	
	__gsignals__ = {"expose-event" : "override"}
	
	def __init__(self, cardlist=None):
		super(self.__class__, self).__init__()
		if cardlist is None:
			cardlist = []
		self.cardlist = cardlist
		self.connect("motion-notify-event", self.mouse_move)
		self.set_events(self.get_events() | gtk.gdk.POINTER_MOTION_MASK)
	
	def do_expose_event(self, event):
		# Check if the widget has been resized:
		if (self.last_width, self.last_height) != self.window.get_size():
			self.last_width, self.last_height = self.window.get_size()
			self.refresh_pics()
		# Handle the expose-event by drawing
		cr = self.window.cairo_create()
		a = event.area
		cr.rectangle(a.x, a.y, a.width, a.height)
		cr.clip()
		self.draw(cr, *self.window.get_size())
	
	def mouse_move(self, widget, event):
		if event.type == gtk.gdk.MOTION_NOTIFY:
			self.mouse_x = event.x
			self.queue_draw()
		
	def set_cardlist(self, cardlist):
		self.cardlist = cardlist
		self.refresh_pics()
		self.queue_draw()
	
	def refresh_pics(self):
		self.pics = []
		for card in self.cardlist:
			pixbuf = pics.get(card.cardid)
			new_h = int(self.window.get_size()[1] * (1 - CARD_ASPECT * DEPTH * abs(SKEW)))
			new_w = int(new_h * CARD_ASPECT * DEPTH)
			self.pics.append(pixbuf.scale_simple(new_w, new_h,
				gtk.gdk.INTERP_BILINEAR))
	
	def draw(self, cr, width, height):
		"""Use Cairo to draw the widget"""
		if self.cardlist != []:
			assert(len(self.pics) >= len(self.cardlist))
			cr.save()
			card_h = height * (1 - CARD_ASPECT * DEPTH * abs(SKEW))
			card_w = card_h * CARD_ASPECT
			skew_h = card_w * DEPTH * SKEW
			skewed_card_w = card_w * DEPTH
			d = (float(width) - 2 * skewed_card_w - card_w) / len(self.cardlist)
			if d < 1:
				return # not enough width to draw
			selected = int((self.mouse_x - skewed_card_w - card_w / 2) / d)
			selected = sorted([0, selected, len(self.cardlist) - 1])[1]
			if self.selected_card != self.cardlist[selected] and self.card_change is not None:
				self.card_change(self.cardlist[selected])
			self.selected_card = self.cardlist[selected]
			for i in range(selected):
				cr.save()
				pixbuf = self.pics[i]
				cr.set_matrix(cairo.Matrix(1, SKEW, 0, 1, 0, 0) * cr.get_matrix())
				cr.set_source_pixbuf(pixbuf, 0, 0)
				cr.paint()
				cr.restore()
				cr.translate(d, 0)
			cr.translate(skewed_card_w, 0)
			cr.save()
			cr.translate(d / 2, skew_h)
			pixbuf = pics.get(self.cardlist[selected].cardid)
			new_h = int(card_h)
			new_w = int(new_h * CARD_ASPECT)
			cr.set_source_pixbuf(pixbuf.scale_simple(new_w, new_h,
				gtk.gdk.INTERP_BILINEAR), 0, 0)
			cr.paint()
			cr.restore()
			cr.restore()
			cr.save()
			cr.translate(width - skewed_card_w, skew_h)
			for i in range(len(self.cardlist) - 1, selected, -1):
				cr.save()
				pixbuf = self.pics[i]
				cr.set_matrix(cairo.Matrix(1, -SKEW, 0, 1, 0, 0) * cr.get_matrix())
				cr.set_source_pixbuf(pixbuf, 0, 0)
				cr.paint()
				cr.restore()
				cr.translate(-d, 0)
			cr.restore()
		else:
			self.selected_card = None


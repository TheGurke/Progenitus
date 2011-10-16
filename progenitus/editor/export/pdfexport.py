# Written by TheGurke 2011


import cairo

from progenitus.db import pics

A4 = 595, 842
USLetter = 612, 792
_cardsize = 180, 252

def export(filename, cardlist, papersize=A4):
	surface = cairo.PDFSurface(filename, *papersize)
	cr = cairo.Context(surface)
	for i in range(len(cardlist)):
		card = cardlist[i]
		
		# Get card picture
		pixbuf = pics.get(card.id)
		picsurface, w, h = pics.surface_from_pixbuf(pixbuf)
		
		# Translate and scale
		border_x = (papersize[0] - 3 * _cardsize[0]) / 2
		border_y = (papersize[1] - 3 * _cardsize[1]) / 2
		cr.save()
		cr.translate(border_x + (i % 3) * _cardsize[0],
			border_y + (i % 9 / 3) * _cardsize[1])
		cr.scale(_cardsize[0] / float(w), _cardsize[1] / float(h))
		
		# Draw
		cr.set_source_surface(picsurface)
		cr.paint()
		cr.restore()
		
		if i % 9 == 8:
			cr.show_page() # new page
	surface.finish()




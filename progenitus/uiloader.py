# Written TheGurke 2010
"""Python interface loader using GTKBuilder"""

import os.path
import warnings
import logging


# Import gtk

try:
	import pygtk
	pygtk.require("2.0")
	import gtk
except:
	import sys
	import os
	os.system("zenity --error --text=\"%s\"" %
		_("GTK not found. Check your python installation."))
	logging.critical(_("GTK not availible"))
	sys.exit(1)



#
# This is the Interface which takes care of the GTKBuilder. A program using this
# should derive from this class. For multiple interface files either derive
# multiple classes or call the load-method multiple times.
#
# The signal connector of GTKBuilder is a little messed up, and that's why the
# interface has to connect all signals to itself. Because of this, the callback
# methods must be set on the class before calling "load" and functional
# attributes wont work. So derivation is strongly encuraged.
#

#
# Instructions for using uiloader.py:
# 1. Create a new glade project and design your widgets. Don't forget to set the
#    signal Object->on_destroy = quit on your main window, otherwise the script
#    will continue indefinetely once all windows have been closed.
# 2. Create a new python file, import interface and derive the class Interface.
#    You may call load("myinterface.glade") in the constructor. Remember to call
#    the superclass constructor, though
# 3. Define callback methods in your class. They need to have a unique name
#    different from "load", "show_dialog", "main" and "quit", and must not be a
#    widget name.
# 4. Call main()
#



class Interface(object):
	"""Interface loader class. Should derive from this."""
	
	def __init__(self):
		self._builder = gtk.Builder()
	
	def load(self, filename):
		"""Load a Glade or GTKBuilder file"""
		
		# Check for file
		assert isinstance(filename, str)
		if not os.path.exists(filename) or not os.path.isfile(filename):
			raise RuntimeError("Interface file \"" + filename + "\" not found.")
			_check_filename(filename)
		
		# Load interface
		assert isinstance(self._builder, gtk.Builder)
		try:
			self._builder.add_from_file(filename) 
		except Exception as e:
			raise RuntimeError("Failed to load interface file \"" + filename +
				"\": " + str(e))
		
		# Get the widgets and add them as attributes it to this instance
		self._widgets = self._builder.get_objects()
		for widget in self._widgets:
			if hasattr(widget, "get_name"):
				setattr(self, gtk.Buildable.get_name(widget), widget)
		
		# Connect signals
		with warnings.catch_warnings():
			warnings.simplefilter('ignore', RuntimeWarning)
			missing = self._builder.connect_signals(self)
		if missing is not None:
			for name in set(missing):
				logging.warning("Missing handler: '%s'", name)
	
	def show_dialog(self, parent_window, text, dialog_type="info"):
		"""Show a dialog popup window"""
		dialogs = { "info" : gtk.MESSAGE_INFO, "warning" : gtk.MESSAGE_WARNING,
			"question" : gtk.MESSAGE_QUESTION, "error" : gtk.MESSAGE_ERROR }
		assert dialog_type in dialogs.keys()
		md = gtk.MessageDialog(parent_window, gtk.DIALOG_DESTROY_WITH_PARENT,
			dialogs[dialog_type], gtk.BUTTONS_CLOSE, text)
		md.connect("response", lambda w, e, md=md: md.destroy())
		md.show()
		return md
	
	def main(self):
		"""Start the GTK loop"""
		gtk.main()
	
	def show_exception(self, exception):
		"""Display a dialog showing details about an exception"""
		text = ("An exception %s occured:\n%s" %
			(type(exception), str(exception)))
		self.show_dialog(None, text, dialog_type="error")
	
	def except_safe(self, function, *args, **kwargs):
		"""Run a function, check for exceptions and display them"""
		try:
			return function(*args, **kwargs)
		except Exception as e:
			self.show_exception(e)
	
	def dont_delete(self, widget, event):
		"""Callback function to hide a widget instead of destroying it"""
		widget.hide()
		return True
	
	def quit(self, *args):
		"""Stop the GTK loop"""
		gtk.main_quit()




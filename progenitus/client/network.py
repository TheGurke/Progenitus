# Written by TheGurke 2011
"""The Progenitus network protocol"""

import re
import glib
from gettext import gettext as _
from pyxmpp.jabber.muc import MucRoomHandler

from progenitus import config
import muc


# 5 Zones where cards can be: library, graveyard, hand, battlefield, removed,
#    void
zones = ["L", "G", "H", "B", "R", "V"]

# All network commands
commands = {
	"hello":    "[Hello]", # Handshake initialization
	"welcome":  "[Welcome]", # Handshake response
	"reset":    "[Reset]", # Reset deck
	"tray":     "[CreateTray] as %x (%d, %d)", # Tray item
	"update":   "[Update] %d %d", # update tray: library count, hand card count
	"setlife":  "[Setlife] %d", # set life points
	"enter":    "[Enter] %d as %x (%d,%d)", # enter the battlefield
	"exit":     "[Exit] %x", # exit the battlefield
	"bury":     "[Bury] %d", # add a card to the graveyard
	"unbury":   "[Unbury] %d", # remove a card from the graveyard by index
	"remove":   "[Remove] %d", # put a card in the removed zone
	"unremove": "[Unremove] %d", # remove a card from the removed zone by index
	"mulligan": "[Mulligan]", # take a mulligan
	"shuffle":  "[Shuffle]", # shuffle the library
	"move":     "[Move] %x to (%d,%d)", # move a card on the battlefield
	"tap":      "[Tap] %x", # tap a card
	"flip":     "[Flip] %x", # flip a card
	"face":     "[Face] %x" # face a card up or down
}

# Regular expressions corresponding to the commands
res = []

# Logger messages
logger_msgs = {
	"hello":    _("{0} connected."),
	"tray":     _("{0} joined the game."),
	"shuffle":  _("{0} shuffles their deck."),
	"setlife":  _("{0} has {1} life points."),
	"mulligan": _("{0} takes a mulligan.")
#	"reset": _("{0} resets their deck.")
#	"tap":      _("{0} taps {1}."),
#	"flip":     _("{0} flips {1}."),
#	"face":     _("{0} turns {1} over.")
}



def create_res():
	"""Create regular expressions to match the incoming commands"""
	global res
	res = []
	for cmd in commands.values():
		r = cmd.replace(" ", '\s+')
		r = r.replace("(", '\(').replace(")", '\)')
		r = r.replace("[", '\[').replace("]", '\]')
		r = r.replace("%d", '\s*(-?\d+)\s*')
		r = r.replace("%x", '\s*([0-9abcdef]+)\s*')
		r = r.replace("%s", '([^"])')
		r = r + "\s*"
		res.append(re.compile(r))

create_res()


# MUC Room handler

class Roomhandler(MucRoomHandler):
	
	def __init__(self, network_manager):
#		super(self.__class__, self).__init__()
		MucRoomHandler.__init__(self)
		self.manager = network_manager
	
	def message_received(self, user, stanza):
		"""Recieved a chat line"""
		text = stanza.get_body()
		if text is not None and not user.same_as(self.manager.get_my_user()):
			matched = False
			cmdlist = []
			lines = text.split('\n')
			for i in range(len(lines)):
				line = lines[i]
				for k in range(len(res)):
					match = res[k].match(line)
					if match is not None:
						if i == 0:
							matched = True
						cmdlist.append((k, match.groups()))
						break
			if matched:
				self.manager._incoming_commands(user, cmdlist)
			else:
				self.manager._incoming_chat(user, text)
	
	def user_left(self, user, stanza):
		"""A user left the room"""
		if self.manager.user_left is not None:
			self.manager.user_left(user)


# Network manager class

class NetworkManager(object):
	
	client = None # MUCClient
	logger = None # Logger
	
	# Callback methods
	incoming_commands = None
	incoming_chat = None
	user_left = None
	exception_handler = None
	
	def __init__(self):
		self.logger = Logger()
		glib.timeout_add(10, self._idle)
	
	def _idle(self):
		"""Idle method which should be called frequently"""
		if self.client is not None:
			try:
				self.client.idle_callback()
			except Exception as e:
				if self.exception_handler is not None:
					self.exception_handler(e)
		return True
	
	def connect(self, username, pwd, gamename, nick, gamepwd):
		"""Connect to a server"""
		self.client = muc.MUCClient(username, pwd, config.APP_NAME, gamename,
			nick, gamepwd, Roomhandler(self))
		self.client.connect()
	
	def is_connected(self):
		"""Is the connection established?"""
		return (hasattr(self.client, 'roomState')
			and self.client.get_my_user() is not None)
	
	def disconnect(self):
		"""Disconnect from the server"""
		if self.client is not None:
			if hasattr(self.client, "roomState"):
				self.client.roomState.leave()
			self.client.disconnect()
			self.client = None
	
	def get_my_user(self):
		"""Get the MucRoomUser object associated with this client"""
		if self.client is not None:
			return self.client.get_my_user()
		else:
			raise RuntimeError(_("Not yet connected"))
	
	def change_nick(self, new_nick):
		"""Change the nick in the current game"""
		self.client.roomState.change_nick(new_nick)
	
	def _incoming_commands(self, user, cmdlist):
		"""Handle an incoming command"""
		cmdlist_ = []
		for k, groups in cmdlist:
			cmd, cmd_str = commands.items()[k]
			
			# Convert arguments
			args = list(groups)
			l = cmd_str.split('%')[1:]
			assert(len(args) == len(l))
			for i in range(len(l)):
				if l[i][0] == "x":
					args[i] = int(args[i], 16)
				elif l[i][0] == "d":
					args[i] = int(args[i])
			cmdlist_.append((cmd, tuple(args)))
		
		self.logger.log_commands(user, cmdlist_)
		if self.incoming_commands is not None:
			self.incoming_commands(user, cmdlist_)
	
	def _incoming_chat(self, user, text):
		"""Recieve an incoming chat messsage"""
		if len(text) == 0:
			return # Ignore message
		if text[0] == '\\':
			text = text[1:]
		if self.incoming_chat is not None:
			self.incoming_chat(user, text)
	
	def send_commands(self, cmdlist, logged=True):
		"""Send a list of commands over the network"""
		for cmd, args in cmdlist:
			assert(cmd in commands.keys())
			assert(len(args) == commands[cmd].count('%'))
		text = ""
		if self.client is not None:
			for cmd, args in cmdlist:
				cmd_str = commands[cmd]
				text += (cmd_str % args) + "\n"
			if logged:
				user = self.client.get_my_user()
				self.logger.log_commands(user, cmdlist)
			glib.idle_add(self.client.send_message, text[:-1])
	
	def send_chat(self, text):
		"""Send a chat message over the network"""
		if text == "":
			return # don't send an empty message
		if text[0] == '[' or text[0] == '\\':
			text = '\\' + text
		glib.idle_add(self.client.send_message, text)


# Logger

class Logger(object):
	"""An object to store log messages"""
	
	_log = []
	log_callback = None
	
	def log(self, message):
		"""Append a log message"""
		self._log.append(message)
		if self.log_callback is not None:
			self.log_callback(message)
	
	def log_commands(self, user, cmdlist):
		"""Log a network command"""
		# TODO
		for cmd, args in cmdlist:
			if cmd in logger_msgs.keys():
				self.log(logger_msgs[cmd].format(user.nick, *args))
	
	def get_log(self):
		"""Get the complete log"""
		return self._log
	
	def clear_log(self):
		"""Clear the log"""
		self._log = []




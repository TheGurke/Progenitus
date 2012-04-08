# Written by TheGurke 2011
"""
Implementation of the Progenitus network protocol

This module recieves network instructions and packages them into xmpp messages.
Incoming messages are unpackaged and returned as instruction tuples.
"""

import datetime
import logging
import re
import gzip
from gettext import gettext as _

import glib

from progenitus import config
import muc


# 5 Zones where cards can be: library, graveyard, hand, battlefield, exile,
#    void
zones = ["L", "G", "H", "B", "E", "V"]

assert(' ' not in config.VERSION)

# All network commands
commands = {
	"hello":    "[Hello] %s", # handshake initialization
	"welcome":  "[Welcome] %s", # handshake response
	"reset":    "[Reset]", # reset deck
	"tray":     "[CreateTray] as %x at (%.2f, %.2f)", # Tray item
	"update":   "[Update] %d %d", # update tray: library count, hand card count
	"setlife":  "[Setlife] %d", # set life points
	"enter":    "[Enter] %s \"%s\" as %x at (%.2f,%.2f)", # onto the battlefield
	"exit":     "[Exit] %x", # exit the battlefield
	"bury":     "[Bury] %s", # add a card to the graveyard
	"unbury":   "[Unbury] %d", # remove a card from the graveyard by index
	"exile":    "[Exile] %s", # move a card to the exile zone
	"unexile":  "[Unexile] %d", # remove a card from the exile by index
	"mulligan": "[Mulligan]", # take a mulligan
	"shuffle":  "[Shuffle]", # shuffle the library
	"move":     "[Move] %x to (%.2f,%.2f)", # move a card on the battlefield
	"tap":      "[Tap] %x", # tap a card
	"flip":     "[Flip] %x", # flip a card
	"face":     "[Face] %x", # face a card up or down
	"counters":  "[Counter] %d \"%s\" counter on %x" # put counters on a card
		# FIXME: counters
}

# Regular expressions corresponding to the commands
res = []

# Logger messages
logger_msgs = {
	"hello":    _("{0} connected."),
	"tray":     _("{0} joined the game."),
	"shuffle":  _("{0} shuffles their deck."),
	"setlife":  _("{0} has {1} life points."),
	"mulligan": _("{0} takes a mulligan."),
	"reset":    _("{0} resets their deck."),
#	"tap":      _("{0} taps {1}."),
	"flip":     _("{0} flips a card."),
	"face":     _("{0} turns a card over."),
	"counters":  _("{0} puts {1} {2} counter on a card.")
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
		r = r.replace("%.2f", '\s*(-?\d+.\d\d)\s*')
		r = r.replace("%x", '\s*([0-9abcdef]+)\s*')
		r = r.replace("\"%s\"", '\"([^"]*)\"')
		r = r.replace("%s", '([^\s]+)')
		r = r + "\s*"
		res.append(re.compile(r))

create_res()



# Network manager class

class NetworkManager(object):
	
	client = None # MUCClient
	games = [] # Joined chat rooms
	logger = None # Logger
	
	# Callback methods (please attach!)
	exception_handler = None
	
	def __init__(self):
		self.logger = Logger()
	
	def connect(self, jid, pwd):
		"""Connect to a server"""
		if self.client is not None:
			self.disconnect() # disconnect the old connection first
		self.client = muc.XMPPClient(jid, pwd, config.APP_NAME)
		if not self.client.connect():
			raise RuntimeError("Connection failed")
		else:
			# Process incoming messages in a seperate thread
			self.client.process(threaded=True)
	
	def join_game(self, gamename, pwd, nick):
		"""Join a network game"""
		logging.info(_("Joining game '%s'..."), gamename)
		game = Game(self.client, gamename, pwd, nick)
		game.logger = self.logger
		self.games.append(game)
		game.join()
		return game
	
	def leave_game(self, game):
		"""Leave a network game"""
		assert(game in self.games)
		game.leave()
		self.games.remove(game)
	
	def is_connected(self):
		"""Is the connection established?"""
		return self.client.is_connected
	
	def disconnect(self):
		"""Disconnect from the server"""
		for game in self.games:
			game.leave()
		self.games = []
		if self.client is not None:
			self.client.disconnect()
			self.client = None
		logging.info(_("Disconnected from server."))
	
	def get_my_jid(self):
		"""Get the JID object associated with this client"""
		if self.client is not None:
			return self.client.boundjid
		else:
			raise RuntimeError(_("Not yet connected"))
	
	def get_room_list(self, server):
		"""Get a list of available chat rooms"""
		iq = self.client.plugin['xep_0030'].get_items("conference." + server)
		for item in iq.values['disco_items']['items']:
			print item
		return iq.values['disco_items']['items']


class Game(muc.Room):
	"""A network game"""
	
	logger = None
	recorder = None
	
	# Callback methods
	incoming_commands = None
	incoming_chat = None
	user_nick_changed = None
	
	def __init__(self, client, jid, password, nick):
		super(self.__class__, self).__init__(client, jid, password, nick)
		self.recorder = Recorder() # record every game by default
	
	def muc_message(self, room, sender, text):
		"""Recieved a muc message"""
		self.recorder.record(sender, text)
		if text is not None and sender != self.get_my_jid():
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
				self._incoming_commands(sender, cmdlist)
			else:
				self._incoming_chat(sender, text)
	
	def _incoming_commands(self, sender, cmdlist):
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
				elif l[i][:3] == ".2f":
					args[i] = float(args[i])
			cmdlist_.append((cmd, tuple(args)))
		
		if self.logger is not None:
			self.logger.log_commands(sender, cmdlist_)
		if self.incoming_commands is not None:
			self.incoming_commands(self, sender, cmdlist_)
	
	def _incoming_chat(self, sender, text):
		"""Recieve an incoming chat messsage"""
		if len(text) == 0:
			return # Ignore message
		if text[0] == '\\':
			text = text[1:]
		if self.incoming_chat is not None:
			self.incoming_chat(self, sender, text)
	
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
			if logged and self.logger is not None:
				self.logger.log_commands(self.get_my_jid(), cmdlist)
			glib.idle_add(self.send_message, text[:-1])
	
	def send_chat(self, text):
		"""Send a chat message over the network"""
		if text == "":
			return # don't send an empty message
		if text[0] == '[' or text[0] == '\\':
			text = '\\' + text
		glib.idle_add(self.send_message, text)
	
	def _nick_changed(self, user, old_nick, stanza):
		"""A user changed their nick"""
		if self.user_nick_changed is not None:
			self.user_nick_changed(user)


class Recorder(object):
	"""Record network commands for later replay"""
	
	_log = []
	
	def record(self, jid, message):
		"""Record a text message"""
		record = (datetime.datetime.now(), jid, message)
		self._log.append(record)
	
	def to_text(self):
		"""Return a string representation of this recorder's log."""
		text = ""
		for time, jid, content in self._log:
			text += "%s %s %s\n" % (str(time),
				"\"%s\"" % jid.resource.replace("\"", "\\\""),
				"%r" % content)
		return text[:-1]
	
	def dump_to_file(self, filename):
		with gzip.GzipFile(filename, 'w') as f:
			f.write(self.to_text())
	
	def clear_log(self):
		"""Clear the log"""
		self._log = []


class Logger(object):
	"""Record network commands"""
	
	_log = []
	log_callback = None
	
	def log(self, message):
		"""Append a log message"""
		self._log.append(message)
		if self.log_callback is not None:
			self.log_callback(message)
	
	def log_commands(self, jid, cmdlist):
		"""Log a network command"""
		# TODO
		for cmd, args in cmdlist:
			if cmd in logger_msgs.keys():
				self.log(logger_msgs[cmd].format(jid.resource, *args))
	
	def get_log(self):
		"""Get the complete log"""
		return self._log
	
	def clear_log(self):
		"""Clear the log"""
		self._log = []




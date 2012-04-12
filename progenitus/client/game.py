# Written by TheGurke 2011
"""
Game instance
"""
# This is in a seperate module to resolve cross-dependencies

import logging
from gettext import gettext as _

import glib

import muc
import replay
import network


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
		self.recorder = replay.Recorder(jid, client.boundjid)
	
	def muc_message(self, room, sender, text):
		"""Recieved a muc message"""
		self.recorder.record(sender, text)
		if text is not None and sender != self.get_my_jid():
			matched = False
			cmdlist = network.parse_msg(text)
			if cmdlist is not None:
				self._incoming_commands(sender, cmdlist)
			else:
				self._incoming_chat(sender, text)
	
	def _incoming_commands(self, sender, cmdlist):
		"""Handle an incoming command"""
		if self.logger is not None:
			self.logger.log_commands(sender, cmdlist)
		if self.incoming_commands is not None:
			self.incoming_commands(self, sender, cmdlist)
	
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
			assert(cmd in network.commands.keys())
			assert(len(args) == network.commands[cmd].count('%'))
		text = ""
		if self.client is not None:
			for cmd, args in cmdlist:
				cmd_str = network.commands[cmd]
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


def join(network_manager, gamename, pwd, nick):
	"""Join a network game"""
	logging.info(_("Joining game '%s'..."), gamename)
	game = Game(network_manager.client, gamename, pwd, nick)
	game.logger = network_manager.logger
	network_manager.games.append(game)
	game.join()
	return game

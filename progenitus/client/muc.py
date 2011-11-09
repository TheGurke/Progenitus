# Written by TheGurke 2011
"""
Multi user chats via XMPP

This is a library abstraction for sleekxmpp; but it could use any library that
supports MUC (XEP 0045).
"""

import logging

import sleekxmpp


class XMPPClient(sleekxmpp.ClientXMPP):
	"""
	A connection object to the XMPP server; derives from sleekxmpp.ClientXMPP
	"""
	
	def __init__(self, username, password, resource):
		"""The constructer does not initialize the connection"""
		sleekxmpp.ClientXMPP.__init__(self, username, password)
		
		# Register plugins
		xmpp.register_plugin('xep_0030') # Service Discovery
		xmpp.register_plugin('xep_0045') # Multi-User Chat
		xmpp.register_plugin('xep_0199') # XMPP Ping
		
		# Add event handlers
		self.add_event_handler("session_start", self.session_started)
		self.add_event_handler("groupchat_message", self.muc_message)
		
		# TODO: set resource
	
	def session_started(self, event):
		"""
		This is called when the connection with the server is established and
		the XML streams are ready for use.
		"""
		self.get_roster()
		self.send_presence()



class Room(object):
	"""
	An connection object to the XMPP chat room (MUC)
	"""
	
	muc_message_handler = None # Handler for incoming messages from the room
	muc_presence_handler = None # Handler for incoming presence from the room
	
	def __init__(self, client, name, password, nick):
		assert(isinstance(client, XMPPClient))
		self.client = client
		self.name = name
		self.password = password
		self.nick = nick
		self.muc_plugin = self.client.plugin['xep_0045']
	
	def join(self):
		"""Connect to the room"""
		self.muc_plugin.joinMUC(self.name, self.nick, password=self.password)
			# wait=True
		self.client.add_event_handler("muc::%s::got_online" % self.name,
			self._muc_presence_handler)
	
	def leave(self, message=""):
		"""Disconnect from the room"""
		self.muc_plugin.leaveMUC(self.name, self.nick, message)
	
	def _muc_message_handler(self, *args):
		"""The message handler passes on incoming room chat messages"""
		if self.muc_message_handler is not None:
			self.muc_message_handler(*args)
	
	def _muc_presence_handler(self, *args):
		"""The presence handler passes on incoming room presence information"""
		if self.muc_presence_handler is not None:
			self.muc_presence_handler(*args)
	
	def list_participants(self):
		"""Fetch a list of all users in the room"""
		return self.muc_plugin.getRoster(self.name)
	
	def invite(self, jid, message=""):
		"""Invite a user to this room"""
		self.muc_plugin.invite(self.name, jid, reason=message)
	
	def send_message(self, text):
		"""Send a message to the room"""
		self.client.send_message(
			mto=self.name,
			mbody=text,
			mtype="groupchat",
			mnick=self.nick
		)
	
	def change_nick(self, text):
		"""Change this client's nick name in the room"""


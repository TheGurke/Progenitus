# Written by TheGurke 2011
"""
Multi user chats via XMPP

This is a library abstraction for sleekxmpp; but it could use any library that
supports MUC (XEP 0045).
"""

import logging

import sleekxmpp
from sleekxmpp.xmlstream.stanzabase import JID


class XMPPClient(sleekxmpp.ClientXMPP):
	"""
	A connection object to the XMPP server; derives from sleekxmpp.ClientXMPP
	"""
	
	is_connected = False
	
	# Event handlers
	connection_established = None
	incoming_message = None
	
	def __init__(self, jid, password, resource):
		"""The constructer does not initialize the connection"""
		sleekxmpp.ClientXMPP.__init__(self, jid, password)
		self.boundjid.resource = resource
		
		# Register plugins
		self.register_plugin('xep_0030') # Service Discovery
		self.register_plugin('xep_0045') # Multi-User Chat
		self.register_plugin('xep_0199') # XMPP Ping
		self.register_plugin('old_0004') # ?
		
		# Add event handlers
		self.add_event_handler("session_start", self._session_started)
#		self.add_event_handler("chat_message", self._incoming_message)

	
	def _session_started(self, event):
		"""
		This is called when the connection with the server is established and
		the XML streams are ready for use.
		"""
		self.get_roster()
		self.send_presence()
		is_connected = True
		if self.connection_established is not None:
			self.connection_established()
	
	def _incoming_message(self, message):
		"""Recieved an incoming chat message"""
		if self.incoming_message is not None:
			self.incoming_message(message)
	
	def disconnect(self, reconnect=False):
		"""Disconnect from the server"""
		is_connected = False
		sleekxmpp.ClientXMPP.disconnect(self, reconnect)


class Room(object):
	"""
	An connection object to the XMPP chat room (MUC)
	"""
	
	joined = None # Handler for successful room joining
	muc_message = None # Handler for incoming messages from the room
	muc_presence = None # Handler for incoming presence from the room
	
	def __init__(self, client, jid, password, nick):
		assert(isinstance(client, XMPPClient))
		self.client = client
		self.jid = jid  # room jid as string
		self.password = password
		self.nick = nick
		self.muc_plugin = self.client.plugin['xep_0045']
	
	def get_my_jid(self):
		"""Get my full jid for this room"""
		return JID(self.muc_plugin.getOurJidInRoom(self.jid))
	
	def join(self):
		"""Connect to the room"""
		self.muc_plugin.joinMUC(self.jid, self.nick, password=self.password)
		self.client.add_event_handler("groupchat_message", self._muc_message)
		self.client.add_event_handler("muc::%s::presence" % self.jid,
			self._joined)
		self.client.add_event_handler("muc::%s::got_online" % self.jid,
			self._muc_presence)
	
	def _joined(self, presence):
		"""The room has been joined successfully"""
		# Look for my own presence information
		if presence["from"].full != self.get_my_jid().full:
			return
		self.client.del_event_handler("muc::%s::presence" % self.jid,
			self._joined)
		self.configure()
		if self.joined is not None:
			self.joined()
	
	def configure(self):
		"""Set the room config"""
		try:
			self.muc_plugin.configureRoom(self.jid)
		except:
			# assume the room has been configured
			pass
		else:
			logging.info(_("Configured room '%s'."), self.jid)
	
	def leave(self, message=""):
		"""Disconnect from the room"""
		self.muc_plugin.leaveMUC(self.jid, self.nick, message)
	
	def _muc_message(self, message):
		"""The message handler passes on incoming room chat messages"""
		# Filter out messages that are not for this room
		if message["from"].bare != self.jid:
			return
		if self.muc_message is not None:
			self.muc_message(self, message["from"], message["body"])
	
	def _muc_presence(self, presence):
		"""The presence handler passes on incoming room presence information"""
		if self.muc_presence is not None:
			self.muc_presence(self, presence["from"], presence["role"]) # TODO
	
	def list_participants(self):
		"""Fetch a list of all users in the room"""
		return self.muc_plugin.getRoster(self.jid)
	
	def invite(self, jid, message=""):
		"""Invite a user to this room"""
		self.muc_plugin.invite(self.jid, jid, reason=message)
	
	def send_message(self, text):
		"""Send a message to the room"""
		self.client.send_message(
			mto=self.jid,
			mbody=text,
			mtype="groupchat",
			mnick=self.nick
		)
	
	def change_nick(self, text):
		"""Change this client's nick name in the room"""
		pass # TODO




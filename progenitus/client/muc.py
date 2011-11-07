# Written by TheGurke 2011
"""Multi user chats via Jabber/XMPP"""

import logging

from pyxmpp.all import JID
from pyxmpp.jabber.client import JabberClient
from pyxmpp.jabber.muc import MucRoomState, MucRoomManager, MucRoomHandler



SET_PRESENCE = False


class MUCClient(JabberClient):
	
	def __init__(self, username, password, resource, room, nick, roompwd,
	             handler):
		# Set up the logger
		self.logger = logging.getLogger()
		self.logger.addHandler(logging.StreamHandler())
		
		self.room_to_join = room, nick, roompwd
		self.roomHandler = handler
		jid = JID(username)
		if not jid.resource: # set resource
			jid = JID(jid.node, jid.domain, resource)
		JabberClient.__init__(self, jid, password, disco_name="client",
			disco_type="bot")
	
	def session_started(self):
		"""This is called automatically once the login process is complete"""
		# Send online presence
		if SET_PRESENCE:
			self.request_roster()
			p=Presence()
			self.stream.send(p)
		self.connectToMUC()
	
	def connectToMUC(self):
		"""Join a multi-user chat room"""
		room, nick, roompwd = self.room_to_join
		self.roomManager = MucRoomManager(self.stream);
		self.room_to_join = None
		self.roomState = self.roomManager.join(room=JID(room), nick=nick,
			handler=self.roomHandler, history_maxchars=0, password=roompwd)
		self.roomManager.set_handlers()
	
	def idle_callback(self):
		"""Call this function regularily to check for new messages"""
		stream = self.get_stream()
		if not stream:
			return
		act = stream.loop_iter(0)
		if not act:
			self.idle()
		return True
	
	def send_message(self, text):
		"""Send a text to the MUC"""
		if hasattr(self, "roomState"):
			self.roomState.send_message(text)
	
	def get_my_user(self):
		"""Get the MucRoomUser object associated with this client"""
		return self.roomState.get_user(self.roomState.get_room_jid())




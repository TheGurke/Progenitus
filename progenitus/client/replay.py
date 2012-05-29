# Written by TheGurke 2012
"""
Game replays

This module provides the functionality to record games and replay them.
"""

import datetime
import re
import gzip

from sleekxmpp.xmlstream.stanzabase import JID

import desktop
import network


class Recorder(object):
	"""Record network commands for later replay"""
	
	_log = None
	_reverse_log = None # For replaying this contains the inverse commands
	_current_pos = -1 # Current point in the replay (list index)
	
	replay_cmds = None # Callback for replaying cmds
	replay_chat = None # Callback for replay messages
	
	def __init__(self, room, my_jid):
		self.room = room
		self.my_jid = my_jid
		self.start_time = datetime.datetime.now()
		self._log = []
		self._reverse_log = []
	
	def record(self, jid, message):
		"""Record a text message"""
		record = (datetime.datetime.now(), jid, message)
		self._log.append(record)
	
	def to_text(self):
		"""Return a string representation of the recoded game."""
		text = "progenitus replay file\n"
		text += "room: %s\n" % self.room
		text += "player: %s\n" % self.my_jid
		for time, jid, content in self._log:
			esc_jid = jid.resource.replace("\\", "\\\\").replace("\"", "\\\"")
			text += "%s %s %s\n" % (str(time),
				"\"%s\"" % esc_jid,
				"%r" % content)
		return text[:-1]
	
	def dump_to_file(self, filename):
		"""Dump the recorded game to a file"""
		with gzip.GzipFile(filename, 'w') as f:
			f.write(self.to_text())
	
	def get_start_time(self):
		"""Return the time at which the replay starts"""
		return self._log[0][0]
	
	def get_end_time(self):
		"""Return the time at which the replay ends"""
		return self._log[-1][0]
	
	def get_current_time(self):
		"""Return the time for the current position in the replay"""
		if self._current_pos < 0:
			return datetime.datetime(datetime.MINYEAR, 1, 1)
		if self._current_pos >= len(self._log):
			return datetime.datetime(datetime.MAXYEAR, 12, 31)
		return self._log[self._current_pos][0]
	
	def get_elapsed_time(self):
		"""Return the time that elapsed since the beginning of the replay"""
		return self.get_current_time() - self.get_start_time()
	
	def replay_to(self, time, players, create_player):
		"""Replay all commands up to a certain point in time"""
		if self.get_current_time() > time:
			while self.get_current_time() > time:
				sender, inv_cmds = self._reverse_log[self._current_pos]
				self.replay_cmds(self, sender, inv_cmds)
				self._current_pos -= 1
		else:
			self._current_pos += 1
			while self.get_current_time() < time:
				sender, msg = self._log[self._current_pos][1:3]
				cmds = network.parse_msg(msg)
				
				# Check if the message need to be inverted
				if len(self._reverse_log) < self._current_pos + 1:
					if cmds is None:
						self._reverse_log.append((sender, []))
					else:
						pl = [pl for pl in players if pl.jid == sender]
						# Dirty hack: create player if it hasn't been yet
						if len(pl) == 0:
							player = create_player(self, sender, "")
						else:
							player = pl[0]
						
						inv_cmds = []
						for (cmd, args) in cmds[::-1]:
							inv_cmds.extend(
								self._invert_cmd(player, cmd, *args))
						self._reverse_log.append((sender, inv_cmds))
				
				if cmds is not None:
					self.replay_cmds(self, sender, cmds)
					self._current_pos += 1
					continue
				if len(msg) == 0:
					self._current_pos += 1
					continue # Ignore message
				if msg[0] == '\\':
					msg = msg[1:]
				self.replay_chat(self, sender, msg)
				self._current_pos += 1
			self._current_pos -= 1
	
	def _invert_cmd(self, player, cmd, *args):
		"""Invert a command; returns a list of commands"""
		if cmd == "hello" or cmd == "welcome":
			return [] # No need for invertation
		elif cmd == "tray":
			return [("exit", (args[0],))]
		elif cmd == "enter":
			return [("exit", (args[2],))]
		elif cmd == "update":
			return [("update", (len(player.library), len(player.hand)))]
		elif cmd == "setlife":
			return [("setlife", (player.life,))]
		elif cmd == "bury":
			return [("unbury", (len(player.graveyard),))]
		elif cmd == "exile":
			return [("unexile", (len(player.graveyard),))]
		elif cmd == "unbury" or cmd == "unexile":
			inv_cmd = "bury" if cmd == "unbury" else "exile"
			cmdlist = []
			for i in range(args[0], len(player.graveyard) - 1):
				cmdlist.append((cmd, (i,)))
			for card in player.graveyard[args[0]:]:
				cmdlist.append((inv_cmd, (card.id,)))
			return cmdlist
		elif cmd == "mulligan":
			return [("update", (len(player.library), len(player.hand)))]
		elif cmd == "shuffle":
			return [] # No need for invertation
		elif cmd == "move":
			item = player._get_item_by_id(args[0])
			return [("move", (item.itemid, item.x, item.y))]
		elif cmd == "tap" or cmd == "flip" or cmd == "face":
			return [(cmd, (args[0],))]
		elif cmd == "counters":
			item = player._get_item_by_id(args[2])
			num = item.counters[args[1]] if args[1] in item.counters else 0
			return [("counters", (num, args[1], args[2]))]
		elif cmd == "exit":
			item = player._get_item_by_id(args[0])
			if isinstance(item, desktop.Tray):
				return [("tray", (item.itemid, item.x, item.y))]
			if isinstance(item, desktop.CardItem):
				name = item.token.name if item.istoken else item.card.name
				return [("enter", (item.cardid, name, item.itemid, item.x,
					item.y))]
		elif cmd == "reset":
			cmdlist = [("update", (len(player.library), len(player.hand)))]
			cmdlist.append(("setlife", (player.life,)))
			for card in player.graveyard:
				cmdlist.append(("bury", (card.id,)))
			for card in player.exile:
				cmdlist.append(("exile", (card.id,)))
			for item in player.battlefield:
				name = item.token.name if item.istoken else item.card.name
				cmdlist.append(("enter",
					(item.cardid, name, item.itemid, item.x, item.y)))
			return cmdlist
		else:
			assert(False)
	
	def get_length(self):
		"""Get the length of this replay as a timedelta object"""
		return self.get_end_time() - self.get_start_time()
	
	def clear(self):
		"""Clear the recorder"""
		self._log = []


def parse_text(text):
	"""Parse a string representation of a recorded game"""
	line0, line1, line2 = text.split("\n")[:3]
	assert(line0 == "progenitus replay file")
	room = re.match(r'room:\s+(.*)', line1).group(1)
	player = re.match(r'player:\s+(.*)', line2).group(1)
	recorder = Recorder(room, player)
	log = text.split("\n")[3:]
	re_line = re.compile(
		r'(\d\d\d\d-\d\d-\d\d\s\d\d:\d\d:\d\d.\d+)\s+"([^"]+)"\s+([^\n]+)')
	for line in log:
		if line == "":
			continue
		match = re_line.match(line)
		timestr, sender, content = match.groups()
		time = datetime.datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S.%f")
		jid = JID(room + "/" + sender)
		recorder._log.append((time, jid, content[1:-1].decode('string-escape')))
	
	# Assert that the list is sort with respect to the time
	l = recorder._log[:]
	l.sort(key=lambda x: x[0])
	assert(recorder._log == l)
	return recorder

def read_from_file(filename):
	"""Parse a file dump"""
	with gzip.GzipFile(filename, 'r') as f:
		text = f.read()
	return parse_text(text)

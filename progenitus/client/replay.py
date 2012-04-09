# Written by TheGurke 2012
"""
Game replays

This module provides the functionality to record games and replay them.
"""

import datetime
import re
import gzip

import network


class Recorder(object):
	"""Record network commands for later replay"""
	
	_log = []
	_reverse_log = [] # For replaying this contains the inverse commands
	_current_pos = 0 # Current point in the replay (list index)
	
	replay_cmds = None # Callback for replaying cmds
	replay_msg = None # Callback for replay messages
	
	def __init__(self, room, my_jid):
		self.room = room
		self.my_jid = my_jid
		self.start_time = datetime.datetime.now()
	
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
		return self._log[self._current_pos][0]
	
	def replay_to(self, time):
		"""Replay all commands up to a certain point in time"""
		if self.get_current_time() > time:
			pass # TODO: seek backwards
		else:
			while self.get_current_time() < time:
				self._current_pos += 1
				sender, msg = self._log[self._current_pos][1:3]
				if len(msg) == 0:
					continue # Ignore message
				
				cmds = network.parse_msg(msg)
				if cmds is not None:
					self.replay_cmds(self, sender, cmds)
					continue
				if msg[0] == '\\':
					msg = msg[1:]
				self.replay_chat(self, sender, msg)
	
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
		timestr, jid, content = match.groups()
		time = datetime.datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S.%f")
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

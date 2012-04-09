# Written by TheGurke 2012
"""
Game replays

This module provides the functionality to record games and replay them.
"""

import datetime
import re
import gzip


class Recorder(object):
	"""Record network commands for later replay"""
	
	_log = []
	
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
		recorder._log.append((time, jid, content))
	return recorder

def read_from_file(filename):
	"""Parse a file dump"""
	with gzip.GzipFile(filename, 'r') as f:
		text = f.read()
	return parse_text(text)


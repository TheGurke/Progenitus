# Written by TheGurke 2011
"""
This module handles virtual 'player' instances consisting of the information
about all the cards and tokens one player controls in the game.

The client will create a Player instance for every player on the network.
The local client will have the send_network_cmds callback set while remote
clients just recieve network commands.
"""

import random
from gettext import gettext as _

import glib

from progenitus import config
from progenitus.db import cards


def do_nothing(*args, **kwargs):
	pass


class Player(object):
	"""A player is the virtual representation of the game from one player's
	point of view"""
	
	name = "" # the player's name
	deck = None
	tray = None # Tray item
	life = config.DEFAULT_LIFE # life points
	has_been_welcomed = False # whether the client has completed the handshake
	
	# Update notifier (will be filled with repaint methods)
	updated_hand      = do_nothing
	updated_library   = do_nothing
	updated_graveyard = do_nothing
	updated_exile     = do_nothing
	updated_life      = do_nothing
	
	# Exception handler
	exception_handler = do_nothing
	
	# Carditem handlers
	new_item    = do_nothing
	new_tray    = do_nothing
	delete_item = do_nothing
	
	# Network command sender
	send_network_cmds = do_nothing
	
	def __init__(self, user):
		self.user = user
		self.name = user.nick
		
		self.library = [] # cards in the library
		self.graveyard = [] # cards in the graveyard
		self.hand = [] # cards in the hand
		self.exile = [] # cards removed from play
		self.battlefield = [] # card and token items in play
		self._items = dict() # Item map: itemid -> item
	
	def set_life(self, life):
		"""Set the life counter to a specific value"""
		assert(isinstance(life, int))
		self.life = life
		self.updated_life()
		self.send_network_cmd("setlife", life)
	
	
	# Tray and Deck
	
	def create_tray(self, itemid=None, color=None):
		"""Create a tray item"""
		if self.tray is not None:
			# delete old tray
			self.delete_item(self.tray)
		self.tray = self.new_tray(self)
		if itemid is None:
			itemid = self._get_new_itemid(self.tray)
			self.tray.itemid = itemid
		else:
			self._set_itemid(itemid, self.tray)
		if color is not None:
			self.tray.bg_color = color
		self.send_network_cmd("tray", itemid, self.tray.x, self.tray.y)
		glib.idle_add(self.tray.repaint) # dirty fix for the textitem width bug
	
	def remove_tray(self):
		"""Remove the tray and all items in play"""
		for item in self.battlefield:
			self.delete_item(item)
		if self.tray is not None:
			self.send_network_cmd("exit", self.tray.itemid)
			self.delete_item(self.tray)
			self.tray = None
	
	def load_deck(self, deck):
		"""Load a deck"""
		self.deck = deck
		self.reset()
	
	def reset(self):
		"""Reset the game"""
		
		self.library = []
		self.graveyard = []
		self.hand = []
		self.exile = []
		for item in self.battlefield[:]:
			self.delete_item(item)
		self.battlefield = []
		self.life = config.DEFAULT_LIFE
		if self.deck is not None:
			self.library = self.deck.decklist[:]
			self.shuffle_library()
		
		self.updated_hand()
		self.updated_library()
		self.updated_graveyard()
		self.updated_exile()
		
		self.send_network_cmd("reset")
		self.send_network_cmd("update", len(self.library), len(self.hand))
	
	def unload(self):
		"""Unload the current deck"""
		self.deck = None
		self.reset()
	
		
	# Library
	
	def shuffle_library(self):
		"""Shuffle the library"""
		random.shuffle(self.library)
		self.updated_library()
		self.send_network_cmd("shuffle")
	
	
	# Hand
	
	def draw_card(self):
		"""Move the top card from the library to the hand"""
		if len(self.library) < 1:
			return
		self.move_card(self.library[-1], self.library, self.hand)
	
	def draw_x_cards(self, x):
		"""Draw x cards"""
		assert(isinstance(x, int))
		if len(self.library) < x:
			x = len(self.library)
		for i in range(x):
			self.move_card(self.library[-1], self.library, self.hand)
	
	def shuffle_hand(self):
		"""Shuffle the hand"""
		random.shuffle(self.hand)
		self.updated_hand()
	
	def discard(self, card):
		"""Discard a card"""
		if card not in self.hand:
			return
		self.move_card(card, self.hand, self.graveyard)
	
	def discard_random(self):
		"""Discard a random card"""
		if len(self.hand) == 0:
			return # No card in hand
		card = random.choice(self.hand)
		self.discard(card)
	
	def discard_all(self):
		"""Discard the hand"""
		self.shuffle_hand()
		for card in self.hand[:]:
			self.discard(card)
	
	def mulligan(self):
		"""Take a mulligan"""
		num = len(self.hand) - 1
		if num < 1:
			return
		self.library += self.hand
		self.hand = []
		random.shuffle(self.library)
		for i in range(num):
			self.hand.append(self.library.pop())
		
		self.updated_library()
		self.updated_hand()
		self.send_network_cmd("mulligan")
	
	
	# Graveyard
	
	def shuffle_graveyard_into_library(self):
		"""Shuffle all graveyard cards into the library"""
		cmdlist = []
		for i in range(len(self.graveyard) - 1, -1, -1):
			cmdlist.append(("unbury", (i,)))
		cmdlist.append(("update", (len(self.library + self.graveyard),
			len(self.hand))))
		self.send_network_cmds(cmdlist)
		
		self.library = self.graveyard + self.library
		self.graveyard = []
		
		self.shuffle_library()
		self.updated_library()
		self.updated_graveyard()
	
	def graveyard_top_to_hand(self):
		"""Return the top card on the graveyard to the hand"""
		if len(self.graveyard) == 0:
			return # no cards in the graveyard
		card = self.graveyard[-1]
		self.move_card(card, self.graveyard, self.hand)
	
	
	# Move
	
	def move_card(self, card, origin, target, x=None, y=None):
		"""Move a single card between two zones"""
		
		# Check parameters
		valid = [self.library, self.graveyard, self.hand, self.exile,
			self.battlefield, None]
		assert(any(map(lambda x: origin is x, valid)))
		assert(any(map(lambda x: target is x, valid)))
		if target is not self.battlefield:
			assert(target is not origin)
		else:
			assert(x is not None)
			assert(y is not None)
		if origin is self.battlefield:
			# card is actually an item
			item = card
			if target is not self.battlefield:
				# item must be a desktop.CardItem
				card = item.card
			if (hasattr(item, "token") and item.istoken
					and target is not self.battlefield):
				# Cannot let tokens leave the battlefield
				target = None
		elif origin is not None:
			assert(card in origin)
		
		# Move card
		if origin is not None and origin is not self.battlefield:
			# remove card by pointer
			index = 0
			while origin[index] is not card:
				index += 1
			origin[index:index + 1] = []
		elif origin is self.battlefield and target is not self.battlefield:
			self.remove_carditem(item)
		if target is not None and target is not self.battlefield:
			target.append(card)
		elif target is self.battlefield and origin is not self.battlefield:
			item = self.create_carditem(card.id, card.name, None, x, y)
		elif target is self.battlefield and origin is self.battlefield:
			item.x = x
			item.y = y
		
		# Call update methods
		for l in (origin, target):
			if l is self.library:
				self.updated_library()
			elif l is self.graveyard:
				self.updated_graveyard()
			elif l is self.hand:
				self.updated_hand()
			elif l is self.exile:
				self.updated_exile()
		
		# Send network commands
		cmdlist = []
		if origin is self.graveyard:
			cmdlist.append(("unbury", (index,)))
		elif origin is self.exile:
			cmdlist.append(("unexile", (index,)))
		elif origin is self.battlefield and target is self.battlefield:
			cmdlist.append(("move", (item.itemid, item.x, item.y)))
		if target is self.graveyard:
			cmdlist.append(("bury", (card.id,)))
		elif target is self.exile:
			cmdlist.append(("exile", (card.id,)))
		l = [self.library, self.hand, self.exile]
		if any(map(lambda x: origin is x or target is x, l)):
			cmdlist.append(("update", (len(self.library), len(self.hand))))
		self.send_network_cmds(cmdlist)
	
	
	# Battlefield
	
	def set_counter(self, item, num, counter):
		"""Put counters on a card"""
		if num != 0:
			item.counters[counter] = num
		elif counter in item.counters:
			del item.counters[counter]
		self.send_network_cmd("counter", num, counter, item.itemid)
	
	def create_carditem(self, cardid, cardname, itemid=None, x=0, y=0):
		item = self.new_item(cardid, self, x, y)
		# FIXME: check for card id
		if itemid is None:
			itemid = self._get_new_itemid(item)
			item.itemid = itemid
		else:
			self._set_itemid(itemid, item)
		self.send_network_cmd("enter", cardid, cardname, itemid, item.x, item.y)
		self.battlefield.append(item)
		return item
	
	def remove_carditem(self, item):
		self.battlefield.remove(item)
		self.delete_item(item)
		self.send_network_cmd("exit", item.itemid)
	
	
	# Network
	
	def send_network_cmd(self, cmd, *args):
		"""Send a single network command"""
		self.send_network_cmds([(cmd, args)])
	
	def make_welcome_message(self):
		"""Assemble a list of commands that describe this player's full current
		status"""
		cmdlist = [("welcome", (config.VERSION,))]
		if self.tray is None:
			return cmdlist
		cmdlist += [
			("tray", (self.tray.itemid, self.tray.x, self.tray.y)),
			("update", (len(self.library), len(self.hand))),
			("setlife", (self.life,))
		]
		for card in self.graveyard:
			cmdlist.append(("bury", (card.id,)))
		for card in self.exile:
			cmdlist.append(("exile", (card.id,)))
		for item in self.battlefield:
			cmdlist.append(("enter", (item.cardid,
				item.card.name if item.card is not None else
					item.token.get_description(),
				item.itemid, item.x, item.y)))
			if item.tapped:
				cmdlist.append(("tap", (item.itemid,)))
			if item.flipped:
				cmdlist.append(("flip", (item.itemid,)))
			if not item.faceup:
				cmdlist.append(("face", (item.itemid,)))
		return cmdlist
	
	def execute_command(self, cmd, *args):
		"""Execute a single network command"""
		if cmd == "reset":
			self.library = []
			self.hand = []
			self.graveyard = []
			self.exile = []
			self.set_life(config.DEFAULT_LIFE)
			for item in self.battlefield[:]:
				self.remove_carditem(item)
			
			self.updated_library()
			self.updated_hand()
			self.updated_graveyard()
			self.updated_exile()
		elif cmd == "tray":
			self.create_tray(args[0])
			self.tray.x = args[1]
			self.tray.y = args[2]
			self.tray.repaint()
		elif cmd == "update":
			self.library = [None] * args[0]
			self.hand = [None] * args[1]
			self.updated_library()
			self.updated_hand()
		elif cmd == "setlife":
			self.set_life(args[0])
		elif cmd == "enter":
			self.create_carditem(*args)
		elif cmd == "exit":
			item = self._get_item_by_id(args[0])
			if item is self.tray:
				self.remove_tray()
			else:
				self.remove_carditem(item)
		elif cmd == "bury":
			self.graveyard.append(cards.get(args[0]))
			self.updated_graveyard()
		elif cmd == "unbury":
			assert(args[0] < len(self.graveyard))
			i = args[0]
			self.graveyard[i:i+1] = []
			self.updated_graveyard()
		elif cmd == "exile":
			self.exile.append(cards.get(args[0]))
			self.updated_exile()
		elif cmd == "unexile":
			assert(args[0] < len(self.exile))
			i = args[0]
			self.exile[i:i+1] = []
			self.updated_exile()
		elif cmd == "mulligan":
			self.library.append(self.hand.pop())
			self.updated_library()
			self.updated_hand()
		elif cmd == "move":
			itemid, x, y = args
			item = self._get_item_by_id(itemid)
			if item is None:
				raise ValueError(_("Client sent unknown item id."))
			item.repaint()
			item.x = x
			item.y = y
			item.repaint()
		elif cmd == "tap":
			item = self._get_item_by_id(args[0])
			item.toggle_tapped()
		elif cmd == "flip":
			item = self._get_item_by_id(args[0])
			item.toggle_flipped()
		elif cmd == "face":
			item = self._get_item_by_id(args[0])
			item.turn_over()
		elif cmd == "counter":
			item = self._get_item_by_id(args[2])
			num, counter = args[0], args[1]
			if num != 0:
				item.counters[counter] = num
			elif counter in item.counters:
				del item.counters[counter]
	
	def handle_network_cmds(self, user, cmdlist):
		"""Handle an incoming network command"""
		cmd1, args1 = cmdlist[0]
		if cmd1 == "hello" and self.tray is not None:
			cmdlist = self.make_welcome_message()
			self.send_network_cmds(cmdlist, logged=False)
		
		# Other than hello only handle commands that concern this player's user
		if not user.same_as(self.user):
			return
		
		if cmd1 == "welcome":
			if self.has_been_welcomed:
				return # ignore welcome message
			else:
				self.has_been_welcomed = True
				# handle welcome updates
		try:
			# handle all other commands
			for cmd, args in cmdlist:
				self.execute_command(cmd, *args)
		except Exception as e:
			self.exception_handler(e)
	
	
	# Item ids
	
	def _get_item_by_id(self, itemid):
		"""Get an item on the battlefield by item id"""
		if itemid in self._items:
			return self._items[itemid]
		return None
	
	def _get_new_itemid(self, item):
		itemid = random.randint(0, config.MAX_ITEMID)
		while itemid in self._items:
			itemid = random.randint(0, config.MAX_ITEMID)
		self._items[itemid] = item
		return itemid
	
	def _set_itemid(self, itemid, item):
		if itemid in self._items:
			raise RuntimeError("%s has already registered a card %x." %
				(self.name, itemid))
		self._items[itemid] = item
		item.itemid = itemid




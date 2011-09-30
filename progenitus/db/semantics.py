# Written by TheGurke 2011
"""Understand some properties of the cards to offer convenience options"""

import re


_text_num = {"one":1, "two":2, "three":3, "four":4, "five":5, "six":6,
	"seven":7, "eight":8, "nine":9, "ten":10, "eleven":11, "twelve":12}

_re_num = re.compile(r'[\d]+')
_re_token = re.compile(r'[pP]ut an? (.*?) creature token onto the battlefield')
_counter1 = '%s enters the battlefield with ([\S]*?) (.*?) counters on it.'
_counter2 = '[pP]ut an? (.*?) counter on %s'


def init_carditem(item):
	"""Initialize a card item by setting some basic properties"""
	card = item.card
	assert(card is not None) # Can only understand cards, not tokens
	
	# Untap by default?
	if card.name + " doesn't untap during your untap step." in card.text:
		item.does_not_untap = True
	
	# Produce tokens?
	match = _re_token.findall(card.text)
	if match is not None:
		item.creates_tokens = match
	
	# Has counters?
	match = re.search(_counter1 % card.name, card.text)
	if match is not None:
		num, counter = match.groups()
		if num in _text_num:
			num = _text_num[num]
		elif _re_num.match(num) is not None:
			num = int(num)
		item.counters[counter] = num
	
	# Default counters
	match = re.search(_counter2 % card.name, card.text)
	if match is not None:
		item.default_counter = match.groups()[0]



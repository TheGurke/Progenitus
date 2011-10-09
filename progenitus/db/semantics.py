# Written by TheGurke 2011
"""Understand some properties of the cards to offer convenience options"""

import re


_text_num = {"one":1, "two":2, "three":3, "four":4, "five":5, "six":6,
	"seven":7, "eight":8, "nine":9, "ten":10, "eleven":11, "twelve":12}

_re_num = re.compile(r'[\d]+')
_re_token = re.compile(r'[pP]ut [\S]+ (.*?) creature tokens? (?:with .*?|)'
	'onto the battlefield')
_counter1 = '(?:%s|[tT]his [\S]+) enters the battlefield with ' \
	'([\S]*?) (.*?) counters on it.'
_counter2 = '[pP]ut an? (.*?) counter on (?:%s|this permanent)'


def init_carditem(item):
	"""Initialize a card item by setting some basic properties"""
	if not hasattr(item, "card") or item.card is None:
		if item.token is not None:
			if "Creature" in item.token.cardtype:
				item.default_counter = "+1/+1"
		return
	card = item.card
	assert(item.cardid is not None)
	
	# Untaps by default?
	if card.name + " doesn't untap during your untap step." in card.text:
		item.does_not_untap = True
	
	# Produces tokens?
	match = _re_token.findall(card.text)
	if match is not None:
		item.creates_tokens = match
#		print match
	
	# Has counters?
	match = re.search(_counter1 % card.name, card.text)
	if match is not None:
		num, counter = match.groups()
		if num in _text_num:
			num = _text_num[num]
		elif _re_num.match(num) is not None:
			num = int(num)
		else:
			num = 0
		item.controller.set_counter(item, num, counter)
	
	# Default counters
	if "Planeswalker" in card.cardtype:
		item.default_counter = "loyalty"
		if card.toughness != "":
			item.controller.set_counter(item, int(card.toughness), "loyalty")
	elif "LEVEL" in card.text:
		item.default_counter = "level"
		item.controller.set_counter(item, 0, "level")
	elif re.search(_counter2 % card.name, card.text) is not None:
		match = re.search(_counter2 % card.name, card.text)
		item.default_counter = match.groups()[0]
	elif "Creature" in card.cardtype:
		item.default_counter = "+1/+1"



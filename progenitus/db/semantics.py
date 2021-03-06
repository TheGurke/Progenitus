# Written by TheGurke 2011
"""Understand some properties of the cards to offer convenience options"""

import re


_text_num = {"one":1, "two":2, "three":3, "four":4, "five":5, "six":6,
	"seven":7, "eight":8, "nine":9, "ten":10, "eleven":11, "twelve":12}

_re_num = re.compile(r'[\d]+')
_re_token = re.compile(r'[pP]ut [\S]+ ([\S]+) creature tokens? (?:with .*?|)'
	'onto the battlefield')
_counter1 = '(?:%s|[tT]his [\S]+) enters the battlefield (?:tapped |)with ' \
	'([\S]*?) (.*?) counters on it.'
_counter2 = '[pP]ut an? ([\S]+) counter on (?:%s|this permanent)'
_counter3 = re.compile(r'(?:Vanishing|Fading|Suspend) ([\d]+)')
_tapped = ('(?:%s|[tT]his [\S]+) enters the battlefield tapped' +
	'(?:\.| with| unless)')


def init_carditem(item):
	"""Initialize a card item by setting some basic properties"""
	if not hasattr(item, "card") or item.card is None:
		if item.token is not None:
			if "Creature" in item.token.cardtype:
				item.default_counters.append("+1/+1")
				item.default_counters.append("-1/-1")
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
	
	# Default counters
	if "Planeswalker" in card.cardtype:
		item.default_counters.append("loyalty")
		if card.toughness != "":
			item.controller.set_counters(item, int(card.toughness), "loyalty")
	if "LEVEL" in card.text:
		item.default_counters.append("level")
		item.controller.set_counters(item, 0, "level")
	if re.search(_counter2 % card.name, card.text) is not None:
		match = re.search(_counter2 % card.name, card.text)
		item.default_counters.append(match.groups()[0])
	if "Creature" in card.cardtype:
		item.default_counters.append("+1/+1")
		item.default_counters.append("-1/-1")
	
	# Starts with counters?
	match = re.search(_counter1 % card.name, card.text)
	if match is not None:
		num, counter = match.groups()
		if num in _text_num:
			num = _text_num[num]
		elif _re_num.match(num) is not None:
			num = int(num)
		else:
			num = 0
		item.controller.set_counters(item, num, counter)
		if counter not in item.default_counters:
			item.default_counters.append(counter)
	match = _counter3.search(card.text)
	if match is not None:
		num = int(match.groups()[0])
		counter = "fade" if "Fading" in card.text else "time"
		item.controller.set_counters(item, num, counter)
		if counter not in item.default_counters:
			item.default_counters.append(counter)
	
	# Enters the battlefield tapped?
	match = re.search(_tapped % card.name, card.text)
	if match is not None:
		item.set_tapped(True)






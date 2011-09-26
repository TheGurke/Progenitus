# Written by TheGurke 2010
"""Remove unnecessary whitespaces from xml files"""

import sys
import os
import re

assert len(sys.argv) > 1
filename = sys.argv[1]
assert os.path.exists(filename)
assert os.path.isfile(filename)

with open(filename, 'r+') as f:
	data = f.read()
	data2 = re.sub(r'(<.*?>)[\s\n]*', r'\1', data)
	f.seek(0)
	f.truncate()
	f.write(data2)


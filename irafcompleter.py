"""irafcompleter.py: command-line completion for pyraf

Does taskname and filename completion using tab key.  Some of this
should be rewritten for Python 1.6, which will fix a bug in
the readline completion implementation and will add some
additional methods for getting information on the context
of the string being completed.  At the moment there are some
hacks to work around the missing functionality.

Another thought would be to use raw_input to do the input when IRAF
tasks prompt for input, and to use a special completer function that just
completes filenames (but knows about IRAF virtual filenames as well as
the native file system.)

See the notes in the (standard Python) module rlcompleter.py for more
information.

$Id$

RLW, 2000 February 13
"""

from rlcompleter import Completer
import readline
import __builtin__
import __main__
import string, re, keyword, glob, os
import iraf, minmatch

# dictionaries mapping between characters and readline names
char2lab = {}
lab2char = {}
for i in range(1,27):
	char = chr(i)
	ichar = chr(ord('a')+i-1)
	lab = "Control-%s" % ichar
	char2lab[char] = lab
	lab2char[lab] = char
	lab2char["Control-%s" % ichar] = char
	lab2char[r"\C-%s" % ichar] = char
char2lab["\t"] = "tab"
lab2char["tab"] = "\t"
char2lab["\033"] = "esc"
lab2char["esc"] = "\033"
lab2char["escape"] = "\033"
lab2char[r"\e"] = "\033"

# commands that take a taskname as argument
taskArgDict = minmatch.MinMatchDict({
				'unlearn': 1,
				'eparam': 1,
				'lparam': 1,
				'update': 1,
				'help': 1,
				'prcache': 1,
				'flprcache': 1,
				})

# commands that take a package name as argument
pkgArgDict = { '?': 1, }

class IrafCompleter(Completer):

	def __init__(self):
		self.completionChar = None
		self.taskpat = re.compile(r"(\?|(?:\w+))[ \t]+(?=$|[\w.<>|/~'" +r'"])')
		# executive commands dictionary (must be set by user)
		self.executiveDict = minmatch.MinMatchDict()

	def activate(self, char="\t"):
		"""Turn on completion using the specified character"""
		self.deactivate()
		lab = char2lab.get(char, char)
		if lab==char: char = lab2char.get(lab, lab)
		readline.set_completer(self.complete)
		readline.parse_and_bind("%s: complete" % lab)
		readline.parse_and_bind("set bell-style none")
		readline.parse_and_bind("set show-all-if-ambiguous")
		self.completionChar = char

	def deactivate(self):
		"""Turn off completion, restoring old behavior for character"""
		if self.completionChar:
			# restore normal behavior for previous completion character
			lab = lab2char.get(self.completionChar, self.completionChar)
			readline.parse_and_bind("%s: self-insert" % lab)
			self.completionChar = None

	def executive(self, elist):
		"""Add list of executive commands (assumed to start with '.')"""
		self.executiveDict = minmatch.MinMatchDict()
		for cmd in elist:
			self.executiveDict.add(cmd, 1)

	def global_matches(self, text):
		"""Compute matches when text is a simple name.

		Return a list of all keywords, built-in functions and names
		currently defined in __main__ that match.
		Also return IRAF task matches.
		"""
		line = self.get_line_buffer()
		# make tab insert blanks at the beginning of an empty line
		if line == "" and self.completionChar == "\t":
			# insert 4 spaces for tabs
			# Note that readline adds an additional blank
			#XXX is converting to blanks really a good idea?
			#XXX ought to allow user to change this mapping
			return ["   "]
		# if this is not the first token on the line, use a different
		# completion strategy
		#XXX once the index functions are available in readline (they tell
		#XXX exactly where this string came from), we can make completion
		#XXX work properly when the cursor is in the middle of a partially
		#XXX editted line.
		if line != text:
			return self.secondary_matches(text, line)
		else:
			return self.primary_matches(text)

	def get_line_buffer(self):
		"""Returns entire current line (with leading whitespace stripped)"""
		#XXX
		# Working around a nasty bug in readline.get_line_buffer
		# If I call readline.get_line_buffer() then a *later* command
		# aborts with
		#    TypeError: function requires no arguments
		# What I do here is deliberately go ahead and raise (and catch)
		# the exception.  This does seem to work, believe it or not.
		# Incredibly ugly though -- remove this as soon as the bug is
		# fixed (I see it was fixed in the CVS version of Python in
		# November 1999, so it should be in the next release.)
		#XXX
		try:
			line = string.lstrip(readline.get_line_buffer())
			raise TypeError
		except TypeError:
			pass
		return line

	def primary_matches(self, text):
		"""Return matches when text is at beginning of the line"""
		matches = []
		n = len(text)
		for list in [keyword.kwlist,
					 __builtin__.__dict__.keys(),
					 __main__.__dict__.keys()]:
			for word in list:
				if word[:n] == text:
					matches.append(word)
		# IRAF module functions
		matches.extend(iraf.getAllMatches(text))
		return matches

	def secondary_matches(self, text, line):
		"""Compute matches for tokens when not at start of line"""
		# Check first character following initial alphabetic string.
		# If next char is alphabetic (or null) use filename matches.
		# Also use filename matches if line starts with '!'.
		# Otherwise use matches from Python dictionaries.
		lt = len(line)-len(text)
		if line[:1] == "!":
			# Matching filename for OS escapes
			# Ideally would use tcsh-style matching of commands
			# as first argument, but that looks unreasonably hard
			return self.filename_matches(text, line[:lt])
		m = self.taskpat.match(line)
		if m is None or keyword.iskeyword(m.group(1)):
			if line[lt-1:lt] in ['"', "'"]:
				# use filename matches for quoted strings
				return self.filename_matches(text, line[:lt])
			else:
				return Completer.global_matches(self,text)
		else:
			taskname = m.group(1)
			# check for pipe/redirection using last non-blank character
			mpipe = re.search(r"[|><][ \t]*$", line[:lt])
			if mpipe:
				s = mpipe.group(0)
				if s[0] == "|":
					# pipe -- use task matches
					return iraf.getAllMatches(text)
				else:
					# redirection -- just match filenames
					return self.filename_matches(text, line[:lt])
			elif taskArgDict.has_key(taskname):
				# task takes task names as arguments
				return iraf.getAllTasks(text)
			elif pkgArgDict.has_key(taskname):
				# task takes package names as arguments
				return iraf.getAllPkgs(text)
			else:
				return self.argument_matches(text, taskname, line)

	def argument_matches(self, text, taskname, line):
		"""Compute matches for tokens that could be file or parameter names"""
		matches = []
		# only look at keywords if this one was whitespace-delimited
		# this avoids matching keywords after e.g. directory part of filename
		lt = len(line)-len(text)
		if line[lt-1:lt] in " \t":
			m = re.match(r"\w*$", text)
			if m is not None:
				# could be a parameter name
				task = iraf.getTask(taskname, found=1)
				# get all parameters that could match (null list if none)
				if task is not None: matches = task.getAllMatches(text)
		# add matching filenames
		matches.extend(self.filename_matches(text, line[:lt]))
		return matches

	def filename_matches(self, text, line):
		"""return matching filenames unless text contains wildcard characters"""
		if glob.has_magic(text): return []
		# look for IRAF virtual filenames
		#XXX This might be simplified if '$' and '/' were added to the set
		#XXX of characters permitted in words.  Can't do that now, as
		#XXX far as I can tell, but Python 1.6 should allow it.
		if line[-1] == '$':
			# preceded by IRAF environment variable
			m = re.search(r'\w*\$$', line)
			dir = iraf.Expand(m.group())
		elif line[-1] == os.sep:
			# filename is preceded by path separator
			# match filenames with letters, numbers, $, ~, . and directory
			# separator
			m = re.search(r'[\w.~$%s]*$' % os.sep, line)
			dir = iraf.Expand(m.group())
		else:
			dir = ''
		return self._dir_matches(text, dir)

	def _dir_matches(self, text, dir):
		"""Return list of files matching text in the given directory"""
		# note this works whether the expanded dir variable is
		# actually a directory (with a slash at the end) or not
		flist = glob.glob(dir + text + '*')
		def f(s, l=len(dir)):
			"""Strip path and append / to directories"""
			if os.path.isdir(s):
				return s[l:] + os.sep
			else:
				return s[l:]
		flist = map(f, flist)
		# If only a single directory matches, get a list of the files
		# in the directory too.  This has the side benefit of suppressing
		# the extra space added to the name by readline.
		if len(flist)==1 and flist[0][-1] == os.sep:
			return self._dir_matches(flist[0], dir)
		else:
			return flist

	def attr_matches(self, text):
		"""Compute matches when text contains a dot."""
		line = self.get_line_buffer()
		if line == text:
			# at start of line, special handling for iraf.xxx and
			# taskname.xxx
			fields = string.split(text,".")
			if fields[0] == "":
				# line starts with dot, look in executive commands
				return self.executive_matches(text)
			elif fields[0] == "iraf":
				return self.taskdot_matches(fields)
			elif iraf.getTask(fields[0], found=1):
				# include both eval results and task. matches
				fields.insert(0, 'iraf')
				matches = self.taskdot_matches(fields)
				try:
					matches.extend(Completer.attr_matches(self,text))
				except:
					pass
				return matches
			else:
				return Completer.attr_matches(self,text)
		else:
			# Check first character following initial alphabetic string
			# If next char is alphabetic (or null) use filename matches
			# Otherwise use matches from Python dictionaries
			#XXX need to make this consistent with the other places
			#XXX where same tests are done
			m = self.taskpat.match(line)
			if m is None or keyword.iskeyword(m.group(1)):
				fields = string.split(text,".")
				if fields[0] == "iraf":
					return self.taskdot_matches(fields)
				else:
					return Completer.attr_matches(self,text)
			else:
				#XXX Could try to match pset.param keywords too?
				lt = len(line)-len(text)
				return self.filename_matches(text, line[:lt])

	def executive_matches(self, text):
		"""Return matches to executive commands"""
		return self.executiveDict.getallkeys(text)

	def taskdot_matches(self, fields):
		"""Return matches for iraf.package.task.param..."""
		head = string.join(fields[:-1],".")
		tail = fields[-1]
		matches = eval("%s.getAllMatches(%s)" % (head, `tail`))
		def addhead(s, head=head+"."): return head+s
		return map(addhead, matches)

completer = IrafCompleter()

def activate(c="\t"):
	completer.activate(c)

def deactivate():
	completer.deactivate()

# turn on completion on import
activate()

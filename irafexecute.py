"""Module contains functions to allow the execution of IRAF connected
subprocesses

$Id$
"""

import os, re, signal, string, struct, sys, time
import subproc
import gki
import gkiopengl
import gwm
import iraf

# for debugging purposes (for generating a tk window for listing
# subprocess communication events
monitor = 0
monwidget = None
if monitor and (monwidget == None):
	import irafmonitor, StringIO
	monwidget = irafmonitor.IRAFmonitor()

stdgraph = None

class IrafProcessError(Exception):
	pass

def IrafExecute(task, envdict):

	"""Execute IRAF task (defined by the IrafTask object task)
	using the provided envionmental variables.  The IrafTask object
	must have these methods:

	getName(): return the name of the task
	getFullpath(): return the full path name of the executable
	getParam(param): get parameter value
	setParam(param,value): set parameter value
	"""

	# Start'er up
	try:
		executable = task.getFullpath()
		process = subproc.Subprocess(executable+' -c')
	except (iraf.IrafError, subproc.SubprocessError), value:
		raise IrafProcessError("problems starting IRAF executable\n" + value)

	try:
		keys = envdict.keys()
		if len(keys) > 0:
			# write environment variables in one big block
			outenvstr = len(keys)*[""]
			for i in xrange(len(keys)):
				outenvstr[i] = "set "+keys[i]+"="+envdict[keys[i]]+"\n"
			WriteStringToIrafProc(process, string.join(outenvstr,""))
		# terminate set up mode
		WriteStringToIrafProc(process,'_go_\n')
		# start IRAF logical task
		WriteStringToIrafProc(process,task.getName()+'\n')
		# begin slave mode
		IrafIO(process,task)
		# kill the damn thing, process caches are for weenies
		IrafTerminate(process)
	except KeyboardInterrupt:
		# On keyboard interrupt (^c), kill the subprocess
		IrafKill(process)
	except (iraf.IrafError, IrafProcessError), exc:
		# on error, kill the subprocess, then re-raise the original exception
		try:
			IrafKill(process)
		except Exception, exc2:
			# append new exception text to previous one (right thing to do?)
			exc.args = exc.args + exc2.args
		raise exc
	return

_re_chan_len = re.compile(r'\((\d+),(\d+)\)\n')
_re_paramset = re.compile(r'([a-zA-Z_][a-zA-Z0-9_.]*)\s*=\s*(.*)\n')
_re_paramrequest = re.compile(r'=([a-zA-Z_$][a-zA-Z0-9_.]*)\n')

def IrafIO(process,task):

	"""Talk to the IRAF process in slave mode. Raises an IrafProcessError
	if an error occurs."""

	global stdgraph
	msg = ''
	xferline = ''
	while 1:
		# each read may return multiple lines; only
		# read new data when old has been used up
		if not msg:
			data = ReadFromIrafProc(process)
			msg = Iraf2AscString(data)
		if msg[0:4] == 'bye\n':
			return
		elif msg[0:5] == "ERROR" or msg[0:5] == 'error':
			raise IrafProcessError("IRAF task terminated abnormally\n" + msg)
		elif msg[0:4] == 'xmit':
			mo = _re_chan_len.match(msg,4)
			if not mo:
				raise IrafProcessError("Illegal xmit command format\n" + msg)
			chan = int(mo.group(1))
			nbytes = int(mo.group(2))
			# this must always be the last command in a message
			msg = msg[mo.end():]
			if msg: raise IrafProcessError("Bad xmit: " +
					`len(msg)` + " bytes follow request")
			xdata = ReadFromIrafProc(process)
			if len(xdata) != 2*nbytes:
				raise IrafProcessError("Error, wrong number of bytes read\n" +
					("(got %d, expected %d, chan %d)" %
						(len(xdata), 2*nbytes, chan)))
			else:
				if chan == 4:
					print Iraf2AscString(xdata),
				elif chan == 5:
					sys.stderr.write(Iraf2AscString(xdata))
				elif chan == 6:
					print "data for STDGRAPH"
					stdgraph.append(Numeric.fromstring(xdata,'s'))
				elif chan == 7:
					print "data for STDIMAGE"
				elif chan == 8:
					print "data for STDPLOT"
				elif chan == 9:
					print "data for PSIOCNTRL"
					sdata = Numeric.fromstring(xdata,'s')
					forChan = sdata[1] # a bit sloppy here
					print forChan
					if forChan == 6:
						# STDPLOT control
						# first see if OPENWS to get device, otherwise
						# pass through to current kernel, use braindead
						# interpetation to look for openws 
						if (sdata[2] == -1) and (sdata[3] == 1):
							print "openws for stdgraph"
							length = sdata[4]
							device = sdata[5:length+2].astype('b').tostring()
							# but of course, for the time being (until
							# we manage another graphics kernel, we ignore
							# device!
							if stdgraph == None:
								stdgraph = gkiopengl.GkiOpenGlKernel()
						
						# pass it to the kernel to deal with
						stdgraph.control(sdata[2:])
 					else:
						print "GRAPHICS control data for channel",forChan
						
#						print adata[0:10]
#						oldstdout = sys.stdout
#						sys.stdout = StringIO.StringIO()
#						gkistr = sys.stdout.getvalue()
#						monwidget.append(gkistr)
#						sys.stdout.close()
#						sys.stdout = oldstdout
				else:
					print "data for channel", chan
		elif msg[0:4] == 'xfer':
			mo = _re_chan_len.match(msg,4)
			if not mo:
				raise IrafProcessError("Illegal xfer command format\n" + msg)
			chan = int(mo.group(1))
			nbytes = int(mo.group(2))
			if chan == 3:
				# Flush output to make sure prompts without newlines appear
				sys.stdout.flush()

				# Read a line from stdin unless xferline already has
				# some untransmitted data from a previous read

				if not xferline: xferline = sys.stdin.readline()

				# Send two messages, the first with the number of characters
				# in the line and the second with the line itself.
				# For very long lines, may need multiple messages.  Task
				# will keep sending xfer requests until it gets the
				# newline.

				nchars = nbytes/2
				lsection = xferline[:nchars]
				WriteStringToIrafProc(process, str(len(lsection)))
				WriteStringToIrafProc(process, lsection)
				xferline = xferline[nchars:]
			else:
				raise IrafProcessError("xfer request for unknown channel " +
					msg)
			# this must always be the last command in a message
			msg = msg[mo.end():]
			if msg: raise IrafProcessError("Bad xfer: " +
					`len(msg)` + " bytes follow request")
		elif msg[0] == '=':
			# parameter get request
			mo = _re_paramrequest.match(msg)
			if mo:
				paramname = mo.group(1)
				WriteStringToIrafProc(process, task.getParam(paramname) + '\n')
				msg = msg[mo.end():]
			else:
				raise IrafProcessError("Bad parameter request from task: " +
					msg)
		else:
			# last possibility: set value of parameter
			mo = _re_paramset.match(msg)
			if mo:
				msg = msg[mo.end():]
				paramname, newvalue = mo.groups()
				task.setParam(paramname,newvalue)
			else:
				print "Warning, unrecognized IRAF pipe protocol"
				print msg

def IrafKill(process):
	"""Try stopping process in IRAF approved way first; if that fails
	blow it away. Copied with minor mods from subproc.py."""

	if not process.pid: return		# no need, process gone

	print " Killing IRAF task"
	if not process.cont():
		raise IrafProcessError("Can't kill IRAF subprocess")
	# get the task's attention for input
	try:
		os.kill(process.pid, signal.SIGTERM)
	except os.error:
		pass
	IrafTerminate(process)

def IrafTerminate(process):
	"""Standard IRAF task termination (assuming we already have the task's
	attention for input.)"""

	# Send bye message to task
	# Wait briefly for EOF, which signals task is done
	# Kill it anyway if it is still hanging around

	if process.pid:
		WriteStringToIrafProc(process,"bye\n")
		if not process.wait(0.5): process.die()

# IRAF string conversions using Numeric module
import Numeric

def Asc2IrafString(ascii_string):
	"""translate ascii to IRAF 16-bit string format"""
	inarr = Numeric.fromstring(ascii_string, Numeric.Int8)
	return inarr.astype(Numeric.Int16).tostring()

def Iraf2AscString(iraf_string):
	"""translate 16-bit IRAF characters to ascii"""
	inarr = Numeric.fromstring(iraf_string, Numeric.Int16)
	return inarr.astype(Numeric.Int8).tostring()

def WriteStringToIrafProc(process, astring):

	"""convert ascii string to IRAF form and write to IRAF process"""

	WriteToIrafProc(process, Asc2IrafString(astring))

def WriteToIrafProc(process, data):

	"""write binary data to IRAF process in blocks of <= 4096 bytes"""

	i = 0
	block = 4096
	while i<len(data):
		dsection = data[i:i+block]
		#     IRAF magic number    number of following bytes      data
		process.write('\002\120'+struct.pack('>h',len(dsection))+dsection)
		i = i + block

def ReadFromIrafProc(process):
	
	"""read input from IRAF pipe"""
	
	# read pipe header first
	header = process.read(4)
	if (header[0:2] != '\002\120'):
		raise IrafProcessError("Not a legal IRAF pipe record")
	ntemp = struct.unpack('>h',header[2:])
	nbytes = ntemp[0]
	# read the rest
	data = process.read(nbytes)
	return data

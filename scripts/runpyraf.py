#! python
"""
Copyright (C) 2003 Association of Universities for Research in Astronomy
(AURA)
See LICENSE.txt in the docs directory of the source distribution for the 
terms of use.

Usage: pyraf [options] [savefile]

where savefile is an optional save file to start from and options are one
or more of:
  -c cmd  Command passed in as string (any valid PyRAF command)
  -e      Turn on ECL mode
  -h      Print this message
  -i      No command line wrapper, just run standard interactive Python shell
  -m      Run command line wrapper to provide extra capabilities (default)
  -n      No splash screen during startup
  -s      Silent initialization (does not print startup messages)
  -v      Set verbosity level (may be repeated to increase verbosity)
  -y      Run the IPython shell instead of the normal PyRAF command shell

Long versions of options:
  -c  --comand=<cmd>
  -e  --ecl
  -h  --help
  -i  --commandwrapper=no
  -m  --commandwrapper=yes
  -n  --nosplash
  -s  --silent
  -v  --verbose
  -y  --ipython
"""

# $Id: pyraf 1472 2011-07-13 17:32:30Z sontag $
#
# R. White, 2000 January 21

from __future__ import division
import sys, os, shutil

# set search path to include directory above this script and current directory
# ... but do not want the pyraf package directory itself in the path, since
# that messes things up by allowing direct imports of pyraf submodules
# (bypassing the __init__ mechanism.)

# follow links to get to the real executable filename
executable = sys.argv[0]
while os.path.islink(executable):
    executable = os.readlink(executable)
pyrafDir = os.path.dirname(executable)
del executable
try:
    sys.path.remove(pyrafDir)
except ValueError:
    pass
del pyrafDir

if "." not in sys.path: sys.path.insert(0, ".")

# allow the use of PYRAF_ARGS
extraArgs = os.getenv('PYRAF_ARGS', '').strip()
extraArgsList = [x for x in extraArgs.split(' ') if len(x)]
if len(extraArgsList):
    sys.argv.extend(extraArgsList)
x = None
del extraArgs, extraArgsList, x

# handle any warning supression right away, before any more imports
if '-s' in sys.argv or '--silent' in sys.argv:
    import warnings
    warnings.simplefilter("ignore")
    del warnings

# read the user's startup file (if there is one)
if 'PYTHONSTARTUP' in os.environ and \
                os.path.isfile(os.environ["PYTHONSTARTUP"]):
    exec(compile(open(os.environ["PYTHONSTARTUP"]).read(), os.environ["PYTHONSTARTUP"], 'exec'))

# In next line we get into pyraf's __init__.py - this does ALL KINDS OF THINGS
from pyraf import doCmdline, _use_ipython_shell, runCmd, __version__
# By now, the bulk of the startup work is done
from pyraf import iraf
from pyraf.irafpar import makeIrafPar
from stsci.tools.irafglobals import yes, no, INDEF, EOF
logout = quit = exit = 'Use ".exit" to exit'

# IPython Pyraf profile RC installation
if _use_ipython_shell:
    import pyraf
    home = None
    ip = os.getenv("IPYTHONDIR")
    if not ip:
        home = os.getenv("HOME") or ""
        ip = os.path.join(home, ".ipython")

    pyrafrc_dest = os.path.join(ip,"ipythonrc-pyraf")
    pyrafrc_source = os.path.join(os.path.split(pyraf.__file__)[0],
                                  "ipythonrc-pyraf")
    if os.path.exists(ip):
        if not os.path.exists(pyrafrc_dest):
            shutil.copy(pyrafrc_source, pyrafrc_dest)
    else:
        os.mkdir(ip)
        shutil.copy(pyrafrc_source, pyrafrc_dest)
    del pyraf, home, ip, pyrafrc_dest, pyrafrc_source
else:
    if '-s' not in sys.argv and '--silent' not in sys.argv:
       print("PyRAF"+' '+__version__+' '+"Copyright (c) 2002 AURA")
       # just print first line of Python copyright (long in v2.0)
       print("Python"+' '+sys.version.split()[0]+' '+sys.copyright.split('\n')[0])

# Run given command
if runCmd:
    iraf.task(cmd_line=runCmd, IsCmdString=1)
    iraf.cmd_line()
    sys.exit()
else:
    del runCmd

# Start command line
if doCmdline:
    del doCmdline
    # Start up command line wrapper keeping definitions in main name space
    # Keep the command-line object in namespace too for access to history
    if _use_ipython_shell:
        import sys
        import IPython
        if '-s' in sys.argv or '--silent' in sys.argv:
           sys.argv = ["ipython","-nobanner","-p","pyraf"]
        else:
           sys.argv = ["ipython","-p","pyraf"]
        IPython.Shell.start(user_ns=globals()).mainloop()
        sys.exit()
    else:
        import pyraf.pycmdline
        del _use_ipython_shell
        _pycmdline = pyraf.pycmdline.PyCmdLine(locals=globals())
        if '-s' in sys.argv or '--silent' in sys.argv:
           _pycmdline.start('') # use no banner
        else:
           _pycmdline.start() # use default banner
else:
    del doCmdline
    # run the standard Python interpreter
    import code
    code.interact(local=locals())
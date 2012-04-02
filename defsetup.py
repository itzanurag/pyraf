#!/usr/bin/env python
from __future__ import division # confidence high

import os, os.path, shutil, sys, commands
import distutils.core
import distutils.sysconfig
import string

x_libraries = 'X11'

add_lib_dirs = [ distutils.sysconfig.get_python_lib(plat_specific=1, standard_lib = 1) ]

add_inc_dirs = [ distutils.sysconfig.get_python_inc(plat_specific=1) ]



def find_x(xdir=""):
    if xdir != "":
        add_lib_dirs.append(os.path.join(xdir,'lib64'))
        add_lib_dirs.append(os.path.join(xdir,'lib'))
        add_inc_dirs.append(os.path.join(xdir,'include'))
    elif sys.platform == 'darwin' or sys.platform.startswith('linux'):
        add_lib_dirs.append('/usr/X11R6/lib64')
        add_lib_dirs.append('/usr/X11R6/lib')
        add_inc_dirs.append('/usr/X11R6/include')
    elif sys.platform == 'sunos5' :
        add_lib_dirs.append('/usr/openwin/lib')
        add_inc_dirs.append('/usr/openwin/include')
    else:
        try:
            import Tkinter
        except:
            raise ImportError("Tkinter is not installed")
        tk=Tkinter.Tk()
        tk.withdraw()
        tcl_lib = os.path.join((tk.getvar('tcl_library')), '../')
        tcl_inc = os.path.join((tk.getvar('tcl_library')), '../../include')
        tk_lib = os.path.join((tk.getvar('tk_library')), '../')
        tkv = str(Tkinter.TkVersion)[:3]
        # yes, the version number of Tkinter really is a float...
        if Tkinter.TkVersion < 8.3:
            print "Tcl/Tk v8.3 or later required\n"
            sys.exit(1)
        else:
            suffix = '.so'
            tklib='libtk'+tkv+suffix
            command = "ldd %s" % (os.path.join(tk_lib, tklib))
            lib_list = string.split(commands.getoutput(command))
            for lib in lib_list:
                if string.find(lib, 'libX11') == 0:
                    ind = lib_list.index(lib)
                    add_lib_dirs.append(os.path.dirname(lib_list[ind + 2]))
                    #break
                    add_inc_dirs.append(os.path.join(os.path.dirname(lib_list[ind + 2]), '../include'))

if not sys.platform.startswith('win'):
    find_x()

def dir_clean(list) :
    # We have a list of directories.  Remove any that don't exist.
    r = [ ]
    for x in list :
        if os.path.isdir(x) :
            r.append(x)
    return r

add_lib_dirs = dir_clean(add_lib_dirs)
add_inc_dirs = dir_clean(add_inc_dirs)

PYRAF_EXTENSIONS=[distutils.core.Extension('pyraf.sscanfmodule', ['src/sscanfmodule.c'],
                      include_dirs=add_inc_dirs),
                  distutils.core.Extension('pyraf.xutilmodule',['src/xutil.c'],
                      include_dirs=add_inc_dirs,
                      library_dirs=add_lib_dirs,
                      libraries = [x_libraries])]

pkg = "pyraf"

if 0 and sys.platform.startswith('win'):
    PYRAF_EXTENSIONS = []
    # Install main "runpyraf.py"
    if not os.path.exists('wintmp'):
        os.mkdir('wintmp')
    if os.path.exists('wintmp'+os.sep+'runpyraf.py'):
        os.remove('wintmp'+os.sep+'runpyraf.py')
    if os.path.exists("pyraf") :
        shutil.copy('pyraf\\scripts'+os.sep+'pyraf', 'wintmp'+os.sep+'runpyraf.py')
    else :
        shutil.copy('scripts'+os.sep+'pyraf', 'wintmp'+os.sep+'runpyraf.py')
    
    # Install optional launcher onto desktop
    if 'USERPROFILE' in os.environ:
       dtop = os.environ['USERPROFILE']+os.sep+'Desktop'
       if os.path.exists(dtop):
           shortcut = dtop+os.sep+"PyRAF.bat"
           if os.path.exists(shortcut):
               os.remove(shortcut)
           target = sys.exec_prefix+os.sep+"Scripts"+os.sep+"runpyraf.py"
           f = open(shortcut, 'w')
           f.write('@echo off\necho.\ncd %APPDATA%\n')
           f.write('echo Launching PyRAF ...\necho.\n')
           f.write(target)
           f.write('\necho.\npause\n')
           f.close()
           print('Installing PyRAF.bat to -> '+dtop)
       else:
           print('Error: User desktop not found at: '+dtop)
    else:
       print('Error: User desktop location unknown')

    # NOTE: a much better solution would be to use something (bdist) to 
    # create installer binaries for Windows, since they are: 1) easier on
    # the win user, and 2) can be used to create actual desktop shortcuts,
    # not this kludgy .bat file.  If we take out the two libraries built
    # from the bdist run (which aren't used on Win anyway) then we can
    # automate this build from Linux (yes, for Windows), via:
    #    python setup.py bdist_wininst --no-target-compile --plat-name=win32
    # and
    #    python setup.py bdist_wininst --no-target-compile --plat-name=win-amd64
    # We would need to provide both 32- and 64-bit versions since the
    # installer will fail gracelessly if you try to install one and the Win
    # node only has the other (listed in its registry).  The above 64-bit bdist
    # fails currently on thor but the 32-bit bdist works.  Need to investigate.

    # Another option to create the shortcut is to bundle win32com w/ installer.


DATA_FILES = [ ( pkg,
                    ['data/blankcursor.xbm',
                    'data/epar.optionDB',
                    'data/pyraflogo_rgb_web.gif',
                    'data/ipythonrc-pyraf',
                    'LICENSE.txt',
                    ]
                ),
                (pkg+'/clcache',  [ "data/clcache/*" ] )
        ]


setupargs = {
    'version' :			    "1.x", # see lib's __init__.py
    'description' :		    "A Python based CL for IRAF",
    'author' :			    "Rick White, Perry Greenfield",
    'maintainer_email' :	"help@stsci.edu",
    'url' :			        "http://www.stsci.edu/resources/software_hardware/pyraf",
    'license' :			    "http://www.stsci.edu/resources/software_hardware/pyraf/LICENSE",
    'platforms' :			["unix"],
    'data_files' :			DATA_FILES,
    'scripts' :			    ['scripts/pyraf', 'scripts/pyraf.bat'],
    'ext_modules' :			PYRAF_EXTENSIONS,
    'package_dir' :         { 'pyraf' : 'lib/pyraf' },
}


if 0 and sys.platform.startswith('win'):
    setupargs['scripts'] = ['wintmp/runpyraf.py', 'scripts/pyraf.bat']

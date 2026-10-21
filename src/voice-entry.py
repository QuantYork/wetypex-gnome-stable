#!/usr/bin/python3
import os,pathlib,sys
os.environ.pop('LD_PRELOAD',None)
p=pathlib.Path.home()/'.local/lib/wetypex-gnome-stable/voice-supervisor.py'
os.execv('/usr/bin/python3',['/usr/bin/python3',str(p),*sys.argv[1:]])

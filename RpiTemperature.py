#!/usr/bin/env python

from dbus.mainloop.glib import DBusGMainLoop
import sys
if sys.version_info.major == 2:
    import gobject
    from gobject import idle_add
else:
    from gi.repository import GLib as gobject
import dbus
import platform
from threading import Timer
import logging
import os

from pprint import pprint

# our own packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-modem'))
from vedbus import VeDbusService, VeDbusItemExport, VeDbusItemImport 
from settingsdevice import SettingsDevice  # available in the velib_python repository

dbusservice = None

def update():
     update_rpi()
     return True

#   update Pi CPU temperature 
def update_rpi():
    if not os.path.exists('/sys/devices/virtual/thermal/thermal_zone0/temp'):
        if dbus_cpu_service['/Connected'] != 0:
            logging.info("cpu temperature interface disconnected")
            dbus_cpu_service['/Connected'] = 0
    else:
        if dbus_cpu_service['/Connected'] != 1:
            logging.info("cpu temperature interface connected")
            dbus_cpu_service['/Connected'] = 1
        fd  = open('/sys/devices/virtual/thermal/thermal_zone0/temp','r')
        value = float(fd.read())
        value = round(value / 1000.0, 1)
        dbus_cpu_service['/Temperature'] = value 
        fd.close

#  No setting interface for Rpi CPU temperature
# =========================== end of settings interface ======================

class SystemBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SYSTEM)

class SessionBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SESSION)

def dbusconnection():
    return SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else SystemBus()


def getrevision():
  # Extract board revision from cpuinfo file
  myrevision = "0000"
  try:
    f = open('/proc/cpuinfo','r')
    for line in f:
      if line[0:8]=='Revision':
        length=len(line)
        myrevision = line[11:length-1]
    f.close()
  except:
    myrevision = "0000"

  return myrevision

# Argument parsing removed from source as never used 
class args: pass
args.debug = False
#args.debug = True

# Init logging
logging.basicConfig(level=(logging.DEBUG if args.debug else logging.INFO))
logging.info(__file__ + " is starting up")
logLevel = {0: 'NOTSET', 10: 'DEBUG', 20: 'INFO', 30: 'WARNING', 40: 'ERROR'}
logging.info('Loglevel set to ' + logLevel[logging.getLogger().getEffectiveLevel()])

# Have a mainloop, so we can send/receive asynchronous calls to and from dbus
DBusGMainLoop(set_as_default=True)

def new_service(base, type, physical, logical, id, instance, settingId = False):
    self =  VeDbusService("{}.{}.{}{:02d}".format(base, type, physical,  id), dbusconnection())
    # physical is the physical connection 
    # logical is the logical connection to allign with the numbering of the console display
    # Create the management objects, as specified in the ccgx dbus-api document
    self.add_path('/Mgmt/ProcessName', __file__)
    self.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self.add_path('/Mgmt/Connection', logical)

    # Create the mandatory objects, note these may need to be customised after object creation
    self.add_path('/DeviceInstance', instance)
    self.add_path('/ProductId', 0)
    self.add_path('/ProductName', '')
    self.add_path('/FirmwareVersion', platform.system())
    self.add_path('/HardwareVersion', getrevision())
    self.add_path('/Connected', 0)  # Mark devices as disconnected until they are confirmed

    # Create device type specific objects set values to empty until connected
    if type == 'temperature':
        self.add_path('/Temperature', [])
       	self.add_path('/Status', 0)
       	self.add_path('/TemperatureType', 2 )
        self.add_path('/CustomName', '', writeable=True, onchangecallback = lambda x,y: handle_changed_value(setting,x,y) )
        self.add_path('/Function', 1, writeable=True )

    return self

#dbusservice = {} # Dictionary to hold the multiple services

base = 'com.victronenergy'

# service defined by (base*, type*, connection*, logial, id*, instance, settings ID):
# Items marked with a (*) are included in the service name
#

dbus_cpu_service   = new_service(base, 'temperature', 'Rpi-cpu',  'Raspberry Pi OS',  6, 29)

# Tidy up custom or missing items
dbus_cpu_service['/ProductName']     = 'Raspberry Pi'
dbus_cpu_service['/CustomName']     = 'CPU Temperature'

# Do a first update so that all the readings appear.
update()
# update every 10 seconds - temperature and humidity should move slowly so no need to demand
# too much CPU time
#
gobject.timeout_add(10000, update)

print('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
mainloop = gobject.MainLoop()
mainloop.run()

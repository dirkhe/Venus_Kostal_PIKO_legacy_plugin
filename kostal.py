#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

from configparser import ConfigParser


from dbus_inverter import DbusInverter

from dbus.mainloop.glib import DBusGMainLoop

from gi.repository import GLib

import sys
import threading
import time
import os

from kostalSocketDataService import KostalSocket, DevState

global inverter
global dbus_inverter

def push_statistics():
    global dbus_inverter
    dbus_inverter.set('/stats/connection_error', inverter.stats.connection_errors)
    dbus_inverter.set('/stats/last_connection_errors', inverter.stats.last_connection_errors)
    dbus_inverter.set('/stats/reconnect', inverter.stats.reconnect)
    dbus_inverter.set('/Mgmt/intervall',inverter.interval)


def parse_config():
    global inverter
    parser = ConfigParser()
    cfgname = 'kostal.ini'
    if len(sys.argv) > 1:
        cfgname = str(sys.argv[1])
    logging.debug('Parsing config: ' + cfgname)
    parser.read(cfgname)

    if len(parser.sections()) == 0:
        logging.error("config seems to be empty...")
        exit(1)

    # Get logging level from config
    if "DEFAULT" in parser:
        if "logging" in parser["DEFAULT"]:
            print("Logging level set to " + parser["DEFAULT"]["logging"])
            if parser["DEFAULT"]["logging"] == "DEBUG":
                logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelnames)s - %(message)s')
            elif parser["DEFAULT"]["logging"] == "INFO":
                logging.basicConfig(level=logging.INFO)
            elif parser["DEFAULT"]["logging"] == "ERROR":
                logging.basicConfig(level=logging.ERROR)
            else:
                logging.basicConfig(level=logging.WARNING)
        else:
            logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelnames)s - %(message)s')
        if "timezone" in parser["DEFAULT"]:
            os.environ['TZ'] = parser["DEFAULT"]["timezone"]
            time.tzset()
            logging.info('Timezone set to ' + parser["DEFAULT"]["timezone"])
            #print('Timezone set to ' + parser["DEFAULT"]["timezone"])
            #print(time.strftime('%X %x %Z'))

    def get_host(section):
        if parser.has_option(section, 'host'):
            return parser.get(section, 'host')
        else:
            logging.error('config section ' + section + ' is missing the host..')
            exit(1)

    def get_port(section):
        if parser.has_option(section, 'port'):
            return parser.get(section, 'port')
        else:
            logging.error('config section ' + section + ' is missing the port..')
            exit(1)            

    def get_addr(section):
        if parser.has_option(section, 'busAddr'):
            return parser.get(section, 'busAddr')
        else:
            logging.debug('config section ' + section + ' is missing the busAddr, useing default 255...')   
            return 255
     
    def get_interval(section):
        if parser.has_option(section, 'interval'):
            return int(parser.get(section, 'interval'))
        else:
            logging.error('config section ' + section + ' is missing the interval..')
            exit(1)

    def get_instance(section):
        if parser.has_option(section, 'instance'):
            return int(parser.get(section, 'instance'))
        else:
            logging.debug('config section ' + section + ' is missing the instance, using default 50...')
            return 50

    def get_position(section):
        if parser.has_option(section, 'position'):
            return int(parser.get(section, 'position'))
        else:
            logging.debug('config section ' + section + ' is missing the position, using default 0...')
            return 0

    section = 'INVERTER'
    if parser.has_section(section) == False:
        logging.error('config seems to be missing the INVERTER section...')
        exit(1)

    inverter = KostalSocket(get_host(section), get_port(section), get_addr(section), get_instance(section), get_interval(section),
                      get_position(section))


def set_dbus_data(data):
    global inverter,dbus_inverter
   
    curTime = time.time()
    time_ms = int(round(curTime * 1000))
    if inverter.stats.last_time == time_ms:
        dbus_inverter.inc('/stats/repeated_values')
        dbus_inverter.inc('/stats/last_repeated_values')
        logging.debug('got repeated value')
    else:
        inverter.stats.last_time = time_ms
        dbus_inverter.set('/stats/last_repeated_values', 0)
        #print(time.strftime('%X %x %Z'))
        #time.tzset()
        dbus_inverter.set('/stats/last_time', time.strftime("%H:%M:%S", time.localtime(curTime)))
        
        dbus_inverter.set('/StatusCode', (data['status']))
        #dbus_inverter.set('/Error', (data['Error']))
        dbus_inverter.set('/Connected', 1 if inverter.dev_state == DevState.Connected else 0)
        

        if 'PT' in data:
            dbus_inverter.set('/Ac/Power', (data['PT']))
            #dbus_inverter.set('/Ac/Current', (data['IN0']), 1)
            dbus_inverter.set('/Ac/L1/Current', (data['IA']), 1)
            dbus_inverter.set('/Ac/L1/Voltage', (data['VA']))
            dbus_inverter.set('/Ac/L1/Power', (data['PA']))
            dbus_inverter.set('/Ac/L2/Current', (data['IB']), 1)
            dbus_inverter.set('/Ac/L2/Voltage', (data['VB']))
            dbus_inverter.set('/Ac/L2/Power', (data['PB']))
            dbus_inverter.set('/Ac/L3/Current', (data['IC']), 1)
            dbus_inverter.set('/Ac/L3/Voltage', (data['VC']))
            dbus_inverter.set('/Ac/L3/Power', (data['PC']))
            dbus_inverter.set('/Ac/Energy/Forward', (data['EFAT']))

        #logging.debug("++++++++++")
        #logging.debug("POWER Phase A: " + str(data['PA']) + "W")
        #logging.debug("POWER Phase B: " + str(data['PB']) + "W")
        #logging.debug("POWER Phase C: " + str(data['PC']) + "W")
        #logging.debug("POWER Total: " + str(data['PT']) + "W")


def init_dbus():
    global dbus_inverter
    dbus_inverter = DbusInverter(inverter.inverter_name, inverter.host, inverter.instance,
                                          '0',
                                          inverter.model,
                                          inverter.sw_version, '0.1', inverter.position)
    return


def read_data():
    global inverter
    try:
        #logging.debug('reading data from ', inverter.model + ' inverter at ' + inverter.host)
        set_dbus_data(inverter.getData())
        return
    except ():
        logging.error('Error reading from ' + inverter.host)
        inverter.stats.connection_errors += 1
        inverter.stats.last_connection_errors += 1
        return 1


def cyclic_update(run_event):
    global inverter, dbus_inverter

    while run_event.is_set():
        #logging.debug("Thread: doing")
        if inverter.stats.last_connection_errors > inverter.max_retries:
            logging.warning('Lost connection to kostal, reset and wait 5 MInutes before retry')
            inverter.disconnect()
            dbus_inverter.set('/Connected', 0)
            dbus_inverter.set('/Ac/L1/Current', None)
            dbus_inverter.set('/Ac/L2/Current', None)
            dbus_inverter.set('/Ac/L3/Current', None)
            dbus_inverter.set('/Ac/L1/Power', None)
            dbus_inverter.set('/Ac/L2/Power', None)
            dbus_inverter.set('/Ac/L3/Power', None)
            dbus_inverter.set('/Ac/L1/Voltage', None)
            dbus_inverter.set('/Ac/L2/Voltage', None)
            dbus_inverter.set('/Ac/L3/Voltage', None)
            dbus_inverter.set('/Ac/Power', None)
            #dbus_inverter.set('/Ac/Current', None)
            #dbus_inverter.set('/Ac/Voltage', None)
            time.sleep(5*60)  # wait 5 minutes before retry           
            inverter.connect()

        read_data()

        push_statistics()
        time.sleep(inverter.interval)
    return


DBusGMainLoop(set_as_default=True)
parse_config()
if inverter.connect() == False:
    logging.error('Could not connect to kostal inverter at ' + inverter.host)
    exit(1)
    
if inverter.initCommonData() == False:
    logging.error('Could not read common data from kostal inverter at ' + inverter.host)
    exit(1)
init_dbus()

try:
    run_event = threading.Event()
    run_event.set()

    update_thread = threading.Thread(target=cyclic_update, args=(run_event,))
    update_thread.start()

    mainloop = GLib.MainLoop()
    mainloop.run()

except (KeyboardInterrupt, SystemExit):
    mainloop.quit()
    run_event.clear()
    update_thread.join()
    logging.info("Host: KeyboardInterrupt")


# Venus Kostal PIKO legacy plugin

reads data from Kostal legacy Inverter and integrate it in venus via dbus.

Tested via Kostal Piko 5.5 (2012)

## Installation

Connect via ssh as root to your venus os. If you don't have root access jet, see here: https://www.victronenergy.com/live/ccgx:root_access


### Install plugin:

copy all files to `/data/venus.kostal_piko_legacy/`
copy kostal.ini.sample to kostal.ini
adapt kostal.ini

install Service by `ln -sf /data/venus.kostal_piko_legacy/service/ /service/dbus-kostal_piko_legacy`


#### start/stop Service

start Service
svc -u /service/dbus-kostal_piko_legacy

stop service
svc -d /service/dbus-kostal_piko_legacy

#### install Service permanent
copy line from install Servive to /data/rc.local


### Contribute
ORIGINAL Venus Kostal Plenticore plugin from https://github.com/davwil/venus_kostal_plenticore/tree/main
socket communication based on Piko stats Home https://sourceforge.net/projects/piko/

"""
@ Author      : Rutger Koebrugge
@ Date        : 04/11/2020
@ Description : Plugwise stretch Sensor - Monitor plugwise circles
"""
VERSION = '0.0.1'
DOMAIN = "plugwise-stretch"
SENSOR_PREFIX = 'plugwise_'

CONF_HOST = "host"
CONF_PASSWORD = 'password'

import json
import logging
import base64
import time
import requests
import async_timeout

from datetime import timedelta
from urllib.request import urlopen
from xml.etree import ElementTree

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
#from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.info('Setup platform')
    host = config.get(CONF_HOST)
    password = config.get(CONF_PASSWORD)

    # First setup all the prerequitites in the data bridge
    data_bridge = PlugwiseStretchBridge(host, password)

    # Get all devices
    data_bridge.fetch()
    appliances = data_bridge.data()

    # Loop trough available and add devices
    devices = []
    #if not data_bridge._data:
    for appliance in appliances:
        devices.append(PlugwiseStretchSensor(data_bridge, appliance['name'], appliance['current_power'], appliance['id'], appliance['unit_of_measure']))

    add_entities(devices)


class PlugwiseStretchBridge(object):
    def __init__(self, host, password):
        self._username = 'stretch'
        self._password = password
        self._url = 'http://' + host
        self._data = None

        credentials = (self._username + ':' + self._password).encode('utf-8')
        base64_encoded_credentials = base64.b64encode(credentials).decode('utf-8')

        headers = {
            'Authorization': 'Basic ' + base64_encoded_credentials
        }
        self._headers = headers

    def data(self):
        return self._data

    @Throttle(timedelta(seconds=30))
    def fetch(self):
        _LOGGER.info('fetch appliances')
        self._url = self._url + '/minirest/appliances/'

        response = requests.get(self._url, headers=self._headers)
        _LOGGER.info('Status_code: ' + str(response.status_code))
        #_LOGGER.info('Status_message: ' + str(response.content.decode("utf-8")))

        # if response.status_code != '200':
        #     # + ', error message: '.response.message
        #     _LOGGER.info('Unable to fetch appliances. Got errorcode' + response.status_code)
        #     return false
        
        dom = ElementTree.fromstring(response.content.decode("utf-8"))
        appliances = dom.findall('appliance')

        devices = []
        for c in appliances:
            id = c.find('module').get('id')
            name = c.find('name').text
            type = c.find('type').text
            current_power = c.find('current_power_usage').text
            is_on = c.find('power_state')
            created_date = c.find('created_date')
            modified_date = c.find('modified_date')
            last_seen_date = c.find('last_seen_date')
            last_known_measurement_date  = c.find('last_known_measurement_date')

            # Create json and add to devices list
            item = {
                    "id": id,
                    "name": name,
                    "type": type,
                    "current_power": current_power,
                    "unit_of_measure": 'W'
                    }
            devices.append(item)

        self._data = devices
    
    def ConverToSimpleArray(self, devices):
        returnArray = {}

        for c in devices:
            returnArray[c["id"]] = c["current_power"]
        
        return returnArray


class PlugwiseStretchSensor(Entity):
    def __init__(self, data_bridge, name, prpt, sensor_id, uom):
        self._state = prpt
        self._name = name
        self._property = prpt
        self._uom = uom
        self._data_bridge = data_bridge
        self._appliance_id = sensor_id
        self.entity_id = 'sensor.' + SENSOR_PREFIX + sensor_id
        self._raw = None

    # Explicit attributes
    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return self._uom

    # Custom attributes
    @property
    def appliance_id(self):
        return self._appliance_id

    def update(self):
        self._data_bridge.fetch()
        self._raw = self._data_bridge.data()
        if self._raw is not None:
            simpleDevices = self._data_bridge.ConverToSimpleArray(self._raw)
            self._state = simpleDevices[self.appliance_id]

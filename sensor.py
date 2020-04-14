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
from datetime import timedelta
from urllib.request import urlopen
from xml.etree import ElementTree

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle


_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_entities, discovery_info=None):
    print('Setup platform')
    host = config.get(CONF_HOST)
    password = config.get(CONF_PASSWORD)

    # First setup all the prerequitites in the data bridge
    data_bridge = PlugwiseStretchBridge(host, password)

    # Get all devices
    data_bridge.update()

    # Loop trough available and add devices
    devices = []
    #if not data_bridge._data:
    for appliance in data_bridge._data:
        devices.append(PlugwiseStretchSensor(data_bridge, appliance.name, appliance._property, appliance.appliance_id, appliance.unit_of_measurement))

    add_entities(devices)


class PlugwiseStretchBridge(object):
    def __init__(self, host, password):
        self._username = 'stretch'
        self._password = password
        self._url = 'http://' + host

        credentials = (self._username + ':' + self._password).encode('utf-8')
        base64_encoded_credentials = base64.b64encode(credentials).decode('utf-8')

        headers = {
            'Authorization': 'Basic ' + base64_encoded_credentials
        }
        self._headers = headers
        
        self._data = None

    def data(self):
        return self._data

    @Throttle(timedelta(seconds=10))
    def update(self):
        _LOGGER.debug('GetMiniRest')
        print('Get minirest appliances')
        self._url = self._url + '/minirest/appliances/'
        print(self._url)

        response = requests.get(self._url, headers=self._headers)

        print('Status:', response.status_code)
        #print('Body:', response.content.decode("utf-8"))

        dom = ElementTree.fromstring(response.content.decode("utf-8"))
        appliances = dom.findall('appliance')

        devices = []
        for c in appliances:
            id = c.find('module').get('id')
            name = c.find('name')
            type = c.find('type')
            current_power_usage = c.find('current_power_usage')

            print(' * {} [{}] {} '.format(
                name.text, id, current_power_usage.text
            ))

            devices.append(PlugwiseStretchSensor(c, name.text, current_power_usage.text, id, 'W'))

        self._data = devices


class PlugwiseStretchSensor(Entity):
    def __init__(self, data_bridge, name, prpt, sensor_id, uom):
        self._state = None
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
        self._data_bridge.update()
        self._raw = self._data_bridge.data()
        if self._raw is not None:
            self._state = self._raw[self._property]

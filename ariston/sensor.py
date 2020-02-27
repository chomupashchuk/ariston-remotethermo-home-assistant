"""Suppoort for Ariston sensors."""
import logging
from datetime import timedelta
from homeassistant.const import CONF_NAME, CONF_SENSORS
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    DATA_ARISTON,
    DEVICES,
    SERVICE_UPDATE,
    PARAM_CH_ANTIFREEZE_TEMPERATURE,
    PARAM_CH_MODE,
    PARAM_CH_SET_TEMPERATURE,
    PARAM_DETECTED_TEMPERATURE,
    PARAM_DHW_SET_TEMPERATURE,
    PARAM_DHW_STORAGE_TEMPERATURE,
    PARAM_MODE,
    PARAM_OUTSIDE_TEMPERATURE,
    VAL_UNKNOWN,
    VALUE_TO_CH_MODE,
    VALUE_TO_MODE,
    UNKNOWN_TEMP,
)
from .exceptions import AristonError
from .helpers import log_update_error, service_signal

"""SENSOR_SCAN_INTERVAL_SECS is used to scan changes in JSON data as command in '__init__' is not for checking and updating sensors"""
SENSOR_SCAN_INTERVAL_SECS = 3

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)

_LOGGER = logging.getLogger(__name__)

# Sensor types are defined like: Name, units, icon
SENSORS = {
    PARAM_CH_ANTIFREEZE_TEMPERATURE: ["CH Antifreeze Temperature", '°C', "mdi:thermometer"],
    PARAM_CH_MODE: ["CH Mode", None, "mdi:hand"],
    PARAM_CH_SET_TEMPERATURE: ["CH Set Temperature", '°C', "mdi:thermometer"],
    PARAM_DHW_SET_TEMPERATURE: ["DHW Set Temperature", '°C', "mdi:thermometer"],
    PARAM_DHW_STORAGE_TEMPERATURE: ["DHW Storage Temperature", '°C', "mdi:thermometer"],
    PARAM_MODE: ["Mode", None, "mdi:water-boiler"],
    PARAM_DETECTED_TEMPERATURE: ["Detected Temperature", '°C', "mdi:thermometer"],
    PARAM_OUTSIDE_TEMPERATURE: ["Outside Temperature", '°C', "mdi:thermometer"],
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a sensor for Ariston."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_ARISTON][DEVICES][name]
    async_add_entities(
        [
            AristonSensor(name, device, sensor_type)
            for sensor_type in discovery_info[CONF_SENSORS]
        ],
        True,
    )


class AristonSensor(Entity):
    """A sensor implementation for Ariston."""

    def __init__(self, name, device, sensor_type):
        """Initialize a sensor for Ariston."""
        self._name = "{} {}".format(name, SENSORS[sensor_type][0])
        self._signal_name = name
        self._api = device.api
        self._sensor_type = sensor_type
        self._state = None
        self._attrs = {}
        self._unit_of_measurement = SENSORS[sensor_type][1]
        self._icon = SENSORS[sensor_type][2]
        self._unsub_dispatcher = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Return True if entity is available."""
        return self._api.available

    def update(self):
        """Get the latest data and updates the state."""
        if not self.available:
            return
        _LOGGER.debug("Updating %s sensor", self._name)

        try:
            if self._sensor_type == PARAM_DETECTED_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["zone"]["roomTemp"]
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_CH_ANTIFREEZE_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["zone"]["antiFreezeTemp"]
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_CH_MODE:
                try:
                    self._state = VALUE_TO_CH_MODE[self._api._ariston_data["zone"]["mode"]["value"]]
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_CH_SET_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["zone"]["comfortTemp"]["value"]
                    self._attrs["Min"] = "{} °C".format(self._api._ariston_data["zone"]["comfortTemp"]["min"])
                    self._attrs["Max"] = "{} °C".format(self._api._ariston_data["zone"]["comfortTemp"]["max"])
                except KeyError:
                    self._state = VAL_UNKNOWN
                    self._attrs["Min"] = "{} °C".format("")
                    self._attrs["Max"] = "{} °C".format("")

            elif self._sensor_type == PARAM_DHW_SET_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["dhwTemp"]["value"]
                    self._attrs["Min"] = "{} °C".format(self._api._ariston_data["dhwTemp"]["min"])
                    self._attrs["Max"] = "{} °C".format(self._api._ariston_data["dhwTemp"]["max"])
                except KeyError:
                    self._state = VAL_UNKNOWN
                    self._attrs["Min"] = "{} °C".format("")
                    self._attrs["Max"] = "{} °C".format("")

            elif self._sensor_type == PARAM_MODE:
                try:
                    self._state = VALUE_TO_MODE[self._api._ariston_data["mode"]]
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_DHW_STORAGE_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["dhwStorageTemp"]
                    if self._state in UNKNOWN_TEMP:
                        self._state = VAL_UNKNOWN
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_OUTSIDE_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["outsideTemp"]
                    if self._state in UNKNOWN_TEMP:
                        self._state = VAL_UNKNOWN
                except KeyError:
                    self._state = VAL_UNKNOWN

        except AristonError as error:
            log_update_error(_LOGGER, "update", self.name, "sensor", error)

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Subscribe to update signal."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            service_signal(SERVICE_UPDATE, self._signal_name),
            self.async_on_demand_update,
        )

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        self._unsub_dispatcher()

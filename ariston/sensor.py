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
    PARAM_CH_ACCOUNT_GAS,
    PARAM_CH_ANTIFREEZE_TEMPERATURE,
    PARAM_CH_MODE,
    PARAM_CH_SET_TEMPERATURE,
    PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE,
    PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE,
    PARAM_CH_DETECTED_TEMPERATURE,
    PARAM_ERRORS,
    PARAM_DHW_ACCOUNT_GAS,
    PARAM_DHW_MODE,
    PARAM_DHW_SET_TEMPERATURE,
    PARAM_DHW_STORAGE_TEMPERATURE,
    PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE,
    PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE,
    PARAM_MODE,
    PARAM_OUTSIDE_TEMPERATURE,
    PARAM_HEATING_LAST_24H,
    PARAM_HEATING_LAST_7d,
    PARAM_HEATING_LAST_30d,
    PARAM_HEATING_LAST_365d,
    PARAM_WATER_LAST_24H,
    PARAM_WATER_LAST_7D,
    PARAM_WATER_LAST_30D,
    PARAM_WATER_LAST_365D,
    VAL_UNKNOWN,
    VAL_UNSUPPORTED,
    VALUE_TO_CH_MODE,
    VALUE_TO_DHW_MODE,
    VALUE_TO_MODE,
    UNKNOWN_TEMP,
)
from .exceptions import AristonError
from .helpers import log_update_error, service_signal

"""SENSOR_SCAN_INTERVAL_SECS is used to scan changes in JSON data as command in '__init__' is not for checking and updating sensors"""
SENSOR_SCAN_INTERVAL_SECS = 5

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)

_LOGGER = logging.getLogger(__name__)

# Sensor types are defined like: Name, units, icon
SENSORS = {
    PARAM_CH_ACCOUNT_GAS: ["CH Gas Use", 'kWh', "mdi:cash"],
    PARAM_CH_ANTIFREEZE_TEMPERATURE: ["CH Antifreeze Temperature", '°C', "mdi:thermometer"],
    PARAM_CH_DETECTED_TEMPERATURE: ["CH Detected Temperature", '°C', "mdi:thermometer"],
    PARAM_CH_MODE: ["CH Mode", None, "mdi:hand"],
    PARAM_CH_SET_TEMPERATURE: ["CH Set Temperature", '°C', "mdi:thermometer"],
    PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE: ["CH Schedule Comfort Temperature", '°C', "mdi:thermometer"],
    PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE: ["CH Schedule Economy Temperature", '°C', "mdi:thermometer"],
    PARAM_DHW_ACCOUNT_GAS: ["DHW Gas Use", 'kWh', "mdi:cash"],
    PARAM_DHW_SET_TEMPERATURE: ["DHW Set Temperature", '°C', "mdi:thermometer"],
    PARAM_DHW_STORAGE_TEMPERATURE: ["DHW Storage Temperature", '°C', "mdi:thermometer"],
    PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE: ["DHW Schedule Comfort Temperature", '°C', "mdi:thermometer"],
    PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE: ["DHW Schedule Economy Temperature", '°C', "mdi:thermometer"],
    PARAM_DHW_MODE: ["DHW Mode", None, "mdi:hand"],
    PARAM_MODE: ["Mode", None, "mdi:water-boiler"],
    PARAM_OUTSIDE_TEMPERATURE: ["Outside Temperature", '°C', "mdi:thermometer"],
    PARAM_ERRORS: ["Errors present", None, "mdi:alert-outline"],
    PARAM_HEATING_LAST_24H: ["Gas for Heating use in last 24 hours", 'kWh', "mdi:cash"],
    PARAM_HEATING_LAST_7d: ["Gas for Heating use in last 7 days", 'kWh', "mdi:cash"],
    PARAM_HEATING_LAST_30d: ["Gas for Heating use in last 30 days", 'kWh', "mdi:cash"],
    PARAM_HEATING_LAST_365d: ["Gas for Heating use in last 365 days", 'kWh', "mdi:cash"],
    PARAM_WATER_LAST_24H: ["Gas for Water use in last 24 hours", 'kWh', "mdi:cash"],
    PARAM_WATER_LAST_7D: ["Gas for Water use in last 7 days", 'kWh', "mdi:cash"],
    PARAM_WATER_LAST_30D: ["Gas for Water use in last 30 days", 'kWh', "mdi:cash"],
    PARAM_WATER_LAST_365D: ["Gas for Water use in last 365 days", 'kWh', "mdi:cash"],
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
            if self._sensor_type == PARAM_CH_DETECTED_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["zone"]["roomTemp"]
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE:
                try:
                    self._state = self._api._ariston_ch_data["comfortTemp"]["value"]
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE:
                try:
                    self._state = self._api._ariston_ch_data["economyTemp"]["value"]
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
                    if self._state in UNKNOWN_TEMP or self._api._ariston_data["dhwBoilerPresent"] != True:
                        self._state = VAL_UNSUPPORTED
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_OUTSIDE_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["outsideTemp"]
                    if self._state in UNKNOWN_TEMP:
                        self._state = VAL_UNSUPPORTED
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["dhwTimeProgComfortTemp"]["value"]
                    if self._state in UNKNOWN_TEMP or self._api._ariston_data["dhwTimeProgSupported"] != True:
                        self._state = VAL_UNSUPPORTED
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["dhwTimeProgEconomyTemp"]["value"]
                    if self._state in UNKNOWN_TEMP or self._api._ariston_data["dhwTimeProgSupported"] != True:
                        self._state = VAL_UNSUPPORTED
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_DHW_MODE:
                try:
                    self._state = VALUE_TO_DHW_MODE[self._api._ariston_data["dhwMode"]]
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_CH_ACCOUNT_GAS:
                try:
                    self._state = self._api._ariston_gas_data["account"]["gasHeat"]
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_DHW_ACCOUNT_GAS:
                try:
                    self._state = self._api._ariston_gas_data["account"]["gasDhw"]
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_ERRORS:
                try:
                    self._attrs = {}
                    self._state = self._api._ariston_error_data["count"]
                    for valid_error in self._api._ariston_error_data["result"]:
                        self._attrs[valid_error] = ""
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_HEATING_LAST_24H:
                try:
                    sum = 0
                    iteration = 1
                    for item in self._api._ariston_gas_data["daily"]["data"]:
                        self._attrs["Period"+str(iteration)] = item["y2"]
                        sum = sum + item["y2"]
                        iteration = iteration + 1
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_WATER_LAST_24H:
                try:
                    sum = 0
                    iteration = 1
                    for item in self._api._ariston_gas_data["daily"]["data"]:
                        self._attrs["Period"+str(iteration)] = item["y"]
                        sum = sum + item["y"]
                        iteration = iteration + 1
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_HEATING_LAST_7d:
                try:
                    sum = 0
                    iteration = 1
                    for item in self._api._ariston_gas_data["weekly"]["data"]:
                        self._attrs["Period"+str(iteration)] = item["y2"]
                        sum = sum + item["y2"]
                        iteration = iteration + 1
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_WATER_LAST_7D:
                try:
                    sum = 0
                    iteration = 1
                    for item in self._api._ariston_gas_data["weekly"]["data"]:
                        self._attrs["Period"+str(iteration)] = item["y"]
                        sum = sum + item["y"]
                        iteration = iteration + 1
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_HEATING_LAST_30d:
                try:
                    sum = 0
                    iteration = 1
                    for item in self._api._ariston_gas_data["monthly"]["data"]:
                        self._attrs["Period"+str(iteration)] = item["y2"]
                        sum = sum + item["y2"]
                        iteration = iteration + 1
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_WATER_LAST_30D:
                try:
                    sum = 0
                    iteration = 1
                    for item in self._api._ariston_gas_data["monthly"]["data"]:
                        self._attrs["Period"+str(iteration)] = item["y"]
                        sum = sum + item["y"]
                        iteration = iteration + 1
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_HEATING_LAST_365d:
                try:
                    sum = 0
                    iteration = 1
                    for item in self._api._ariston_gas_data["yearly"]["data"]:
                        self._attrs["Period"+str(iteration)] = item["y2"]
                        sum = sum + item["y2"]
                        iteration = iteration + 1
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN

            elif self._sensor_type == PARAM_WATER_LAST_365D:
                try:
                    sum = 0
                    iteration = 1
                    for item in self._api._ariston_gas_data["yearly"]["data"]:
                        self._attrs["Period"+str(iteration)] = item["y"]
                        sum = sum + item["y"]
                        iteration = iteration + 1
                    self._state = round(sum, 3)
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

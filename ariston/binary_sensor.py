"""Suppoort for Ariston binary sensors."""
import logging
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_HEAT,
    BinarySensorEntity,
)
from homeassistant.const import CONF_BINARY_SENSORS, CONF_NAME
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ARISTON_INTERNET_TIME,
    ARISTON_INTERNET_WEATHER,
    ARISTON_CH_AUTO_FUNCTION,
    ARISTON_THERMAL_CLEANSE_FUNCTION,
    CONF_DHW_FLAME_UNKNOWN_ON,
    CONF_DHW_AND_CH,
    DATA_ARISTON,
    DEVICES,
    SERVICE_UPDATE,
    PARAM_HOLIDAY_MODE,
    PARAM_ONLINE,
    PARAM_FLAME,
    PARAM_HEAT_PUMP,
    PARAM_CHANGING_DATA,
    PARAM_INTERNET_TIME,
    PARAM_INTERNET_WEATHER,
    PARAM_CH_AUTO_FUNCTION,
    PARAM_CH_FLAME,
    PARAM_DHW_FLAME,
    PARAM_THERMAL_CLEANSE_FUNCTION,
    PARAM_CH_PILOT,
    PARAM_UPDATE,
    BINARY_SENSOR_HOLIDAY_MODE,
    BINARY_SENSOR_ONLINE,
    BINARY_SENSOR_FLAME,
    BINARY_SENSOR_HEAT_PUMP,
    BINARY_SENSOR_CHANGING_DATA,
    BINARY_SENSOR_INTERNET_TIME,
    BINARY_SENSOR_INTERNET_WEATHER,
    BINARY_SENSOR_CH_AUTO_FUNCTION,
    BINARY_SENSOR_CH_FLAME,
    BINARY_SENSOR_DHW_FLAME,
    BINARY_SENSOR_THERMAL_CLEANSE_FUNCTION,
    BINARY_SENSOR_CH_PILOT,
    BINARY_SENSOR_UPDATE,
    VERSION,
    GET_REQUEST_PARAM,
    GET_REQUEST_VERSION,
    VALUE_TO_MODE,
    VAL_SUMMER,
    VAL_WINTER,
    INVALID_STORAGE_TEMP,
)
from .exceptions import AristonError
from .helpers import log_update_error, service_signal

"""BINARY_SENSOR_SCAN_INTERVAL_SECS is used to scan changes in JSON data as command in '__init__' is not for checking and updating sensors"""
BINARY_SENSOR_SCAN_INTERVAL_SECS = 2

SCAN_INTERVAL = timedelta(seconds=BINARY_SENSOR_SCAN_INTERVAL_SECS)

_LOGGER = logging.getLogger(__name__)

# Binary sensor types are defined like: Name, device class
BINARY_SENSORS = {
    PARAM_CH_AUTO_FUNCTION: (BINARY_SENSOR_CH_AUTO_FUNCTION, None, "mdi:radiator"),
    PARAM_CH_FLAME: (BINARY_SENSOR_CH_FLAME, None, "mdi:fire"),
    PARAM_DHW_FLAME: (BINARY_SENSOR_DHW_FLAME, None, "mdi:fire"),
    PARAM_HOLIDAY_MODE: (BINARY_SENSOR_HOLIDAY_MODE, None, "mdi:island"),
    PARAM_ONLINE: (BINARY_SENSOR_ONLINE, DEVICE_CLASS_CONNECTIVITY, None),
    PARAM_FLAME: (BINARY_SENSOR_FLAME, None, "mdi:fire"),
    PARAM_HEAT_PUMP: (BINARY_SENSOR_HEAT_PUMP, DEVICE_CLASS_HEAT, None),
    PARAM_CHANGING_DATA: (BINARY_SENSOR_CHANGING_DATA, None, "mdi:cogs"),
    PARAM_INTERNET_TIME: (BINARY_SENSOR_INTERNET_TIME, None, "mdi:update"),
    PARAM_INTERNET_WEATHER: (BINARY_SENSOR_INTERNET_WEATHER, None, "mdi:weather-partly-cloudy"),
    PARAM_THERMAL_CLEANSE_FUNCTION: (BINARY_SENSOR_THERMAL_CLEANSE_FUNCTION, None, "mdi:allergy"),
    PARAM_CH_PILOT: (BINARY_SENSOR_CH_PILOT, None, "mdi:head-cog-outline"),
    PARAM_UPDATE: (BINARY_SENSOR_UPDATE, None, "mdi:package-down"),
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a binary sensor for Ariston."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_ARISTON][DEVICES][name]
    async_add_entities(
        [
            AristonBinarySensor(name, device, sensor_type)
            for sensor_type in discovery_info[CONF_BINARY_SENSORS]
        ],
        True,
    )


class AristonBinarySensor(BinarySensorEntity):
    """Binary sensor for Ariston."""

    def __init__(self, name, device, sensor_type):
        """Initialize entity."""
        self._api = device.api
        self._attrs = {}
        self._device_class = BINARY_SENSORS[sensor_type][1]
        self._icon = BINARY_SENSORS[sensor_type][2]
        self._name = "{} {}".format(name, BINARY_SENSORS[sensor_type][0])
        self._sensor_type = sensor_type
        self._signal_name = name
        self._state = None
        self._unsub_dispatcher = None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return self._sensor_type != PARAM_ONLINE

    @property
    def name(self):
        """Return entity name."""
        return self._name

    @property
    def is_on(self):
        """Return if entity is on."""
        return self._state

    @property
    def device_class(self):
        """Return device class."""
        return self._device_class

    @property
    def available(self):
        """Return True if entity is available."""
        if self._sensor_type == PARAM_ONLINE:
            return True
        elif self._sensor_type in GET_REQUEST_PARAM:
            return self._api.available and self._api._ariston_other_data != {}
        elif self._sensor_type in GET_REQUEST_VERSION:
            return self._api._version != ""
        else:
            return self._api.available and self._api._ariston_data != {}

    @property
    def icon(self):
        """Return the state attributes."""
        return self._icon

    def update(self):
        """Update entity."""
        if not self.available:
            return
        _LOGGER.debug("Updating %s binary sensor", self._name)

        try:

            if self._sensor_type == PARAM_HOLIDAY_MODE:
                try:
                    if self._api._ariston_data["zone"]["comfortTemp"]["value"] == self._api._ariston_data["zone"][
                        "antiFreezeTemp"] or self._api._ariston_data["holidayEnabled"]:
                        self._state = True
                    else:
                        self._state = False
                except:
                    self._state = False
                    pass

            elif self._sensor_type == PARAM_ONLINE:
                self._state = self._api.available

            elif self._sensor_type == PARAM_FLAME:
                try:
                    self._state = self._api._ariston_data["flameSensor"]
                except:
                    self._state = False
                    pass

            elif self._sensor_type == PARAM_HEAT_PUMP:
                try:
                    self._state = self._api._ariston_data["heatingPumpOn"]
                except:
                    self._state = False
                    pass

            elif self._sensor_type == PARAM_CH_PILOT:
                try:
                    self._state = self._api._ariston_data["zone"]["pilotOn"]
                except:
                    self._state = False
                    pass

            elif self._sensor_type == PARAM_CHANGING_DATA:
                if self._api._set_param == {}:
                    self._state = False
                else:
                    self._state = True

            elif self._sensor_type == PARAM_INTERNET_TIME:
                self._state = False
                try:
                    for param_item in self._api._ariston_other_data:
                        if param_item["id"] == ARISTON_INTERNET_TIME:
                            if param_item["value"] == 1:
                                self._state = True
                                break
                except:
                    pass

            elif self._sensor_type == PARAM_INTERNET_WEATHER:
                self._state = False
                try:
                    for param_item in self._api._ariston_other_data:
                        if param_item["id"] == ARISTON_INTERNET_WEATHER:
                            if param_item["value"] == 1:
                                self._state = True
                                break
                except:
                    pass

            elif self._sensor_type == PARAM_CH_AUTO_FUNCTION:
                self._state = False
                try:
                    for param_item in self._api._ariston_other_data:
                        if param_item["id"] == ARISTON_CH_AUTO_FUNCTION:
                            if param_item["value"] == 1:
                                self._state = True
                                break
                except:
                    pass

            elif self._sensor_type == PARAM_THERMAL_CLEANSE_FUNCTION:
                self._state = False
                try:
                    for param_item in self._api._ariston_other_data:
                        if param_item["id"] == ARISTON_THERMAL_CLEANSE_FUNCTION:
                            if param_item["value"] == 1:
                                self._state = True
                                break
                except:
                    pass

            elif self._sensor_type == PARAM_CH_FLAME:
                self._state = False
                try:
                    self._state = self._api._ariston_data["zone"]["heatRequest"]
                    if self._api._ariston_data["dhwStorageTemp"] != INVALID_STORAGE_TEMP and self._api._dhw_trend_up and \
                            VALUE_TO_MODE[self._api._ariston_data["mode"]] in [VAL_SUMMER, VAL_WINTER] and \
                            self._api._ariston_data["flameSensor"] and not self._api._device[CONF_DHW_AND_CH]:
                        self._state = False
                except:
                    pass

            elif self._sensor_type == PARAM_DHW_FLAME:
                self._state = False
                try:
                    if not self._api._ariston_data["zone"]["heatRequest"] and self._api._ariston_data["flameSensor"]:
                        self._state = True
                    elif self._api._ariston_data["flameForDhw"]:
                        self._state = True
                    elif self._api._ariston_data["dhwStorageTemp"] != INVALID_STORAGE_TEMP and self._api._dhw_trend_up and \
                            VALUE_TO_MODE[self._api._ariston_data["mode"]] in [VAL_SUMMER, VAL_WINTER] and \
                            self._api._ariston_data["flameSensor"]:
                        self._state = True
                    elif self._api._device[CONF_DHW_FLAME_UNKNOWN_ON] and self._api._ariston_data["flameSensor"]:
                        self._state = True
                except:
                    pass

            elif self._sensor_type == PARAM_UPDATE:
                self._state = False
                self._attrs = {}
                self._attrs["Installed"] = VERSION
                try:
                    if self._api._version != "":
                        self._attrs["Git Version"] = self._api._version
                        web_version = self._api._version.split(".")
                        installed_version = VERSION.split(".")
                        web_symbols = len(web_version)
                        installed_symbols = len(installed_version)
                        if web_symbols <= installed_symbols:
                            # same amount of symbols to check, update available if web has higher value
                            for symbol in range(0, web_symbols):
                                if int(web_version[symbol]) > int(installed_version[symbol]):
                                    self._state = True
                                    break
                        else:
                            # same amount of symbols to check, update available if web has higher value
                            # or if symbols match but web has additional last symbol
                            for symbol in range(0, installed_symbols):
                                if int(web_version[symbol]) > int(installed_version[symbol]):
                                    self._state = True
                                    break
                            self._state = True
                except:
                    pass

        except AristonError as error:
            log_update_error(_LOGGER, "update", self.name, "binary sensor", error)

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

"""Suppoort for Ariston sensors."""
import logging
from datetime import timedelta

from homeassistant.const import CONF_NAME, CONF_SENSORS
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    ARISTON_DHW_COMFORT_FUNCTION,
    ARISTON_SIGNAL_STRENGHT,
    DATA_ARISTON,
    DAYS_OF_WEEK,
    DEVICES,
    SERVICE_UPDATE,
    DHW_COMFORT_VALUE_TO_FUNCT,
    PARAM_CH_ACCOUNT_GAS,
    PARAM_CH_ANTIFREEZE_TEMPERATURE,
    PARAM_CH_MODE,
    PARAM_CH_SET_TEMPERATURE,
    PARAM_CH_COMFORT_TEMPERATURE,
    PARAM_CH_ECONOMY_TEMPERATURE,
    PARAM_CH_DETECTED_TEMPERATURE,
    PARAM_CH_PROGRAM,
    PARAM_ERRORS,
    PARAM_DHW_ACCOUNT_GAS,
    PARAM_DHW_COMFORT_FUNCTION,
    PARAM_DHW_MODE,
    PARAM_DHW_SET_TEMPERATURE,
    PARAM_DHW_STORAGE_TEMPERATURE,
    PARAM_DHW_COMFORT_TEMPERATURE,
    PARAM_DHW_ECONOMY_TEMPERATURE,
    PARAM_MODE,
    PARAM_OUTSIDE_TEMPERATURE,
    PARAM_HEATING_LAST_24H,
    PARAM_HEATING_LAST_7d,
    PARAM_HEATING_LAST_30d,
    PARAM_HEATING_LAST_365d,
    PARAM_SIGNAL_STRENGTH,
    PARAM_WATER_LAST_24H,
    PARAM_WATER_LAST_7D,
    PARAM_WATER_LAST_30D,
    PARAM_WATER_LAST_365D,
    VAL_AVAILABLE,
    VAL_UNKNOWN,
    VAL_UNSUPPORTED,
    VALUE_TO_CH_MODE,
    VALUE_TO_DHW_MODE,
    VALUE_TO_MODE,
    UNKNOWN_TEMP,
    SENSOR_CH_ACCOUNT_GAS,
    SENSOR_CH_ANTIFREEZE_TEMPERATURE,
    SENSOR_CH_DETECTED_TEMPERATURE,
    SENSOR_CH_MODE,
    SENSOR_CH_SET_TEMPERATURE,
    SENSOR_CH_PROGRAM,
    SENSOR_CH_COMFORT_TEMPERATURE,
    SENSOR_CH_ECONOMY_TEMPERATURE,
    SENSOR_DHW_ACCOUNT_GAS,
    SENSOR_DHW_COMFORT_FUNCTION,
    SENSOR_DHW_SET_TEMPERATURE,
    SENSOR_DHW_STORAGE_TEMPERATURE,
    SENSOR_DHW_COMFORT_TEMPERATURE,
    SENSOR_DHW_ECONOMY_TEMPERATURE,
    SENSOR_DHW_MODE,
    SENSOR_ERRORS,
    SENSOR_HEATING_LAST_24H,
    SENSOR_HEATING_LAST_7d,
    SENSOR_HEATING_LAST_30d,
    SENSOR_HEATING_LAST_365d,
    SENSOR_MODE,
    SENSOR_OUTSIDE_TEMPERATURE,
    SENSOR_SIGNAL_STRENGTH,
    SENSOR_WATER_LAST_24H,
    SENSOR_WATER_LAST_7D,
    SENSOR_WATER_LAST_30D,
    SENSOR_WATER_LAST_365D,
)
from .exceptions import AristonError
from .helpers import log_update_error, service_signal

VAL_UNKNOWN_TEMP = 0.0
DEFAULT_ICON = "default_icon"

"""SENSOR_SCAN_INTERVAL_SECS is used to scan changes in JSON data as command in '__init__' is not for checking and updating sensors"""
SENSOR_SCAN_INTERVAL_SECS = 5

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)

_LOGGER = logging.getLogger(__name__)

# Sensor types are defined like: Name, units, icon
SENSORS = {
    PARAM_CH_ACCOUNT_GAS: [SENSOR_CH_ACCOUNT_GAS, 'kWh', {DEFAULT_ICON: "mdi:cash"}],
    PARAM_CH_ANTIFREEZE_TEMPERATURE: [SENSOR_CH_ANTIFREEZE_TEMPERATURE, '°C', {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_CH_DETECTED_TEMPERATURE: [SENSOR_CH_DETECTED_TEMPERATURE, '°C', {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_CH_MODE: [SENSOR_CH_MODE, None, {DEFAULT_ICON: "mdi:hand"}],
    PARAM_CH_SET_TEMPERATURE: [SENSOR_CH_SET_TEMPERATURE, '°C', {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_CH_PROGRAM: [SENSOR_CH_PROGRAM, None, {DEFAULT_ICON: "mdi:calendar-month"}],
    PARAM_CH_COMFORT_TEMPERATURE: [SENSOR_CH_COMFORT_TEMPERATURE, '°C', {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_CH_ECONOMY_TEMPERATURE: [SENSOR_CH_ECONOMY_TEMPERATURE, '°C', {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_DHW_ACCOUNT_GAS: [SENSOR_DHW_ACCOUNT_GAS, 'kWh', {DEFAULT_ICON: "mdi:cash"}],
    PARAM_DHW_COMFORT_FUNCTION: [SENSOR_DHW_COMFORT_FUNCTION, None, {DEFAULT_ICON: "mdi:water-pump"}],
    PARAM_DHW_SET_TEMPERATURE: [SENSOR_DHW_SET_TEMPERATURE, '°C', {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_DHW_STORAGE_TEMPERATURE: [SENSOR_DHW_STORAGE_TEMPERATURE, '°C', {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_DHW_COMFORT_TEMPERATURE: [SENSOR_DHW_COMFORT_TEMPERATURE, '°C', {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_DHW_ECONOMY_TEMPERATURE: [SENSOR_DHW_ECONOMY_TEMPERATURE, '°C', {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_DHW_MODE: [SENSOR_DHW_MODE, None, {DEFAULT_ICON: "mdi:hand"}],
    PARAM_ERRORS: [SENSOR_ERRORS, None, {DEFAULT_ICON: "mdi:alert-outline", 0: "mdi:shield-check"}],
    PARAM_HEATING_LAST_24H: [SENSOR_HEATING_LAST_24H, 'kWh', {DEFAULT_ICON: "mdi:cash"}],
    PARAM_HEATING_LAST_7d: [SENSOR_HEATING_LAST_7d, 'kWh', {DEFAULT_ICON: "mdi:cash"}],
    PARAM_HEATING_LAST_30d: [SENSOR_HEATING_LAST_30d, 'kWh', {DEFAULT_ICON: "mdi:cash"}],
    PARAM_HEATING_LAST_365d: [SENSOR_HEATING_LAST_365d, 'kWh', {DEFAULT_ICON: "mdi:cash"}],
    PARAM_MODE: [SENSOR_MODE, None, {DEFAULT_ICON: "mdi:water-boiler"}],
    PARAM_OUTSIDE_TEMPERATURE: [SENSOR_OUTSIDE_TEMPERATURE, '°C', {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_SIGNAL_STRENGTH: [SENSOR_SIGNAL_STRENGTH, '%', {DEFAULT_ICON: "mdi:signal"}],
    PARAM_WATER_LAST_24H: [SENSOR_WATER_LAST_24H, 'kWh', {DEFAULT_ICON: "mdi:cash"}],
    PARAM_WATER_LAST_7D: [SENSOR_WATER_LAST_7D, 'kWh', {DEFAULT_ICON: "mdi:cash"}],
    PARAM_WATER_LAST_30D: [SENSOR_WATER_LAST_30D, 'kWh', {DEFAULT_ICON: "mdi:cash"}],
    PARAM_WATER_LAST_365D: [SENSOR_WATER_LAST_365D, 'kWh', {DEFAULT_ICON: "mdi:cash"}],
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
        if self._state in self._icon:
            return self._icon[self._state]
        elif DEFAULT_ICON in self._icon:
            return self._icon[DEFAULT_ICON]
        else:
            return None

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Return True if entity is available."""
        if self._sensor_type in [PARAM_ERRORS]:
            return self._api.available and self._api._ariston_error_data != {}
        elif self._sensor_type in [PARAM_CH_PROGRAM]:
            return self._api.available and self._api._ariston_ch_data != {}
        elif self._sensor_type in [PARAM_DHW_ACCOUNT_GAS,
                                   PARAM_CH_ACCOUNT_GAS,
                                   PARAM_HEATING_LAST_24H,
                                   PARAM_HEATING_LAST_7d,
                                   PARAM_HEATING_LAST_30d,
                                   PARAM_HEATING_LAST_365d,
                                   PARAM_WATER_LAST_24H,
                                   PARAM_WATER_LAST_7D, PARAM_WATER_LAST_30D,
                                   PARAM_WATER_LAST_365D]:
            return self._api.available and self._api._ariston_gas_data != {}
        elif self._sensor_type in [PARAM_DHW_COMFORT_FUNCTION,
                                   PARAM_SIGNAL_STRENGTH]:
            return self._api.available and self._api._ariston_other_data != {}
        else:
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
                    pass

            elif self._sensor_type == PARAM_CH_COMFORT_TEMPERATURE:
                try:
                    self._state = self._api._ariston_ch_data["comfortTemp"]["value"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_CH_ECONOMY_TEMPERATURE:
                try:
                    self._state = self._api._ariston_ch_data["economyTemp"]["value"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_CH_ANTIFREEZE_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["zone"]["antiFreezeTemp"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_CH_MODE:
                try:
                    self._state = VALUE_TO_CH_MODE[self._api._ariston_data["zone"]["mode"]["value"]]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_CH_SET_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["zone"]["comfortTemp"]["value"]
                    self._attrs["Min"] = "{} °C".format(self._api._ariston_data["zone"]["comfortTemp"]["min"])
                    self._attrs["Max"] = "{} °C".format(self._api._ariston_data["zone"]["comfortTemp"]["max"])
                except KeyError:
                    self._state = VAL_UNKNOWN
                    self._attrs["Min"] = "{} °C".format("")
                    self._attrs["Max"] = "{} °C".format("")
                    pass

            elif self._sensor_type == PARAM_DHW_SET_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["dhwTemp"]["value"]
                    self._attrs["Min"] = "{} °C".format(self._api._ariston_data["dhwTemp"]["min"])
                    self._attrs["Max"] = "{} °C".format(self._api._ariston_data["dhwTemp"]["max"])
                except KeyError:
                    self._state = VAL_UNKNOWN
                    self._attrs["Min"] = "{} °C".format("")
                    self._attrs["Max"] = "{} °C".format("")
                    pass

            elif self._sensor_type == PARAM_MODE:
                try:
                    self._state = VALUE_TO_MODE[self._api._ariston_data["mode"]]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_DHW_STORAGE_TEMPERATURE:
                try:
                    if self._state in UNKNOWN_TEMP or self._api._ariston_data["dhwBoilerPresent"] != True:
                        self._state = VAL_UNKNOWN_TEMP
                    else:
                        self._state = self._api._ariston_data["dhwStorageTemp"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_OUTSIDE_TEMPERATURE:
                try:
                    if self._state in UNKNOWN_TEMP:
                        self._state = VAL_UNKNOWN_TEMP
                    else:
                        self._state = self._api._ariston_data["outsideTemp"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_DHW_COMFORT_TEMPERATURE:
                try:
                    if self._state in UNKNOWN_TEMP or self._api._ariston_data["dhwTimeProgSupported"] != True:
                        self._state = VAL_UNKNOWN_TEMP
                    else:
                        self._state = self._api._ariston_data["dhwTimeProgComfortTemp"]["value"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_DHW_ECONOMY_TEMPERATURE:
                try:
                    if self._state in UNKNOWN_TEMP or self._api._ariston_data["dhwTimeProgSupported"] != True:
                        self._state = VAL_UNKNOWN_TEMP
                    else:
                        self._state = self._api._ariston_data["dhwTimeProgEconomyTemp"]["value"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_DHW_MODE:
                try:
                    self._state = VALUE_TO_DHW_MODE[self._api._ariston_data["dhwMode"]]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_CH_ACCOUNT_GAS:
                try:
                    self._state = self._api._ariston_gas_data["account"]["gasHeat"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_DHW_ACCOUNT_GAS:
                try:
                    self._state = self._api._ariston_gas_data["account"]["gasDhw"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_ERRORS:
                self._state = VAL_UNKNOWN
                try:
                    self._attrs = {}
                    self._state = self._api._ariston_error_data["count"]
                    for valid_error in self._api._ariston_error_data["result"]:
                        self._attrs[valid_error] = ""
                except KeyError:
                    pass

            elif self._sensor_type == PARAM_HEATING_LAST_24H:
                try:
                    sum = 0
                    for iteration, item in enumerate(self._api._ariston_gas_data["daily"]["data"], 1):
                        self._attrs["Period" + str(iteration)] = item["y2"]
                        sum = sum + item["y2"]
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_WATER_LAST_24H:
                try:
                    sum = 0
                    for iteration, item in enumerate(self._api._ariston_gas_data["daily"]["data"], 1):
                        self._attrs["Period" + str(iteration)] = item["y"]
                        sum = sum + item["y"]
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_HEATING_LAST_7d:
                try:
                    sum = 0
                    for iteration, item in enumerate(self._api._ariston_gas_data["weekly"]["data"], 1):
                        self._attrs["Period" + str(iteration)] = item["y2"]
                        sum = sum + item["y2"]
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_WATER_LAST_7D:
                try:
                    sum = 0
                    for iteration, item in enumerate(self._api._ariston_gas_data["weekly"]["data"], 1):
                        self._attrs["Period" + str(iteration)] = item["y"]
                        sum = sum + item["y"]
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_HEATING_LAST_30d:
                try:
                    sum = 0
                    for iteration, item in enumerate(self._api._ariston_gas_data["monthly"]["data"], 1):
                        self._attrs["Period" + str(iteration)] = item["y2"]
                        sum = sum + item["y2"]
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_WATER_LAST_30D:
                try:
                    sum = 0
                    for iteration, item in enumerate(self._api._ariston_gas_data["monthly"]["data"], 1):
                        self._attrs["Period" + str(iteration)] = item["y"]
                        sum = sum + item["y"]
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_HEATING_LAST_365d:
                try:
                    sum = 0
                    for iteration, item in enumerate(self._api._ariston_gas_data["yearly"]["data"], 1):
                        self._attrs["Period" + str(iteration)] = item["y2"]
                        sum = sum + item["y2"]
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_WATER_LAST_365D:
                try:
                    sum = 0
                    for iteration, item in enumerate(self._api._ariston_gas_data["yearly"]["data"], 1):
                        self._attrs["Period" + str(iteration)] = item["y"]
                        sum = sum + item["y"]
                    self._state = round(sum, 3)
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_CH_PROGRAM:
                try:
                    if self._api._ariston_ch_data != {}:
                        self._state = VAL_AVAILABLE
                        for day_of_week in DAYS_OF_WEEK:
                            if day_of_week in self._api._ariston_ch_data:
                                for day_slices in self._api._ariston_ch_data[day_of_week]["slices"]:
                                    attribute_name = day_of_week + '_' + day_slices["from"] + '_' + day_slices["to"]
                                    if day_slices["temperatureId"] == 1:
                                        attribute_value = "Comfort"
                                    else:
                                        attribute_value = "Economy"
                                    self._attrs[attribute_name] = attribute_value
                    else:
                        self._state = VAL_UNKNOWN
                except:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_DHW_COMFORT_FUNCTION:
                self._state = VAL_UNKNOWN
                try:
                    for param_item in self._api._ariston_other_data:
                        if param_item["id"] == ARISTON_DHW_COMFORT_FUNCTION:
                            self._state = DHW_COMFORT_VALUE_TO_FUNCT[param_item["value"]]
                            break
                except:
                    pass

            elif self._sensor_type == PARAM_SIGNAL_STRENGTH:
                self._state = VAL_UNKNOWN
                try:
                    for param_item in self._api._ariston_other_data:
                        if param_item["id"] == ARISTON_SIGNAL_STRENGHT:
                            self._state = param_item["value"]
                            break
                except:
                    pass

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

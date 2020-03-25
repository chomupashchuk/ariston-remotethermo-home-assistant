"""Suppoort for Ariston sensors."""
import logging
import os
from datetime import timedelta

from homeassistant.const import CONF_NAME, CONF_SENSORS
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    ARISTON_DHW_COMFORT_FUNCTION,
    ARISTON_SIGNAL_STRENGHT,
    ARISTON_CH_COMFORT_TEMP,
    ARISTON_CH_ECONOMY_TEMP,
    ARISTON_THERMAL_CLEANSE_CYCLE,
    DATA_ARISTON,
    DAYS_OF_WEEK,
    DEVICES,
    SERVICE_UPDATE,
    DHW_COMFORT_VALUE_TO_FUNCT,
    PARAM_ACCOUNT_CH_GAS,
    PARAM_ACCOUNT_CH_ELECTRICITY,
    PARAM_ACCOUNT_DHW_GAS,
    PARAM_ACCOUNT_DHW_ELECTRICITY,
    PARAM_CH_ANTIFREEZE_TEMPERATURE,
    PARAM_CH_MODE,
    PARAM_CH_SET_TEMPERATURE,
    PARAM_CH_COMFORT_TEMPERATURE,
    PARAM_CH_ECONOMY_TEMPERATURE,
    PARAM_CH_DETECTED_TEMPERATURE,
    PARAM_CH_PROGRAM,
    PARAM_ERRORS,
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
    PARAM_UNITS,
    PARAM_THERMAL_CLEANSE_CYCLE,
    PARAM_DHW_PROGRAM,
    PARAM_GAS_TYPE,
    PARAM_GAS_COST,
    PARAM_ELECTRICITY_COST,
    VAL_WINTER,
    VAL_SUMMER,
    VAL_OFF,
    VAL_HEATING_ONLY,
    VAL_MANUAL,
    VAL_PROGRAM,
    VAL_LEARNING,
    VAL_DISABLED,
    VAL_TIME_BASED,
    VAL_ALWAYS_ACTIVE,
    VAL_AVAILABLE,
    VAL_UNKNOWN,
    VAL_UNSUPPORTED,
    VALUE_TO_CH_MODE,
    VALUE_TO_DHW_MODE,
    VALUE_TO_MODE,
    VALUE_TO_UNIT,
    VAL_IMPERIAL,
    VAL_AUTO,
    SENSOR_ACCOUNT_CH_GAS,
    SENSOR_ACCOUNT_CH_ELECTRICITY,
    SENSOR_ACCOUNT_DHW_GAS,
    SENSOR_ACCOUNT_DHW_ELECTRICITY,
    SENSOR_CH_ANTIFREEZE_TEMPERATURE,
    SENSOR_CH_DETECTED_TEMPERATURE,
    SENSOR_CH_MODE,
    SENSOR_CH_SET_TEMPERATURE,
    SENSOR_CH_PROGRAM,
    SENSOR_CH_COMFORT_TEMPERATURE,
    SENSOR_CH_ECONOMY_TEMPERATURE,
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
    SENSOR_UNITS,
    SENSOR_THERMAL_CLEANSE_CYCLE,
    SENSOR_DHW_PROGRAM,
    SENSOR_GAS_TYPE,
    SENSOR_GAS_COST,
    SENSOR_ELECTRICITY_COST,
)
from .exceptions import AristonError
from .helpers import log_update_error, service_signal

DEFAULT_ICON = "default_icon"
DEFAULT_UNIT = 0
MODE_TO_ICON = {
    VAL_OFF: "ariston_off.png",
    VAL_WINTER: "ariston_water_and_heating.png",
    VAL_SUMMER: "ariston_water_only.png",
    VAL_HEATING_ONLY: "ariston_heating_only.png"
}

"""SENSOR_SCAN_INTERVAL_SECS is used to scan changes in JSON data as command in '__init__' is not for checking and updating sensors"""
SENSOR_SCAN_INTERVAL_SECS = 5

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)

_LOGGER = logging.getLogger(__name__)

# Sensor types are defined like: Name, units, icon
SENSORS = {
    PARAM_ACCOUNT_CH_GAS: [SENSOR_ACCOUNT_CH_GAS, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"}, {DEFAULT_ICON: "mdi:cash"}],
    PARAM_ACCOUNT_DHW_GAS: [SENSOR_ACCOUNT_DHW_GAS, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"}, {DEFAULT_ICON: "mdi:cash"}],
    PARAM_ACCOUNT_CH_ELECTRICITY: [SENSOR_ACCOUNT_CH_ELECTRICITY, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"},
                                   {DEFAULT_ICON: "mdi:cash"}],
    PARAM_ACCOUNT_DHW_ELECTRICITY: [SENSOR_ACCOUNT_DHW_ELECTRICITY, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"},
                                    {DEFAULT_ICON: "mdi:cash"}],
    PARAM_CH_ANTIFREEZE_TEMPERATURE: [SENSOR_CH_ANTIFREEZE_TEMPERATURE, {DEFAULT_UNIT: '°C', 1: "°F"},
                                      {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_CH_DETECTED_TEMPERATURE: [SENSOR_CH_DETECTED_TEMPERATURE, {DEFAULT_UNIT: '°C', 1: "°F"},
                                    {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_CH_MODE: [SENSOR_CH_MODE, None, {
        DEFAULT_ICON: "mdi:radiator-off",
        VAL_MANUAL: "mdi:hand",
        VAL_PROGRAM: "mdi:clock-outline",
        VAL_LEARNING: "mdi:mdi:head-cog-outline"
    }],
    PARAM_CH_SET_TEMPERATURE: [SENSOR_CH_SET_TEMPERATURE, {DEFAULT_UNIT: '°C', 1: "°F"},
                               {DEFAULT_ICON: "mdi:radiator"}],
    PARAM_CH_PROGRAM: [SENSOR_CH_PROGRAM, None, {DEFAULT_ICON: "mdi:calendar-month"}],
    PARAM_CH_COMFORT_TEMPERATURE: [SENSOR_CH_COMFORT_TEMPERATURE, {DEFAULT_UNIT: '°C', 1: "°F"},
                                   {DEFAULT_ICON: "mdi:radiator"}],
    PARAM_CH_ECONOMY_TEMPERATURE: [SENSOR_CH_ECONOMY_TEMPERATURE, {DEFAULT_UNIT: '°C', 1: "°F"},
                                   {DEFAULT_ICON: "mdi:radiator"}],
    PARAM_DHW_PROGRAM: [SENSOR_DHW_PROGRAM, None, {DEFAULT_ICON: "mdi:calendar-month"}],
    PARAM_DHW_COMFORT_FUNCTION: [SENSOR_DHW_COMFORT_FUNCTION, None, {
        DEFAULT_ICON: "mdi:water-pump-off",
        VAL_DISABLED: "mdi:water-pump-off",
        VAL_TIME_BASED: "mdi:clock-outline",
        VAL_ALWAYS_ACTIVE: "mdi:water-pump"
    }],
    PARAM_DHW_SET_TEMPERATURE: [SENSOR_DHW_SET_TEMPERATURE, {DEFAULT_UNIT: '°C', 1: "°F"},
                                {DEFAULT_ICON: "mdi:water-pump"}],
    PARAM_DHW_STORAGE_TEMPERATURE: [SENSOR_DHW_STORAGE_TEMPERATURE, {DEFAULT_UNIT: '°C', 1: "°F"},
                                    {DEFAULT_ICON: "mdi:water-pump"}],
    PARAM_DHW_COMFORT_TEMPERATURE: [SENSOR_DHW_COMFORT_TEMPERATURE, {DEFAULT_UNIT: '°C', 1: "°F"},
                                    {DEFAULT_ICON: "mdi:water-pump"}],
    PARAM_DHW_ECONOMY_TEMPERATURE: [SENSOR_DHW_ECONOMY_TEMPERATURE, {DEFAULT_UNIT: '°C', 1: "°F"},
                                    {DEFAULT_ICON: "mdi:water-pump"}],
    PARAM_DHW_MODE: [SENSOR_DHW_MODE, None, {
        DEFAULT_ICON: "mdi:water-pump-off",
        VAL_MANUAL: "mdi:hand",
        VAL_PROGRAM: "mdi:clock-outline",
        VAL_UNSUPPORTED: "mdi:water-pump"
    }],
    PARAM_ERRORS: [SENSOR_ERRORS, None, {
        DEFAULT_ICON: "mdi:alert-outline",
        0: "mdi:shield-check"
    }],
    PARAM_HEATING_LAST_24H: [SENSOR_HEATING_LAST_24H, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"}, {DEFAULT_ICON: "mdi:cash"}],
    PARAM_HEATING_LAST_7d: [SENSOR_HEATING_LAST_7d, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"}, {DEFAULT_ICON: "mdi:cash"}],
    PARAM_HEATING_LAST_30d: [SENSOR_HEATING_LAST_30d, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"}, {DEFAULT_ICON: "mdi:cash"}],
    PARAM_HEATING_LAST_365d: [SENSOR_HEATING_LAST_365d, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"},
                              {DEFAULT_ICON: "mdi:cash"}],
    PARAM_MODE: [SENSOR_MODE, None, {
        DEFAULT_ICON: "mdi:water-boiler-off",
        VAL_WINTER: "mdi:snowflake",
        VAL_SUMMER: "mdi:water-pump",
        VAL_HEATING_ONLY: "mdi:mdi:radiator",
        VAL_OFF: "mdi:water-boiler-off"
    }],
    PARAM_OUTSIDE_TEMPERATURE: [SENSOR_OUTSIDE_TEMPERATURE, {DEFAULT_UNIT: '°C', 1: "°F"},
                                {DEFAULT_ICON: "mdi:thermometer"}],
    PARAM_SIGNAL_STRENGTH: [SENSOR_SIGNAL_STRENGTH, '%', {DEFAULT_ICON: "mdi:signal"}],
    PARAM_WATER_LAST_24H: [SENSOR_WATER_LAST_24H, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"}, {DEFAULT_ICON: "mdi:cash"}],
    PARAM_WATER_LAST_7D: [SENSOR_WATER_LAST_7D, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"}, {DEFAULT_ICON: "mdi:cash"}],
    PARAM_WATER_LAST_30D: [SENSOR_WATER_LAST_30D, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"}, {DEFAULT_ICON: "mdi:cash"}],
    PARAM_WATER_LAST_365D: [SENSOR_WATER_LAST_365D, {DEFAULT_UNIT: 'kWh', 1: "kBtuh"}, {DEFAULT_ICON: "mdi:cash"}],
    PARAM_UNITS: [SENSOR_UNITS, None, {DEFAULT_ICON: "mdi:scale-balance"}],
    PARAM_THERMAL_CLEANSE_CYCLE: [SENSOR_THERMAL_CLEANSE_CYCLE, 'h', {DEFAULT_ICON: "mdi:update"}],
    PARAM_GAS_TYPE: [SENSOR_GAS_TYPE, None, {DEFAULT_ICON: "mdi:gas-cylinder"}],
    PARAM_GAS_COST: [SENSOR_GAS_COST, None, {DEFAULT_ICON: "mdi:cash"}],
    PARAM_ELECTRICITY_COST: [SENSOR_ELECTRICITY_COST, None, {DEFAULT_ICON: "mdi:cash"}],
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
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        if self._sensor_type == PARAM_MODE:
            if self._state in MODE_TO_ICON:
                if os.path.isfile('/config/www/icons/' + MODE_TO_ICON[self._state]):
                    return "/local/icons/" + MODE_TO_ICON[self._state]
        return None

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        if isinstance(self._unit_of_measurement, dict):
            try:
                measurement = DEFAULT_UNIT
                if self._api._units == VAL_AUTO:
                    if self._api._ariston_units != {}:
                        measurement = self._api._ariston_units["measurementSystem"]
                elif self._api._units == VAL_IMPERIAL:
                    measurement = 1
                if measurement in self._unit_of_measurement:
                    return self._unit_of_measurement[measurement]
                else:
                    return self._unit_of_measurement[DEFAULT_UNIT]
            except:
                if DEFAULT_UNIT in self._unit_of_measurement:
                    return self._unit_of_measurement[DEFAULT_UNIT]
                return None
        else:
            return self._unit_of_measurement

    @property
    def available(self):
        """Return True if entity is available."""
        if self._sensor_type in [
            PARAM_ERRORS]:
            return self._api.available and self._api._ariston_error_data != {}
        elif self._sensor_type in [
            PARAM_CH_PROGRAM]:
            return self._api.available and self._api._ariston_ch_data != {}
        elif self._sensor_type in [
            PARAM_ACCOUNT_CH_GAS,
            PARAM_ACCOUNT_CH_ELECTRICITY,
            PARAM_ACCOUNT_DHW_GAS,
            PARAM_ACCOUNT_DHW_ELECTRICITY,
            PARAM_HEATING_LAST_24H,
            PARAM_HEATING_LAST_7d,
            PARAM_HEATING_LAST_30d,
            PARAM_HEATING_LAST_365d,
            PARAM_WATER_LAST_24H,
            PARAM_WATER_LAST_7D,
            PARAM_WATER_LAST_30D,
            PARAM_WATER_LAST_365D]:
            return self._api.available and self._api._ariston_gas_data != {}
        elif self._sensor_type in [
            PARAM_DHW_COMFORT_FUNCTION,
            PARAM_SIGNAL_STRENGTH,
            PARAM_THERMAL_CLEANSE_CYCLE]:
            return self._api.available and self._api._ariston_other_data != {}
        elif self._sensor_type in [
            PARAM_UNITS]:
            return self._api.available and self._api._ariston_units != {}
        elif self._sensor_type in [
            PARAM_GAS_TYPE,
            PARAM_GAS_COST,
            PARAM_ELECTRICITY_COST]:
            return self._api.available and self._api._ariston_currency != {}
        elif self._sensor_type in [
            PARAM_DHW_PROGRAM]:
            return self._api.available and self._api._ariston_dhw_data != {}
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
                self._state = VAL_UNKNOWN
                try:
                    for param_item in self._api._ariston_other_data:
                        if param_item["id"] == ARISTON_CH_COMFORT_TEMP:
                            self._state = param_item["value"]
                            break
                except:
                    pass

            elif self._sensor_type == PARAM_CH_ECONOMY_TEMPERATURE:
                self._state = VAL_UNKNOWN
                try:
                    for param_item in self._api._ariston_other_data:
                        if param_item["id"] == ARISTON_CH_ECONOMY_TEMP:
                            self._state = param_item["value"]
                            break
                except:
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
                    self._state = self._api._ariston_data["dhwStorageTemp"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_OUTSIDE_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["outsideTemp"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_DHW_COMFORT_TEMPERATURE:
                try:
                    self._state = self._api._ariston_data["dhwTimeProgComfortTemp"]["value"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_DHW_ECONOMY_TEMPERATURE:
                try:
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

            elif self._sensor_type == PARAM_ACCOUNT_CH_GAS:
                try:
                    self._state = self._api._ariston_gas_data["account"]["gasHeat"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_ACCOUNT_DHW_GAS:
                try:
                    self._state = self._api._ariston_gas_data["account"]["gasDhw"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_ACCOUNT_CH_ELECTRICITY:
                try:
                    self._state = self._api._ariston_gas_data["account"]["elecHeat"]
                except KeyError:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_ACCOUNT_DHW_ELECTRICITY:
                try:
                    self._state = self._api._ariston_gas_data["account"]["elecDhw"]
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

            elif self._sensor_type == PARAM_DHW_PROGRAM:
                try:
                    if self._api._ariston_dhw_data != {}:
                        self._state = VAL_AVAILABLE
                        for day_of_week in DAYS_OF_WEEK:
                            if day_of_week in self._api._ariston_dhw_data:
                                for day_slices in self._api._ariston_dhw_data[day_of_week]["slices"]:
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

            elif self._sensor_type == PARAM_THERMAL_CLEANSE_CYCLE:
                self._state = VAL_UNKNOWN
                try:
                    for param_item in self._api._ariston_other_data:
                        if param_item["id"] == ARISTON_THERMAL_CLEANSE_CYCLE:
                            self._state = param_item["value"]
                            break
                except:
                    pass

            elif self._sensor_type == PARAM_UNITS:
                try:
                    self._state = VALUE_TO_UNIT[self._api._ariston_units["measurementSystem"]]
                except:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_GAS_TYPE:
                try:
                    type_fetch = next((item for item in self._api._ariston_currency["gasTypeOptions"] if
                                       item["value"] == self._api._ariston_currency["gasType"]), {})
                    currency_fetch = next((item for item in self._api._ariston_currency["gasEnergyUnitOptions"] if
                                       item["value"] == self._api._ariston_currency["gasEnergyUnit"]), {})
                    self._state = type_fetch["text"]
                    self._unit_of_measurement = currency_fetch["text"]
                except:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_GAS_COST:
                self._attrs = {}
                try:
                    currency_symbol = next((item for item in self._api._ariston_currency["currencySymbols"] if
                                           item["Key"] == self._api._ariston_currency["currency"]), {})
                    currency_description = next((item for item in self._api._ariston_currency["currencyOptions"] if
                                            item["value"] == self._api._ariston_currency["currency"]), {})
                    if self._api._ariston_currency["gasCost"] == None:
                        self._state = VAL_UNKNOWN
                    else:
                        self._state = str(self._api._ariston_currency["gasCost"])
                    self._unit_of_measurement = currency_symbol["Value"]
                    self._attrs["currency"] = currency_description["text"]
                except:
                    self._state = VAL_UNKNOWN
                    pass

            elif self._sensor_type == PARAM_ELECTRICITY_COST:
                self._attrs = {}
                try:
                    currency_symbol = next((item for item in self._api._ariston_currency["currencySymbols"] if
                                           item["Key"] == self._api._ariston_currency["currency"]), {})
                    currency_description = next((item for item in self._api._ariston_currency["currencyOptions"] if
                                            item["value"] == self._api._ariston_currency["currency"]), {})
                    if self._api._ariston_currency["gasCost"] == None:
                        self._state = VAL_UNKNOWN
                    else:
                        self._state = str(self._api._ariston_currency["electricityCost"])
                    self._unit_of_measurement = currency_symbol["Value"]
                    self._attrs["currency"] = currency_description["text"]
                except:
                    self._state = VAL_UNKNOWN
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

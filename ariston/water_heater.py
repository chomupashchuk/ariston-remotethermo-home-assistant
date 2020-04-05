"""Support for Ariston water heaters."""
import json
import logging
import os
from datetime import timedelta

from homeassistant.components.water_heater import (
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterDevice,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

from .const import (
    DATA_ARISTON,
    DEVICES,
    CONF_CONTROL_FROM_WATER_HEATER,
    CONF_LOCALIZATION,
    CONF_DHW_FLAME_UNKNOWN_ON,
    LANG_LOCATION,
    MODE_TO_VALUE,
    PARAM_DHW_MODE,
    PARAM_DHW_COMFORT_TEMPERATURE,
    PARAM_DHW_ECONOMY_TEMPERATURE,
    PARAM_MODE,
    VAL_OFF,
    VAL_SUMMER,
    VAL_WINTER,
    VAL_SUMMER_MANUAL,
    VAL_SUMMER_PROGRAM,
    VAL_WINTER_MANUAL,
    VAL_WINTER_PROGRAM,
    VAL_HEATING_ONLY,
    VAL_OFFLINE,
    VAL_NOT_READY,
    VAL_MANUAL,
    VAL_PROGRAM,
    VAL_AUTO,
    VAL_IMPERIAL,
    VALUE_TO_MODE,
    VALUE_TO_DHW_MODE,
    UNKNOWN_TEMP,
    INVALID_STORAGE_TEMP,
)

"""STATE_SCAN_INTERVAL_SECS is used to scan changes in JSON data as command in '__init__' is not for checking and updating sensors"""
DEFAULT_MIN = 36.0
DEFAULT_MAX = 60.0
DEFAULT_TEMP = 0.0
ACTION_IDLE = "idle"
ACTION_HEATING = "heating"
STATE_SCAN_INTERVAL_SECS = 2

SUPPORT_FLAGS_HEATER = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE)
SUPPORT_FLAGS_HEATER_NO_OP = (SUPPORT_TARGET_TEMPERATURE)

SUPPORTED_OPERATIONS_1 = [
    VAL_OFF,
    VAL_SUMMER,
    VAL_WINTER,
    VAL_HEATING_ONLY
]
SUPPORTED_OPERATIONS_2 = [
    VAL_MANUAL,
    VAL_PROGRAM,
]

MODE_TO_ICON = {
    VAL_OFF: "ariston_water_heater_off.png",
    VAL_HEATING_ONLY: "ariston_water_heater_off.png",
    VAL_OFFLINE: "ariston_water_heater_off.png",
    VAL_SUMMER_MANUAL: "ariston_water_heater_off.png",
    VAL_SUMMER_PROGRAM: "ariston_water_heater_off.png",
    VAL_SUMMER: "ariston_water_heater_off.png",
    VAL_WINTER: "ariston_water_heater_manual.png",
    VAL_WINTER_MANUAL: "ariston_water_heater_manual.png",
    VAL_WINTER_PROGRAM: "ariston_water_heater_program.png",
    VAL_MANUAL: "ariston_water_heater_manual.png",
    VAL_PROGRAM: "ariston_water_heater_program.png"
}

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=STATE_SCAN_INTERVAL_SECS)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ariston water heater devices."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_ARISTON][DEVICES][name]

    add_entities([AristonWaterHeater(name, device)])


class AristonWaterHeater(WaterHeaterDevice):
    """Ariston Water Heater Device."""

    def __init__(self, name, device):
        """Initialize the thermostat."""
        self._name = name
        self._api = device.api
        try:
            lang = self._api._device[CONF_LOCALIZATION]
            with open(LANG_LOCATION + 'backend.' + lang + '.json') as translation_file:
                self._operations_translate = json.load(translation_file)["water_heater_operation"]
        except:
            self._operations_translate = {}
            pass

    @property
    def name(self):
        """Return the name of the Climate device."""
        return self._name

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        current_op = self.current_operation
        for item in self._operations_translate:
            if self._operations_translate[item] == current_op:
                # translate operation back to system format
                current_op = item
                break
        if current_op in MODE_TO_ICON:
            if os.path.isfile('/config/www/icons/' + MODE_TO_ICON[current_op]):
                return "/local/icons/" + MODE_TO_ICON[current_op]
        return None

    @property
    def icon(self):
        """Return the name of the Water Heater device."""
        try:
            current_mode = VALUE_TO_MODE[self._api._ariston_data["mode"]]
        except:
            current_mode = VAL_OFFLINE
            pass
        if current_mode in [VAL_SUMMER, VAL_WINTER]:
            return "mdi:water-pump"
        else:
            return "mdi:water-pump-off"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this thermostat."""
        return '_'.join([self._name, 'water_heater'])

    @property
    def should_poll(self):
        """Polling is required."""
        return True

    @property
    def available(self):
        """Return True if entity is available."""
        return self._api.available and self._api._ariston_data != {}

    @property
    def supported_features(self):
        """Return the list of supported features."""
        if self._api._device[CONF_CONTROL_FROM_WATER_HEATER]:
            return SUPPORT_FLAGS_HEATER
        elif "dhwModeNotChangeable" in self._api._ariston_data:
            if self._api._ariston_data["dhwModeNotChangeable"] == False:
                return SUPPORT_FLAGS_HEATER
        return SUPPORT_FLAGS_HEATER_NO_OP

    @property
    def current_temperature(self):
        """Return the temperature"""
        try:
            dhw_temp = self._api._ariston_data["dhwStorageTemp"]
            if dhw_temp in UNKNOWN_TEMP:
                dhw_temp = None
        except:
            dhw_temp = None
            pass
        return dhw_temp

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._api._units == VAL_AUTO:
            if "measurementSystem" in self._api._ariston_units:
                if self._api._ariston_units["measurementSystem"] == 1:
                    return TEMP_FAHRENHEIT
            return TEMP_CELSIUS
        elif self._api._units == VAL_IMPERIAL:
            return TEMP_FAHRENHEIT
        else:
            return TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return minimum temperature."""
        try:
            minimum_temp = self._api._ariston_data["dhwTemp"]["min"]
        except:
            minimum_temp = DEFAULT_MIN
            pass
        return minimum_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        try:
            maximum_temp = self._api._ariston_data["dhwTemp"]["max"]
        except:
            maximum_temp = DEFAULT_MAX
            pass
        return maximum_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        try:
            target_temp = self._api._ariston_data["dhwTemp"]["value"]
        except:
            target_temp = DEFAULT_TEMP
            pass
        return target_temp

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1.0

    @property
    def device_state_attributes(self):
        """Return the supported step of target temperature."""
        action = ACTION_IDLE
        try:
            if not self._api._ariston_data["zone"]["heatRequest"] and self._api._ariston_data["flameSensor"]:
                action = ACTION_HEATING
            elif self._api._ariston_data["flameForDhw"]:
                action = ACTION_HEATING
            elif self._api._ariston_data["dhwStorageTemp"] != INVALID_STORAGE_TEMP and self._api._dhw_trend_up and \
                    VALUE_TO_MODE[self._api._ariston_data["mode"]] in [VAL_SUMMER, VAL_WINTER] and \
                    self._api._ariston_data["flameSensor"]:
                action = ACTION_HEATING
            elif self._api._device[CONF_DHW_FLAME_UNKNOWN_ON] and self._api._ariston_data["flameSensor"]:
                action = ACTION_HEATING
        except:
            pass
        data = {"target_temp_step": 1.0, "hvac_action": action}
        return data

    @property
    def operation_list(self):
        """List of available operation modes."""
        op_list = []
        if self._api._device[CONF_CONTROL_FROM_WATER_HEATER]:
            for item in SUPPORTED_OPERATIONS_1:
                op_list.append(item)
            if not "allowedModes" in self._api._ariston_data:
                op_list.remove(VAL_HEATING_ONLY)
            elif not MODE_TO_VALUE[VAL_HEATING_ONLY] in self._api._ariston_data["allowedModes"]:
                op_list.remove(VAL_HEATING_ONLY)
        if "dhwModeNotChangeable" in self._api._ariston_data:
            if self._api._ariston_data["dhwModeNotChangeable"] == False:
                op_list.append(VAL_MANUAL)
                op_list.append(VAL_PROGRAM)
        for pos, item in enumerate(op_list):
            if item in self._operations_translate:
                # translate operation in operation list
                op_list[pos] = self._operations_translate[item]
        return op_list

    @property
    def current_operation(self):
        """Return current operation"""
        try:
            current_mode = VALUE_TO_MODE[self._api._ariston_data["mode"]]
            current_dhw_mode = VALUE_TO_DHW_MODE[self._api._ariston_data["dhwMode"]]
            if not self._api._device[CONF_CONTROL_FROM_WATER_HEATER]:
                current_op = current_dhw_mode
            elif self._api._ariston_data["dhwModeNotChangeable"] == False:
                if current_mode == VAL_SUMMER:
                    if current_dhw_mode == VAL_MANUAL:
                        current_op = VAL_SUMMER_MANUAL
                    else:
                        current_op = VAL_SUMMER_PROGRAM
                elif current_mode == VAL_WINTER:
                    if current_dhw_mode == VAL_MANUAL:
                        current_op = VAL_WINTER_MANUAL
                    else:
                        current_op = VAL_WINTER_PROGRAM
                elif current_mode == VAL_HEATING_ONLY:
                    current_op = VAL_HEATING_ONLY
                else:
                    current_op = VAL_OFF
            else:
                current_op = current_mode
        except:
            current_op = VAL_NOT_READY
            pass
        if current_op in self._operations_translate:
            # translate current operation
            current_op = self._operations_translate[current_op]
        return current_op

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        new_temperature = kwargs.get(ATTR_TEMPERATURE)
        if new_temperature is not None:
            try:
                if VALUE_TO_DHW_MODE[self._api._ariston_data["dhwMode"]] == VAL_PROGRAM:
                    if self._api._ariston_data["dhwTimeProgComfortActive"] == False:
                        # economy temperature is being used
                        self._api.set_http_data({PARAM_DHW_ECONOMY_TEMPERATURE: new_temperature})
                        return
            except:
                pass
            self._api.set_http_data({PARAM_DHW_COMFORT_TEMPERATURE: new_temperature})

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        for item in self._operations_translate:
            if self._operations_translate[item] == operation_mode:
                # translate operation back to system format
                operation_mode = item
                break
        if operation_mode in SUPPORTED_OPERATIONS_1:
            self._api.set_http_data({PARAM_MODE: operation_mode})
        elif operation_mode in SUPPORTED_OPERATIONS_2:
            self._api.set_http_data({PARAM_DHW_MODE: operation_mode})

    def update(self):
        """Update all Node data from Hive."""
        return

"""
Adds support for the Ariston Boiler
"""
import logging
from datetime import timedelta
import json

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    TEMP_CELSIUS,
)

from .const import (
    CONF_HVAC_OFF,
    CONF_HVAC_OFF_PRESENT,
    CONF_LOCALIZATION,
    LANG_LOCATION,
    DATA_ARISTON,
    DEVICES,
    PARAM_CH_MODE,
    PARAM_MODE,
    PARAM_CH_SET_TEMPERATURE,
    VAL_WINTER,
    VAL_SUMMER,
    VAL_HEATING_ONLY,
    VAL_OFF,
    VAL_MANUAL,
    VAL_PROGRAM,
    VAL_HOLIDAY,
    VAL_OFFLINE,
    VALUE_TO_MODE,
    VALUE_TO_CH_MODE,
)

DEFAULT_MIN = 10.0
DEFAULT_MAX = 30.0
DEFAULT_TEMP = 0.0

"""STATE_SCAN_INTERVAL_SECS is used to scan changes in JSON data as command in '__init__' is not for checking and updating sensors"""
STATE_SCAN_INTERVAL_SECS = 10

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=STATE_SCAN_INTERVAL_SECS)

SUPPORT_FLAGS = SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE
SUPPORTED_HVAC_MODES = [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]
SUPPORTED_HVAC_MODES_NO_OFF = [HVAC_MODE_AUTO, HVAC_MODE_HEAT]
SUPPORTED_PRESETS = [VAL_SUMMER, VAL_WINTER, VAL_OFF, VAL_HEATING_ONLY]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the Ariston Platform."""
    if discovery_info is None:
        return
    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_ARISTON][DEVICES][name]

    add_entities([AristonThermostat(name, device)])


class AristonThermostat(ClimateDevice):
    """Representation of a Ariston Thermostat."""

    def __init__(self, name, device):
        """Initialize the thermostat."""
        self._name = name
        self._api = device.api
        try:
            lang = self._api._device[CONF_LOCALIZATION]
            with open(LANG_LOCATION + 'backend.' + lang + '.json') as translation_file:
                self._preset_translate = json.load(translation_file)["climate_preset"]
        except:
            self._preset_translate = {}
            pass

    @property
    def icon(self):
        """Return the name of the Climate device."""
        return "mdi:water-boiler"

    @property
    def name(self):
        """Return the name of the Climate device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this thermostat."""
        return '_'.join([self._name, 'climate'])

    @property
    def should_poll(self):
        """Polling is required."""
        return True

    @property
    def min_temp(self):
        """Return minimum temperature."""
        try:
            minimum_temp = self._api._ariston_data["zone"]["comfortTemp"]["min"]
        except:
            minimum_temp = DEFAULT_MIN
            pass
        return minimum_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        try:
            maximum_temp = self._api._ariston_data["zone"]["comfortTemp"]["max"]
        except:
            maximum_temp = DEFAULT_MAX
            pass
        return maximum_temp

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        try:
            current_temp = self._api._ariston_data["zone"]["roomTemp"]
        except:
            current_temp = DEFAULT_TEMP
            pass
        return current_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        try:
            target_temp = self._api._ariston_data["zone"]["comfortTemp"]["value"]
        except:
            target_temp = DEFAULT_TEMP
            pass
        return target_temp

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        try:
            climate_mode = VALUE_TO_MODE[self._api._ariston_data["mode"]]
            climate_ch_mode = VALUE_TO_CH_MODE[self._api._ariston_data["zone"]["mode"]["value"]]
            curr_hvac_mode = HVAC_MODE_OFF
            if climate_mode in [VAL_WINTER, VAL_HEATING_ONLY]:
                if climate_ch_mode == VAL_MANUAL:
                    curr_hvac_mode = HVAC_MODE_HEAT
                elif climate_ch_mode == VAL_PROGRAM:
                    curr_hvac_mode = HVAC_MODE_AUTO
        except:
            curr_hvac_mode = HVAC_MODE_OFF
            pass
        return curr_hvac_mode

    @property
    def hvac_modes(self):
        """HVAC modes."""
        if self._api._device[CONF_HVAC_OFF_PRESENT] == True:
            return SUPPORTED_HVAC_MODES
        else:
            return SUPPORTED_HVAC_MODES_NO_OFF

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        try:
            climate_mode = VALUE_TO_MODE[self._api._ariston_data["mode"]]
            if climate_mode != VAL_OFF:
                if self._api._ariston_data["zone"]["heatRequest"] == True:
                    curr_hvac_action = CURRENT_HVAC_HEAT
                elif self._api._ariston_data["flameSensor"] == True and self._api._ariston_data["flameForDhw"] != True:
                    curr_hvac_action = CURRENT_HVAC_HEAT
                else:
                    curr_hvac_action = CURRENT_HVAC_IDLE
            else:
                curr_hvac_action = CURRENT_HVAC_OFF
        except:
            curr_hvac_action = CURRENT_HVAC_OFF
            pass
        return curr_hvac_action

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        try:
            if self.available:
                curr_preset_mode = VALUE_TO_MODE[self._api._ariston_data["mode"]]
                if self._api._ariston_data["zone"]["comfortTemp"]["value"] == self._api._ariston_data["zone"][
                    "antiFreezeTemp"] or self._api._ariston_data["holidayEnabled"]:
                    curr_preset_mode = VAL_HOLIDAY
            else:
                curr_preset_mode = VAL_OFFLINE
        except:
            curr_preset_mode = VAL_OFFLINE
            pass
        if curr_preset_mode in self._preset_translate:
            # translate current operation
            curr_preset_mode = self._preset_translate[curr_preset_mode]
        return curr_preset_mode

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        all_presets = []
        try:
            for item in self._api._ariston_data["allowedModes"]:
                try:
                    all_presets.append(VALUE_TO_MODE[item])
                except:
                    pass
        except:
            pass
        for pos, item in enumerate(all_presets):
            if item in self._preset_translate:
                # translate preset in preset list
                all_presets[pos] = self._preset_translate[item]
        return all_presets

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def available(self):
        """Return True if entity is available."""
        return self._api.available

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.5

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            if self._api._device[CONF_HVAC_OFF].lower() == VAL_OFF.lower():
                self._api.set_http_data({PARAM_MODE: VAL_OFF})
            else:
                self._api.set_http_data({PARAM_MODE: VAL_SUMMER})
        elif hvac_mode == HVAC_MODE_HEAT:
            self._api.set_http_data({PARAM_MODE: VAL_WINTER, PARAM_CH_MODE: VAL_MANUAL})
        elif hvac_mode == HVAC_MODE_AUTO:
            self._api.set_http_data({PARAM_MODE: VAL_WINTER, PARAM_CH_MODE: VAL_PROGRAM})

    def set_preset_mode(self, preset_mode):
        """Set new target hvac mode."""
        for item in self._preset_translate:
            if self._preset_translate[item] == preset_mode:
                # translate operation back to system format
                preset_mode = item
                break
        if preset_mode in SUPPORTED_PRESETS:
            self._api.set_http_data({PARAM_MODE: preset_mode})

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        new_temperature = kwargs.get(ATTR_TEMPERATURE)
        if new_temperature is not None:
            self._api.set_http_data({PARAM_CH_SET_TEMPERATURE: new_temperature})

    def update(self):
        """Update all Node data from Hive."""
        return

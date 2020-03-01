"""Support for Ariston water heaters."""
import logging
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
)

from .const import (
    DATA_ARISTON,
    DEVICES,
    MODE_TO_VALUE,
    PARAM_DHW_MODE,
    PARAM_DHW_SET_TEMPERATURE,
    PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE,
    PARAM_MODE,
    VAL_OFF,
    VAL_SUMMER,
    VAL_WINTER,
    VAL_SUMMER_MANUAL,
    VAL_SUMMER_SCHEDULED,
    VAL_WINTER_MANUAL,
    VAL_WINTER_SCHEDULED,
    VAL_HEATING_ONLY,
    VAL_OFFLINE,
    VAL_MANUAL,
    VAL_SCHEDULED,
    VALUE_TO_MODE,
    VALUE_TO_DHW_MODE,
    UNKNOWN_TEMP,
)

"""STATE_SCAN_INTERVAL_SECS is used to scan changes in JSON data as command in '__init__' is not for checking and updating sensors"""
DEFAULT_MIN = 36.0
DEFAULT_MAX = 60.0
DEFAULT_TEMP = 0.0
STATE_SCAN_INTERVAL_SECS = 10

SUPPORT_FLAGS_HEATER = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE)
SUPPORTED_OPERATIONS_1 = [
    VAL_OFF,
    VAL_SUMMER,
    VAL_WINTER,
    VAL_HEATING_ONLY,
]
SUPPORTED_OPERATIONS_2 = [
    VAL_MANUAL,
    VAL_SCHEDULED,
]

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

    @property
    def name(self):
        """Return the name of the Climate device."""
        return self._name

    @property
    def icon(self):
        """Return the name of the Water Heater device."""
        return "mdi:water-pump"

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
        return self._api.available

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_HEATER

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
    def operation_list(self):
        """List of available operation modes."""
        op_list = [VAL_OFF]
        op_list.append(VAL_SUMMER)
        op_list.append(VAL_WINTER)
        try:
            if MODE_TO_VALUE[VAL_HEATING_ONLY] in self._api._ariston_data["allowedModes"]:
                op_list.append(VAL_HEATING_ONLY)
            if self._api._ariston_data["dhwModeNotChangeable"] == False:
                op_list.append(VAL_MANUAL)
                op_list.append(VAL_SCHEDULED)
        except:
            pass
        return op_list

    @property
    def current_operation(self):
        """Return current operation"""
        try:
            current_mode = VALUE_TO_MODE[self._api._ariston_data["mode"]]
            current_dhw_mode = VALUE_TO_DHW_MODE[self._api._ariston_data["dhwMode"]]
            if self._api._ariston_data["dhwModeNotChangeable"] == False:
                if current_mode == VAL_SUMMER:
                    if current_dhw_mode == VAL_MANUAL:
                        current_op = VAL_SUMMER_MANUAL
                    else:
                        current_op = VAL_SUMMER_SCHEDULED
                elif current_mode == VAL_WINTER:
                    if current_dhw_mode == VAL_MANUAL:
                        current_op = VAL_WINTER_MANUAL
                    else:
                        current_op = VAL_WINTER_SCHEDULED
                elif current_mode == VAL_HEATING_ONLY:
                    current_op = VAL_HEATING_ONLY
                else:
                    current_op = VAL_OFF
            else:
                current_op = current_mode
        except:
            current_op = VAL_OFFLINE
            pass
        return current_op

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        new_temperature = kwargs.get(ATTR_TEMPERATURE)
        if new_temperature is not None:
            self._api.set_http_data({PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE: new_temperature})

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        if operation_mode in SUPPORTED_OPERATIONS_1:
            self._api.set_http_data({PARAM_MODE: operation_mode})
        elif operation_mode in SUPPORTED_OPERATIONS_2:
            self._api.set_http_data({PARAM_DHW_MODE: operation_mode})

    def update(self):
        """Update all Node data from Hive."""
        return

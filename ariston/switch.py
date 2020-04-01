"""Suppoort for Ariston switch."""
from datetime import timedelta

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_SWITCHES, CONF_NAME

from .const import (
    ARISTON_INTERNET_TIME,
    ARISTON_INTERNET_WEATHER,
    ARISTON_CH_AUTO_FUNCTION,
    ARISTON_THERMAL_CLEANSE_FUNCTION,
    CONF_POWER_ON,
    DATA_ARISTON,
    DEVICES,
    PARAM_MODE,
    VAL_OFF,
    VALUE_TO_MODE,
    PARAM_INTERNET_TIME,
    PARAM_INTERNET_WEATHER,
    PARAM_POWER,
    PARAM_CH_AUTO_FUNCTION,
    PARAM_THERMAL_CLEANSE_FUNCTION,
    SWITCH_POWER,
    BINARY_SENSOR_INTERNET_TIME,
    BINARY_SENSOR_INTERNET_WEATHER,
    BINARY_SENSOR_CH_AUTO_FUNCTION,
    BINARY_SENSOR_THERMAL_CLEANSE_FUNCTION,
    GET_REQUEST_CH_PROGRAM,
    GET_REQUEST_CURRENCY,
    GET_REQUEST_DHW_PROGRAM,
    GET_REQUEST_ERRORS,
    GET_REQUEST_GAS,
    GET_REQUEST_MAIN,
    GET_REQUEST_PARAM,
    GET_REQUEST_UNITS,
    GET_REQUEST_VERSION,
)

STATE_SCAN_INTERVAL_SECS = 3

SCAN_INTERVAL = timedelta(seconds=STATE_SCAN_INTERVAL_SECS)

SWITCHES = {
    PARAM_POWER: (SWITCH_POWER, "mdi:power"),
    PARAM_INTERNET_TIME: (BINARY_SENSOR_INTERNET_TIME, "mdi:update"),
    PARAM_INTERNET_WEATHER: (BINARY_SENSOR_INTERNET_WEATHER, "mdi:weather-partly-cloudy"),
    PARAM_CH_AUTO_FUNCTION: (BINARY_SENSOR_CH_AUTO_FUNCTION, "mdi:radiator"),
    PARAM_THERMAL_CLEANSE_FUNCTION: (BINARY_SENSOR_THERMAL_CLEANSE_FUNCTION, "mdi:allergy"),
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a switches for Ariston."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_ARISTON][DEVICES][name]
    async_add_entities(
        [
            AristonSwitch(name, device, switch_type)
            for switch_type in discovery_info[CONF_SWITCHES]
        ],
        True,
    )


class AristonSwitch(SwitchDevice):
    """Switch for Ariston."""

    def __init__(self, name, device, switch_type):
        """Initialize entity."""
        self._api = device.api
        self._icon = SWITCHES[switch_type][1]
        self._name = "{} {}".format(name, SWITCHES[switch_type][0])
        self._switch_type = switch_type
        self._signal_name = name
        self._state = None
        self._unsub_dispatcher = None

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return True

    @property
    def name(self):
        """Return the name of this Switch device if any."""
        return self._name

    @property
    def icon(self):
        """Return the state attributes."""
        return self._icon

    @property
    def available(self):
        """Return True if entity is available."""
        if self._switch_type in GET_REQUEST_PARAM:
            return self._api.available and self._api._ariston_other_data != {}
        else:
            return self._api.available and self._api._ariston_data != {}

    @property
    def is_on(self):
        """Return true if switch is on."""
        try:
            status_on = False
            if self._switch_type == PARAM_POWER:
                climate_mode = VALUE_TO_MODE[self._api._ariston_data["mode"]]
                if climate_mode == VAL_OFF:
                    status_on = False
                else:
                    status_on = True
            elif self._switch_type == PARAM_INTERNET_TIME:
                for param_item in self._api._ariston_other_data:
                    if param_item["id"] == ARISTON_INTERNET_TIME:
                        if param_item["value"] == 1:
                            status_on = True
                            break
            elif self._switch_type == PARAM_INTERNET_WEATHER:
                for param_item in self._api._ariston_other_data:
                    if param_item["id"] == ARISTON_INTERNET_WEATHER:
                        if param_item["value"] == 1:
                            status_on = True
                            break
            elif self._switch_type == PARAM_CH_AUTO_FUNCTION:
                for param_item in self._api._ariston_other_data:
                    if param_item["id"] == ARISTON_CH_AUTO_FUNCTION:
                        if param_item["value"] == 1:
                            status_on = True
                            break
            elif self._switch_type == PARAM_THERMAL_CLEANSE_FUNCTION:
                for param_item in self._api._ariston_other_data:
                    if param_item["id"] == ARISTON_THERMAL_CLEANSE_FUNCTION:
                        if param_item["value"] == 1:
                            status_on = True
                            break
        except:
            status_on = False
            pass
        return status_on

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self._switch_type == PARAM_POWER:
            self._api.set_http_data({PARAM_MODE: self._api._device[CONF_POWER_ON]})
        elif self._switch_type in [
            PARAM_INTERNET_TIME,
            PARAM_INTERNET_WEATHER,
            PARAM_CH_AUTO_FUNCTION,
            PARAM_THERMAL_CLEANSE_FUNCTION]:
            self._api.set_http_data({self._switch_type: "true"})

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self._switch_type == PARAM_POWER:
            self._api.set_http_data({PARAM_MODE: VAL_OFF})
        elif self._switch_type in [
            PARAM_INTERNET_TIME,
            PARAM_INTERNET_WEATHER,
            PARAM_CH_AUTO_FUNCTION,
            PARAM_THERMAL_CLEANSE_FUNCTION]:
            self._api.set_http_data({self._switch_type: "false"})

    def update(self):
        """Update data"""
        return

"""Suppoort for Ariston switch."""
from datetime import timedelta

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_SWITCHES, CONF_NAME
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CONF_POWER_ON,
    DATA_ARISTON,
    DEVICES,
    PARAM_MODE,
    SERVICE_UPDATE,
    VAL_SUMMER,
    VAL_OFF,
    VAL_WINTER,
    VALUE_TO_MODE,
)
from .helpers import service_signal

STATE_SCAN_INTERVAL_SECS = 3

SCAN_INTERVAL = timedelta(seconds=STATE_SCAN_INTERVAL_SECS)

POWER = "power"

SWITCHES = {
    POWER: ("Power", "mdi:power"),
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
        return self._api.available

    @property
    def is_on(self):
        """Return true if switch is on."""
        try:
            climate_mode = VALUE_TO_MODE[self._api._ariston_data["mode"]]
            if self._switch_type == POWER:
                if climate_mode == VAL_OFF:
                    status_on = False
                else:
                    status_on = True
            else:
                status_on = False
        except:
            status_on = False
        return status_on

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self._switch_type == POWER:
            if self._api._device[CONF_POWER_ON].lower() == VAL_SUMMER.lower():
                self._api._set_http_data({PARAM_MODE: VAL_SUMMER})
            elif self._api._device[CONF_POWER_ON].lower() == VAL_WINTER.lower():
                self._api._set_http_data({PARAM_MODE: VAL_WINTER})

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self._switch_type == POWER:
            self._api._set_http_data({PARAM_MODE: VAL_OFF})

    def update(self):
        """Update data"""
        return

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

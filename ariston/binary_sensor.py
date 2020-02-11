"""Suppoort for Ariston binary sensors."""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_HEAT,
    BinarySensorDevice,
)
from homeassistant.const import CONF_BINARY_SENSORS, CONF_NAME
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DATA_ARISTON,
    DEVICES,
    SERVICE_UPDATE,
    PARAM_HOLIDAY_MODE,
    PARAM_ONLINE,
    PARAM_FLAME,
)
from .helpers import log_update_error, service_signal
from .exceptions import AristonError

"""BINARY_SENSOR_SCAN_INTERVAL_SECS is used to scan changes in JSON data as command in '__init__' is not for checking and updating sensors"""
BINARY_SENSOR_SCAN_INTERVAL_SECS = 3

SCAN_INTERVAL = timedelta(seconds=BINARY_SENSOR_SCAN_INTERVAL_SECS)

_LOGGER = logging.getLogger(__name__)

# Binary sensor types are defined like: Name, device class
BINARY_SENSORS = {
    PARAM_HOLIDAY_MODE: ("Hiliday Mode", None, "mdi:island"),
    PARAM_ONLINE: ("Online", DEVICE_CLASS_CONNECTIVITY, None),
    PARAM_FLAME: ("Flame", DEVICE_CLASS_HEAT, None),
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


class AristonBinarySensor(BinarySensorDevice):
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
        return self._sensor_type == PARAM_ONLINE or self._api.available

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
                    if self._api._ariston_data["zone"]["comfortTemp"]["value"] == self._api._ariston_data["zone"]["antiFreezeTemp"] or self._api._ariston_data["holidayEnabled"]:
                        self._state = True
                    else:
                        self._state = False
                except:
                    self._state = False

            elif self._sensor_type == PARAM_ONLINE:
                self._state = self._api.available
            
            elif self._sensor_type == PARAM_FLAME:
                try:
                    self._state = self._api._ariston_data["flameSensor"]
                except:
                    self._state = False
            
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
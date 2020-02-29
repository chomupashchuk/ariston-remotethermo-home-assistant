"""Suppoort for Ariston."""
import copy
import json
import logging
import threading
import time
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import requests
import voluptuous as vol
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.climate import DOMAIN as CLIMATE
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_BINARY_SENSORS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_USERNAME,
)
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_point_in_time
from homeassistant.util import dt as dt_util

from .binary_sensor import BINARY_SENSORS
from .const import (
    CH_MODE_TO_VALUE,
    CLIMATES,
    CONF_HVAC_OFF,
    CONF_POWER_ON,
    CONF_MAX_RETRIES,
    CONF_STORE_CONFIG_FILES,
    DATA_ARISTON,
    DAYS_OF_WEEK,
    DEVICES,
    DHW_MODE_TO_VALUE,
    DOMAIN,
    MODE_TO_VALUE,
    SERVICE_SET_DATA,
    SERVICE_UPDATE,
    PARAM_MODE,
    PARAM_CH_MODE,
    PARAM_CH_SET_TEMPERATURE,
    PARAM_DHW_MODE,
    PARAM_DHW_SET_TEMPERATURE,
    PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE,
    PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE,
    PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE,
    PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE,
    VAL_MODE_WINTER,
    VAL_MODE_SUMMER,
    VAL_MODE_OFF,
    VAL_CH_MODE_MANUAL,
    VAL_CH_MODE_SCHEDULED,
    WATER_HEATERS,
)
from .exceptions import CommError, LoginError, AristonError
from .helpers import service_signal
from .sensor import SENSORS
from .switch import SWITCHES

"""HTTP_RETRY_INTERVAL is time between 2 GET requests. Note that it often takes more than 10 seconds to properly fetch data, also potential login"""
"""MAX_ERRORS is number of errors for device to become not available"""
"""HTTP_TIMEOUT_LOGIN is timeout for login procedure"""
"""HTTP_TIMEOUT_GET is timeout to get data (can increase restart time in some cases). For tested environment often around 10 seconds, rarely above 15"""
"""HTTP_TIMEOUT_SET is timeout to set data"""

ARISTON_URL = "https://www.ariston-net.remotethermo.com"
DEFAULT_HVAC = "summer"
DEFAULT_POWER_ON = "summer"
DEFAULT_NAME = "Ariston"
DEFAULT_MAX_RETRIES = 1
DEFAULT_TIME = "00:00"
HTTP_RETRY_INTERVAL = 60
HTTP_RETRY_INTERVAL_DOWN = 90
TIMER_SET_LOCK = 25
HTTP_TIMEOUT_LOGIN = 3
HTTP_TIMEOUT_GET = 15
HTTP_TIMEOUT_SET = 15
HTTP_TIMEOUT_SET_CH = 10
HTTP_ADDITIONAL_GET = 3
MAX_ERRORS = 3
MAX_ERRORS_TIMER_EXTEND = 2
HTTP_GAS_WATER_MULTIPLY_TIME = 10
HTTP_ERROR_MULTIPLY_TIME = 3
HTTP_CH_MULTIPLY_TIME = 3
HTTP_OTHER_MULTIPLY_TIME = 10
DEFAULT_MODES = [0, 1, 5]
DEFAULT_CH_MODES = [2, 3]
HTTP_SET_INTERVAL = HTTP_RETRY_INTERVAL_DOWN + TIMER_SET_LOCK + 5
HTTP_SET_INTERVAL_CH = HTTP_RETRY_INTERVAL_DOWN * HTTP_CH_MULTIPLY_TIME + TIMER_SET_LOCK + 5

_LOGGER = logging.getLogger(__name__)

def _has_unique_names(devices):
    names = [device[CONF_NAME] for device in devices]
    vol.Schema(vol.Unique())(names)
    return devices


def _change_to_24h_format(time_str_12h=""):
    """Convert to 24H format if in 12H format"""
    if not isinstance(time_str_12h, str):
        time_str_12h = DEFAULT_TIME
    try:
        if len(time_str_12h) > 5:
            time_and_indic = time_str_12h.split(' ')
            if time_and_indic[1] == "AM":
                if time_and_indic[0] == "12:00":
                    time_str_24h = "00:00"
                else:
                    time_str_24h = time_and_indic[0]
            elif time_and_indic[1] == "PM":
                if time_and_indic[0] == "12:00":
                    time_str_24h = "12:00"
                else:
                    time_hour_minute = time_and_indic[0].split(":")
                    time_str_24h = str(int(time_hour_minute[0]) + 12) + ":" + time_hour_minute[1]
            else:
                time_str_24h = DEFAULT_TIME
        else:
            time_str_24h = time_str_12h
    except:
        time_str_24h = DEFAULT_TIME
        pass
    return time_str_24h


ARISTON_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_BINARY_SENSORS): vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)]),
        vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [vol.In(SENSORS)]),
        vol.Optional(CONF_HVAC_OFF, default=DEFAULT_HVAC): vol.In(["OFF", "off", "Off", "summer", "SUMMER", "Summer"]),
        vol.Optional(CONF_POWER_ON, default=DEFAULT_POWER_ON): vol.In(
            ["WINTER", "winter", "Winter", "summer", "SUMMER", "Summer"]),
        vol.Optional(CONF_MAX_RETRIES, default=DEFAULT_MAX_RETRIES): vol.All(int, vol.Range(min=0, max=65535)),
        vol.Optional(CONF_SWITCHES): vol.All(cv.ensure_list, [vol.In(SWITCHES)]),
        vol.Optional(CONF_STORE_CONFIG_FILES, default=False): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [ARISTON_SCHEMA], _has_unique_names)},
    extra=vol.ALLOW_EXTRA,
)


class AristonChecker():
    """Ariston checker"""

    def __init__(self, hass, device, name, username, password, retries, store_file):
        """Initialize."""
        self._ariston_data = {}
        self._ariston_gas_data = {}
        self._ariston_error_data = {}
        self._ariston_ch_data = {}
        self._ariston_other_data = {}
        self._data_lock = threading.Lock()
        self._device = device
        self._errors = 0
        self._get_time_start = 0
        self._get_time_end = 0
        self._get_time_start_ch = 0
        self._get_time_end_ch = 0
        self._hass = hass
        self._init_available = False
        self._lock = threading.Lock()
        self._login = False
        self._name = name
        self._password = password
        self._plant_id = ""
        self._plant_id_lock = threading.Lock()
        self._retry_timeout = HTTP_RETRY_INTERVAL
        self._session = requests.Session()
        self._set_param = {}
        self._set_main_retry = 0
        self._set_ch_retry = 0
        self._set_max_retries = retries
        self._set_new_data_pending = False
        self._set_scheduled = False
        self._set_time_start = 0
        self._set_time_end = 0
        self._store_file = store_file
        self._token_lock = threading.Lock()
        self._token = None
        self._url = ARISTON_URL
        self._user = username
        self._verify = True

    @property
    def available(self):
        """Return if Aristons's API is responding."""
        return self._errors <= MAX_ERRORS and self._init_available

    def _login_session(self):
        """Login to fetch Ariston Plant ID and confirm login"""
        if not self._login:
            url = self._url + '/Account/Login'
            try:
                with self._token_lock:
                    self._token = requests.auth.HTTPDigestAuth(
                        self._user, self._password)
                login_data = {"Email": self._user, "Password": self._password}
                resp = self._session.post(
                    url,
                    auth=self._token,
                    timeout=HTTP_TIMEOUT_LOGIN,
                    json=login_data)
            except requests.exceptions.ReadTimeout as error:
                _LOGGER.warning('%s Authentication timeout', self)
                raise CommError(error)
            except LoginError:
                _LOGGER.warning('%s Authentication login error', self)
                raise
            except CommError:
                _LOGGER.warning('%s Authentication communication error', self)
                raise
            if resp.url.startswith(self._url + "/PlantDashboard/Index/"):
                with self._plant_id_lock:
                    self._plant_id = resp.url.split("/")[5]
                    self._login = True
                    _LOGGER.info('%s Plant ID is %s', self, self._plant_id)
            else:
                _LOGGER.warning('%s Authentication login error', self)
                raise LoginError

    def _store_main_data(self, received_data={}, request_type=""):
        """Store received dictionary"""
        try:
            allowed_modes = self._ariston_data["allowedModes"]
            allowed_ch_modes = allowed_ch_modes = self._ariston_data["zone"]["mode"]["allowedOptions"]
        except:
            allowed_modes = []
            allowed_ch_modes = []
            pass
        try:
            self._ariston_data = copy.deepcopy(received_data)
        except:
            with self._plant_id_lock:
                self._login = False
            _LOGGER.warning("%s Invalid data received, not JSON", self)
            raise CommError
        try:
            if self._ariston_data["allowedModes"] == []:
                if allowed_modes != []:
                    self._ariston_data["allowedModes"] = allowed_modes
                else:
                    self._ariston_data["allowedModes"] = DEFAULT_MODES
            if self._ariston_data["zone"]["mode"]["allowedOptions"] == []:
                if allowed_ch_modes != []:
                    self._ariston_data["zone"]["mode"]["allowedOptions"] = allowed_ch_modes
                else:
                    self._ariston_data["zone"]["mode"]["allowedOptions"] = DEFAULT_CH_MODES
            if self._store_file:
                with open('/config/data_' + self._name + request_type + '_main.json', 'w') as ariston_fetched:
                    json.dump(self._ariston_data, ariston_fetched)
        except:
            self._ariston_data["allowedModes"] = DEFAULT_MODES
            self._ariston_data["zone"]["mode"]["allowedOptions"] = DEFAULT_CH_MODES
            raise

    def _get_http_data(self):
        """Get Ariston data from http"""
        self._login_session()
        if self._login and self._plant_id != "":
            if time.time() - self._set_time_start > TIMER_SET_LOCK:
                # give time to read new data
                with self._data_lock:
                    try:
                        url = self._url + '/PlantDashboard/GetPlantData/' + self._plant_id
                        self._get_time_start = time.time()
                        resp = self._session.get(
                            url,
                            auth=self._token,
                            timeout=HTTP_TIMEOUT_GET,
                            verify=self._verify)
                        if resp.status_code == 599:
                            _LOGGER.warning("%s Code %s, data is %s", self, resp.status_code, resp.text)
                            raise CommError
                        elif resp.status_code == 500:
                            with self._plant_id_lock:
                                self._login = False
                            _LOGGER.warning("%s Code %s, data is %s", self, resp.status_code, resp.text)
                            raise CommError
                        elif resp.status_code != 200:
                            _LOGGER.warning("%s Unexpected reply %s", self, resp.status_code)
                            raise CommError
                        resp.raise_for_status()
                        # successful data fetching
                        self._get_time_end = time.time()
                        """
                        #uncomment below to store request time
                        f=open("/config/tmp/read_time.txt", "a+")
                        f.write("{}\n".format(self._get_time_end - self._get_time_start))
                        """
                    except requests.RequestException as error:
                        _LOGGER.warning("%s Failed due to error: %r", self, error)
                        raise CommError(error)
                    _LOGGER.info("%s Query worked. Exit code: <%s>", self, resp.status_code)

                    self._store_main_data(resp.json(), "_get")
            else:
                _LOGGER.debug("%s Setting data read restricted", self)
        else:
            _LOGGER.warning("%s Not properly logged in to get data", self)
            raise LoginError

    def _get_gas_water_data(self, dummy=None):
        """Get Ariston gas and water use data from http"""
        if self._errors >= MAX_ERRORS_TIMER_EXTEND:
            # give a little rest to the system
            retry_in = HTTP_RETRY_INTERVAL_DOWN * HTTP_GAS_WATER_MULTIPLY_TIME
        else:
            retry_in = HTTP_RETRY_INTERVAL * HTTP_GAS_WATER_MULTIPLY_TIME
        retry_time = dt_util.now() + timedelta(seconds=retry_in)
        track_point_in_time(self._hass, self._get_gas_water_data, retry_time)
        self._login_session()
        if self._login and self._plant_id != "":
            if time.time() - self._set_time_start > TIMER_SET_LOCK:
                with self._data_lock:
                    # give time to read new data
                    try:
                        url = self._url + '/Metering/GetData/' + self._plant_id + '?kind=1&umsys=si'
                        resp = self._session.get(
                            url,
                            auth=self._token,
                            timeout=HTTP_ADDITIONAL_GET,
                            verify=self._verify)
                        resp.raise_for_status()
                        if resp.status_code == 200:
                            self._ariston_gas_data = copy.deepcopy(resp.json())
                            if self._store_file:
                                with open('/config/data_' + self._name + '_gas.json', 'w') as ariston_fetched:
                                    json.dump(resp.json(), ariston_fetched)
                    except:
                        _LOGGER.warning("%s Problem reading Gas and Water use data", self)
                        raise CommError
            else:
                _LOGGER.debug("%s Setting data read restricted", self)
        else:
            _LOGGER.warning("%s Not properly logged in to get data", self)
            raise LoginError

    def _get_error_data(self, dummy=None):
        """Get Ariston error data from http"""
        if self._errors >= MAX_ERRORS_TIMER_EXTEND:
            # give a little rest to the system
            retry_in = HTTP_RETRY_INTERVAL_DOWN * HTTP_ERROR_MULTIPLY_TIME
        else:
            retry_in = HTTP_RETRY_INTERVAL * HTTP_ERROR_MULTIPLY_TIME
        retry_time = dt_util.now() + timedelta(seconds=retry_in)
        track_point_in_time(self._hass, self._get_error_data, retry_time)
        self._login_session()
        if self._login and self._plant_id != "":
            if time.time() - self._set_time_start > TIMER_SET_LOCK:
                with self._data_lock:
                    # give time to read new data
                    try:
                        url = self._url + '/Error/ActiveDataSource/' + self._plant_id + '?$inlinecount=allpages&$skip=0&$top=100'
                        resp = self._session.get(
                            url,
                            auth=self._token,
                            timeout=HTTP_ADDITIONAL_GET,
                            verify=self._verify)
                        resp.raise_for_status()
                        if resp.status_code == 200:
                            self._ariston_error_data = copy.deepcopy(resp.json())
                            if self._store_file:
                                with open('/config/data_' + self._name + '_errors.json', 'w') as ariston_fetched:
                                    json.dump(resp.json(), ariston_fetched)
                    except:
                        _LOGGER.warning("%s Problem reading Error use data", self)
                        raise CommError
            else:
                _LOGGER.debug("%s Setting data read restricted", self)
        else:
            _LOGGER.warning("%s Not properly logged in to get data", self)
            raise LoginError

    def _get_ch_data(self, dummy=None):
        """Get Ariston CH data from http"""
        if self._errors >= MAX_ERRORS_TIMER_EXTEND:
            # give a little rest to the system
            retry_in = HTTP_RETRY_INTERVAL_DOWN * HTTP_CH_MULTIPLY_TIME
        else:
            retry_in = HTTP_RETRY_INTERVAL * HTTP_CH_MULTIPLY_TIME
        retry_time = dt_util.now() + timedelta(seconds=retry_in)
        track_point_in_time(self._hass, self._get_ch_data, retry_time)
        self._login_session()
        if self._login and self._plant_id != "":
            if time.time() - self._set_time_start > TIMER_SET_LOCK:
                with self._data_lock:
                    # give time to read new data
                    try:
                        self._get_time_start_ch = time.time()
                        url = self._url + '/TimeProg/GetWeeklyPlan/' + self._plant_id + '?progId=ChZn1&umsys=si'
                        resp = self._session.get(
                            url,
                            auth=self._token,
                            timeout=HTTP_ADDITIONAL_GET,
                            verify=self._verify)
                        resp.raise_for_status()
                        if resp.status_code == 200:
                            self._get_time_end_ch = time.time()
                            self._ariston_ch_data = copy.deepcopy(resp.json())
                            if self._store_file:
                                with open('/config/data_' + self._name + '_ch_weekly.json', 'w') as ariston_ch_fetched:
                                    json.dump(resp.json(), ariston_ch_fetched)
                    except:
                        _LOGGER.warning("%s Problem reading CH data", self)
                        raise CommError
            else:
                _LOGGER.debug("%s Setting data read restricted", self)
        else:
            _LOGGER.warning("%s Not properly logged in to get data", self)
            raise LoginError

    def _get_other_data(self, dummy=None):
        """Get Ariston other data from http"""
        if self._errors >= MAX_ERRORS_TIMER_EXTEND:
            # give a little rest to the system
            retry_in = HTTP_RETRY_INTERVAL_DOWN * HTTP_OTHER_MULTIPLY_TIME
        else:
            retry_in = HTTP_RETRY_INTERVAL * HTTP_OTHER_MULTIPLY_TIME
        retry_time = dt_util.now() + timedelta(seconds=retry_in)
        track_point_in_time(self._hass, self._get_other_data, retry_time)
        self._login_session()
        if self._login and self._plant_id != "":
            if time.time() - self._set_time_start > TIMER_SET_LOCK:
                with self._data_lock:
                    # give time to read new data
                    try:
                        url = self._url + '/Menu/User/Refresh/' + self._plant_id + '?paramIds=U6_16_0,U6_16_5,U6_16_6,U6_16_7,U6_9_2&umsys=si'
                        resp = self._session.get(
                            url,
                            auth=self._token,
                            timeout=HTTP_ADDITIONAL_GET,
                            verify=self._verify)
                        resp.raise_for_status()

                        if resp.status_code == 200:
                            self._ariston_other_data = copy.deepcopy(resp.json())
                            if self._store_file:
                                with open('/config/data_' + self._name + '_params.json', 'w') as ariston_fetched:
                                    json.dump(resp.json(), ariston_fetched)
                    except:
                        _LOGGER.warning("%s Problem reading other data", self)
                        raise CommError
            else:
                _LOGGER.debug("%s Setting data read restricted", self)

        else:
            _LOGGER.warning("%s Not properly logged in to get data", self)
            raise LoginError


    def _actual_set_http_data(self, dummy=None):
        self._login_session()
        with self._data_lock:
            if not self._set_new_data_pending:
                # initiated from schedule, no longer scheduled
                self._set_scheduled = False
            else:
                # initiated from set_http_data, no longer pending
                self._set_new_data_pending = False
                self._set_main_retry = 0
                self._set_ch_retry = 0
                if self._set_scheduled:
                    # we wait for another attempt after timeout, data will be set then
                    return
            if self._login and self.available and self._plant_id != "":
                main_data_changed = False
                ch_data_changed = False
                set_data = {}

                # prepare setting of main data dictionary
                set_data["NewValue"] = copy.deepcopy(self._ariston_data)
                set_data["OldValue"] = copy.deepcopy(self._ariston_data)
                # Format is received in 12H format but for some reason REST tools send it fine but python must send 24H format
                try:
                    set_data["NewValue"]["zone"]["derogaUntil"] = _change_to_24h_format(
                        self._ariston_data["zone"]["derogaUntil"])
                    set_data["OldValue"]["zone"]["derogaUntil"] = _change_to_24h_format(
                        self._ariston_data["zone"]["derogaUntil"])
                except:
                    set_data["NewValue"]["zone"]["derogaUntil"] = DEFAULT_TIME
                    set_data["OldValue"]["zone"]["derogaUntil"] = DEFAULT_TIME
                    pass
    
                # prepare setting of CH data dictionary
                try:
                    set_ch_data = copy.deepcopy(self._ariston_ch_data)
                    set_ch_data["progId"] = "ChZn1"
                    set_ch_data["comfortTemp"]["formattedValue"] = str(set_ch_data["comfortTemp"]["value"])
                    set_ch_data["comfortTemp"]["upDownVisible"] = False
                    set_ch_data["comfortTemp"]["readOnly"] = True
                    set_ch_data["economyTemp"]["formattedValue"] = str(set_ch_data["economyTemp"]["value"])
                    set_ch_data["economyTemp"]["upDownVisible"] = False
                    set_ch_data["economyTemp"]["readOnly"] = True
                    for day_of_week in DAYS_OF_WEEK:
                        if day_of_week in set_ch_data:
                            set_ch_data[day_of_week]["dayName"] = day_of_week
                            item = 0
                            for day_slices in set_ch_data[day_of_week]["slices"]:
                                set_ch_data[day_of_week]["slices"][item]["from"] = _change_to_24h_format(
                                    day_slices["from"])
                                set_ch_data[day_of_week]["slices"][item]["fromOri"] = _change_to_24h_format(
                                    day_slices["from"])
                                set_ch_data[day_of_week]["slices"][item]["to"] = _change_to_24h_format(
                                    day_slices["to"])
                                set_ch_data[day_of_week]["slices"][item]["toOri"] = _change_to_24h_format(
                                    day_slices["to"])
                                if day_slices["temperatureId"] == 1:
                                    set_ch_data[day_of_week]["slices"][item]["temperature"] = "Comfort"
                                else:
                                    set_ch_data[day_of_week]["slices"][item]["temperature"] = "Economy"
                                item = item + 1
                except:
                    set_ch_data = {}
                    pass

                if PARAM_MODE in self._set_param:
                    if set_data["NewValue"]["mode"] == self._set_param[PARAM_MODE]:
                        if self._set_time_start < self._get_time_end:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_MODE]
                        else:
                            # assume data was not yet changed
                            main_data_changed = True
                    else:
                        set_data["NewValue"]["mode"] = self._set_param[PARAM_MODE]
                        main_data_changed = True
    
                if PARAM_DHW_SET_TEMPERATURE in self._set_param:
                    if set_data["NewValue"]["dhwTemp"]["value"] == self._set_param[PARAM_DHW_SET_TEMPERATURE]:
                        if self._set_time_start < self._get_time_end:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_SET_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            main_data_changed = True
                    else:
                        set_data["NewValue"]["dhwTemp"]["value"] = self._set_param[PARAM_DHW_SET_TEMPERATURE]
                        main_data_changed = True
    
                if PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE in self._set_param:
                    if set_data["NewValue"]["dhwTimeProgComfortTemp"]["value"] == self._set_param[
                        PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE]:
                        if self._set_time_start < self._get_time_end:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            main_data_changed = True
                    else:
                        set_data["NewValue"]["dhwTimeProgComfortTemp"]["value"] = self._set_param[
                            PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE]
                        main_data_changed = True
    
                if PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE in self._set_param:
                    if set_data["NewValue"]["dhwTimeProgEconomyTemp"]["value"] == self._set_param[
                        PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE]:
                        if self._set_time_start < self._get_time_end:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            main_data_changed = True
                    else:
                        set_data["NewValue"]["dhwTimeProgEconomyTemp"]["value"] = self._set_param[
                            PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE]
                        main_data_changed = True
    
                if PARAM_CH_SET_TEMPERATURE in self._set_param:
                    if set_data["NewValue"]["zone"]["comfortTemp"]["value"] == self._set_param[
                        PARAM_CH_SET_TEMPERATURE]:
                        if self._set_time_start < self._get_time_end:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_CH_SET_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            main_data_changed = True
                    else:
                        set_data["NewValue"]["zone"]["comfortTemp"]["value"] = self._set_param[PARAM_CH_SET_TEMPERATURE]
                        main_data_changed = True
    
                if PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE in self._set_param:
                    if set_ch_data != {}:
                        if set_ch_data["comfortTemp"]["value"] == self._set_param[
                            PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE]:
                            if self._set_time_start < self._get_time_end_ch:
                                # value should be up to date and match to remove from setting
                                del self._set_param[PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE]
                            else:
                                # assume data was not yet changed
                                ch_data_changed = True
                        else:
                            set_ch_data["comfortTemp"]["value"] = self._set_param[
                                PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE]
                            ch_data_changed = True
                    else:
                        ch_data_changed = True
    
                if PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE in self._set_param:
                    if set_ch_data != {}:
                        if set_ch_data["economyTemp"]["value"] == self._set_param[
                            PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE]:
                            if self._set_time_start < self._get_time_end_ch:
                                # value should be up to date and match to remove from setting
                                del self._set_param[PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE]
                            else:
                                # assume data was not yet changed
                                ch_data_changed = True
                        else:
                            set_ch_data["economyTemp"]["value"] = self._set_param[
                                PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE]
                            ch_data_changed = True
                    else:
                        ch_data_changed = True

                if PARAM_CH_MODE in self._set_param:
                    if set_data["NewValue"]["zone"]["mode"]["value"] == self._set_param[PARAM_CH_MODE]:
                        if self._set_time_start < self._get_time_end:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_CH_MODE]
                        else:
                            # assume data was not yet changed
                            main_data_changed = True
                    else:
                        set_data["NewValue"]["zone"]["mode"]["value"] = self._set_param[PARAM_CH_MODE]
                        main_data_changed = True
    
                if PARAM_DHW_MODE in self._set_param:
                    if set_data["NewValue"]["dhwMode"] == self._set_param[PARAM_DHW_MODE]:
                        if self._set_time_start < self._get_time_end:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_MODE]
                        else:
                            # assume data was not yet changed
                            main_data_changed = True
                    else:
                        set_data["NewValue"]["dhwMode"] = self._set_param[PARAM_DHW_MODE]
                        main_data_changed = True

                if main_data_changed or ch_data_changed:
                    if main_data_changed and self._set_main_retry < self._set_max_retries:
                        # retry again after enough time to fetch data twice
                        retry_time = dt_util.now() + timedelta(seconds=HTTP_SET_INTERVAL)
                        track_point_in_time(self._hass, self._actual_set_http_data, retry_time)
                        self._set_main_retry = self._set_main_retry + 1
                        self._set_scheduled = True
                    elif ch_data_changed and ((self._set_ch_retry == 0 and main_data_changed) or self._set_ch_retry
                                              < self._set_max_retries):
                        # retry again after enough time to fetch data twice
                        retry_time = dt_util.now() + timedelta(seconds=HTTP_SET_INTERVAL_CH)
                        track_point_in_time(self._hass, self._actual_set_http_data, retry_time)
                        self._set_main_retry = self._set_main_retry + 1
                        self._set_scheduled = True
                    else:
                        # no more retries, no need to keep changed data
                        self._set_param = {}
                else:
                    self._set_param = {}
                        
                if main_data_changed:
                    try:
                        url = self._url + '/PlantDashboard/SetPlantAndZoneData/' + self._plant_id + '?zoneNum=1&umsys=si'
                        self._set_time_start = time.time()
                        resp = self._session.post(
                            url,
                            auth=self._token,
                            timeout=HTTP_TIMEOUT_SET,
                            json=set_data)
                        if resp.status_code != 200:
                            _LOGGER.warning("%s Command to set data failed with code: %s", self, resp.status_code)
                            raise CommError
                        resp.raise_for_status()
                        self._set_time_end = time.time()
                        """
                        #uncomment below to store request time
                        request_time = time.time() - self._set_time_start
                        f=open("/config/tmp/set_time.txt", "a+")
                        f.write("{}\n".format(request_time))
                        """
                    except requests.exceptions.ReadTimeout as error:
                        _LOGGER.warning('%s Request timeout', self)
                        raise CommError(error)
                    except CommError:
                        _LOGGER.warning('%s Request communication error', self)
                        raise
                    _LOGGER.info('%s Data was presumably changed', self)
    
                    self._store_main_data(resp.json(), "_set")
    
                elif ch_data_changed:
                    try:

                        url = self._url + '/TimeProg/SubmitWeeklyPlan/' + self._plant_id + '?umsys=si'
                        self._set_time_start = time.time()
                        resp = self._session.post(
                            url,
                            auth=self._token,
                            timeout=HTTP_TIMEOUT_SET_CH,
                            json=set_ch_data)
                        if resp.status_code != 200:
                            _LOGGER.warning("%s Command to set data failed with code: %s", self, resp.status_code)
                            raise CommError
                        resp.raise_for_status()
                        self._set_time_end = time.time()
                        """
                        #uncomment below to store request time
                        request_time = time.time() - self._set_time_start
                        f=open("/config/tmp/set_time.txt", "a+")
                        f.write("{}\n".format(request_time))
                        """
                    except requests.exceptions.ReadTimeout as error:
                        _LOGGER.warning('%s Request timeout', self)
                        raise CommError(error)
                    except CommError:
                        _LOGGER.warning('%s Request communication error', self)
                        raise
                    _LOGGER.info('%s CH data was presumably changed', self)
                else:
                    _LOGGER.debug('%s Same data was used', self)
            else:
                # api is down
                if not self._set_scheduled:
                    if self._set_main_retry < self._set_max_retries:
                        # retry again after enough time to fetch data twice
                        retry_time = dt_util.now() + timedelta(seconds=HTTP_SET_INTERVAL)
                        track_point_in_time(self._hass, self._actual_set_http_data, retry_time)
                        self._set_main_retry = self._set_main_retry + 1
                        self._set_scheduled = True
                else:
                    # no more retries, no need to keep changed data
                    self._set_param = {}
                    _LOGGER.warning("%s No stable connection to set the data", self)
                    raise CommError


    def set_http_data(self, parameter_list={}):
        """Set Ariston data over http after data verification"""
        if self._ariston_data != {}:
            url = self._url + '/PlantDashboard/SetPlantAndZoneData/' + self._plant_id + '?zoneNum=1&umsys=si'
            with self._data_lock:
    
                # check mode and set it
                if PARAM_MODE in parameter_list:
                    wanted_mode = str(parameter_list[PARAM_MODE]).lower()
                    try:
                        if wanted_mode in MODE_TO_VALUE and MODE_TO_VALUE[wanted_mode] in self._ariston_data[
                            "allowedModes"]:
                            self._set_param[PARAM_MODE] = MODE_TO_VALUE[wanted_mode]
                            _LOGGER.info('%s New mode %s', self, wanted_mode)
                        else:
                            _LOGGER.warning('%s Unknown or unsupported mode: %s', self, wanted_mode)
                    except:
                        _LOGGER.warning('%s Unknown or unsupported mode or key error: %s', self, wanted_mode)
                        pass
    
                # check dhw temperature
                if PARAM_DHW_SET_TEMPERATURE in parameter_list:
                    wanted_dhw_temperature = str(parameter_list[PARAM_DHW_SET_TEMPERATURE]).lower()
                    try:
                        # round to nearest 1
                        temperature = round(float(wanted_dhw_temperature))
                        if temperature >= self._ariston_data["dhwTemp"]["min"] and temperature <= \
                                self._ariston_data["dhwTemp"]["max"]:
                            self._set_param[PARAM_DHW_SET_TEMPERATURE] = temperature
                            _LOGGER.info('%s New DHW temperature %s', self, temperature)
                        else:
                            _LOGGER.warning('%s Not supported DHW temperature value: %s', self, wanted_dhw_temperature)
                    except:
                        _LOGGER.warning('%s Not supported DHW temperature value: %s', self, wanted_dhw_temperature)
                        pass
    
                # check dhw comfort temperature
                if PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE in parameter_list:
                    wanted_dhw_temperature = str(parameter_list[PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE]).lower()
                    try:
                        # round to nearest 1
                        temperature = round(float(wanted_dhw_temperature))
                        if temperature >= self._ariston_data["dhwTimeProgComfortTemp"]["min"] and temperature <= \
                                self._ariston_data["dhwTimeProgComfortTemp"]["max"]:
                            self._set_param[PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE] = temperature
                            _LOGGER.info('%s New DHW scheduled comfort temperature %s', self, temperature)
                        else:
                            _LOGGER.warning('%s Not supported DHW scheduled comfort temperature value: %s', self,
                                            wanted_dhw_temperature)
                    except:
                        _LOGGER.warning('%s Not supported DHW scheduled comfort temperature value: %s', self,
                                        wanted_dhw_temperature)
                        pass
    
                # check dhw economy temperature
                if PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE in parameter_list:
                    wanted_dhw_temperature = str(parameter_list[PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE]).lower()
                    try:
                        # round to nearest 1
                        temperature = round(float(wanted_dhw_temperature))
                        if temperature >= self._ariston_data["dhwTimeProgEconomyTemp"]["min"] and temperature <= \
                                self._ariston_data["dhwTimeProgEconomyTemp"]["max"]:
                            self._set_param[PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE] = temperature
                            _LOGGER.info('%s New DHW scheduled economy temperature %s', self, temperature)
                        else:
                            _LOGGER.warning('%s Not supported DHW scheduled economy temperature value: %s', self,
                                            wanted_dhw_temperature)
                    except:
                        _LOGGER.warning('%s Not supported DHW scheduled economy temperature value: %s', self,
                                        wanted_dhw_temperature)
                        pass
    
                # check CH temperature
                if PARAM_CH_SET_TEMPERATURE in parameter_list:
                    wanted_ch_temperature = str(parameter_list[PARAM_CH_SET_TEMPERATURE]).lower()
                    try:
                        # round to nearest 0.5
                        temperature = round(float(wanted_ch_temperature) * 2.0) / 2.0
                        if temperature >= self._ariston_data["zone"]["comfortTemp"]["min"] and temperature <= \
                                self._ariston_data["zone"]["comfortTemp"]["max"]:
                            self._set_param[PARAM_CH_SET_TEMPERATURE] = temperature
                            _LOGGER.info('%s New CH temperature %s', self, temperature)
                        else:
                            _LOGGER.warning('%s Not supported CH temperature value: %s', self, wanted_ch_temperature)
                    except:
                        _LOGGER.warning('%s Not supported CH temperature value: %s', self, wanted_ch_temperature)
                        pass
    
                # check CH comfort scheduled temperature
                if PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE in parameter_list:
                    wanted_ch_temperature = str(parameter_list[PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE]).lower()
                    try:
                        # round to nearest 0.5
                        temperature = round(float(wanted_ch_temperature) * 2.0) / 2.0
                        if temperature >= self._ariston_data["zone"]["comfortTemp"]["min"] and temperature <= \
                                self._ariston_data["zone"]["comfortTemp"]["max"]:
                            self._set_param[PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE] = temperature
                            _LOGGER.info('%s New CH temperature %s', self, temperature)
                        else:
                            _LOGGER.warning('%s Not supported CH comfort scheduled temperature value: %s', self,
                                            wanted_ch_temperature)
                    except:
                        _LOGGER.warning('%s Not supported CH comfort scheduled temperature value: %s', self,
                                        wanted_ch_temperature)
                        pass
    
                # check CH economy scheduled temperature
                if PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE in parameter_list:
                    wanted_ch_temperature = str(parameter_list[PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE]).lower()
                    try:
                        # round to nearest 0.5
                        temperature = round(float(wanted_ch_temperature) * 2.0) / 2.0
                        if temperature >= self._ariston_data["zone"]["comfortTemp"]["min"] and temperature <= \
                                self._ariston_data["zone"]["comfortTemp"]["max"]:
                            self._set_param[PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE] = temperature
                            _LOGGER.info('%s New CH temperature %s', self, temperature)
                        else:
                            _LOGGER.warning('%s Not supported CH economy scheduled temperature value: %s', self,
                                            wanted_ch_temperature)
                    except:
                        _LOGGER.warning('%s Not supported CH economy scheduled temperature value: %s', self,
                                        wanted_ch_temperature)
                        pass
    
                # check CH mode
                if PARAM_CH_MODE in parameter_list:
                    wanted_ch_mode = str(parameter_list[PARAM_CH_MODE]).lower()
                    try:
                        if wanted_ch_mode in CH_MODE_TO_VALUE and CH_MODE_TO_VALUE[wanted_ch_mode] in \
                                self._ariston_data["zone"]["mode"]["allowedOptions"]:
                            self._set_param[PARAM_CH_MODE] = CH_MODE_TO_VALUE[wanted_ch_mode]
                            _LOGGER.info('%s New CH mode %s', self, wanted_ch_mode)
                        else:
                            _LOGGER.warning('%s Unknown or unsupported CH mode: %s', self, wanted_ch_mode)
                    except:
                        _LOGGER.warning('%s Unknown or unsupported CH mode or key error: %s', self, wanted_ch_mode)
                        pass
    
                # check DHW mode
                if PARAM_DHW_MODE in parameter_list:
                    wanted_dhw_mode = str(parameter_list[PARAM_DHW_MODE]).lower()
                    try:
                        if wanted_dhw_mode in DHW_MODE_TO_VALUE:
                            self._set_param[PARAM_DHW_MODE] = DHW_MODE_TO_VALUE[wanted_dhw_mode]
                            _LOGGER.info('%s New DHW mode %s', self, wanted_dhw_mode)
                        else:
                            _LOGGER.warning('%s Unknown or unsupported DHW mode: %s', self, wanted_dhw_mode)
                    except:
                        _LOGGER.warning('%s Unknown or unsupported DHW mode or key error: %s', self, wanted_dhw_mode)
                        pass
    
                self._set_new_data_pending = True
    
            self._actual_set_http_data()
    
        else:
            _LOGGER.warning("%s No valid data fetched from server to set changes", self)
            raise CommError
    
    
    def command(self, dummy=None):
        """trigger fetching of data"""
        with self._data_lock:
            if self._errors >= MAX_ERRORS_TIMER_EXTEND:
                # give a little rest to the system
                self._retry_timeout = HTTP_RETRY_INTERVAL_DOWN
                _LOGGER.warning('%s Retrying in %s seconds', self, self._retry_timeout)
            else:
                self._retry_timeout = HTTP_RETRY_INTERVAL
                _LOGGER.debug('%s Fetching data in %s seconds', self, self._retry_timeout)
            retry_time = dt_util.now() + timedelta(seconds=self._retry_timeout)
            track_point_in_time(self._hass, self.command, retry_time)
        try:
            self._get_http_data()
        except AristonError:
            with self._lock:
                was_online = self.available
                self._errors += 1
                _LOGGER.warning("%s errors: %i", self._name, self._errors)
                offline = not self.available
            if offline and was_online:
                with self._plant_id_lock:
                    self._login = False
                _LOGGER.error("%s is offline: Too many errors", self._name)
                dispatcher_send(self._hass, service_signal(SERVICE_UPDATE, self._name))
            raise
        with self._lock:
            was_offline = not self.available
            self._errors = 0
            self._init_available = True
        if was_offline:
            _LOGGER.info("%s Ariston back online", self._name)
            dispatcher_send(self._hass, service_signal(SERVICE_UPDATE, self._name))
    
    
def setup(hass, config):
    """Set up the Ariston component."""
    hass.data.setdefault(DATA_ARISTON, {DEVICES: {}, CLIMATES: [], WATER_HEATERS: []})
    api_list = []
    for device in config[DOMAIN]:
        name = device[CONF_NAME]
        username = device[CONF_USERNAME]
        password = device[CONF_PASSWORD]
        retries = device[CONF_MAX_RETRIES]
        store_file = device[CONF_STORE_CONFIG_FILES]
        try:
            api = AristonChecker(hass, device=device, name=name, username=username, password=password, retries=retries,
                                store_file=store_file)
            api_list.append(api)
            api.command()
            # schedule other data fetching
            track_point_in_time(api._hass, api._get_ch_data, dt_util.now() + timedelta(seconds=20))
            track_point_in_time(api._hass, api._get_error_data, dt_util.now() + timedelta(seconds=35))
            track_point_in_time(api._hass, api._get_gas_water_data, dt_util.now() + timedelta(seconds=50))
            #track_point_in_time(api._hass, api._get_other_data, dt_util.now() + timedelta(seconds=50))
        except LoginError as ex:
            _LOGGER.error("Login error for %s: %s", name, ex)
            pass
        except AristonError as ex:
            _LOGGER.error("Communication error for %s: %s", name, ex)
            pass
        binary_sensors = device.get(CONF_BINARY_SENSORS)
        sensors = device.get(CONF_SENSORS)
        switches = device.get(CONF_SWITCHES)
        hass.data[DATA_ARISTON][DEVICES][name] = AristonDevice(api)
        discovery.load_platform(
            hass, CLIMATE,
            DOMAIN,
            {CONF_NAME: name},
            config)
        discovery.load_platform(
            hass, WATER_HEATER,
            DOMAIN,
            {CONF_NAME: name},
            config)
        if switches:
            discovery.load_platform(
                hass,
                SWITCH,
                DOMAIN,
                {CONF_NAME: name, CONF_SWITCHES: switches},
                config,
            )
        if binary_sensors:
            discovery.load_platform(
                hass,
                BINARY_SENSOR,
                DOMAIN,
                {CONF_NAME: name, CONF_BINARY_SENSORS: binary_sensors},
                config,
            )
        if sensors:
            discovery.load_platform(
                hass,
                SENSOR,
                DOMAIN,
                {CONF_NAME: name, CONF_SENSORS: sensors},
                config
            )

    def set_ariston_data(call):
        """Handle the service call."""
        entity_id = call.data.get(ATTR_ENTITY_ID, "")
        try:
            domain = entity_id.split(".")[0]
        except:
            _LOGGER.warning("invalid entity_id domain")
            raise AristonError
        if domain.lower() != "climate":
            _LOGGER.warning("invalid entity_id domain")
            raise AristonError
        try:
            device = entity_id.split(".")[1]
        except:
            _LOGGER.warning("invalid entity_id device")
            raise AristonError
        for api in api_list:
            if api._name.lower() == device.lower():
                try:
                    with api._data_lock:
                        parameter_list = {}

                        data = call.data.get(PARAM_MODE, "")
                        if data != "":
                            parameter_list[PARAM_MODE] = data

                        data = call.data.get(PARAM_CH_MODE, "")
                        if data != "":
                            parameter_list[PARAM_CH_MODE] = data

                        data = call.data.get(PARAM_CH_SET_TEMPERATURE, "")
                        if data != "":
                            parameter_list[PARAM_CH_SET_TEMPERATURE] = data

                        data = call.data.get(PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE, "")
                        if data != "":
                            parameter_list[PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE] = data

                        data = call.data.get(PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE, "")
                        if data != "":
                            parameter_list[PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE] = data

                        data = call.data.get(PARAM_DHW_SET_TEMPERATURE, "")
                        if data != "":
                            parameter_list[PARAM_DHW_SET_TEMPERATURE] = data

                        data = call.data.get(PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE, "")
                        if data != "":
                            parameter_list[PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE] = data

                        data = call.data.get(PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE, "")
                        if data != "":
                            parameter_list[PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE] = data

                        data = call.data.get(PARAM_DHW_MODE, "")
                        if data != "":
                            parameter_list[PARAM_DHW_MODE] = data

                    _LOGGER.debug("device found, data to check and send")

                    api.set_http_data(parameter_list)

                except CommError:
                    _LOGGER.warning("Communication error for Ariston")
                    raise
                return
        _LOGGER.warning("Entity %s not found", entity_id)
        raise AristonError
        return

    hass.services.register(DOMAIN, SERVICE_SET_DATA, set_ariston_data)

    if not hass.data[DATA_ARISTON][DEVICES]:
        return False

    # Return boolean to indicate that initialization was successful.
    return True


class AristonDevice:
    """Representation of a base Ariston discovery device."""

    def __init__(
            self,
            api,
    ):
        """Initialize the entity."""
        self.api = api

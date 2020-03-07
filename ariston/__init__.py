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
    ARISTON_PARAM_LIST,
    ARISTON_DHW_TIME_PROG_COMFORT,
    ARISTON_DHW_TIME_PROG_ECONOMY,
    ARISTON_DHW_COMFORT_FUNCTION,
    ARISTON_INTERNET_TIME,
    ARISTON_INTERNET_WEATHER,
    CH_MODE_TO_VALUE,
    CLIMATES,
    CONF_HVAC_OFF,
    CONF_HVAC_OFF_PRESENT,
    CONF_POWER_ON,
    CONF_MAX_RETRIES,
    CONF_STORE_CONFIG_FILES,
    CONF_CONTROL_FROM_WATER_HEATER,
    CONF_LOCALIZATION,
    DATA_ARISTON,
    DAYS_OF_WEEK,
    DEVICES,
    DHW_MODE_TO_VALUE,
    DOMAIN,
    MODE_TO_VALUE,
    DHW_COMFORT_FUNCT_TO_VALUE,
    SERVICE_SET_DATA,
    SERVICE_UPDATE,
    PARAM_MODE,
    PARAM_CH_MODE,
    PARAM_CH_SET_TEMPERATURE,
    PARAM_DHW_COMFORT_FUNCTION,
    PARAM_DHW_MODE,
    PARAM_DHW_SET_TEMPERATURE,
    PARAM_DHW_COMFORT_TEMPERATURE,
    PARAM_DHW_ECONOMY_TEMPERATURE,
    PARAM_DHW_STORAGE_TEMPERATURE,
    PARAM_CH_COMFORT_TEMPERATURE,
    PARAM_CH_ECONOMY_TEMPERATURE,
    PARAM_INTERNET_TIME,
    PARAM_INTERNET_WEATHER,
    PARAM_STRING_TO_VALUE,
    VAL_WINTER,
    VAL_SUMMER,
    VAL_HEATING_ONLY,
    VAL_OFF,
    VAL_MANUAL,
    VAL_PROGRAM,
    WATER_HEATERS,
    LANG_EN,
    LANG_LIST,
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
DEFAULT_HVAC = VAL_SUMMER
DEFAULT_POWER_ON = VAL_SUMMER
DEFAULT_NAME = "Ariston"
DEFAULT_MAX_RETRIES = 1
DEFAULT_TIME = "00:00"
DEFAULT_MODES = [0, 1, 5]
DEFAULT_CH_MODES = [2, 3]
MAX_ERRORS = 3
MAX_ERRORS_TIMER_EXTEND = 2
HTTP_RETRY_INTERVAL = 60
HTTP_RETRY_INTERVAL_DOWN = 90
HTTP_RETRY_GAS_MULTIPLY = 11
HTTP_RETRY_ERROR_MULTIPLY = 5
HTTP_RETRY_CH_MULTIPLY = 3
HTTP_RETRY_OTHER_MULTIPLY = 4
HTTP_TIMER_SET_LOCK = 25
HTTP_TIMEOUT_LOGIN = 3
HTTP_TIMEOUT_GET = 15
HTTP_TIMEOUT_GET_OTHERS = 7
HTTP_TIMEOUT_SET = 15
HTTP_TIMEOUT_SET_CH = 10
HTTP_TIMEOUT_SET_PARAM = 10
HTTP_SET_INTERVAL = HTTP_RETRY_INTERVAL_DOWN + HTTP_TIMER_SET_LOCK + 5
HTTP_SET_INTERVAL_CH = HTTP_RETRY_INTERVAL_DOWN * HTTP_RETRY_CH_MULTIPLY + HTTP_TIMER_SET_LOCK + 5
HTTP_SET_INTERVAL_PARAM = HTTP_RETRY_INTERVAL_DOWN * HTTP_RETRY_OTHER_MULTIPLY + HTTP_TIMER_SET_LOCK + 5

UNKNOWN_TEMP = 0
REQUEST_GET_MAIN = "_get_main"
REQUEST_GET_CH = "_get_ch"
REQUEST_GET_ERROR = "_get_error"
REQUEST_GET_GAS = "_get_gas"
REQUEST_GET_OTHER = "_get_param"
REQUEST_SET_MAIN = "_set_main"
REQUEST_SET_CH = "_set_ch"
REQUEST_SET_OTHER = "_set_param"

_LOGGER = logging.getLogger(__name__)

ARISTON_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_BINARY_SENSORS): vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)]),
        vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [vol.In(SENSORS)]),
        vol.Optional(CONF_HVAC_OFF, default=DEFAULT_HVAC): vol.In([VAL_OFF, VAL_SUMMER]),
        vol.Optional(CONF_POWER_ON, default=DEFAULT_POWER_ON): vol.In([VAL_WINTER, VAL_SUMMER, VAL_HEATING_ONLY]),
        vol.Optional(CONF_MAX_RETRIES, default=DEFAULT_MAX_RETRIES): vol.All(int, vol.Range(min=0, max=65535)),
        vol.Optional(CONF_SWITCHES): vol.All(cv.ensure_list, [vol.In(SWITCHES)]),
        vol.Optional(CONF_STORE_CONFIG_FILES, default=False): cv.boolean,
        vol.Optional(CONF_CONTROL_FROM_WATER_HEATER, default=False): cv.boolean,
        vol.Optional(CONF_HVAC_OFF_PRESENT, default=False): cv.boolean,
        vol.Optional(CONF_LOCALIZATION, default=LANG_EN): vol.In(LANG_LIST),
    }
)


def _has_unique_names(devices):
    names = [device[CONF_NAME] for device in devices]
    vol.Schema(vol.Unique())(names)
    return devices


CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [ARISTON_SCHEMA], _has_unique_names)},
    extra=vol.ALLOW_EXTRA,
)


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


def _json_validator(data):
    try:
        if isinstance(data, dict):
            if data == {}:
                return False
            else:
                return True
        if isinstance(data, list):
            if data == []:
                return False
            else:
                for item in data:
                    if not isinstance(item, dict):
                        return False
                return True
        else:
            return False
    except:
        return False


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
        self._get_time_start = {REQUEST_GET_MAIN: 0,
                                REQUEST_GET_CH: 0,
                                REQUEST_GET_ERROR: 0,
                                REQUEST_GET_GAS: 0,
                                REQUEST_GET_OTHER: 0
                                }
        self._get_time_end = {REQUEST_GET_MAIN: 0,
                              REQUEST_GET_CH: 0,
                              REQUEST_GET_ERROR: 0,
                              REQUEST_GET_GAS: 0,
                              REQUEST_GET_OTHER: 0
                              }
        self._hass = hass
        self._init_available = False
        self._lock = threading.Lock()
        self._login = False
        self._name = name
        self._password = password
        self._plant_id = ""
        self._plant_id_lock = threading.Lock()
        self._session = requests.Session()
        self._set_param = {}
        self._set_main_retry = 0
        self._set_ch_retry = 0
        self._set_param_retry = 0
        self._set_max_retries = retries
        self._set_new_data_pending = False
        self._set_scheduled = False
        self._set_time_start = {REQUEST_GET_MAIN: 0,
                                REQUEST_GET_CH: 0,
                                REQUEST_GET_ERROR: 0,
                                REQUEST_GET_GAS: 0,
                                REQUEST_GET_OTHER: 0
                                }
        self._set_time_end = {REQUEST_GET_MAIN: 0,
                              REQUEST_GET_CH: 0,
                              REQUEST_GET_ERROR: 0,
                              REQUEST_GET_GAS: 0,
                              REQUEST_GET_OTHER: 0
                              }
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

    def _store_data(self, resp, request_type=""):
        """Store received dictionary"""
        if resp.status_code != 200:
            _LOGGER.warning('%s %s invalid reply code %s', self, request_type, resp.status_code)
            raise CommError(error)
        if not _json_validator(resp.json()):
            _LOGGER.warning('%s %s No json detected', self, request_type)
            raise CommError(error)
        log_temp_zero = False
        dhw_temp = {}
        if request_type in [REQUEST_GET_MAIN, REQUEST_SET_MAIN]:
            try:
                allowed_modes = self._ariston_data["allowedModes"]
                allowed_ch_modes = self._ariston_data["zone"]["mode"]["allowedOptions"]
                dhw_temp[PARAM_DHW_STORAGE_TEMPERATURE] = self._ariston_data["dhwStorageTemp"]
                dhw_temp[PARAM_DHW_COMFORT_TEMPERATURE] = self._ariston_data["dhwTimeProgComfortTemp"]["value"]
                dhw_temp[PARAM_DHW_ECONOMY_TEMPERATURE] = self._ariston_data["dhwTimeProgEconomyTemp"]["value"]
            except:
                allowed_modes = []
                allowed_ch_modes = []
                dhw_temp[PARAM_DHW_STORAGE_TEMPERATURE] = UNKNOWN_TEMP
                dhw_temp[PARAM_DHW_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                dhw_temp[PARAM_DHW_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                pass
            try:
                self._ariston_data = copy.deepcopy(resp.json())
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
                if self._ariston_data["dhwStorageTemp"] == UNKNOWN_TEMP:
                    if dhw_temp[PARAM_DHW_STORAGE_TEMPERATURE] != UNKNOWN_TEMP:
                        log_temp_zero = True
                if self._ariston_data["dhwTimeProgComfortTemp"]["value"] == UNKNOWN_TEMP:
                    if dhw_temp[PARAM_DHW_COMFORT_TEMPERATURE] != UNKNOWN_TEMP:
                        log_temp_zero = True
                if self._ariston_data["dhwTimeProgEconomyTemp"]["value"] == UNKNOWN_TEMP:
                    if dhw_temp[PARAM_DHW_ECONOMY_TEMPERATURE] != UNKNOWN_TEMP:
                        log_temp_zero = True
            except:
                self._ariston_data["allowedModes"] = DEFAULT_MODES
                self._ariston_data["zone"]["mode"]["allowedOptions"] = DEFAULT_CH_MODES
                raise CommError(error)
        elif request_type == REQUEST_GET_CH:
            self._ariston_ch_data = copy.deepcopy(resp.json())
        elif request_type == REQUEST_GET_ERROR:
            self._ariston_error_data = copy.deepcopy(resp.json())
        elif request_type == REQUEST_GET_GAS:
            self._ariston_gas_data = copy.deepcopy(resp.json())
        elif request_type == REQUEST_GET_OTHER:
            self._ariston_other_data = copy.deepcopy(resp.json())
            for param_item in self._ariston_other_data:
                try:
                    # Copy latest DHW temperature
                    if param_item["id"] == ARISTON_DHW_TIME_PROG_COMFORT and param_item["value"] != UNKNOWN_TEMP:
                        if "dhwTimeProgComfortTemp" in self._ariston_data and "value" in \
                                self._ariston_data["dhwTimeProgComfortTemp"]:
                            self._ariston_data["dhwTimeProgComfortTemp"]["value"] = param_item["value"]
                    elif param_item["id"] == ARISTON_DHW_TIME_PROG_ECONOMY and param_item["value"] != UNKNOWN_TEMP:
                        if "dhwTimeProgEconomyTemp" in self._ariston_data and "value" in \
                                self._ariston_data["dhwTimeProgEconomyTemp"]:
                            self._ariston_data["dhwTimeProgEconomyTemp"]["value"] = param_item["value"]
                except:
                    continue
        self._get_time_end[request_type] = time.time()
        if self._store_file:
            with open('/config/data_' + self._name + request_type, 'w') as ariston_fetched:
                json.dump(self._ariston_data, ariston_fetched)
            if log_temp_zero:
                with open('/config/data_' + self._name + request_type + '_zero.json', 'w') as ariston_fetched:
                    json.dump(self._ariston_data, ariston_fetched)
                with open('/config/data_' + self._name + request_type + '_non_zero.json', 'w') as ariston_fetched:
                    json.dump(dhw_temp, ariston_fetched)

    def _get_http_data(self, request_type=""):
        """Common fetching of http data"""
        self._login_session()
        if self._login and self._plant_id != "":
            try:
                last_set_of_data = _set_time_start[max(_set_time_start.keys(), key=(lambda k: _set_time_start[k]))]
            except:
                last_set_of_data = 0
                pass
            if time.time() - last_set_of_data > HTTP_TIMER_SET_LOCK:
                # do not read immediately during set attempt
                if request_type == REQUEST_GET_CH:
                    url_get = self._url + '/TimeProg/GetWeeklyPlan/' + self._plant_id + '?progId=ChZn1&umsys=si'
                    http_timeout = HTTP_TIMEOUT_GET_OTHERS
                elif request_type == REQUEST_GET_ERROR:
                    url_get = self._url + '/Error/ActiveDataSource/' + self._plant_id + \
                              '?$inlinecount=allpages&$skip=0&$top=100'
                    http_timeout = HTTP_TIMEOUT_GET_OTHERS
                elif request_type == REQUEST_GET_GAS:
                    url_get = self._url + '/Metering/GetData/' + self._plant_id + '?kind=1&umsys=si'
                    http_timeout = HTTP_TIMEOUT_GET_OTHERS
                elif request_type == REQUEST_GET_OTHER:
                    ids_to_fetch = ",".join(map(str, ARISTON_PARAM_LIST))
                    url_get = self._url + '/Menu/User/Refresh/' + self._plant_id + '?paramIds=' + ids_to_fetch + \
                              '&umsys=si'
                    http_timeout = HTTP_TIMEOUT_GET_OTHERS
                else:
                    url_get = self._url + '/PlantDashboard/GetPlantData/' + self._plant_id
                    http_timeout = HTTP_TIMEOUT_GET
                with self._data_lock:
                    try:
                        self._get_time_start[request_type] = time.time()
                        resp = self._session.get(
                            url_get,
                            auth=self._token,
                            timeout=http_timeout,
                            verify=self._verify)
                        resp.raise_for_status()
                        self._store_data(resp, request_type)
                    except:
                        _LOGGER.warning("%s %s Problem reading data", self, request_type)
                        raise CommError
            else:
                _LOGGER.debug("%s %s Still setting data, read restricted", self, request_type)
        else:
            _LOGGER.warning("%s %s Not properly logged in to get the data", self, request_type)
            raise LoginError

    def _get_main_data(self, dummy=None):
        """Get Ariston main data from http"""
        with self._data_lock:
            if self._errors >= MAX_ERRORS_TIMER_EXTEND:
                # give a little rest to the system
                retry_in = HTTP_RETRY_INTERVAL_DOWN
                _LOGGER.warning('%s Retrying in %s seconds', self, retry_in)
            else:
                retry_in = HTTP_RETRY_INTERVAL
                _LOGGER.debug('%s Fetching data in %s seconds', self, retry_in)
            retry_time = dt_util.now() + timedelta(seconds=retry_in)
            track_point_in_time(self._hass, self._get_main_data, retry_time)
        try:
            self._get_http_data(REQUEST_GET_MAIN)
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

    def _get_gas_water_data(self, dummy=None):
        """Get Ariston gas and water use data from http"""
        if self._errors >= MAX_ERRORS_TIMER_EXTEND:
            # give a little rest to the system
            retry_in = HTTP_RETRY_INTERVAL_DOWN * HTTP_RETRY_GAS_MULTIPLY
        else:
            retry_in = HTTP_RETRY_INTERVAL * HTTP_RETRY_GAS_MULTIPLY
        retry_time = dt_util.now() + timedelta(seconds=retry_in)
        track_point_in_time(self._hass, self._get_gas_water_data, retry_time)
        self._get_http_data(REQUEST_GET_GAS)

    def _get_error_data(self, dummy=None):
        """Get Ariston error data from http"""
        if self._errors >= MAX_ERRORS_TIMER_EXTEND:
            # give a little rest to the system
            retry_in = HTTP_RETRY_INTERVAL_DOWN * HTTP_RETRY_ERROR_MULTIPLY
        else:
            retry_in = HTTP_RETRY_INTERVAL * HTTP_RETRY_ERROR_MULTIPLY
        retry_time = dt_util.now() + timedelta(seconds=retry_in)
        track_point_in_time(self._hass, self._get_error_data, retry_time)
        self._get_http_data(REQUEST_GET_ERROR)

    def _get_ch_data(self, dummy=None):
        """Get Ariston CH data from http"""
        if self._errors >= MAX_ERRORS_TIMER_EXTEND:
            # give a little rest to the system
            retry_in = HTTP_RETRY_INTERVAL_DOWN * HTTP_RETRY_CH_MULTIPLY
        else:
            retry_in = HTTP_RETRY_INTERVAL * HTTP_RETRY_CH_MULTIPLY
        retry_time = dt_util.now() + timedelta(seconds=retry_in)
        track_point_in_time(self._hass, self._get_ch_data, retry_time)
        self._get_http_data(REQUEST_GET_CH)

    def _get_other_data(self, dummy=None):
        """Get Ariston other data from http"""
        if self._errors >= MAX_ERRORS_TIMER_EXTEND:
            # give a little rest to the system
            retry_in = HTTP_RETRY_INTERVAL_DOWN * HTTP_RETRY_OTHER_MULTIPLY
        else:
            retry_in = HTTP_RETRY_INTERVAL * HTTP_RETRY_OTHER_MULTIPLY
        retry_time = dt_util.now() + timedelta(seconds=retry_in)
        track_point_in_time(self._hass, self._get_other_data, retry_time)
        self._get_http_data(REQUEST_GET_OTHER)

    def _setting_http_data(self, set_data, request=""):
        """setting of data"""
        try:
            if self._store_file:
                with open('/config/data_' + self._name + request, 'w') as ariston_fetched:
                    json.dump(set_data, ariston_fetched)
        except:
            pass
        if request == REQUEST_SET_CH:
            url = self._url + '/TimeProg/SubmitWeeklyPlan/' + self._plant_id + '?umsys=si'
            get_request = REQUEST_GET_CH
            http_timeout = HTTP_TIMEOUT_SET_CH
        elif request == REQUEST_SET_OTHER:
            url = self._url + '/Menu/User/Submit/' + self._plant_id + '?umsys=si'
            get_request = REQUEST_GET_OTHER
            http_timeout = HTTP_TIMEOUT_SET_PARAM
        else:
            url = self._url + '/PlantDashboard/SetPlantAndZoneData/' + self._plant_id + '?zoneNum=1&umsys=si'
            get_request = REQUEST_GET_MAIN
            http_timeout = HTTP_TIMEOUT_SET
        try:
            self._set_time_start[get_request] = time.time()
            resp = self._session.post(
                url,
                auth=self._token,
                timeout=http_timeout,
                json=set_data)
            if resp.status_code != 200:
                _LOGGER.warning("%s %s Command to set data failed with code: %s", self, request, resp.status_code)
                raise CommError
            resp.raise_for_status()
            self._set_time_end[get_request] = time.time()
            try:
                if request == REQUEST_SET_MAIN:
                    self._store_data(resp, REQUEST_SET_MAIN)
                    if self._store_file:
                        with open("/config/data_" + self._name + request + "_reply.txt", "w") as f:
                            f.write(resp.text)
            except:
                pass
        except requests.exceptions.ReadTimeout as error:
            _LOGGER.warning('%s %s Request timeout', self, request)
            raise CommError(error)
        except CommError:
            _LOGGER.warning('%s %s Request communication error', self, request)
            raise
        _LOGGER.info('%s %s Data was presumably changed', self, request)

    def _preparing_setting_http_data(self, dummy=None):
        """Preparing and setting http data"""
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
                param_data_changed = False
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

                # prepare setting of parameter data dictionary
                set_param_data = []

                if PARAM_MODE in self._set_param:
                    if set_data["NewValue"]["mode"] == self._set_param[PARAM_MODE]:
                        if self._set_time_start[REQUEST_GET_MAIN] < self._get_time_end[REQUEST_GET_MAIN]:
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
                        if self._set_time_start[REQUEST_GET_MAIN] < self._get_time_end[REQUEST_GET_MAIN]:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_SET_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            main_data_changed = True
                    else:
                        set_data["NewValue"]["dhwTemp"]["value"] = self._set_param[PARAM_DHW_SET_TEMPERATURE]
                        main_data_changed = True

                if PARAM_DHW_COMFORT_TEMPERATURE in self._set_param:
                    if set_data["NewValue"]["dhwTimeProgComfortTemp"]["value"] == self._set_param[
                        PARAM_DHW_COMFORT_TEMPERATURE]:
                        last_set_of_data = max(self._set_time_start[REQUEST_GET_MAIN],
                                               self._set_time_start[REQUEST_GET_OTHER])
                        last_read_of_data = max(self._get_time_end[REQUEST_GET_MAIN],
                                                self._get_time_end[REQUEST_GET_OTHER])
                        if last_set_of_data < last_read_of_data:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_COMFORT_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            param_data = {
                                "id": ARISTON_DHW_TIME_PROG_COMFORT,
                                "newValue": self._set_param[PARAM_DHW_COMFORT_TEMPERATURE],
                                "oldValue": set_data["NewValue"]["dhwTimeProgComfortTemp"]["value"]}
                            set_param_data.append(param_data)
                            param_data_changed = True
                    else:
                        param_data = {
                            "id": ARISTON_DHW_TIME_PROG_COMFORT,
                            "newValue": self._set_param[PARAM_DHW_COMFORT_TEMPERATURE],
                            "oldValue": set_data["NewValue"]["dhwTimeProgComfortTemp"]["value"]}
                        set_param_data.append(param_data)
                        param_data_changed = True

                if PARAM_DHW_ECONOMY_TEMPERATURE in self._set_param:
                    if set_data["NewValue"]["dhwTimeProgEconomyTemp"]["value"] == self._set_param[
                        PARAM_DHW_ECONOMY_TEMPERATURE]:
                        last_set_of_data = max(self._set_time_start[REQUEST_GET_MAIN],
                                               self._set_time_start[REQUEST_GET_OTHER])
                        last_read_of_data = max(self._get_time_end[REQUEST_GET_MAIN],
                                                self._get_time_end[REQUEST_GET_OTHER])
                        if last_set_of_data < last_read_of_data:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_ECONOMY_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            param_data = {
                                "id": ARISTON_DHW_TIME_PROG_ECONOMY,
                                "newValue": self._set_param[PARAM_DHW_ECONOMY_TEMPERATURE],
                                "oldValue": set_data["NewValue"]["dhwTimeProgEconomyTemp"]["value"]}
                            set_param_data.append(param_data)
                            param_data_changed = True
                    else:
                        param_data = {
                            "id": ARISTON_DHW_TIME_PROG_ECONOMY,
                            "newValue": self._set_param[PARAM_DHW_ECONOMY_TEMPERATURE],
                            "oldValue": set_data["NewValue"]["dhwTimeProgEconomyTemp"]["value"]}
                        set_param_data.append(param_data)
                        param_data_changed = True

                if PARAM_DHW_COMFORT_FUNCTION in self._set_param:
                    try:
                        for param_item in self._ariston_other_data:
                            if param_item["id"] == ARISTON_DHW_COMFORT_FUNCTION:
                                if param_item["value"] == self._set_param[PARAM_DHW_COMFORT_FUNCTION]:
                                    if self._set_time_start[REQUEST_GET_OTHER] < self._get_time_end[REQUEST_GET_OTHER]:
                                        # value should be up to date and match to remove from setting
                                        del self._set_param[PARAM_DHW_COMFORT_FUNCTION]
                                    else:
                                        # assume data was not yet changed
                                        param_data = {
                                            "id": ARISTON_DHW_COMFORT_FUNCTION,
                                            "newValue": self._set_param[PARAM_DHW_COMFORT_FUNCTION],
                                            "oldValue": param_item["value"]}
                                        set_param_data.append(param_data)
                                        param_data_changed = True
                                    break
                                else:
                                    param_data = {
                                        "id": ARISTON_DHW_COMFORT_FUNCTION,
                                        "newValue": self._set_param[PARAM_DHW_COMFORT_FUNCTION],
                                        "oldValue": param_item["value"]}
                                    set_param_data.append(param_data)
                                    param_data_changed = True
                                    break
                    except:
                        param_data_changed = True
                        pass

                if PARAM_INTERNET_TIME in self._set_param:
                    try:
                        for param_item in self._ariston_other_data:
                            if param_item["id"] == ARISTON_INTERNET_TIME:
                                if param_item["value"] == self._set_param[PARAM_INTERNET_TIME]:
                                    if self._set_time_start[REQUEST_GET_OTHER] < self._get_time_end[REQUEST_GET_OTHER]:
                                        # value should be up to date and match to remove from setting
                                        del self._set_param[PARAM_INTERNET_TIME]
                                    else:
                                        # assume data was not yet changed
                                        param_data = {
                                            "id": ARISTON_INTERNET_TIME,
                                            "newValue": self._set_param[PARAM_INTERNET_TIME],
                                            "oldValue": param_item["value"]}
                                        set_param_data.append(param_data)
                                        param_data_changed = True
                                    break
                                else:
                                    param_data = {
                                        "id": ARISTON_INTERNET_TIME,
                                        "newValue": self._set_param[PARAM_INTERNET_TIME],
                                        "oldValue": param_item["value"]}
                                    set_param_data.append(param_data)
                                    param_data_changed = True
                                    break
                    except:
                        param_data_changed = True
                        pass

                if PARAM_INTERNET_WEATHER in self._set_param:
                    try:
                        for param_item in self._ariston_other_data:
                            if param_item["id"] == ARISTON_INTERNET_WEATHER:
                                if param_item["value"] == self._set_param[PARAM_INTERNET_TIME]:
                                    if self._set_time_start[REQUEST_GET_OTHER] < self._get_time_end[REQUEST_GET_OTHER]:
                                        # value should be up to date and match to remove from setting
                                        del self._set_param[PARAM_INTERNET_WEATHER]
                                    else:
                                        # assume data was not yet changed
                                        param_data = {
                                            "id": ARISTON_INTERNET_WEATHER,
                                            "newValue": self._set_param[PARAM_INTERNET_WEATHER],
                                            "oldValue": param_item["value"]}
                                        set_param_data.append(param_data)
                                        param_data_changed = True
                                    break
                                else:
                                    param_data = {
                                        "id": ARISTON_INTERNET_WEATHER,
                                        "newValue": self._set_param[PARAM_INTERNET_WEATHER],
                                        "oldValue": param_item["value"]}
                                    set_param_data.append(param_data)
                                    param_data_changed = True
                                    break
                    except:
                        param_data_changed = True
                        pass

                if PARAM_CH_SET_TEMPERATURE in self._set_param:
                    if set_data["NewValue"]["zone"]["comfortTemp"]["value"] == self._set_param[
                        PARAM_CH_SET_TEMPERATURE]:
                        if self._set_time_start[REQUEST_GET_MAIN] < self._get_time_end[REQUEST_GET_MAIN]:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_CH_SET_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            main_data_changed = True
                    else:
                        set_data["NewValue"]["zone"]["comfortTemp"]["value"] = self._set_param[PARAM_CH_SET_TEMPERATURE]
                        main_data_changed = True

                if PARAM_CH_COMFORT_TEMPERATURE in self._set_param:
                    if set_ch_data != {}:
                        if set_ch_data["comfortTemp"]["value"] == self._set_param[
                            PARAM_CH_COMFORT_TEMPERATURE]:
                            if self._set_time_start[REQUEST_GET_CH] < self._get_time_end[REQUEST_GET_CH]:
                                # value should be up to date and match to remove from setting
                                del self._set_param[PARAM_CH_COMFORT_TEMPERATURE]
                            else:
                                # assume data was not yet changed
                                ch_data_changed = True
                        else:
                            set_ch_data["comfortTemp"]["value"] = self._set_param[
                                PARAM_CH_COMFORT_TEMPERATURE]
                            ch_data_changed = True
                    else:
                        ch_data_changed = True

                if PARAM_CH_ECONOMY_TEMPERATURE in self._set_param:
                    if set_ch_data != {}:
                        if set_ch_data["economyTemp"]["value"] == self._set_param[
                            PARAM_CH_ECONOMY_TEMPERATURE]:
                            if self._set_time_start[REQUEST_GET_CH] < self._get_time_end[REQUEST_GET_CH]:
                                # value should be up to date and match to remove from setting
                                del self._set_param[PARAM_CH_ECONOMY_TEMPERATURE]
                            else:
                                # assume data was not yet changed
                                ch_data_changed = True
                        else:
                            set_ch_data["economyTemp"]["value"] = self._set_param[
                                PARAM_CH_ECONOMY_TEMPERATURE]
                            ch_data_changed = True
                    else:
                        ch_data_changed = True

                if PARAM_CH_MODE in self._set_param:
                    if set_data["NewValue"]["zone"]["mode"]["value"] == self._set_param[PARAM_CH_MODE]:
                        if self._set_time_start[REQUEST_GET_MAIN] < self._get_time_end[REQUEST_GET_MAIN]:
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
                        if self._set_time_start[REQUEST_GET_MAIN] < self._get_time_end[REQUEST_GET_MAIN]:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_MODE]
                        else:
                            # assume data was not yet changed
                            main_data_changed = True
                    else:
                        set_data["NewValue"]["dhwMode"] = self._set_param[PARAM_DHW_MODE]
                        main_data_changed = True

                if main_data_changed or ch_data_changed or param_data_changed:
                    if main_data_changed and self._set_main_retry < self._set_max_retries:

                        # retry again after enough time
                        retry_time = dt_util.now() + timedelta(seconds=HTTP_SET_INTERVAL)
                        track_point_in_time(self._hass, self._preparing_setting_http_data, retry_time)
                        self._set_main_retry = self._set_main_retry + 1
                        self._set_scheduled = True

                    elif ch_data_changed and ((self._set_ch_retry == 0 and main_data_changed) or
                                              self._set_ch_retry < self._set_max_retries):

                        # retry again after enough time
                        retry_time = dt_util.now() + timedelta(seconds=HTTP_SET_INTERVAL_CH)
                        track_point_in_time(self._hass, self._preparing_setting_http_data, retry_time)
                        self._set_ch_retry = self._set_ch_retry + 1
                        self._set_scheduled = True

                    elif param_data_changed and ((self._set_param_retry == 0 and (
                            main_data_changed or ch_data_changed)) or self._set_ch_retry < self._set_max_retries):

                        # retry again after enough time
                        retry_time = dt_util.now() + timedelta(seconds=HTTP_SET_INTERVAL_PARAM)
                        track_point_in_time(self._hass, self._preparing_setting_http_data, retry_time)
                        self._set_param_retry = self._set_param_retry + 1
                        self._set_scheduled = True

                    else:
                        # no more retries, no need to keep changed data
                        self._set_param = {}
                else:
                    self._set_param = {}

                if main_data_changed:
                    try:
                        self._setting_http_data(set_data, REQUEST_SET_MAIN)
                    except:
                        pass

                elif ch_data_changed:
                    try:
                        if set_ch_data != {}:
                            self._setting_http_data(set_ch_data, REQUEST_SET_CH)
                        else:
                            _LOGGER.warning('%s No valid data to set CH data', self)
                            raise CommError(error)
                    except:
                        pass

                elif param_data_changed:

                    try:
                        if set_param_data != []:
                            self._setting_http_data(set_param_data, REQUEST_SET_OTHER)
                        else:
                            _LOGGER.warning('%s No valid data to set parameters', self)
                            raise CommError(error)
                    except:
                        pass
                else:
                    _LOGGER.debug('%s Same data was used', self)
            else:
                # api is down
                if not self._set_scheduled:
                    if self._set_main_retry < self._set_max_retries:
                        # retry again after enough time to fetch data twice
                        retry_time = dt_util.now() + timedelta(seconds=HTTP_SET_INTERVAL)
                        track_point_in_time(self._hass, self._preparing_setting_http_data, retry_time)
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
                if PARAM_DHW_COMFORT_TEMPERATURE in parameter_list:
                    wanted_dhw_temperature = str(parameter_list[PARAM_DHW_COMFORT_TEMPERATURE]).lower()
                    try:
                        # round to nearest 1
                        temperature = round(float(wanted_dhw_temperature))
                        if temperature >= self._ariston_data["dhwTemp"]["min"] and temperature <= \
                                self._ariston_data["dhwTemp"]["max"]:
                            self._set_param[PARAM_DHW_COMFORT_TEMPERATURE] = temperature
                            _LOGGER.info('%s New DHW scheduled comfort temperature %s', self, temperature)
                        else:
                            _LOGGER.warning('%s Not supported DHW scheduled comfort temperature value: %s', self,
                                            wanted_dhw_temperature)
                    except:
                        _LOGGER.warning('%s Not supported DHW scheduled comfort temperature value: %s', self,
                                        wanted_dhw_temperature)
                        pass

                # check dhw economy temperature
                if PARAM_DHW_ECONOMY_TEMPERATURE in parameter_list:
                    wanted_dhw_temperature = str(parameter_list[PARAM_DHW_ECONOMY_TEMPERATURE]).lower()
                    try:
                        # round to nearest 1
                        temperature = round(float(wanted_dhw_temperature))
                        if temperature >= self._ariston_data["dhwTemp"]["min"] and temperature <= \
                                self._ariston_data["dhwTemp"]["max"]:
                            self._set_param[PARAM_DHW_ECONOMY_TEMPERATURE] = temperature
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
                if PARAM_CH_COMFORT_TEMPERATURE in parameter_list:
                    wanted_ch_temperature = str(parameter_list[PARAM_CH_COMFORT_TEMPERATURE]).lower()
                    try:
                        # round to nearest 0.5
                        temperature = round(float(wanted_ch_temperature) * 2.0) / 2.0
                        if temperature >= self._ariston_data["zone"]["comfortTemp"]["min"] and temperature <= \
                                self._ariston_data["zone"]["comfortTemp"]["max"]:
                            self._set_param[PARAM_CH_COMFORT_TEMPERATURE] = temperature
                            _LOGGER.info('%s New CH temperature %s', self, temperature)
                        else:
                            _LOGGER.warning('%s Not supported CH comfort scheduled temperature value: %s', self,
                                            wanted_ch_temperature)
                    except:
                        _LOGGER.warning('%s Not supported CH comfort scheduled temperature value: %s', self,
                                        wanted_ch_temperature)
                        pass

                # check CH economy scheduled temperature
                if PARAM_CH_ECONOMY_TEMPERATURE in parameter_list:
                    wanted_ch_temperature = str(parameter_list[PARAM_CH_ECONOMY_TEMPERATURE]).lower()
                    try:
                        # round to nearest 0.5
                        temperature = round(float(wanted_ch_temperature) * 2.0) / 2.0
                        if temperature >= self._ariston_data["zone"]["comfortTemp"]["min"] and temperature <= \
                                self._ariston_data["zone"]["comfortTemp"]["max"]:
                            self._set_param[PARAM_CH_ECONOMY_TEMPERATURE] = temperature
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

                # check DHW Comfort mode
                if PARAM_DHW_COMFORT_FUNCTION in parameter_list:
                    wanted_dhw_function = str(parameter_list[PARAM_DHW_COMFORT_FUNCTION]).lower()
                    try:
                        if wanted_dhw_function in DHW_COMFORT_FUNCT_TO_VALUE:
                            self._set_param[PARAM_DHW_COMFORT_FUNCTION] = DHW_COMFORT_FUNCT_TO_VALUE[
                                wanted_dhw_function]
                            _LOGGER.info('%s New DHW Comfort function %s', self, wanted_dhw_function)
                        else:
                            _LOGGER.warning('%s Unknown or unsupported DHW Comfort function: %s', self,
                                            wanted_dhw_function)
                    except:
                        _LOGGER.warning('%s Unknown or unsupported DHW Comfort function or key error: %s', self,
                                        wanted_dhw_function)
                        pass

                # check internet time
                if PARAM_INTERNET_TIME in parameter_list:
                    wanted_internet_time = str(parameter_list[PARAM_INTERNET_TIME]).lower()
                    try:
                        if wanted_internet_time in PARAM_STRING_TO_VALUE:
                            self._set_param[PARAM_INTERNET_TIME] = PARAM_STRING_TO_VALUE[wanted_internet_time]
                            _LOGGER.info('%s New Internet time is %s', self, wanted_internet_time)
                        else:
                            _LOGGER.warning('%s Unknown or unsupported Internet time: %s', self, wanted_internet_time)
                    except:
                        _LOGGER.warning('%s Unknown or unsupported Internet time or key error: %s', self,
                                        wanted_internet_time)
                        pass

                # check internet time
                if PARAM_INTERNET_WEATHER in parameter_list:
                    wanted_internet_weather = str(parameter_list[PARAM_INTERNET_WEATHER]).lower()
                    try:
                        if wanted_internet_weather in PARAM_STRING_TO_VALUE:
                            self._set_param[PARAM_INTERNET_WEATHER] = PARAM_STRING_TO_VALUE[wanted_internet_weather]
                            _LOGGER.info('%s New Internet weather is %s', self, wanted_internet_weather)
                        else:
                            _LOGGER.warning('%s Unknown or unsupported Internet weather: %s', self,
                                            wanted_internet_weather)
                    except:
                        _LOGGER.warning('%s Unknown or unsupported Internet weather or key error: %s', self,
                                        wanted_internet_weather)
                        pass

                self._set_new_data_pending = True

            self._preparing_setting_http_data()

        else:
            _LOGGER.warning("%s No valid data fetched from server to set changes", self)
            raise CommError


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
            api._get_main_data()
            # schedule other data fetching
            #track_point_in_time(api._hass, api._get_main_data, dt_util.now() + timedelta(seconds=1))
            track_point_in_time(api._hass, api._get_other_data, dt_util.now() + timedelta(seconds=20))
            track_point_in_time(api._hass, api._get_ch_data, dt_util.now() + timedelta(seconds=35))
            track_point_in_time(api._hass, api._get_error_data, dt_util.now() + timedelta(seconds=50))
            track_point_in_time(api._hass, api._get_gas_water_data, dt_util.now() + timedelta(seconds=90))
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

                        data = call.data.get(PARAM_CH_COMFORT_TEMPERATURE, "")
                        if data != "":
                            # handle comfort temperature via different request
                            parameter_list[PARAM_CH_SET_TEMPERATURE] = data

                        data = call.data.get(PARAM_CH_ECONOMY_TEMPERATURE, "")
                        if data != "":
                            parameter_list[PARAM_CH_ECONOMY_TEMPERATURE] = data

                        data = call.data.get(PARAM_DHW_SET_TEMPERATURE, "")
                        if data != "":
                            parameter_list[PARAM_DHW_SET_TEMPERATURE] = data

                        data = call.data.get(PARAM_DHW_COMFORT_TEMPERATURE, "")
                        if data != "":
                            parameter_list[PARAM_DHW_COMFORT_TEMPERATURE] = data

                        data = call.data.get(PARAM_DHW_ECONOMY_TEMPERATURE, "")
                        if data != "":
                            parameter_list[PARAM_DHW_ECONOMY_TEMPERATURE] = data

                        data = call.data.get(PARAM_DHW_MODE, "")
                        if data != "":
                            parameter_list[PARAM_DHW_MODE] = data

                        data = call.data.get(PARAM_DHW_COMFORT_FUNCTION, "")
                        if data != "":
                            parameter_list[PARAM_DHW_COMFORT_FUNCTION] = data

                        data = call.data.get(PARAM_INTERNET_TIME, "")
                        if data != "":
                            parameter_list[PARAM_INTERNET_TIME] = data

                        data = call.data.get(PARAM_INTERNET_WEATHER, "")
                        if data != "":
                            parameter_list[PARAM_INTERNET_WEATHER] = data

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

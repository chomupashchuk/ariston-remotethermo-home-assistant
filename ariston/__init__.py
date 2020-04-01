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
    ARISTON_CH_AUTO_FUNCTION,
    ARISTON_CH_COMFORT_TEMP,
    ARISTON_CH_ECONOMY_TEMP,
    ARISTON_THERMAL_CLEANSE_FUNCTION,
    ARISTON_THERMAL_CLEANSE_CYCLE,
    CH_MODE_TO_VALUE,
    CLIMATES,
    CONF_HVAC_OFF,
    CONF_HVAC_OFF_PRESENT,
    CONF_POWER_ON,
    CONF_MAX_RETRIES,
    CONF_STORE_CONFIG_FILES,
    CONF_CONTROL_FROM_WATER_HEATER,
    CONF_LOCALIZATION,
    CONF_UNITS,
    CONF_POLLING_RATE,
    DATA_ARISTON,
    DAYS_OF_WEEK,
    DEVICES,
    DHW_MODE_TO_VALUE,
    DOMAIN,
    MODE_TO_VALUE,
    DHW_COMFORT_FUNCT_TO_VALUE,
    UNIT_TO_VALUE,
    SERVICE_SET_DATA,
    SERVICE_UPDATE,
    PARAM_MODE,
    PARAM_CH_AUTO_FUNCTION,
    PARAM_CH_MODE,
    PARAM_CH_SET_TEMPERATURE,
    PARAM_CH_COMFORT_TEMPERATURE,
    PARAM_CH_ECONOMY_TEMPERATURE,
    PARAM_CH_DETECTED_TEMPERATURE,
    PARAM_DHW_COMFORT_FUNCTION,
    PARAM_DHW_MODE,
    PARAM_DHW_SET_TEMPERATURE,
    PARAM_DHW_COMFORT_TEMPERATURE,
    PARAM_DHW_ECONOMY_TEMPERATURE,
    PARAM_DHW_STORAGE_TEMPERATURE,
    PARAM_INTERNET_TIME,
    PARAM_INTERNET_WEATHER,
    PARAM_STRING_TO_VALUE,
    PARAM_UNITS,
    PARAM_THERMAL_CLEANSE_CYCLE,
    PARAM_THERMAL_CLEANSE_FUNCTION,
    VAL_WINTER,
    VAL_SUMMER,
    VAL_HEATING_ONLY,
    VAL_OFF,
    VAL_MANUAL,
    VAL_PROGRAM,
    VAL_UNSUPPORTED,
    VAL_METRIC,
    VAL_IMPERIAL,
    VAL_AUTO,
    VAL_NORMAL,
    VAL_LONG,
    VALUE_TO_DHW_MODE,
    WATER_HEATERS,
    LANG_EN,
    LANG_LIST,
    GET_REQUEST_CH_PROGRAM,
    GET_REQUEST_CURRENCY,
    GET_REQUEST_DHW_PROGRAM,
    GET_REQUEST_ERRORS,
    GET_REQUEST_GAS,
    GET_REQUEST_MAIN,
    GET_REQUEST_PARAM,
    GET_REQUEST_UNITS,
    GET_REQUEST_VERSION,
    SET_REQUEST_MAIN,
    SET_REQUEST_PARAM,
    SET_REQUEST_UNITS,
)
from .exceptions import CommError, LoginError, AristonError
from .helpers import service_signal
from .sensor import SENSORS
from .switch import SWITCHES

"""HTTP_RETRY_INTERVAL is time between 2 GET requests. Note that it often takes more than 10 seconds to properly fetch data, also potential login"""
"""MAX_ERRORS is number of errors for device to become not available"""
"""HTTP_TIMEOUT_LOGIN is timeout for login procedure"""
"""HTTP_TIMEOUT_GET is timeout to get data (can increase restart time in some cases). For tested environment often around 10 seconds, rarely above 15"""

ARISTON_URL = "https://www.ariston-net.remotethermo.com"
GITHUB_LATEST_RELEASE = 'https://api.github.com/repos/chomupashchuk/ariston-remotethermo-home-assistant/releases/latest'

DEFAULT_HVAC = VAL_SUMMER
DEFAULT_POWER_ON = VAL_SUMMER
DEFAULT_NAME = "Ariston"
DEFAULT_MAX_RETRIES = 1
DEFAULT_TIME = "00:00"
DEFAULT_MODES = [0, 1, 5]
DEFAULT_CH_MODES = [2, 3]
MAX_ERRORS = 10
MAX_ERRORS_TIMER_EXTEND = 5
MAX_ZERO_TOLERANCE = 10
HTTP_DELAY_MULTIPLY = 3
HTTP_TIMER_SET_LOCK = 25
HTTP_TIMER_SET_WAIT = 30
HTTP_TIMEOUT_LOGIN = 5.0
HTTP_TIMEOUT_GET_LONG = 16.0
HTTP_TIMEOUT_GET_MEDIUM = 10.0
HTTP_TIMEOUT_GET_SHORT = 6.0
HTTP_PARAM_DELAY = 30.0

UNKNOWN_TEMP = 0.0
UNKNOWN_UNITS = 3276
REQUEST_GET_MAIN = "_get_main"
REQUEST_GET_CH = "_get_ch"
REQUEST_GET_DHW = "_get_dhw"
REQUEST_GET_ERROR = "_get_error"
REQUEST_GET_GAS = "_get_gas"
REQUEST_GET_OTHER = "_get_param"
REQUEST_GET_UNITS = "_get_units"
REQUEST_GET_CURRENCY = "_get_currency"
REQUEST_GET_VERSION = "_get_version"

REQUEST_SET_MAIN = "_set_main"
REQUEST_SET_OTHER = "_set_param"
REQUEST_SET_UNITS = "_set_units"

POLLING_RATE_TO_VALUE = {VAL_NORMAL: 1, VAL_LONG: 1.3}

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
        vol.Optional(CONF_UNITS, default=VAL_METRIC): vol.In([VAL_METRIC, VAL_IMPERIAL, VAL_AUTO]),
        vol.Optional(CONF_POLLING_RATE, default=VAL_NORMAL): vol.In([VAL_NORMAL, VAL_LONG]),
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


def _get_request_for_parameter(data):
    if data in GET_REQUEST_CH_PROGRAM:
        return REQUEST_GET_CH
    elif data in GET_REQUEST_CURRENCY:
        return REQUEST_GET_CURRENCY
    elif data in GET_REQUEST_DHW_PROGRAM:
        return REQUEST_GET_DHW
    elif data in GET_REQUEST_ERRORS:
        return REQUEST_GET_ERROR
    elif data in GET_REQUEST_GAS:
        return REQUEST_GET_GAS
    elif data in GET_REQUEST_PARAM:
        return REQUEST_GET_OTHER
    elif data in GET_REQUEST_UNITS:
        return REQUEST_GET_UNITS
    elif data in GET_REQUEST_VERSION:
        return REQUEST_GET_VERSION
    return REQUEST_GET_MAIN


def _set_request_for_parameter(data):
    if data in SET_REQUEST_PARAM:
        return REQUEST_SET_OTHER
    elif data in SET_REQUEST_UNITS:
        return REQUEST_SET_UNITS
    return REQUEST_SET_MAIN


class AristonChecker():
    """Ariston checker"""

    def __init__(self, hass, device, name, username, password, retries, store_file, units, polling, sensors,
                 binary_sensors, switches):
        """Initialize."""
        # clear visible configuration data
        self._ariston_data = {}
        self._ariston_gas_data = {}
        self._ariston_error_data = {}
        self._ariston_ch_data = {}
        self._ariston_dhw_data = {}
        self._ariston_currency = {}
        self._ariston_other_data = {}
        self._ariston_units = {}
        # clear actual configuration data fetched from the server
        self._ariston_data_actual = {}
        self._ariston_gas_data_actual = {}
        self._ariston_error_data_actual = {}
        self._ariston_ch_data_actual = {}
        self._ariston_dhw_data_actual = {}
        self._ariston_currency_actual = {}
        self._ariston_other_data_actual = {}
        self._ariston_units_actual = {}
        # initiate all other data
        self._data_lock = threading.Lock()
        self._device = device
        self._errors = 0
        self._get_request_number_low_prio = 0
        self._get_request_number_high_prio = 0
        self._get_time_start = {
            REQUEST_GET_MAIN: 0,
            REQUEST_GET_CH: 0,
            REQUEST_GET_DHW: 0,
            REQUEST_GET_ERROR: 0,
            REQUEST_GET_GAS: 0,
            REQUEST_GET_OTHER: 0,
            REQUEST_GET_UNITS: 0,
            REQUEST_GET_CURRENCY: 0,
            REQUEST_GET_VERSION: 0
        }
        self._get_time_end = {
            REQUEST_GET_MAIN: 0,
            REQUEST_GET_CH: 0,
            REQUEST_GET_DHW: 0,
            REQUEST_GET_ERROR: 0,
            REQUEST_GET_GAS: 0,
            REQUEST_GET_OTHER: 0,
            REQUEST_GET_UNITS: 0,
            REQUEST_GET_CURRENCY: 0,
            REQUEST_GET_VERSION: 0
        }
        self._get_zero_temperature = {
            PARAM_CH_SET_TEMPERATURE: UNKNOWN_TEMP,
            PARAM_CH_COMFORT_TEMPERATURE: UNKNOWN_TEMP,
            PARAM_CH_ECONOMY_TEMPERATURE: UNKNOWN_TEMP,
            PARAM_CH_DETECTED_TEMPERATURE: UNKNOWN_TEMP,
            PARAM_DHW_SET_TEMPERATURE: UNKNOWN_TEMP,
            PARAM_DHW_COMFORT_TEMPERATURE: UNKNOWN_TEMP,
            PARAM_DHW_ECONOMY_TEMPERATURE: UNKNOWN_TEMP,
            PARAM_DHW_STORAGE_TEMPERATURE: UNKNOWN_TEMP
        }
        self._hass = hass
        self._lock = threading.Lock()
        self._login = False
        self._name = name
        self._password = password
        self._plant_id = ""
        self._plant_id_lock = threading.Lock()
        self._session = requests.Session()
        self._set_param = {}
        self._set_param_group = {
            REQUEST_GET_MAIN: False,
            REQUEST_GET_OTHER: False,
            REQUEST_GET_UNITS: False
        }
        self._set_retry = {
            REQUEST_SET_MAIN: 0,
            REQUEST_SET_OTHER: 0,
            REQUEST_SET_UNITS: 0
        }
        self._set_max_retries = retries
        self._set_new_data_pending = False
        self._set_scheduled = False
        self._set_time_start = {
            REQUEST_SET_MAIN: 0,
            REQUEST_SET_OTHER: 0,
            REQUEST_SET_UNITS: 0
        }
        self._set_time_end = {
            REQUEST_SET_MAIN: 0,
            REQUEST_SET_OTHER: 0,
            REQUEST_SET_UNITS: 0
        }
        self._store_file = store_file
        self._token_lock = threading.Lock()
        self._token = None
        self._units = units
        self._url = ARISTON_URL
        self._user = username
        self._verify = True
        self._version = ""
        # check which requests should be used
        # note that main and other are mandatory for climate and water_heater operations
        self._valid_requests = {
            REQUEST_GET_MAIN: True,
            REQUEST_GET_CH: False,
            REQUEST_GET_DHW: False,
            REQUEST_GET_ERROR: False,
            REQUEST_GET_GAS: False,
            REQUEST_GET_OTHER: True,
            REQUEST_GET_UNITS: False,
            REQUEST_GET_CURRENCY: False,
            REQUEST_GET_VERSION: False
        }
        if binary_sensors != [] and binary_sensors != None:
            for item in binary_sensors:
                self._valid_requests[_get_request_for_parameter(item)] = True
        if sensors != [] and sensors != None:
            for item in sensors:
                self._valid_requests[_get_request_for_parameter(item)] = True
        if switches != [] and switches != None:
            for item in switches:
                self._valid_requests[_get_request_for_parameter(item)] = True
        if self._units == VAL_AUTO:
            self._valid_requests[REQUEST_GET_UNITS] = True
        # prepare lists of requests
        # prepare list of higher priority
        self._request_list_high_prio = []
        if self._valid_requests[REQUEST_GET_MAIN]:
            self._request_list_high_prio.append(self._get_main_data)
        if self._valid_requests[REQUEST_GET_OTHER]:
            self._request_list_high_prio.append(self._get_other_data)
        if self._valid_requests[REQUEST_GET_ERROR]:
            self._request_list_high_prio.append(self._get_error_data)
        # prepare list of lower priority
        self._request_list_low_prio = []
        if self._valid_requests[REQUEST_GET_UNITS]:
            self._request_list_low_prio.append(self._get_unit_data)
        if self._valid_requests[REQUEST_GET_CH]:
            self._request_list_low_prio.append(self._get_ch_data)
        if self._valid_requests[REQUEST_GET_DHW]:
            self._request_list_low_prio.append(self._get_dhw_data)
        if self._valid_requests[REQUEST_GET_GAS]:
            self._request_list_low_prio.append(self._get_gas_water_data)
        if self._valid_requests[REQUEST_GET_CURRENCY]:
            self._request_list_low_prio.append(self._get_currency_data)
        if self._valid_requests[REQUEST_GET_VERSION]:
            self._request_list_low_prio.append(self._get_version_data)

        # initiate timer between requests within one loop
        self._timer_between_param_delay = HTTP_PARAM_DELAY * POLLING_RATE_TO_VALUE[polling]

        # initiate timers for http requests to reading or setting of data
        self._timeout_long = HTTP_TIMEOUT_GET_LONG * POLLING_RATE_TO_VALUE[polling]
        self._timeout_medium = HTTP_TIMEOUT_GET_MEDIUM * POLLING_RATE_TO_VALUE[polling]
        self._timeout_short = HTTP_TIMEOUT_GET_SHORT * POLLING_RATE_TO_VALUE[polling]

        # initiate timer between set request attempts
        self._timer_between_set = VAL_NORMAL

        if self._store_file:
            with open('/config/data_' + self._name + '_valid_requests.json', 'w') as ariston_fetched:
                json.dump(self._valid_requests, ariston_fetched)

    @property
    def available(self):
        """Return if Aristons's API is responding."""
        return self._errors <= MAX_ERRORS and self._login and self._plant_id != ""

    def _login_session(self):
        """Login to fetch Ariston Plant ID and confirm login"""
        if not self._login:
            url = self._url + '/Account/Login'
            login_data = {"Email": self._user, "Password": self._password}
            try:
                with self._token_lock:
                    self._token = requests.auth.HTTPDigestAuth(self._user, self._password)
                resp = self._session.post(
                    url,
                    auth=self._token,
                    timeout=HTTP_TIMEOUT_LOGIN,
                    json=login_data,
                    verify=True)
            except:
                _LOGGER.warning('%s Authentication login error', self)
                raise LoginError
            if resp.status_code != 200:
                _LOGGER.warning('%s Unexpected reply during login: %s', self, resp.status_code)
                raise CommError
            if resp.url.startswith(self._url + "/PlantDashboard/Index/") or resp.url.startswith(
                    self._url + "/PlantManagement/Index/") or resp.url.startswith(
                self._url + "/PlantPreference/Index/") or resp.url.startswith(
                self._url + "/Error/Active/") or resp.url.startswith(
                self._url + "/PlantGuest/Index/") or resp.url.startswith(
                self._url + "/TimeProg/Index/"):
                with self._plant_id_lock:
                    self._plant_id = resp.url.split("/")[5]
                    self._login = True
                    _LOGGER.info('%s Plant ID is %s', self, self._plant_id)
            elif resp.url.startswith(self._url + "/PlantData/Index/") or resp.url.startswith(
                    self._url + "/UserData/Index/"):
                with self._plant_id_lock:
                    plant_id_attribute = resp.url.split("/")[5]
                    self._plant_id = plant_id_attribute.split("?")[0]
                    self._login = True
                    _LOGGER.info('%s Plant ID is %s', self, self._plant_id)
            elif resp.url.startswith(self._url + "/Menu/User/Index/"):
                with self._plant_id_lock:
                    self._plant_id = resp.url.split("/")[6]
                    self._login = True
                    _LOGGER.info('%s Plant ID is %s', self, self._plant_id)
            else:
                _LOGGER.warning('%s Authentication login error', self)
                raise LoginError
            dispatcher_send(self._hass, service_signal(SERVICE_UPDATE, self._name))
        return

    def _store_data(self, resp, request_type=""):
        """Store received dictionary"""
        if resp.status_code != 200:
            _LOGGER.warning('%s %s invalid reply code %s', self, request_type, resp.status_code)
            raise CommError
        if not _json_validator(resp.json()):
            _LOGGER.warning('%s %s No json detected', self, request_type)
            raise CommError
        store_none_zero = False
        last_temp = {}
        last_temp_min = {}
        last_temp_max = {}
        if request_type in [REQUEST_GET_MAIN, REQUEST_SET_MAIN]:

            try:
                allowed_modes = self._ariston_data_actual["allowedModes"]
                allowed_ch_modes = self._ariston_data_actual["zone"]["mode"]["allowedOptions"]
                last_temp[PARAM_DHW_STORAGE_TEMPERATURE] = self._ariston_data_actual["dhwStorageTemp"]
                last_temp[PARAM_DHW_COMFORT_TEMPERATURE] = self._ariston_data_actual["dhwTimeProgComfortTemp"]["value"]
                last_temp[PARAM_DHW_ECONOMY_TEMPERATURE] = self._ariston_data_actual["dhwTimeProgEconomyTemp"]["value"]
                last_temp[PARAM_DHW_SET_TEMPERATURE] = self._ariston_data_actual["dhwTemp"]["value"]
                last_temp[PARAM_CH_DETECTED_TEMPERATURE] = self._ariston_data_actual["zone"]["roomTemp"]
                last_temp[PARAM_CH_SET_TEMPERATURE] = self._ariston_data_actual["zone"]["comfortTemp"]["value"]
                last_temp_min[PARAM_DHW_COMFORT_TEMPERATURE] = self._ariston_data_actual["dhwTimeProgComfortTemp"][
                    "min"]
                last_temp_min[PARAM_DHW_ECONOMY_TEMPERATURE] = self._ariston_data_actual["dhwTimeProgEconomyTemp"][
                    "min"]
                last_temp_min[PARAM_DHW_SET_TEMPERATURE] = self._ariston_data_actual["dhwTemp"]["min"]
                last_temp_min[PARAM_CH_SET_TEMPERATURE] = self._ariston_data_actual["zone"]["comfortTemp"]["min"]
                last_temp_max[PARAM_DHW_COMFORT_TEMPERATURE] = self._ariston_data_actual["dhwTimeProgComfortTemp"][
                    "max"]
                last_temp_max[PARAM_DHW_ECONOMY_TEMPERATURE] = self._ariston_data_actual["dhwTimeProgEconomyTemp"][
                    "max"]
                last_temp_max[PARAM_DHW_SET_TEMPERATURE] = self._ariston_data_actual["dhwTemp"]["max"]
                last_temp_max[PARAM_CH_SET_TEMPERATURE] = self._ariston_data_actual["zone"]["comfortTemp"]["max"]
            except:
                allowed_modes = []
                allowed_ch_modes = []
                last_temp[PARAM_DHW_STORAGE_TEMPERATURE] = UNKNOWN_TEMP
                last_temp[PARAM_DHW_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp[PARAM_DHW_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                last_temp[PARAM_DHW_SET_TEMPERATURE] = UNKNOWN_TEMP
                last_temp[PARAM_CH_DETECTED_TEMPERATURE] = UNKNOWN_TEMP
                last_temp[PARAM_CH_SET_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_min[PARAM_DHW_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_min[PARAM_DHW_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_min[PARAM_DHW_SET_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_min[PARAM_CH_SET_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_max[PARAM_DHW_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_max[PARAM_DHW_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_max[PARAM_DHW_SET_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_max[PARAM_CH_SET_TEMPERATURE] = UNKNOWN_TEMP
                pass
            try:
                self._ariston_data_actual = copy.deepcopy(resp.json())
            except:
                self._ariston_data_actual = {}
                _LOGGER.warning("%s Invalid data received for Main, not JSON", self)
                pass
            try:
                # force default modes if received none
                if self._ariston_data_actual["allowedModes"] == []:
                    if allowed_modes != []:
                        self._ariston_data_actual["allowedModes"] = allowed_modes
                    else:
                        self._ariston_data_actual["allowedModes"] = DEFAULT_MODES
                # force default CH modes if received none
                if self._ariston_data_actual["zone"]["mode"]["allowedOptions"] == []:
                    if allowed_ch_modes != []:
                        self._ariston_data_actual["zone"]["mode"]["allowedOptions"] = allowed_ch_modes
                    else:
                        self._ariston_data_actual["zone"]["mode"]["allowedOptions"] = DEFAULT_CH_MODES
                # keep latest DHW storage temperature if received invalid
                if self._ariston_data_actual["dhwStorageTemp"] == UNKNOWN_TEMP:
                    if last_temp[PARAM_DHW_STORAGE_TEMPERATURE] != UNKNOWN_TEMP:
                        self._get_zero_temperature[PARAM_DHW_STORAGE_TEMPERATURE] += 1
                        store_none_zero = True
                        if self._get_zero_temperature[PARAM_DHW_STORAGE_TEMPERATURE] < MAX_ZERO_TOLERANCE:
                            self._ariston_data_actual["dhwStorageTemp"] = last_temp[PARAM_DHW_STORAGE_TEMPERATURE]
                else:
                    self._get_zero_temperature[PARAM_DHW_STORAGE_TEMPERATURE] = 0
                # keep latest DHW comfort temperature if received invalid
                if self._ariston_data_actual["dhwTimeProgComfortTemp"]["value"] == UNKNOWN_TEMP:
                    if last_temp[PARAM_DHW_COMFORT_TEMPERATURE] != UNKNOWN_TEMP and last_temp_min[
                        PARAM_DHW_COMFORT_TEMPERATURE] != UNKNOWN_TEMP and last_temp_max[
                        PARAM_DHW_COMFORT_TEMPERATURE] != UNKNOWN_TEMP:
                        self._get_zero_temperature[PARAM_DHW_COMFORT_TEMPERATURE] += 1
                        store_none_zero = True
                        if self._get_zero_temperature[PARAM_DHW_COMFORT_TEMPERATURE] < MAX_ZERO_TOLERANCE:
                            self._ariston_data_actual["dhwTimeProgComfortTemp"]["value"] = last_temp[
                                PARAM_DHW_COMFORT_TEMPERATURE]
                else:
                    self._get_zero_temperature[PARAM_DHW_COMFORT_TEMPERATURE] = 0
                # keep latest DHW economy temperature if received invalid
                if self._ariston_data_actual["dhwTimeProgEconomyTemp"]["value"] == UNKNOWN_TEMP:
                    if last_temp[PARAM_DHW_ECONOMY_TEMPERATURE] != UNKNOWN_TEMP and last_temp_min[
                        PARAM_DHW_ECONOMY_TEMPERATURE] != UNKNOWN_TEMP and last_temp_max[
                        PARAM_DHW_ECONOMY_TEMPERATURE] != UNKNOWN_TEMP:
                        self._get_zero_temperature[PARAM_DHW_ECONOMY_TEMPERATURE] += 1
                        store_none_zero = True
                        if self._get_zero_temperature[PARAM_DHW_ECONOMY_TEMPERATURE] < MAX_ZERO_TOLERANCE:
                            self._ariston_data_actual["dhwTimeProgEconomyTemp"]["value"] = last_temp[
                                PARAM_DHW_ECONOMY_TEMPERATURE]
                else:
                    self._get_zero_temperature[PARAM_DHW_ECONOMY_TEMPERATURE] = 0
                # keep latest DHW set temperature if received invalid
                if self._ariston_data_actual["dhwTemp"]["value"] == UNKNOWN_TEMP:
                    if last_temp[PARAM_DHW_SET_TEMPERATURE] != UNKNOWN_TEMP:
                        self._get_zero_temperature[PARAM_DHW_SET_TEMPERATURE] += 1
                        store_none_zero = True
                        if self._get_zero_temperature[PARAM_DHW_SET_TEMPERATURE] < MAX_ZERO_TOLERANCE:
                            self._ariston_data_actual["dhwTemp"]["value"] = last_temp[
                                PARAM_DHW_SET_TEMPERATURE]
                else:
                    self._get_zero_temperature[PARAM_DHW_SET_TEMPERATURE] = 0
                # keep latest CH detected temperature if received invalid
                if self._ariston_data_actual["zone"]["roomTemp"] == UNKNOWN_TEMP:
                    if last_temp[PARAM_CH_DETECTED_TEMPERATURE] != UNKNOWN_TEMP:
                        self._get_zero_temperature[PARAM_CH_DETECTED_TEMPERATURE] += 1
                        store_none_zero = True
                        if self._get_zero_temperature[PARAM_CH_DETECTED_TEMPERATURE] < MAX_ZERO_TOLERANCE:
                            self._ariston_data_actual["zone"]["roomTemp"] = last_temp[
                                PARAM_CH_DETECTED_TEMPERATURE]
                else:
                    self._get_zero_temperature[PARAM_CH_DETECTED_TEMPERATURE] = 0
                # keep latest CH set temperature if received invalid
                if self._ariston_data_actual["zone"]["comfortTemp"]["value"] == UNKNOWN_TEMP:
                    if last_temp[PARAM_CH_SET_TEMPERATURE] != UNKNOWN_TEMP:
                        self._get_zero_temperature[PARAM_CH_SET_TEMPERATURE] += 1
                        store_none_zero = True
                        if self._get_zero_temperature[PARAM_CH_SET_TEMPERATURE] < MAX_ZERO_TOLERANCE:
                            self._ariston_data_actual["zone"]["comfortTemp"]["value"] = last_temp[
                                PARAM_CH_SET_TEMPERATURE]
                else:
                    self._get_zero_temperature[PARAM_CH_SET_TEMPERATURE] = 0
            except:
                self._ariston_data_actual["allowedModes"] = DEFAULT_MODES
                self._ariston_data_actual["zone"]["mode"]["allowedOptions"] = DEFAULT_CH_MODES
                _LOGGER.warning("%s Invalid data received for Main", self)
                pass

            self._ariston_data = copy.deepcopy(self._ariston_data_actual)

        elif request_type == REQUEST_GET_CH:

            try:
                last_temp[PARAM_CH_COMFORT_TEMPERATURE] = self._ariston_ch_data_actual["comfortTemp"]["value"]
                last_temp[PARAM_CH_ECONOMY_TEMPERATURE] = self._ariston_ch_data_actual["economyTemp"]["value"]
                last_temp_min[PARAM_CH_COMFORT_TEMPERATURE] = self._ariston_ch_data_actual["comfortTemp"]["min"]
                last_temp_min[PARAM_CH_ECONOMY_TEMPERATURE] = self._ariston_ch_data_actual["economyTemp"]["min"]
                last_temp_max[PARAM_CH_COMFORT_TEMPERATURE] = self._ariston_ch_data_actual["comfortTemp"]["max"]
                last_temp_max[PARAM_CH_ECONOMY_TEMPERATURE] = self._ariston_ch_data_actual["economyTemp"]["max"]
            except:
                last_temp[PARAM_CH_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp[PARAM_CH_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_min[PARAM_CH_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_min[PARAM_CH_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_max[PARAM_CH_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_max[PARAM_CH_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                pass
            try:
                self._ariston_ch_data_actual = copy.deepcopy(resp.json())
            except:
                self._ariston_ch_data_actual = {}
                _LOGGER.warning("%s Invalid data received for CH, not JSON", self)
                pass
            try:
                # keep latest CH comfort temperature if received invalid
                if self._ariston_ch_data_actual["comfortTemp"]["value"] == UNKNOWN_TEMP:
                    if last_temp[PARAM_CH_COMFORT_TEMPERATURE] != UNKNOWN_TEMP:
                        self._get_zero_temperature[PARAM_CH_COMFORT_TEMPERATURE] += 1
                        store_none_zero = True
                        if self._get_zero_temperature[PARAM_CH_COMFORT_TEMPERATURE] < MAX_ZERO_TOLERANCE:
                            self._ariston_ch_data_actual["comfortTemp"]["value"] = last_temp[
                                PARAM_CH_COMFORT_TEMPERATURE]
                else:
                    self._get_zero_temperature[PARAM_CH_COMFORT_TEMPERATURE] = 0
                # keep latest CH comfort temperature if received invalid
                if self._ariston_ch_data_actual["economyTemp"]["value"] == UNKNOWN_TEMP:
                    if last_temp[PARAM_CH_ECONOMY_TEMPERATURE] != UNKNOWN_TEMP:
                        self._get_zero_temperature[PARAM_CH_ECONOMY_TEMPERATURE] += 1
                        store_none_zero = True
                        if self._get_zero_temperature[PARAM_CH_ECONOMY_TEMPERATURE] < MAX_ZERO_TOLERANCE:
                            self._ariston_ch_data_actual["economyTemp"]["value"] = last_temp[
                                PARAM_CH_ECONOMY_TEMPERATURE]
                    else:
                        self._get_zero_temperature[PARAM_CH_ECONOMY_TEMPERATURE] = 0
            except:
                _LOGGER.warning("%s Invalid data received for CH", self)
                pass

            self._ariston_ch_data = copy.deepcopy(self._ariston_ch_data_actual)

        elif request_type == REQUEST_GET_ERROR:

            try:
                self._ariston_error_data_actual = copy.deepcopy(resp.json())
            except:
                self._ariston_error_data_actual = {}
                _LOGGER.warning("%s Invalid data received for error, not JSON", self)
                pass

            self._ariston_error_data = copy.deepcopy(self._ariston_error_data_actual)

        elif request_type == REQUEST_GET_GAS:

            try:
                self._ariston_gas_data_actual = copy.deepcopy(resp.json())
            except:
                self._ariston_gas_data_actual = {}
                _LOGGER.warning("%s Invalid data received for energy use, not JSON", self)
                pass

            self._ariston_gas_data = copy.deepcopy(self._ariston_gas_data_actual)

        elif request_type == REQUEST_GET_OTHER:

            try:
                last_temp[PARAM_CH_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp[PARAM_CH_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_min[PARAM_CH_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_min[PARAM_CH_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_max[PARAM_CH_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_max[PARAM_CH_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                for param_item in self._ariston_other_data_actual:
                    try:
                        # Copy latest DHW temperatures
                        if param_item["id"] == ARISTON_CH_COMFORT_TEMP:
                            last_temp[PARAM_CH_COMFORT_TEMPERATURE] = param_item["value"]
                        elif param_item["id"] == ARISTON_CH_ECONOMY_TEMP:
                            last_temp[PARAM_CH_ECONOMY_TEMPERATURE] = param_item["value"]
                    except:
                        continue
            except:
                last_temp[PARAM_CH_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp[PARAM_CH_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_min[PARAM_CH_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_min[PARAM_CH_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_max[PARAM_CH_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                last_temp_max[PARAM_CH_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                pass
            try:
                self._ariston_other_data_actual = copy.deepcopy(resp.json())
            except:
                self._ariston_other_data_actual = {}
                _LOGGER.warning("%s Invalid data received for parameters, not JSON", self)
                pass

            for item, param_item in enumerate(self._ariston_other_data_actual):
                try:
                    # Copy latest DHW temperatures
                    if param_item["id"] == ARISTON_DHW_TIME_PROG_COMFORT and param_item["value"] != UNKNOWN_TEMP:
                        if "dhwTimeProgComfortTemp" in self._ariston_data_actual and "value" in \
                                self._ariston_data_actual["dhwTimeProgComfortTemp"]:
                            self._ariston_data_actual["dhwTimeProgComfortTemp"]["value"] = param_item["value"]
                    elif param_item["id"] == ARISTON_DHW_TIME_PROG_ECONOMY and param_item["value"] != UNKNOWN_TEMP:
                        if "dhwTimeProgEconomyTemp" in self._ariston_data_actual and "value" in \
                                self._ariston_data_actual["dhwTimeProgEconomyTemp"]:
                            self._ariston_data_actual["dhwTimeProgEconomyTemp"]["value"] = param_item["value"]
                    elif param_item["id"] == ARISTON_CH_COMFORT_TEMP:
                        # keep latest CH comfort temperature if received invalid
                        if param_item["value"] == UNKNOWN_TEMP:
                            if last_temp[PARAM_CH_COMFORT_TEMPERATURE] != UNKNOWN_TEMP:
                                self._get_zero_temperature[PARAM_CH_COMFORT_TEMPERATURE] += 1
                                store_none_zero = True
                                if self._get_zero_temperature[PARAM_CH_COMFORT_TEMPERATURE] < MAX_ZERO_TOLERANCE:
                                    self._ariston_other_data_actual[item]["value"] = last_temp[
                                        PARAM_CH_COMFORT_TEMPERATURE]
                        else:
                            self._get_zero_temperature[PARAM_CH_COMFORT_TEMPERATURE] = 0
                    elif param_item["id"] == ARISTON_CH_ECONOMY_TEMP:
                        # keep latest CH economy temperature if received invalid
                        if param_item["value"] == UNKNOWN_TEMP:
                            if last_temp[PARAM_CH_ECONOMY_TEMPERATURE] != UNKNOWN_TEMP:
                                self._get_zero_temperature[PARAM_CH_ECONOMY_TEMPERATURE] += 1
                                store_none_zero = True
                                if self._get_zero_temperature[PARAM_CH_ECONOMY_TEMPERATURE] < MAX_ZERO_TOLERANCE:
                                    self._ariston_other_data_actual[item]["value"] = last_temp[
                                        PARAM_CH_ECONOMY_TEMPERATURE]
                            else:
                                self._get_zero_temperature[PARAM_CH_ECONOMY_TEMPERATURE] = 0
                except:
                    continue

            self._ariston_other_data = copy.deepcopy(self._ariston_other_data_actual)

        elif request_type == REQUEST_GET_UNITS:
            try:
                self._ariston_units_actual = copy.deepcopy(resp.json())
            except:
                self._ariston_units_actual = {}
                _LOGGER.warning("%s Invalid data received for units, not JSON", self)
                pass

            self._ariston_units = copy.deepcopy(self._ariston_units_actual)

        elif request_type == REQUEST_GET_CURRENCY:
            try:
                self._ariston_currency_actual = copy.deepcopy(resp.json())
            except:
                self._ariston_currency_actual = {}
                _LOGGER.warning("%s Invalid data received for currency, not JSON", self)
                pass

            self._ariston_currency = copy.deepcopy(self._ariston_currency_actual)

        elif request_type == REQUEST_GET_DHW:
            try:
                self._ariston_dhw_data_actual = copy.deepcopy(resp.json())
            except:
                self._ariston_dhw_data_actual = {}
                _LOGGER.warning("%s Invalid data received for DHW, not JSON", self)
                pass

            self._ariston_dhw_data = copy.deepcopy(self._ariston_dhw_data_actual)

        elif request_type == REQUEST_GET_VERSION:
            try:
                self._version = resp.json()["tag_name"]
            except:
                self._version = ""
                _LOGGER.warning("%s Invalid version fetched", self)

        self._get_time_end[request_type] = time.time()

        if self._store_file:
            with open('/config/data_' + self._name + request_type + '.json', 'w') as ariston_fetched:
                if request_type in [REQUEST_GET_MAIN, REQUEST_SET_MAIN]:
                    json.dump(self._ariston_data_actual, ariston_fetched)
                elif request_type == REQUEST_GET_CH:
                    json.dump(self._ariston_ch_data_actual, ariston_fetched)
                elif request_type == REQUEST_GET_DHW:
                    json.dump(self._ariston_dhw_data_actual, ariston_fetched)
                elif request_type == REQUEST_GET_ERROR:
                    json.dump(self._ariston_error_data_actual, ariston_fetched)
                elif request_type == REQUEST_GET_GAS:
                    json.dump(self._ariston_gas_data_actual, ariston_fetched)
                elif request_type == REQUEST_GET_OTHER:
                    json.dump(self._ariston_other_data_actual, ariston_fetched)
                elif request_type == REQUEST_GET_UNITS:
                    json.dump(self._ariston_units_actual, ariston_fetched)
                elif request_type == REQUEST_GET_CURRENCY:
                    json.dump(self._ariston_currency_actual, ariston_fetched)
                elif request_type == REQUEST_GET_VERSION:
                    ariston_fetched.write(self._version)
            with open('/config/data_' + self._name + '_zero_count.json', 'w') as ariston_fetched:
                json.dump(self._get_zero_temperature, ariston_fetched)
            with open('/config/data_' + self._name + '_timers.json', 'w') as ariston_fetched:
                json.dump([self._set_time_start, self._set_time_end, self._get_time_start, self._get_time_end],
                          ariston_fetched)
            if store_none_zero:
                with open('/config/data_' + self._name + request_type + '_non_zero.json', 'w') as ariston_fetched:
                    json.dump([last_temp, last_temp_min, last_temp_max], ariston_fetched)

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
                    url = self._url + '/TimeProg/GetWeeklyPlan/' + self._plant_id + '?progId=ChZn1&umsys=si'
                    http_timeout = self._timeout_medium
                elif request_type == REQUEST_GET_DHW:
                    url = self._url + '/TimeProg/GetWeeklyPlan/' + self._plant_id + '?progId=Dhw&umsys=si'
                    http_timeout = self._timeout_medium
                elif request_type == REQUEST_GET_ERROR:
                    url = self._url + '/Error/ActiveDataSource/' + self._plant_id + \
                          '?$inlinecount=allpages&$skip=0&$top=100'
                    http_timeout = self._timeout_medium
                elif request_type == REQUEST_GET_GAS:
                    url = self._url + '/Metering/GetData/' + self._plant_id + '?kind=1&umsys=si'
                    http_timeout = self._timeout_medium
                elif request_type == REQUEST_GET_OTHER:
                    list_to_send = ARISTON_PARAM_LIST.copy()
                    try:
                        if self._ariston_data_actual["dhwBoilerPresent"]:
                            list_to_send.append(ARISTON_THERMAL_CLEANSE_FUNCTION)
                            list_to_send.append(ARISTON_THERMAL_CLEANSE_CYCLE)
                    except:
                        pass
                    ids_to_fetch = ",".join(map(str, list_to_send))
                    url = self._url + '/Menu/User/Refresh/' + self._plant_id + '?paramIds=' + ids_to_fetch + \
                          '&umsys=si'
                    http_timeout = self._timeout_long
                elif request_type == REQUEST_GET_UNITS:
                    url = self._url + '/PlantPreference/GetData/' + self._plant_id
                    http_timeout = self._timeout_short
                elif request_type == REQUEST_GET_CURRENCY:
                    url = self._url + '/Metering/GetCurrencySettings/' + self._plant_id
                    http_timeout = self._timeout_medium
                elif request_type == REQUEST_GET_VERSION:
                    url = GITHUB_LATEST_RELEASE
                    http_timeout = self._timeout_short
                else:
                    url = self._url + '/PlantDashboard/GetPlantData/' + self._plant_id
                    http_timeout = self._timeout_long
                with self._data_lock:
                    try:
                        self._get_time_start[request_type] = time.time()
                        resp = self._session.get(
                            url,
                            auth=self._token,
                            timeout=http_timeout,
                            verify=True)
                    except:
                        _LOGGER.warning("%s %s Problem reading data", self, request_type)
                        raise CommError
                    self._store_data(resp, request_type)
            else:
                _LOGGER.debug("%s %s Still setting data, read restricted", self, request_type)
        else:
            _LOGGER.warning("%s %s Not properly logged in to get the data", self, request_type)
            raise LoginError
        _LOGGER.info('Data fetched')
        return True

    def _queue_get_data(self, dummy=None):
        """Queue all request items"""
        with self._data_lock:
            # schedule next get request
            if self._errors >= MAX_ERRORS_TIMER_EXTEND:
                # give a little rest to the system if too many errors
                retry_in = self._timer_between_param_delay * HTTP_DELAY_MULTIPLY
                self._timer_between_set = VAL_LONG
                _LOGGER.warning('%s Retrying in %s seconds', self, retry_in)
            else:
                # work as usual
                retry_in = self._timer_between_param_delay
                self._timer_between_set = VAL_NORMAL
                _LOGGER.debug('%s Fetching data in %s seconds', self, retry_in)
            track_point_in_time(self._hass, self._queue_get_data, dt_util.now() + timedelta(seconds=retry_in))

            # first trigger fetching parameters that are being changed
            if self._set_param_group[REQUEST_GET_MAIN]:
                # setting of main data is ongoing, prioritize it
                track_point_in_time(self._hass, self._get_main_data, dt_util.now() + timedelta(seconds=1))
                if not self._set_scheduled:
                    self._set_param_group[REQUEST_GET_MAIN] = False
            elif self._set_param_group[REQUEST_GET_OTHER]:
                # setting of parameter data is ongoing, prioritize it
                track_point_in_time(self._hass, self._get_other_data, dt_util.now() + timedelta(seconds=1))
                if not self._set_scheduled:
                    self._set_param_group[REQUEST_GET_OTHER] = False
            elif self._set_param_group[REQUEST_GET_UNITS]:
                # setting of parameter units is ongoing, prioritize it
                track_point_in_time(self._hass, self._get_unit_data, dt_util.now() + timedelta(seconds=1))
                if not self._set_scheduled:
                    self._set_param_group[REQUEST_GET_UNITS] = False
            else:
                # second is fetch higher priority list items
                # select next item from high priority list
                if self._get_request_number_high_prio < len(self._request_list_high_prio):
                    # item is available in the list
                    track_point_in_time(self._hass,
                                        self._request_list_high_prio[self._get_request_number_high_prio],
                                        dt_util.now() + timedelta(seconds=1))
                    self._get_request_number_high_prio += 1
                elif self._get_request_number_high_prio > len(self._request_list_high_prio):
                    # start from the beginning of the list
                    self._get_request_number_high_prio = 0
                else:
                    # third we reserve one place for one of lower priority tasks among higher priority ones
                    self._get_request_number_high_prio += 1
                    if self._errors < MAX_ERRORS_TIMER_EXTEND:
                        # skip lower priority requests if too many errors and give time to recover
                        # other data is not that important, so just handle in queue
                        if self._get_request_number_low_prio < len(self._request_list_low_prio):
                            # item is available in the list
                            track_point_in_time(self._hass,
                                                self._request_list_low_prio[self._get_request_number_low_prio],
                                                dt_util.now() + timedelta(seconds=1))
                            self._get_request_number_low_prio += 1
                        if self._get_request_number_low_prio >= len(self._request_list_low_prio):
                            self._get_request_number_low_prio = 0

            if self._store_file:
                with open('/config/data_' + self._name + '_all_set_get.json', 'w') as ariston_fetched:
                    json.dump(self._set_param_group, ariston_fetched)

    def _control_availability_state(self, request_type):
        """Control component availability"""
        try:
            self._get_http_data(request_type)
        except:
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
            raise AristonError
        with self._lock:
            was_offline = not self.available
            self._errors = 0
        if was_offline:
            _LOGGER.info("%s Ariston back online", self._name)
            dispatcher_send(self._hass, service_signal(SERVICE_UPDATE, self._name))
        return

    def _get_main_data(self, dummy=None):
        """Get Ariston main data from http"""
        self._control_availability_state(REQUEST_GET_MAIN)

    def _get_gas_water_data(self, dummy=None):
        """Get Ariston gas and water use data from http"""
        self._control_availability_state(REQUEST_GET_GAS)

    def _get_error_data(self, dummy=None):
        """Get Ariston error data from http"""
        self._control_availability_state(REQUEST_GET_ERROR)

    def _get_ch_data(self, dummy=None):
        """Get Ariston CH data from http"""
        self._control_availability_state(REQUEST_GET_CH)

    def _get_dhw_data(self, dummy=None):
        """Get Ariston DHW data from http"""
        self._control_availability_state(REQUEST_GET_DHW)

    def _get_other_data(self, dummy=None):
        """Get Ariston other data from http"""
        self._control_availability_state(REQUEST_GET_OTHER)

    def _get_unit_data(self, dummy=None):
        """Get Ariston unit data from http"""
        self._control_availability_state(REQUEST_GET_UNITS)

    def _get_currency_data(self, dummy=None):
        """Get Ariston currency data from http"""
        self._control_availability_state(REQUEST_GET_CURRENCY)

    def _get_version_data(self, dummy=None):
        """Get Ariston version from GitHub"""
        self._control_availability_state(REQUEST_GET_VERSION)

    def _setting_http_data(self, set_data, request_type=""):
        """setting of data"""
        _LOGGER.info('setting http data')
        try:
            if self._store_file:
                with open('/config/data_' + self._name + request_type + '.json', 'w') as ariston_fetched:
                    json.dump(set_data, ariston_fetched)
                with open('/config/data_' + self._name + '_all_set.json', 'w') as ariston_fetched:
                    json.dump(self._set_param, ariston_fetched)
                with open('/config/data_' + self._name + '_timers.json', 'w') as ariston_fetched:
                    json.dump([self._set_time_start, self._set_time_end, self._get_time_start, self._get_time_end],
                              ariston_fetched)
        except:
            pass
        if request_type == REQUEST_SET_OTHER:
            url = self._url + '/Menu/User/Submit/' + self._plant_id + '?umsys=si'
            http_timeout = self._timeout_medium
        elif request_type == REQUEST_SET_UNITS:
            url = self._url + '/PlantPreference/SetData/' + self._plant_id
            http_timeout = self._timeout_short
        else:
            url = self._url + '/PlantDashboard/SetPlantAndZoneData/' + self._plant_id + '?zoneNum=1&umsys=si'
            http_timeout = self._timeout_long
        try:
            self._set_time_start[request_type] = time.time()
            resp = self._session.post(
                url,
                auth=self._token,
                timeout=http_timeout,
                json=set_data,
                verify=True)
        except:
            _LOGGER.warning('%s %s error', self, request_type)
            raise CommError
        if resp.status_code != 200:
            _LOGGER.warning("%s %s Command to set data failed with code: %s", self, request_type, resp.status_code)
            raise CommError
        self._set_time_end[request_type] = time.time()
        if request_type == REQUEST_SET_MAIN:
            """
            data in reply cannot be fully trusted as occasionally we receive changed data but on next read turns out 
            that it was in fact not changed, so uncomment below on your own risk
            """
            # self._store_data(resp, request_type)
            if self._store_file:
                with open("/config/data_" + self._name + request_type + "_reply.txt", "w") as f:
                    f.write(resp.text)
        _LOGGER.info('%s %s Data was presumably changed', self, request_type)

    def _set_visible_data(self):
        try:
            # set visible values as if they have in fact changed
            for parameter, value in self._set_param.items():
                try:
                    if self._valid_requests[_get_request_for_parameter(parameter)]:
                        if parameter == PARAM_MODE:
                            self._ariston_data["mode"] = value
                        elif parameter == PARAM_CH_MODE:
                            self._ariston_data["zone"]["mode"]["value"] = value
                        elif parameter == PARAM_CH_SET_TEMPERATURE:
                            self._ariston_data["zone"]["comfortTemp"]["value"] = value
                        elif parameter == PARAM_CH_COMFORT_TEMPERATURE:
                            for iteration, item in enumerate(self._ariston_other_data):
                                if item["id"] == ARISTON_CH_COMFORT_TEMP:
                                    self._ariston_other_data[iteration]["value"] = value
                                    break
                        elif parameter == PARAM_CH_ECONOMY_TEMPERATURE:
                            for iteration, item in enumerate(self._ariston_other_data):
                                if item["id"] == ARISTON_CH_ECONOMY_TEMP:
                                    self._ariston_other_data[iteration]["value"] = value
                                    break
                        elif parameter == PARAM_DHW_SET_TEMPERATURE:
                            self._ariston_data["dhwTemp"]["value"] = value
                        elif parameter == PARAM_DHW_COMFORT_TEMPERATURE:
                            self._ariston_data["dhwTimeProgComfortTemp"]["value"] = value
                            try:
                                if VALUE_TO_DHW_MODE[self._ariston_data_actual["dhwMode"]] == VAL_PROGRAM:
                                    if self._ariston_data_actual["dhwTimeProgComfortActive"] == True:
                                        # economy temperature is being used
                                        self._ariston_data["dhwTemp"]["value"] = value
                                elif VALUE_TO_DHW_MODE[self._ariston_data_actual["dhwMode"]] == VAL_UNSUPPORTED:
                                    self._ariston_data["dhwTemp"]["value"] = value
                            except:
                                pass
                        elif parameter == PARAM_DHW_ECONOMY_TEMPERATURE:
                            self._ariston_data["dhwTimeProgEconomyTemp"]["value"] = value
                            try:
                                if VALUE_TO_DHW_MODE[self._ariston_data_actual["dhwMode"]] == VAL_PROGRAM:
                                    if self._ariston_data_actual["dhwTimeProgComfortActive"] == False:
                                        # comfort temperature is being used
                                        self._ariston_data["dhwTemp"]["value"] = value
                            except:
                                pass
                        elif parameter == PARAM_DHW_MODE:
                            self._ariston_data["dhwMode"] = value
                        elif parameter == PARAM_DHW_COMFORT_FUNCTION:
                            for iteration, item in enumerate(self._ariston_other_data):
                                if item["id"] == ARISTON_DHW_COMFORT_FUNCTION:
                                    self._ariston_other_data[iteration]["value"] = value
                                    break
                        elif parameter == PARAM_INTERNET_TIME:
                            for iteration, item in enumerate(self._ariston_other_data):
                                if item["id"] == ARISTON_INTERNET_TIME:
                                    self._ariston_other_data[iteration]["value"] = value
                                    break
                        elif parameter == PARAM_INTERNET_WEATHER:
                            for iteration, item in enumerate(self._ariston_other_data):
                                if item["id"] == ARISTON_INTERNET_WEATHER:
                                    self._ariston_other_data[iteration]["value"] = value
                                    break
                        elif parameter == PARAM_CH_AUTO_FUNCTION:
                            for iteration, item in enumerate(self._ariston_other_data):
                                if item["id"] == ARISTON_CH_AUTO_FUNCTION:
                                    self._ariston_other_data[iteration]["value"] = value
                                    break
                        elif parameter == PARAM_UNITS:
                            self._ariston_units["measurementSystem"] = value
                        elif parameter == PARAM_THERMAL_CLEANSE_CYCLE:
                            for iteration, item in enumerate(self._ariston_other_data):
                                if item["id"] == ARISTON_THERMAL_CLEANSE_CYCLE:
                                    self._ariston_other_data[iteration]["value"] = value
                                    break
                        elif parameter == PARAM_THERMAL_CLEANSE_FUNCTION:
                            for iteration, item in enumerate(self._ariston_other_data):
                                if item["id"] == ARISTON_THERMAL_CLEANSE_FUNCTION:
                                    self._ariston_other_data[iteration]["value"] = value
                                    break
                except:
                    continue
        except:
            pass

        try:
            if self._store_file:
                with open('/config/data_' + self._name + '_temp_main.json', 'w') as ariston_fetched:
                    json.dump(self._ariston_data, ariston_fetched)
                with open('/config/data_' + self._name + '_temp_param.json', 'w') as ariston_fetched:
                    json.dump(self._ariston_other_data, ariston_fetched)
                with open('/config/data_' + self._name + '_temp_units.json', 'w') as ariston_fetched:
                    json.dump(self._ariston_units, ariston_fetched)
        except:
            pass

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
                for request_item in self._set_retry:
                    self._set_retry[request_item] = 0
                if self._set_scheduled:
                    # we wait for another attempt after timeout, data will be set then
                    return
            if self._login and self.available and self._plant_id != "":

                changed_parameter = {
                    REQUEST_SET_MAIN: {},
                    REQUEST_SET_OTHER: {},
                    REQUEST_SET_UNITS: {}
                }

                set_data = {}
                # prepare setting of main data dictionary
                set_data["NewValue"] = copy.deepcopy(self._ariston_data_actual)
                set_data["OldValue"] = copy.deepcopy(self._ariston_data_actual)
                # Format is received in 12H format but for some reason REST tools send it fine but python must send 24H format
                try:
                    set_data["NewValue"]["zone"]["derogaUntil"] = _change_to_24h_format(
                        self._ariston_data_actual["zone"]["derogaUntil"])
                    set_data["OldValue"]["zone"]["derogaUntil"] = _change_to_24h_format(
                        self._ariston_data_actual["zone"]["derogaUntil"])
                except:
                    set_data["NewValue"]["zone"]["derogaUntil"] = DEFAULT_TIME
                    set_data["OldValue"]["zone"]["derogaUntil"] = DEFAULT_TIME
                    pass

                set_units_data = {}
                try:
                    set_units_data["measurementSystem"] = self._ariston_units_actual["measurementSystem"]
                except:
                    set_units_data["measurementSystem"] = UNKNOWN_UNITS
                    pass

                dhw_temp = {}
                dhw_temp_time = {}
                try:
                    dhw_temp[PARAM_DHW_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                    dhw_temp[PARAM_DHW_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                    dhw_temp_time[PARAM_DHW_COMFORT_TEMPERATURE] = 0
                    dhw_temp_time[PARAM_DHW_ECONOMY_TEMPERATURE] = 0
                    if self._get_time_end[REQUEST_GET_MAIN] > self._get_time_end[REQUEST_GET_OTHER] and \
                            self._get_zero_temperature[PARAM_DHW_COMFORT_TEMPERATURE] == 0:
                        if set_data["NewValue"]["dhwTimeProgSupported"]:
                            dhw_temp[PARAM_DHW_COMFORT_TEMPERATURE] = set_data["NewValue"]["dhwTimeProgComfortTemp"][
                                "value"]
                            dhw_temp_time[PARAM_DHW_COMFORT_TEMPERATURE] = self._get_time_end[REQUEST_GET_MAIN]
                        else:
                            dhw_temp[PARAM_DHW_COMFORT_TEMPERATURE] = set_data["NewValue"]["dhwTemp"]["value"]
                            dhw_temp_time[PARAM_DHW_COMFORT_TEMPERATURE] = self._get_time_end[REQUEST_GET_MAIN]
                    else:
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_DHW_TIME_PROG_COMFORT:
                                dhw_temp[PARAM_DHW_COMFORT_TEMPERATURE] = param_item["value"]
                                dhw_temp_time[PARAM_DHW_COMFORT_TEMPERATURE] = self._get_time_end[REQUEST_GET_OTHER]

                    if self._get_time_end[REQUEST_GET_MAIN] > self._get_time_end[REQUEST_GET_OTHER] and \
                            self._get_zero_temperature[PARAM_DHW_ECONOMY_TEMPERATURE] == 0 and set_data["NewValue"][
                        "dhwTimeProgSupported"]:
                        dhw_temp[PARAM_DHW_ECONOMY_TEMPERATURE] = set_data["NewValue"]["dhwTimeProgEconomyTemp"][
                            "value"]
                        dhw_temp_time[PARAM_DHW_ECONOMY_TEMPERATURE] = self._get_time_end[REQUEST_GET_MAIN]
                    else:
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_DHW_TIME_PROG_ECONOMY:
                                dhw_temp[PARAM_DHW_ECONOMY_TEMPERATURE] = param_item["value"]
                                dhw_temp_time[PARAM_DHW_ECONOMY_TEMPERATURE] = self._get_time_end[REQUEST_GET_OTHER]

                except:
                    dhw_temp[PARAM_DHW_COMFORT_TEMPERATURE] = UNKNOWN_TEMP
                    dhw_temp[PARAM_DHW_ECONOMY_TEMPERATURE] = UNKNOWN_TEMP
                    dhw_temp_time[PARAM_DHW_COMFORT_TEMPERATURE] = 0
                    dhw_temp_time[PARAM_DHW_ECONOMY_TEMPERATURE] = 0
                    pass

                # prepare setting of parameter data dictionary
                set_param_data = []

                if PARAM_MODE in self._set_param:
                    if set_data["NewValue"]["mode"] == self._set_param[PARAM_MODE]:
                        if self._set_time_start[_set_request_for_parameter(PARAM_MODE)] < self._get_time_end[
                            _get_request_for_parameter(PARAM_MODE)]:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_MODE]
                        else:
                            # assume data was not yet changed
                            changed_parameter[_set_request_for_parameter(PARAM_MODE)][
                                _get_request_for_parameter(PARAM_MODE)] = True
                    else:
                        set_data["NewValue"]["mode"] = self._set_param[PARAM_MODE]
                        changed_parameter[_set_request_for_parameter(PARAM_MODE)][
                            _get_request_for_parameter(PARAM_MODE)] = True

                if PARAM_DHW_SET_TEMPERATURE in self._set_param:
                    if set_data["NewValue"]["dhwTemp"]["value"] == self._set_param[PARAM_DHW_SET_TEMPERATURE]:
                        if self._set_time_start[_set_request_for_parameter(PARAM_DHW_SET_TEMPERATURE)] < \
                                self._get_time_end[_get_request_for_parameter(PARAM_DHW_SET_TEMPERATURE)] and \
                                self._get_zero_temperature[PARAM_DHW_SET_TEMPERATURE] == 0:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_SET_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            changed_parameter[_set_request_for_parameter(PARAM_DHW_SET_TEMPERATURE)][
                                _get_request_for_parameter(PARAM_DHW_SET_TEMPERATURE)] = True
                    else:
                        set_data["NewValue"]["dhwTemp"]["value"] = self._set_param[PARAM_DHW_SET_TEMPERATURE]
                        changed_parameter[_set_request_for_parameter(PARAM_DHW_SET_TEMPERATURE)][
                            _get_request_for_parameter(PARAM_DHW_SET_TEMPERATURE)] = True

                if PARAM_DHW_COMFORT_TEMPERATURE in self._set_param:
                    if dhw_temp[PARAM_DHW_COMFORT_TEMPERATURE] == self._set_param[PARAM_DHW_COMFORT_TEMPERATURE]:
                        if self._set_time_start[_set_request_for_parameter(PARAM_DHW_COMFORT_TEMPERATURE)] < \
                                dhw_temp_time[PARAM_DHW_COMFORT_TEMPERATURE]:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_COMFORT_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            param_data = {
                                "id": ARISTON_DHW_TIME_PROG_COMFORT,
                                "newValue": self._set_param[PARAM_DHW_COMFORT_TEMPERATURE],
                                "oldValue": set_data["NewValue"]["dhwTimeProgComfortTemp"]["value"]}
                            set_param_data.append(param_data)
                            changed_parameter[_set_request_for_parameter(PARAM_DHW_COMFORT_TEMPERATURE)][
                                _get_request_for_parameter(PARAM_DHW_COMFORT_TEMPERATURE)] = True
                    else:
                        param_data = {
                            "id": ARISTON_DHW_TIME_PROG_COMFORT,
                            "newValue": self._set_param[PARAM_DHW_COMFORT_TEMPERATURE],
                            "oldValue": set_data["NewValue"]["dhwTimeProgComfortTemp"]["value"]}
                        set_param_data.append(param_data)
                        changed_parameter[_set_request_for_parameter(PARAM_DHW_COMFORT_TEMPERATURE)][
                            _get_request_for_parameter(PARAM_DHW_COMFORT_TEMPERATURE)] = True

                if PARAM_DHW_ECONOMY_TEMPERATURE in self._set_param:
                    if dhw_temp[PARAM_DHW_ECONOMY_TEMPERATURE] == self._set_param[PARAM_DHW_ECONOMY_TEMPERATURE]:
                        if self._set_time_start[_set_request_for_parameter(PARAM_DHW_ECONOMY_TEMPERATURE)] < \
                                dhw_temp_time[PARAM_DHW_ECONOMY_TEMPERATURE]:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_ECONOMY_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            param_data = {
                                "id": ARISTON_DHW_TIME_PROG_ECONOMY,
                                "newValue": self._set_param[PARAM_DHW_ECONOMY_TEMPERATURE],
                                "oldValue": set_data["NewValue"]["dhwTimeProgEconomyTemp"]["value"]}
                            set_param_data.append(param_data)
                            changed_parameter[_set_request_for_parameter(PARAM_DHW_ECONOMY_TEMPERATURE)][
                                _get_request_for_parameter(PARAM_DHW_ECONOMY_TEMPERATURE)] = True
                    else:
                        param_data = {
                            "id": ARISTON_DHW_TIME_PROG_ECONOMY,
                            "newValue": self._set_param[PARAM_DHW_ECONOMY_TEMPERATURE],
                            "oldValue": set_data["NewValue"]["dhwTimeProgEconomyTemp"]["value"]}
                        set_param_data.append(param_data)
                        changed_parameter[_set_request_for_parameter(PARAM_DHW_ECONOMY_TEMPERATURE)][
                            _get_request_for_parameter(PARAM_DHW_ECONOMY_TEMPERATURE)] = True

                if PARAM_DHW_COMFORT_FUNCTION in self._set_param:
                    try:
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_DHW_COMFORT_FUNCTION:
                                if param_item["value"] == self._set_param[PARAM_DHW_COMFORT_FUNCTION]:
                                    if self._set_time_start[_set_request_for_parameter(PARAM_DHW_COMFORT_FUNCTION)] < \
                                            self._get_time_end[_get_request_for_parameter(PARAM_DHW_COMFORT_FUNCTION)]:
                                        # value should be up to date and match to remove from setting
                                        del self._set_param[PARAM_DHW_COMFORT_FUNCTION]
                                    else:
                                        # assume data was not yet changed
                                        param_data = {
                                            "id": ARISTON_DHW_COMFORT_FUNCTION,
                                            "newValue": self._set_param[PARAM_DHW_COMFORT_FUNCTION],
                                            "oldValue": param_item["value"]}
                                        set_param_data.append(param_data)
                                        changed_parameter[_set_request_for_parameter(PARAM_DHW_COMFORT_FUNCTION)][
                                            _get_request_for_parameter(PARAM_DHW_COMFORT_FUNCTION)] = True
                                    break
                                else:
                                    param_data = {
                                        "id": ARISTON_DHW_COMFORT_FUNCTION,
                                        "newValue": self._set_param[PARAM_DHW_COMFORT_FUNCTION],
                                        "oldValue": param_item["value"]}
                                    set_param_data.append(param_data)
                                    changed_parameter[_set_request_for_parameter(PARAM_DHW_COMFORT_FUNCTION)][
                                        _get_request_for_parameter(PARAM_DHW_COMFORT_FUNCTION)] = True
                                    break
                    except:
                        changed_parameter[_set_request_for_parameter(PARAM_DHW_COMFORT_FUNCTION)][
                            _get_request_for_parameter(PARAM_DHW_COMFORT_FUNCTION)] = True
                        pass

                if PARAM_INTERNET_TIME in self._set_param:
                    try:
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_INTERNET_TIME:
                                if param_item["value"] == self._set_param[PARAM_INTERNET_TIME]:
                                    if self._set_time_start[_set_request_for_parameter(PARAM_INTERNET_TIME)] < \
                                            self._get_time_end[_get_request_for_parameter(PARAM_INTERNET_TIME)]:
                                        # value should be up to date and match to remove from setting
                                        del self._set_param[PARAM_INTERNET_TIME]
                                    else:
                                        # assume data was not yet changed
                                        param_data = {
                                            "id": ARISTON_INTERNET_TIME,
                                            "newValue": self._set_param[PARAM_INTERNET_TIME],
                                            "oldValue": param_item["value"]}
                                        set_param_data.append(param_data)
                                        changed_parameter[_set_request_for_parameter(PARAM_INTERNET_TIME)][
                                            _get_request_for_parameter(PARAM_INTERNET_TIME)] = True
                                    break
                                else:
                                    param_data = {
                                        "id": ARISTON_INTERNET_TIME,
                                        "newValue": self._set_param[PARAM_INTERNET_TIME],
                                        "oldValue": param_item["value"]}
                                    set_param_data.append(param_data)
                                    changed_parameter[_set_request_for_parameter(PARAM_INTERNET_TIME)][
                                        _get_request_for_parameter(PARAM_INTERNET_TIME)] = True
                                    break
                    except:
                        changed_parameter[_set_request_for_parameter(PARAM_INTERNET_TIME)][
                            _get_request_for_parameter(PARAM_INTERNET_TIME)] = True
                        pass

                if PARAM_INTERNET_WEATHER in self._set_param:
                    try:
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_INTERNET_WEATHER:
                                if param_item["value"] == self._set_param[PARAM_INTERNET_WEATHER]:
                                    if self._set_time_start[_set_request_for_parameter(PARAM_INTERNET_WEATHER)] < \
                                            self._get_time_end[_get_request_for_parameter(PARAM_INTERNET_WEATHER)]:
                                        # value should be up to date and match to remove from setting
                                        del self._set_param[PARAM_INTERNET_WEATHER]
                                    else:
                                        # assume data was not yet changed
                                        param_data = {
                                            "id": ARISTON_INTERNET_WEATHER,
                                            "newValue": self._set_param[PARAM_INTERNET_WEATHER],
                                            "oldValue": param_item["value"]}
                                        set_param_data.append(param_data)
                                        changed_parameter[_set_request_for_parameter(PARAM_INTERNET_WEATHER)][
                                            _get_request_for_parameter(PARAM_INTERNET_WEATHER)] = True
                                    break
                                else:
                                    param_data = {
                                        "id": ARISTON_INTERNET_WEATHER,
                                        "newValue": self._set_param[PARAM_INTERNET_WEATHER],
                                        "oldValue": param_item["value"]}
                                    set_param_data.append(param_data)
                                    changed_parameter[_set_request_for_parameter(PARAM_INTERNET_WEATHER)][
                                        _get_request_for_parameter(PARAM_INTERNET_WEATHER)] = True
                                    break
                    except:
                        changed_parameter[_set_request_for_parameter(PARAM_INTERNET_WEATHER)][
                            _get_request_for_parameter(PARAM_INTERNET_WEATHER)] = True
                        pass

                if PARAM_THERMAL_CLEANSE_CYCLE in self._set_param:
                    try:
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_THERMAL_CLEANSE_CYCLE:
                                if param_item["value"] == self._set_param[PARAM_THERMAL_CLEANSE_CYCLE]:
                                    if self._set_time_start[_set_request_for_parameter(PARAM_THERMAL_CLEANSE_CYCLE)] < \
                                            self._get_time_end[
                                                _get_request_for_parameter(PARAM_THERMAL_CLEANSE_CYCLE)]:
                                        # value should be up to date and match to remove from setting
                                        del self._set_param[PARAM_THERMAL_CLEANSE_CYCLE]
                                    else:
                                        # assume data was not yet changed
                                        param_data = {
                                            "id": ARISTON_THERMAL_CLEANSE_CYCLE,
                                            "newValue": self._set_param[PARAM_THERMAL_CLEANSE_CYCLE],
                                            "oldValue": param_item["value"]}
                                        set_param_data.append(param_data)
                                        changed_parameter[_set_request_for_parameter(PARAM_THERMAL_CLEANSE_CYCLE)][
                                            _get_request_for_parameter(PARAM_THERMAL_CLEANSE_CYCLE)] = True
                                    break
                                else:
                                    param_data = {
                                        "id": ARISTON_THERMAL_CLEANSE_CYCLE,
                                        "newValue": self._set_param[PARAM_THERMAL_CLEANSE_CYCLE],
                                        "oldValue": param_item["value"]}
                                    set_param_data.append(param_data)
                                    changed_parameter[_set_request_for_parameter(PARAM_THERMAL_CLEANSE_CYCLE)][
                                        _get_request_for_parameter(PARAM_THERMAL_CLEANSE_CYCLE)] = True
                                    break
                    except:
                        changed_parameter[_set_request_for_parameter(PARAM_THERMAL_CLEANSE_CYCLE)][
                            _get_request_for_parameter(PARAM_THERMAL_CLEANSE_CYCLE)] = True
                        pass

                if PARAM_THERMAL_CLEANSE_FUNCTION in self._set_param:
                    try:
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_THERMAL_CLEANSE_FUNCTION:
                                if param_item["value"] == self._set_param[PARAM_THERMAL_CLEANSE_FUNCTION]:
                                    if self._set_time_start[
                                        _set_request_for_parameter(PARAM_THERMAL_CLEANSE_FUNCTION)] < \
                                            self._get_time_end[
                                                _get_request_for_parameter(PARAM_THERMAL_CLEANSE_FUNCTION)]:
                                        # value should be up to date and match to remove from setting
                                        del self._set_param[PARAM_THERMAL_CLEANSE_FUNCTION]
                                    else:
                                        # assume data was not yet changed
                                        param_data = {
                                            "id": ARISTON_THERMAL_CLEANSE_FUNCTION,
                                            "newValue": self._set_param[PARAM_THERMAL_CLEANSE_FUNCTION],
                                            "oldValue": param_item["value"]}
                                        set_param_data.append(param_data)
                                        changed_parameter[_set_request_for_parameter(PARAM_THERMAL_CLEANSE_FUNCTION)][
                                            _get_request_for_parameter(PARAM_THERMAL_CLEANSE_FUNCTION)] = True
                                    break
                                else:
                                    param_data = {
                                        "id": ARISTON_THERMAL_CLEANSE_FUNCTION,
                                        "newValue": self._set_param[PARAM_THERMAL_CLEANSE_FUNCTION],
                                        "oldValue": param_item["value"]}
                                    set_param_data.append(param_data)
                                    changed_parameter[_set_request_for_parameter(PARAM_THERMAL_CLEANSE_FUNCTION)][
                                        _get_request_for_parameter(PARAM_THERMAL_CLEANSE_FUNCTION)] = True
                                    break
                    except:
                        changed_parameter[_set_request_for_parameter(PARAM_THERMAL_CLEANSE_FUNCTION)][
                            _get_request_for_parameter(PARAM_THERMAL_CLEANSE_FUNCTION)] = True
                        pass

                if PARAM_CH_AUTO_FUNCTION in self._set_param:
                    try:
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_CH_AUTO_FUNCTION:
                                if param_item["value"] == self._set_param[PARAM_CH_AUTO_FUNCTION]:
                                    if self._set_time_start[_set_request_for_parameter(PARAM_CH_AUTO_FUNCTION)] < \
                                            self._get_time_end[_get_request_for_parameter(PARAM_CH_AUTO_FUNCTION)]:
                                        # value should be up to date and match to remove from setting
                                        del self._set_param[PARAM_CH_AUTO_FUNCTION]
                                    else:
                                        # assume data was not yet changed
                                        param_data = {
                                            "id": ARISTON_CH_AUTO_FUNCTION,
                                            "newValue": self._set_param[PARAM_CH_AUTO_FUNCTION],
                                            "oldValue": param_item["value"]}
                                        set_param_data.append(param_data)
                                        changed_parameter[_set_request_for_parameter(PARAM_CH_AUTO_FUNCTION)][
                                            _get_request_for_parameter(PARAM_CH_AUTO_FUNCTION)] = True
                                    break
                                else:
                                    param_data = {
                                        "id": ARISTON_CH_AUTO_FUNCTION,
                                        "newValue": self._set_param[PARAM_CH_AUTO_FUNCTION],
                                        "oldValue": param_item["value"]}
                                    set_param_data.append(param_data)
                                    changed_parameter[_set_request_for_parameter(PARAM_CH_AUTO_FUNCTION)][
                                        _get_request_for_parameter(PARAM_CH_AUTO_FUNCTION)] = True
                                    break
                    except:
                        changed_parameter[_set_request_for_parameter(PARAM_CH_AUTO_FUNCTION)][
                            _get_request_for_parameter(PARAM_CH_AUTO_FUNCTION)] = True
                        pass

                if PARAM_CH_SET_TEMPERATURE in self._set_param:
                    if set_data["NewValue"]["zone"]["comfortTemp"]["value"] == self._set_param[
                        PARAM_CH_SET_TEMPERATURE]:
                        if self._set_time_start[_set_request_for_parameter(PARAM_CH_SET_TEMPERATURE)] < \
                                self._get_time_end[_get_request_for_parameter(PARAM_CH_SET_TEMPERATURE)] and \
                                self._get_zero_temperature[PARAM_CH_SET_TEMPERATURE] == 0:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_CH_SET_TEMPERATURE]
                        else:
                            # assume data was not yet changed
                            changed_parameter[_set_request_for_parameter(PARAM_CH_SET_TEMPERATURE)][
                                _get_request_for_parameter(PARAM_CH_SET_TEMPERATURE)] = True
                    else:
                        set_data["NewValue"]["zone"]["comfortTemp"]["value"] = self._set_param[PARAM_CH_SET_TEMPERATURE]
                        changed_parameter[_set_request_for_parameter(PARAM_CH_SET_TEMPERATURE)][
                            _get_request_for_parameter(PARAM_CH_SET_TEMPERATURE)] = True

                if PARAM_CH_COMFORT_TEMPERATURE in self._set_param:
                    try:
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_CH_COMFORT_TEMP:
                                if param_item["value"] == self._set_param[PARAM_CH_COMFORT_TEMPERATURE]:
                                    if self._set_time_start[_set_request_for_parameter(PARAM_CH_COMFORT_TEMPERATURE)] < \
                                            self._get_time_end[
                                                _get_request_for_parameter(PARAM_CH_COMFORT_TEMPERATURE)]:
                                        # value should be up to date and match to remove from setting
                                        del self._set_param[PARAM_CH_COMFORT_TEMPERATURE]
                                    else:
                                        # assume data was not yet changed
                                        param_data = {
                                            "id": ARISTON_CH_COMFORT_TEMP,
                                            "newValue": self._set_param[PARAM_CH_COMFORT_TEMPERATURE],
                                            "oldValue": param_item["value"]}
                                        set_param_data.append(param_data)
                                        changed_parameter[_set_request_for_parameter(PARAM_CH_COMFORT_TEMPERATURE)][
                                            _get_request_for_parameter(PARAM_CH_COMFORT_TEMPERATURE)] = True
                                    break
                                else:
                                    param_data = {
                                        "id": ARISTON_CH_COMFORT_TEMP,
                                        "newValue": self._set_param[PARAM_CH_COMFORT_TEMPERATURE],
                                        "oldValue": param_item["value"]}
                                    set_param_data.append(param_data)
                                    changed_parameter[_set_request_for_parameter(PARAM_CH_COMFORT_TEMPERATURE)][
                                        _get_request_for_parameter(PARAM_CH_COMFORT_TEMPERATURE)] = True
                                    break
                    except:
                        changed_parameter[_set_request_for_parameter(PARAM_CH_COMFORT_TEMPERATURE)][
                            _get_request_for_parameter(PARAM_CH_COMFORT_TEMPERATURE)] = True
                        pass

                if PARAM_CH_ECONOMY_TEMPERATURE in self._set_param:
                    try:
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_CH_ECONOMY_TEMP:
                                if param_item["value"] == self._set_param[PARAM_CH_ECONOMY_TEMPERATURE]:
                                    if self._set_time_start[_set_request_for_parameter(PARAM_CH_ECONOMY_TEMPERATURE)] < \
                                            self._get_time_end[
                                                _get_request_for_parameter(PARAM_CH_ECONOMY_TEMPERATURE)]:
                                        # value should be up to date and match to remove from setting
                                        del self._set_param[PARAM_CH_ECONOMY_TEMPERATURE]
                                    else:
                                        # assume data was not yet changed
                                        param_data = {
                                            "id": ARISTON_CH_ECONOMY_TEMP,
                                            "newValue": self._set_param[PARAM_CH_ECONOMY_TEMPERATURE],
                                            "oldValue": param_item["value"]}
                                        set_param_data.append(param_data)
                                        changed_parameter[_set_request_for_parameter(PARAM_CH_ECONOMY_TEMPERATURE)][
                                            _get_request_for_parameter(PARAM_CH_ECONOMY_TEMPERATURE)] = True
                                    break
                                else:
                                    param_data = {
                                        "id": ARISTON_CH_ECONOMY_TEMP,
                                        "newValue": self._set_param[PARAM_CH_ECONOMY_TEMPERATURE],
                                        "oldValue": param_item["value"]}
                                    set_param_data.append(param_data)
                                    changed_parameter[_set_request_for_parameter(PARAM_CH_ECONOMY_TEMPERATURE)][
                                        _get_request_for_parameter(PARAM_CH_ECONOMY_TEMPERATURE)] = True
                                    break
                    except:
                        changed_parameter[_set_request_for_parameter(PARAM_CH_ECONOMY_TEMPERATURE)][
                            _get_request_for_parameter(PARAM_CH_ECONOMY_TEMPERATURE)] = True
                        pass

                if PARAM_CH_MODE in self._set_param:
                    if set_data["NewValue"]["zone"]["mode"]["value"] == self._set_param[PARAM_CH_MODE]:
                        if self._set_time_start[_set_request_for_parameter(PARAM_CH_MODE)] < self._get_time_end[
                            _get_request_for_parameter(PARAM_CH_MODE)]:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_CH_MODE]
                        else:
                            # assume data was not yet changed
                            changed_parameter[_set_request_for_parameter(PARAM_CH_MODE)][
                                _get_request_for_parameter(PARAM_CH_MODE)] = True
                    else:
                        set_data["NewValue"]["zone"]["mode"]["value"] = self._set_param[PARAM_CH_MODE]
                        changed_parameter[_set_request_for_parameter(PARAM_CH_MODE)][
                            _get_request_for_parameter(PARAM_CH_MODE)] = True

                if PARAM_DHW_MODE in self._set_param:
                    if set_data["NewValue"]["dhwMode"] == self._set_param[PARAM_DHW_MODE]:
                        if self._set_time_start[_set_request_for_parameter(PARAM_DHW_MODE)] < self._get_time_end[
                            _get_request_for_parameter(PARAM_DHW_MODE)]:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_DHW_MODE]
                        else:
                            # assume data was not yet changed
                            changed_parameter[_set_request_for_parameter(PARAM_DHW_MODE)][
                                _get_request_for_parameter(PARAM_DHW_MODE)] = True
                    else:
                        set_data["NewValue"]["dhwMode"] = self._set_param[PARAM_DHW_MODE]
                        changed_parameter[_set_request_for_parameter(PARAM_DHW_MODE)][
                            _get_request_for_parameter(PARAM_DHW_MODE)] = True

                if PARAM_UNITS in self._set_param:
                    if set_units_data["measurementSystem"] == self._set_param[PARAM_UNITS]:
                        if self._set_time_start[_set_request_for_parameter(PARAM_UNITS)] < self._get_time_end[
                            _get_request_for_parameter(PARAM_UNITS)]:
                            # value should be up to date and match to remove from setting
                            del self._set_param[PARAM_UNITS]
                        else:
                            # assume data was not yet changed
                            changed_parameter[_set_request_for_parameter(PARAM_UNITS)][
                                _get_request_for_parameter(PARAM_UNITS)] = True
                    else:
                        set_units_data["measurementSystem"] = self._set_param[PARAM_UNITS]
                        changed_parameter[_set_request_for_parameter(PARAM_UNITS)][
                            _get_request_for_parameter(PARAM_UNITS)] = True

                for request_item in self._set_param_group:
                    self._set_param_group[request_item] = False

                for key, value in changed_parameter.items():
                    if value != {} and self._set_retry[key] < self._set_max_retries:
                        if not self._set_scheduled:
                            # retry again after enough time
                            if self._timer_between_set == VAL_NORMAL:
                                retry_in = timedelta(seconds=self._timer_between_param_delay + HTTP_TIMER_SET_WAIT)
                            else:
                                retry_in = timedelta(
                                    seconds=self._timer_between_param_delay * HTTP_DELAY_MULTIPLY + HTTP_TIMER_SET_WAIT)
                            track_point_in_time(self._hass, self._preparing_setting_http_data,
                                                dt_util.now() + retry_in)
                            self._set_retry[key] += 1
                            self._set_scheduled = True
                    elif value != {} and self._set_retry[key] == self._set_max_retries:
                        # last retry, we keep changed parameter but do not schedule anything
                        self._set_retry[key] += 1
                    else:
                        changed_parameter[key] = {}

                try:
                    for parameter, value in self._set_param.items():
                        if _get_request_for_parameter(parameter) not in changed_parameter[
                            _set_request_for_parameter(parameter)]:
                            del self._set_param[parameter]
                except:
                    pass

                # show data as changed in case we were able to read data in between requests
                self._set_visible_data()

                if changed_parameter[REQUEST_SET_MAIN] != {}:
                    try:
                        self._setting_http_data(set_data, REQUEST_SET_MAIN)
                    except:
                        pass

                elif changed_parameter[REQUEST_SET_OTHER] != {}:

                    try:
                        if set_param_data != []:
                            self._setting_http_data(set_param_data, REQUEST_SET_OTHER)
                        else:
                            _LOGGER.warning('%s No valid data to set parameters', self)
                            raise CommError(error)
                    except:
                        pass

                elif changed_parameter[REQUEST_SET_UNITS] != {}:
                    try:
                        self._setting_http_data(set_units_data, REQUEST_SET_UNITS)
                    except:
                        pass

                else:
                    _LOGGER.debug('%s Same data was used', self)

                for key, value in changed_parameter.items():
                    if value != {}:
                        for request_item in value:
                            self._set_param_group[request_item] = True

                if not self._set_scheduled:
                    # no more retries or no changes, no need to keep any changed data
                    self._set_param = {}

                if self._store_file:
                    with open('/config/data_' + self._name + '_all_set_get.json', 'w') as ariston_fetched:
                        json.dump(self._set_param_group, ariston_fetched)
                    with open('/config/data_' + self._name + '_all_set.json', 'w') as ariston_fetched:
                        json.dump(self._set_param, ariston_fetched)

            else:
                # api is down
                if not self._set_scheduled:
                    if self._set_retry[REQUEST_SET_MAIN] < self._set_max_retries:
                        # retry again after enough time to fetch data twice
                        if self._timer_between_set == VAL_NORMAL:
                            retry_in = timedelta(
                                seconds=self._timer_between_param_delay + HTTP_TIMER_SET_WAIT)
                        else:
                            retry_in = timedelta(
                                seconds=self._timer_between_param_delay * HTTP_DELAY_MULTIPLY + HTTP_TIMER_SET_WAIT)
                        track_point_in_time(self._hass, self._preparing_setting_http_data,
                                            dt_util.now() + retry_in)
                        self._set_retry[REQUEST_SET_MAIN] += 1
                        self._set_scheduled = True
                    else:
                        # no more retries, no need to keep changed data
                        self._set_param = {}
                        for request_item in self._set_param_group:
                            self._set_param_group[request_item] = False

                        if self._store_file:
                            with open('/config/data_' + self._name + '_all_set_get.json', 'w') as ariston_fetched:
                                json.dump(self._set_param_group, ariston_fetched)
                            with open('/config/data_' + self._name + '_all_set.json', 'w') as ariston_fetched:
                                json.dump(self._set_param, ariston_fetched)

                        _LOGGER.warning("%s No stable connection to set the data", self)
                        raise CommError

    def set_http_data(self, parameter_list={}):
        """Set Ariston data over http after data verification"""
        if self._ariston_data_actual != {}:
            with self._data_lock:

                # check mode and set it
                if PARAM_MODE in parameter_list:
                    wanted_mode = str(parameter_list[PARAM_MODE]).lower()
                    try:
                        if wanted_mode in MODE_TO_VALUE and MODE_TO_VALUE[wanted_mode] in self._ariston_data_actual[
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
                        dhw_temp_min = self._ariston_data_actual["dhwTimeProgEconomyTemp"]["min"]
                        dhw_temp_max = self._ariston_data_actual["dhwTimeProgEconomyTemp"]["max"]
                        if temperature >= dhw_temp_min and temperature <= dhw_temp_max:
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
                        dhw_temp_min = max(self._ariston_data_actual["dhwTemp"]["min"],
                                           self._ariston_data_actual["dhwTimeProgComfortTemp"]["min"])
                        dhw_temp_max = max(self._ariston_data_actual["dhwTemp"]["max"],
                                           self._ariston_data_actual["dhwTimeProgComfortTemp"]["max"])
                        if temperature >= dhw_temp_min and temperature <= dhw_temp_max:
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
                        if temperature >= self._ariston_data_actual["dhwTemp"]["min"] and temperature <= \
                                self._ariston_data_actual["dhwTemp"]["max"]:
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
                        if temperature >= self._ariston_data_actual["zone"]["comfortTemp"]["min"] and temperature <= \
                                self._ariston_data_actual["zone"]["comfortTemp"]["max"]:
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
                        if temperature >= self._ariston_data_actual["zone"]["comfortTemp"]["min"] and temperature <= \
                                self._ariston_data_actual["zone"]["comfortTemp"]["max"]:
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
                        if temperature >= self._ariston_data_actual["zone"]["comfortTemp"]["min"] and temperature <= \
                                self._ariston_data_actual["zone"]["comfortTemp"]["max"]:
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
                                self._ariston_data_actual["zone"]["mode"]["allowedOptions"]:
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

                # check cleanse cycle
                if PARAM_THERMAL_CLEANSE_CYCLE in parameter_list:
                    wanted_cleanse_cycle = str(parameter_list[PARAM_THERMAL_CLEANSE_CYCLE]).lower()
                    try:
                        item_present = False
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_THERMAL_CLEANSE_CYCLE:
                                cycle_min = param_item["min"]
                                cycle_max = param_item["max"]
                                if wanted_cleanse_cycle <= cycle_max and wanted_cleanse_cycle >= cycle_min:
                                    self._set_param[PARAM_THERMAL_CLEANSE_CYCLE] = wanted_cleanse_cycle
                                    item_present = True
                                    _LOGGER.info('%s New Thermal Cleanse Cycle is %s', self, wanted_cleanse_cycle)
                                else:
                                    _LOGGER.warning('%s Unknown or unsupported Thermal Cleanse Cycle: %s', self,
                                                    wanted_cleanse_cycle)
                                break
                        if not item_present:
                            _LOGGER.warning('%s Can not set Thermal Cleanse Cycle: %s', self, wanted_cleanse_cycle)
                    except:
                        _LOGGER.warning('%s Unknown or unsupported Thermal Cleanse Cycle or key error: %s', self,
                                        wanted_cleanse_cycle)
                        pass

                # check cleanse function
                if PARAM_THERMAL_CLEANSE_FUNCTION in parameter_list:
                    wanted_cleanse_function = str(parameter_list[PARAM_THERMAL_CLEANSE_FUNCTION]).lower()
                    try:
                        item_present = False
                        for param_item in self._ariston_other_data_actual:
                            if param_item["id"] == ARISTON_THERMAL_CLEANSE_FUNCTION:
                                if wanted_cleanse_function in PARAM_STRING_TO_VALUE:
                                    self._set_param[PARAM_THERMAL_CLEANSE_FUNCTION] = PARAM_STRING_TO_VALUE[
                                        wanted_cleanse_function]
                                    item_present = True
                                    _LOGGER.info('%s New Thermal Cleanse Function is %s', self, wanted_cleanse_function)
                                else:
                                    _LOGGER.warning('%s Unknown or unsupported Thermal Cleanse Function: %s', self,
                                                    wanted_cleanse_function)
                                break
                        if not item_present:
                            _LOGGER.warning('%s Can not set Thermal Cleanse Function: %s', self,
                                            wanted_cleanse_function)
                    except:
                        _LOGGER.warning('%s Unknown or unsupported Thermal Cleanse Function or key error: %s', self,
                                        wanted_cleanse_function)
                        pass

                # check CH auto function
                if PARAM_CH_AUTO_FUNCTION in parameter_list:
                    wanted_ch_auto = str(parameter_list[PARAM_CH_AUTO_FUNCTION]).lower()
                    try:
                        if wanted_ch_auto in PARAM_STRING_TO_VALUE:
                            self._set_param[PARAM_CH_AUTO_FUNCTION] = PARAM_STRING_TO_VALUE[wanted_ch_auto]
                            _LOGGER.info('%s New Internet weather is %s', self, wanted_ch_auto)
                        else:
                            _LOGGER.warning('%s Unknown or unsupported Internet weather: %s', self,
                                            wanted_ch_auto)
                    except:
                        _LOGGER.warning('%s Unknown or unsupported Internet weather or key error: %s', self,
                                        wanted_ch_auto)
                        pass

                # check units of measurement
                if PARAM_UNITS in parameter_list:
                    wanted_units = str(parameter_list[PARAM_UNITS]).lower()
                    try:
                        if wanted_units in UNIT_TO_VALUE:
                            self._set_param[PARAM_UNITS] = UNIT_TO_VALUE[wanted_units]
                            _LOGGER.info('%s New units of measurement is %s', self, wanted_units)
                        else:
                            _LOGGER.warning('%s Unknown or unsupported units of measurement: %s', self, wanted_units)
                    except:
                        _LOGGER.warning('%s Unknown or unsupported units of measurement or key error: %s', self,
                                        wanted_units)
                        pass

                # show data as changed
                self._set_visible_data()

                self._set_new_data_pending = True
                # set after short delay to not affect switch or climate or water_heater
                retry_time = dt_util.now() + timedelta(seconds=1)
                track_point_in_time(self._hass, self._preparing_setting_http_data, retry_time)

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
        units = device[CONF_UNITS]
        polling = device[CONF_POLLING_RATE]
        binary_sensors = device.get(CONF_BINARY_SENSORS)
        sensors = device.get(CONF_SENSORS)
        switches = device.get(CONF_SWITCHES)
        api_valid = False
        try:
            api = AristonChecker(hass, device=device, name=name, username=username, password=password, retries=retries,
                                 store_file=store_file, units=units, polling=polling, sensors=sensors,
                                 binary_sensors=binary_sensors, switches=switches)
            api_list.append(api)
            api_valid = True
            # start api execution by logging in
            api._login_session()
        except LoginError as ex:
            _LOGGER.error("Login error for %s: %s", name, ex)
            pass
        except AristonError as ex:
            _LOGGER.error("Communication error for %s: %s", name, ex)
            pass
        except:
            _LOGGER.error("Unexpected error for %s:", name)
            pass
        if api_valid:
            # proceed with data fetching
            track_point_in_time(api._hass, api._queue_get_data, dt_util.now() + timedelta(seconds=2))
        # load all devices
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
        """Handle the service call to set the data."""
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
                            parameter_list[PARAM_CH_COMFORT_TEMPERATURE] = data

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

                        data = call.data.get(PARAM_CH_AUTO_FUNCTION, "")
                        if data != "":
                            parameter_list[PARAM_CH_AUTO_FUNCTION] = data

                        data = call.data.get(PARAM_UNITS, "")
                        if data != "":
                            parameter_list[PARAM_UNITS] = data

                        data = call.data.get(PARAM_THERMAL_CLEANSE_CYCLE, "")
                        if data != "":
                            parameter_list[PARAM_THERMAL_CLEANSE_CYCLE] = data

                        data = call.data.get(PARAM_THERMAL_CLEANSE_FUNCTION, "")
                        if data != "":
                            parameter_list[PARAM_THERMAL_CLEANSE_FUNCTION] = data

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

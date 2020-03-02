"""Constants for Ariston component."""
DOMAIN = "ariston"
DATA_ARISTON = DOMAIN
DEVICES = "devices"
SERVICE_SET_DATA = "set_data"
SERVICE_UPDATE = "update"
CLIMATES = "climates"
WATER_HEATERS = "water_heaters"

# sensors
PARAM_CH_ACCOUNT_GAS = "ch_account_gas"
PARAM_CH_ANTIFREEZE_TEMPERATURE = "ch_antifreeze_temperature"
PARAM_CH_MODE = "ch_mode"
PARAM_CH_SET_TEMPERATURE = "ch_set_temperature"
PARAM_CH_PROGRAM_COMFORT_TEMPERATURE = "ch_program_comfort_temperature"
PARAM_CH_PROGRAM_ECONOMY_TEMPERATURE = "ch_program_economy_temperature"
PARAM_CH_DETECTED_TEMPERATURE = "ch_detected_temperature"
PARAM_CH_PROGRAM = "ch_program"
PARAM_ERRORS = "errors"
PARAM_DHW_ACCOUNT_GAS = "dhw_account_gas"
PARAM_DHW_COMFORT_FUNCTION = "dhw_comfort_function"
PARAM_DHW_MODE = "dhw_mode"
PARAM_DHW_SET_TEMPERATURE = "dhw_set_temperature"
PARAM_DHW_STORAGE_TEMPERATURE = "dhw_storage_temperature"
PARAM_DHW_PROGRAM_COMFORT_TEMPERATURE = "dhw_program_comfort_temperature"
PARAM_DHW_PROGRAM_ECONOMY_TEMPERATURE = "dhw_program_economy_temperature"
PARAM_HEATING_LAST_24H = "heating_last_24h"
PARAM_HEATING_LAST_7d = "heating_last_7d"
PARAM_HEATING_LAST_30d = "heating_last_30d"
PARAM_HEATING_LAST_365d = "heating_last_365d"
PARAM_MODE = "mode"
PARAM_OUTSIDE_TEMPERATURE = "outside_temperature"
PARAM_SIGNAL_STRENGTH = "signal_strength"
PARAM_WATER_LAST_24H = "water_last_24h"
PARAM_WATER_LAST_7D = "water_last_7d"
PARAM_WATER_LAST_30D = "water_last_30d"
PARAM_WATER_LAST_365D = "water_last_365d"

# binary sensors
PARAM_FLAME = "flame"
PARAM_HEAT_PUMP = "heat_pump"
PARAM_HOLIDAY_MODE = "holiday_mode"
PARAM_INTERNET_TIME = "internet_time"
PARAM_INTERNET_WEATHER = "internet_weather"
PARAM_ONLINE = "online"
PARAM_CHANGING_DATA = "changing_data"

ARISTON_DHW_COMFORT_TEMP = "U6_9_0"
ARISTON_DHW_COMFORT_FUNCTION = "U6_9_2"
ARISTON_DHW_TIME_PROG_COMFORT = "U6_9_1_0_0"
ARISTON_DHW_TIME_PROG_ECONOMY = "U6_9_1_0_1"
ARISTON_SIGNAL_STRENGHT = "U6_16_5"
ARISTON_INTERNET_TIME = "U6_16_6"
ARISTON_INTERNET_WEATHER = "U6_16_7"

ARISTON_PARAM_LIST = [
    ARISTON_DHW_COMFORT_TEMP,
    ARISTON_DHW_COMFORT_FUNCTION,
    ARISTON_DHW_TIME_PROG_COMFORT,
    ARISTON_DHW_TIME_PROG_ECONOMY,
    ARISTON_SIGNAL_STRENGHT,
    ARISTON_INTERNET_TIME,
    ARISTON_INTERNET_WEATHER
]

UNKNOWN_TEMP = [0, 3276]
DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

VAL_WINTER = "winter"
VAL_SUMMER = "summer"
VAL_OFF = "off"
VAL_HEATING_ONLY = "heating only"
VAL_SUMMER_MANUAL = "summer manual"
VAL_SUMMER_PROGRAM = "summer program"
VAL_WINTER_MANUAL = "winter manual"
VAL_WINTER_PROGRAM = "winter program"
VAL_MANUAL = "manual"
VAL_PROGRAM = "program"
VAL_LEARNING = "intelligent"
VAL_UNKNOWN = "unknown"
VAL_OFFLINE = "offline"
VAL_HOLIDAY = "holiday"
VAL_UNSUPPORTED = "unsupported"
VAL_AVAILABLE = "available"

VAL_DISABLED = "disabled"
VAL_TIME_BASED = "time based"
VAL_ALWAYS_ACTIVE = "always active"

CONF_HVAC_OFF = "hvac_off"
CONF_POWER_ON = "power_on"
CONF_MAX_RETRIES = "max_retries"
CONF_STORE_CONFIG_FILES = "store_config_files"
CONF_CONTROL_FROM_WATER_HEATER = "control_from_water_heater"
CONF_HVAC_OFF_PRESENT = "hvac_off_present"

MODE_TO_VALUE = {VAL_WINTER: 1, VAL_SUMMER: 0, VAL_OFF: 5, VAL_HEATING_ONLY: 2}
VALUE_TO_MODE = {1: VAL_WINTER, 0: VAL_SUMMER, 5: VAL_OFF, 2: VAL_HEATING_ONLY}
CH_MODE_TO_VALUE = {VAL_MANUAL: 2, VAL_PROGRAM: 3, VAL_LEARNING: 0}
VALUE_TO_CH_MODE = {2: VAL_MANUAL, 3: VAL_PROGRAM, 0: VAL_LEARNING}
DHW_MODE_TO_VALUE = {VAL_MANUAL: 2, VAL_PROGRAM: 1}
VALUE_TO_DHW_MODE = {2: VAL_MANUAL, 1: VAL_PROGRAM, 0: VAL_UNSUPPORTED}
DHW_COMFORT_FUNCT_TO_VALUE = {VAL_DISABLED: 0, VAL_TIME_BASED: 1, VAL_ALWAYS_ACTIVE: 2}
DHW_COMFORT_VALUE_TO_FUNCT = {0: VAL_DISABLED, 1: VAL_TIME_BASED, 2: VAL_ALWAYS_ACTIVE}
PARAM_STRING_TO_VALUE = {"true": 1, "false": 0}
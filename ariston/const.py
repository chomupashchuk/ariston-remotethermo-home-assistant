"""Constants for Ariston component."""
DOMAIN = "ariston"
DATA_ARISTON = DOMAIN
DEVICES = "devices"
SERVICE_SET_DATA = "set_data"
SERVICE_UPDATE = "update"
CLIMATES = "climates"
WATER_HEATERS = "water_heaters"

PARAM_CH_ACCOUNT_GAS = "ch_account_gas"
PARAM_CH_ANTIFREEZE_TEMPERATURE = "ch_antifreeze_temperature"
PARAM_CH_MODE = "ch_mode"
PARAM_CH_SET_TEMPERATURE = "ch_set_temperature"
PARAM_CH_SCHEDULED_COMFORT_TEMPERATURE = "ch_scheduled_comfort_temperature"
PARAM_CH_SCHEDULED_ECONOMY_TEMPERATURE = "ch_scheduled_economy_temperature"
PARAM_CH_DETECTED_TEMPERATURE = "ch_detected_temperature"
PARAM_ERRORS = "errors"
PARAM_DHW_ACCOUNT_GAS = "dhw_account_gas"
PARAM_DHW_FLAME = "dhw_flame"
PARAM_DHW_MODE = "dhw_mode"
PARAM_DHW_SET_TEMPERATURE = "dhw_set_temperature"
PARAM_DHW_STORAGE_TEMPERATURE = "dhw_storage_temperature"
PARAM_DHW_SCHEDULED_COMFORT_TEMPERATURE = "dhw_scheduled_comfort_temperature"
PARAM_DHW_SCHEDULED_ECONOMY_TEMPERATURE = "dhw_scheduled_economy_temperature"
PARAM_FLAME = "flame"
PARAM_HEAT_PUMP = "heat_pump"
PARAM_HOLIDAY_MODE = "holiday_mode"
PARAM_MODE = "mode"
PARAM_ONLINE = "online"
PARAM_OUTSIDE_TEMPERATURE = "outside_temperature"
PARAM_HEATING_LAST_24H = "heating_last_24h"
PARAM_HEATING_LAST_7d = "heating_last_7d"
PARAM_HEATING_LAST_30d = "heating_last_30d"
PARAM_HEATING_LAST_365d = "heating_last_365d"
PARAM_WATER_LAST_24H = "water_last_24h"
PARAM_WATER_LAST_7D = "water_last_7d"
PARAM_WATER_LAST_30D = "water_last_30d"
PARAM_WATER_LAST_365D = "water_last_365d"

UNKNOWN_TEMP = [0, 3276]

VAL_MODE_WINTER = "winter"
VAL_MODE_SUMMER = "summer"
VAL_MODE_OFF = "off"
VAL_MODE_HEATING_ONLY = "heating only"
VAL_MODE_SUMMER_MANUAL = "summer manual"
VAL_MODE_SUMMER_SCHEDULED = "summer scheduled"
VAL_MODE_WINTER_MANUAL = "winter manual"
VAL_MODE_WINTER_SCHEDULED = "winter scheduled"
VAL_CH_MODE_MANUAL = "manual"
VAL_CH_MODE_SCHEDULED = "scheduled"
VAL_CH_MODE_LEARNING = "intelligent"
VAL_UNKNOWN = "unknown"
VAL_OFFLINE = "offline"
VAL_HOLIDAY = "holiday"
VAL_UNSUPPORTED = "unsupported"

CONF_HVAC_OFF = "hvac_off"
CONF_POWER_ON = "power_on"
CONF_MAX_RETRIES = "max_retries"
CONF_STORE_CONFIG_FILES = "store_config_files"

MODE_TO_VALUE = {VAL_MODE_WINTER: 1, VAL_MODE_SUMMER: 0, VAL_MODE_OFF: 5, VAL_MODE_HEATING_ONLY: 2}
VALUE_TO_MODE = {1: VAL_MODE_WINTER, 0: VAL_MODE_SUMMER, 5: VAL_MODE_OFF, 2: VAL_MODE_HEATING_ONLY}
CH_MODE_TO_VALUE = {VAL_CH_MODE_MANUAL: 2, VAL_CH_MODE_SCHEDULED: 3, VAL_CH_MODE_LEARNING: 0}
VALUE_TO_CH_MODE = {2: VAL_CH_MODE_MANUAL, 3: VAL_CH_MODE_SCHEDULED, 0: VAL_CH_MODE_LEARNING}
DHW_MODE_TO_VALUE = {VAL_CH_MODE_MANUAL: 0, VAL_CH_MODE_SCHEDULED: 1}
VALUE_TO_DHW_MODE = {0: VAL_CH_MODE_MANUAL, 1: VAL_CH_MODE_SCHEDULED}

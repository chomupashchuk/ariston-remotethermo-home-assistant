"""Constants for Ariston component."""
DOMAIN = "ariston"
DATA_ARISTON = DOMAIN
DEVICES = "devices"
SERVICE_SET_DATA = "set_data"
SERVICE_UPDATE = "update"
CLIMATES = "climates"
WATER_HEATERS = "water_heaters"

PARAM_CH_ANTIFREEZE_TEMPERATURE = "ch_antifreeze_temperature"
PARAM_CH_MODE = "ch_mode"
PARAM_CH_SET_TEMPERATURE = "ch_set_temperature"
PARAM_DETECTED_TEMPERATURE = "detected_temperature"
PARAM_DHW_SET_TEMPERATURE = "dhw_set_temperature"
PARAM_HOLIDAY_MODE = "holiday_mode"
PARAM_MODE = "mode"
PARAM_ONLINE = "online"
PARAM_FLAME = "flame"

VAL_MODE_WINTER = "winter"
VAL_MODE_SUMMER = "summer"
VAL_MODE_OFF = "off"
VAL_CH_MODE_MANUAL = "manual"
VAL_CH_MODE_SCHEDULED = "scheduled"
VAL_UNKNOWN = "unknown"
VAL_OFFLINE = "offline"
VAL_HOLIDAY = "holiday"

CONF_HVAC_OFF = "hvac_off"
CONF_POWER_ON = "power_on"
CONF_MAX_RETRIES = "max_retries"

MODE_TO_VALUE = {VAL_MODE_WINTER: 1, VAL_MODE_SUMMER: 0, VAL_MODE_OFF: 5}
VALUE_TO_MODE = {1: VAL_MODE_WINTER, 0: VAL_MODE_SUMMER, 5: VAL_MODE_OFF}
CH_MODE_TO_VALUE = {VAL_CH_MODE_MANUAL: 2, VAL_CH_MODE_SCHEDULED: 3}
VALUE_TO_CH_MODE = {2: VAL_CH_MODE_MANUAL, 3: VAL_CH_MODE_SCHEDULED}
# Ariston NET remotethermo integration for Home Assistant
Thin integration is a side project (my first integration) and was tested only with 1 zone climate. It logs in Ariston website and fetches/sets data on that site. Due to interaction with boiler it is time consuming process and thus intergation is relatively slow.
You are free to modify and distribute it, but it is distributed 'as is' with no liability (see license file).

Cimate and Water Heater components have presets to switch between `off`, `summer` and `winter` in order to be able to control boiler from one entity.

## Integration was tested on:
  - Ariston Clas Evo
  - Ariston Genus One with Ariston BCH cylinder

## Integration installation
In `/config` folder create `custom_components` folder and load source files folder `ariston` in it
In `configuration.yaml` include:
```
ariston:
  username: !secret ariston_username
  password: !secret ariston_password
```
All additional attributes are described in **Integration attributes**


## Localizations
Localizations are located in corresponding `.json` file within `.translations` folder.
Localization consists of two main parts:
  - Frontend translation (within corresponding `sensor.__.json` file), which works only with sensors due to functionality limitations. Change of frontend language automatically changes displayed value in frontend.
  - Backend translation (objects within `backend.__.json` file), which forces translated values to be used during components initilization for `climate` (preset) and `water_heater` (operation). Change of language can only be changed in `configuration.yaml` and is applied during Home Assistant start.

**Supported localizations**:
  - `en` - English (default)
  - `uk` - Ukrainian
  - `pl` - Polish

## Custom icons for mode status
Store `icons` folder contents within `\config\www\icons`.

### Integration attributes
  - `username` - **mandatory** user name used in https://www.ariston-net.remotethermo.com
  - `password` - **mandatory** password used in https://www.ariston-net.remotethermo.com
    **! It is recommended for security purposes to not use your common password, just in case !**
  - `name` - friendly name for integration
  - `localization` - localization to be used. See **Localizations**
  - `hvac_off_present` - indicates if `HVAC OFF` shall be present in climate entity. Default value is `false`.
  - `hvac_off` - indicates how to treat `HVAC OFF` action in climate. Options are `off` and `summer`. By default it is `summer`, which means that turning off would keep DHW water heating on (e.g. summer mode). Presets in climate allow switching between `off`, `summer` and `winter`.
  - `power_on` - indicates which mode would be used for `switch.turn_on` action. Options are `summer` and `winter`. By default it is `summer`.
  - `max_retries` - number of retries to set the data in boiler. Retries are made in case of communication issues for example, which take place occasionally. By default the value is '1'.
  - `store_config_files` - `true` or `false` indicating if configuration `json` files to be stored in `/config` folder. Can be used for troubleshooting purposes for example. Default value is `false`.
  - `control_from_water_heater` - if `water_heater` entity will have controling parameters like `summer` or `winter` or `off` as part of operations. Default value is `false`.

#### Switches
  - `power` - turn power off and on (on value is defined by `power_on` attribute).

#### Sensors
  - `ch_account_gas` - gas use summary for CH. Not supported on all models.
  - `ch_antifreeze_temperature` - CH antifreeze temperature.
  - `ch_detected_temperature` - temperature measured by thermostat.
  - `ch_mode` - mode of CH (`manual` or `scheduled` and others).
  - `ch_comfort_temperature` - CH comfort temperature.
  - `ch_economy_temperature` - CH economy temperature.
  - `ch_set_temperature` - set CH temperature.
  - `ch_program` - CH Time Program.
  - `dhw_account_gas` - gas use summary for DHW. Not supported on all models.
  - `dhw_comfort_function` - DHW comfort function.
  - `dhw_mode` - mode of DHW. Not supported on all models.
  - `dhw_comfort_temperature` - DHW storage comfort temperature. Not supported on all models.
  - `dhw_economy_temperature` - DHW storage economy temperature. Not supported on all models.
  - `dhw_set_temperature` - set DHW temperature.
  - `dhw_storage_temperature` - DHW storage temperature. Not supported on all models.
  - `errors` - active errors (no errors to test on)
  - `heating_last_24h` - gas use in last 24 hours. Not supported on all models.
  - `heating_last_30d` - gas use in last 7 days. Not supported on all models.
  - `heating_last_365d` - gas use in last 30 days. Not supported on all models.
  - `heating_last_7d` - gas use in last 365 days. Not supported on all models.
  - `mode` - mode of boiler (`off` or `summer` or `winter` and others).
  - `outside_temperature` - outside temperature. Not supported on all models.
  - `signal_strength` - Wifi signal strength.
  - `water_last_24h` - water use in last 24 hours. Not supported on all models.
  - `water_last_30d` - water use in last 7 days. Not supported on all models.
  - `water_last_365d` - water use in last 30 days. Not supported on all models.
  - `water_last_7d` - water use in last 365 days. Not supported on all models.

#### Binary sensors
  - `changing_data` - if change of data via Home Assistant is ongoing.
  - `flame` - if boiler is heating water (DHW or CH).
  - `heat_pump` - if heating pump is ON. Not supported on all models.
  - `holiday_mode` - if holiday mode switch on via application or site.
  - `internet_time` - if time from the internet is used.
  - `internet_weather` - if weather from the internet is used.
  - `online` - online status.


### Example of configuration.yaml entry
```
ariston:
  username: !secret ariston_user
  password: !secret ariston_password
  max_retries: 5
  localization: 'pl'
  switches:
    - power
  sensors:
    - ch_account_gas
    - ch_antifreeze_temperature
    - ch_detected_temperature
    - ch_mode
    - ch_comfort_temperature
    - ch_economy_temperature
    - ch_set_temperature
    - ch_program
    - dhw_account_gas
    - dhw_comfort_function
    - dhw_mode
    - dhw_comfort_temperature
    - dhw_economy_temperature
    - dhw_set_temperature
    - dhw_storage_temperature
    - errors
    - heating_last_24h
    - heating_last_30d
    - heating_last_365d
    - heating_last_7d
    - mode
    - outside_temperature
    - signal_strength
    - water_last_24h
    - water_last_30d
    - water_last_365d
    - water_last_7d
  binary_sensors:
    - changing_data
    - flame
    - holiday_mode
    - heat_pump
    - internet_time
    - internet_weather
    - online
```

## Services
`ariston.set_data` - sets data in the boiler. Uses `max_retries` attribute from configuration.

### Service attributes:
- `entity_id` - **mandatory** entity of Ariston `climate`.
- for the rest of attributes please see `Developer Tools` tab `Services` within Home Assistant and select `ariston.set_data`. Or you may also directly read `services.yaml` within the `ariston` folder.

### Service use example
```
service: ariston.set_data
data:
    entity_id: 'climate.ariston'
    ch_comfort_temperature: 20.5
```

# Ariston NET remotethermo integration for Home Assistant
Thin integration is a side project (my first integration) and was tested only with 1 zone climate. It logs in Ariston website and fetches/sets data on that site. Due to interaction with boiler it is time consuming process and thus intergation is relatively slow.
You are free to modify and distribute it, but it is distributed 'as is' with no liability (see license file).

Cimate and Water Heater components have presets to switch between `off`, `summer` and `winter` in order to be able to control boiler from one entity.


## Integration installation
In `/config` folder create `custom_components` folder and load source files folder `ariston` in it
In `configuration.yaml` include:
```
ariston:
  username: !secret ariston_username
  password: !secret ariston_password
```
With additional attributes if needed, which are described below.


## Integration attributes
**username** - **mandatory** user name used in https://www.ariston-net.remotethermo.com

**password** - **mandatory** password used in https://www.ariston-net.remotethermo.com
**! It is recommended for security purposes to not use your common password, just in case !**

**name** - friendly name for integration

**hvac_off** - indicates how to treat `HVAC OFF` action in climate. Options are `off` and `summer`. By default it is `summer`, which means that turning off would keep DHW water heating on (e.g. summer mode). Presets in climate allow switching between `off`, `summer` and `winter`.

**power_on** - indicates which mode would be used for `switch.turn_on` action. Options are `summer` and `winter`. By default it is `summer`.

**max_retries** - number of retries to set the data in boiler. Retries are made in case of communication issues for example, which take place occasionally. By default the value is '1'.

**store_config_files** - `true` or `false` indicating if configuration `json` files to be stored in `/config` folder.

**switches** - lists switches to be defined
  - `power` - turn power off and on (on value is defined by **power_on**).

**sensors** - lists sensors to be defined
  - `ch_account_gas` - gas use summary for CH. Not supported on all models.
  - `ch_antifreeze_temperature` - CH antifreeze temperature.
  - `ch_detected_temperature` - temperature measured by thermostat.
  - `ch_mode` - mode of CH (`manual` or `scheduled` and others).
  - `ch_scheduled_comfort_temperature` - CH comfort temperature for scheduled mode. Not supported on all models.
  - `ch_scheduled_economy_temperature` - CH economy temperature for scheduled mode. Not supported on all models.
  - `ch_set_temperature` - set CH temperature.
  - `ch_schedule` - CH Schedule
  - `dhw_account_gas` - gas use summary for DHW. Not supported on all models.
  - `dhw_mode` - mode of DHW. Not supported on all models.
  - `dhw_scheduled_comfort_temperature` - DHW storage comfort temperature for scheduled mode. Not supported on all models.
  - `dhw_scheduled_economy_temperature` - DHW storage economy temperature for scheduled mode. Not supported on all models.
  - `dhw_set_temperature` - set DHW temperature.
  - `dhw_storage_temperature` - DHW storage temperature. Not supported on all models.
  - `errors` - active errors (no errors to test on)
  - `heating_last_24h` - gas use in last 24 hours. Not supported on all models.
  - `heating_last_30d` - gas use in last 7 days. Not supported on all models.
  - `heating_last_365d` - gas use in last 30 days. Not supported on all models.
  - `heating_last_7d` - gas use in last 365 days. Not supported on all models.
  - `mode` - mode of boiler (`off` or `summer` or `winter` and others).
  - `outside_temperature` - outside temperature. Not supported on all models.
  - `water_last_24h` - water use in last 24 hours. Not supported on all models.
  - `water_last_30d` - water use in last 7 days. Not supported on all models.
  - `water_last_365d` - water use in last 30 days. Not supported on all models.
  - `water_last_7d` - water use in last 365 days. Not supported on all models.

**binary_sensors**
  - `changing_data` - if change of data via Home Assistant is ongoing
  - `flame` - if boiler is heating water (DHW or CH).
  - `heat_pump` - if heating pump is ON. Not supported on all models.
  - `holiday_mode` - if holiday mode switch on via application or site.
  - `online` - online status.


## Example of configuration.yaml entry
```
ariston:
  username: !secret ariston_user
  password: !secret ariston_password
  hvac_off: "summer"
  power_on: "summer"
  store_config_files: true
  max_retries: 5
  switches:
    - power
  sensors:
    - ch_account_gas
    - ch_antifreeze_temperature
    - ch_detected_temperature
    - ch_mode
    - ch_scheduled_comfort_temperature
    - ch_scheduled_economy_temperature
    - ch_set_temperature
    - ch_schedule
    - dhw_account_gas
    - dhw_mode
    - dhw_scheduled_comfort_temperature
    - dhw_scheduled_economy_temperature
    - dhw_set_temperature
    - dhw_storage_temperature
    - errors
    - heating_last_24h
    - heating_last_30d
    - heating_last_365d
    - heating_last_7d
    - mode
    - outside_temperature
    - water_last_24h
    - water_last_30d
    - water_last_365d
    - water_last_7d
  binary_sensors:
    - changing_data
    - flame
    - holiday_mode
    - heat_pump
    - online
```

## Services
`ariston.set_data` - sets data in the boiler. Uses **max_retries** attribute from configuration.

### Service attributes:
`entity_id` - **mandatory** entity of Ariston `climate`.

`mode` - mode of the boiler: `off`, `summer`, `winter` etc.

`ch_mode` - mode of CH: `manual`, `scheduled` etc.

`ch_set_temperature` - CH temperature to be set. Also changes comfort temperature for scheduled mode (because Ariston api)

`ch_scheduled_comfort_temperature` - CH comfort temperature to be set.

`ch_scheduled_economy_temperature` - CH economy temperature to be set.

`dhw_set_temperature` - DHW temperature to be set. Also changes comfort temperature for scheduled mode (because Ariston api)

`dhw_scheduled_comfort_temperature` - DHW comfort temperature to be set (not supported on my hardware to test).

`dhw_scheduled_economy_temperature` - DHW economy temperature to be set (not supported on my hardware to test).

## Service use example
```
service: ariston.set_data
data:
    entity_id: 'climate.ariston'
    ch_set_temperature: 20.5
```

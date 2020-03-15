# Ariston NET remotethermo integration for Home Assistant
Thin integration is a side project (my first integration) and was tested only with 1 zone climate. It logs in to Ariston website and fetches/sets data on that site.
You are free to modify and distribute it, but it is distributed 'as is' with no liability (see license file).

Cimate and Water Heater components have presets to switch between `off`, `summer` and `winter` in order to be able to control boiler from one entity.

## Integration slow nature
In order not to interfere with other applications (official Ariston applications via android or web, and Google Home) fetching of data has timers to read data from 1 to 6 minutes with possible skip if some data was changed. Interfereing with other application causes their timeouts and occasionally gateway disconnection from the internet or hanging for long periods of time, thus decrease of retry intervals is not recommended.
Setting of data is perfomed immediately on request with attempts scheduled to every 2 minutes (see `max_retries` for number of retries) while checking latest fetched data to determine if setting was successful or not. If new request comes during setting procedure, it shall be processed during next scheduled attempt.
Monitoring change of configuration can be viewed via binary sensor `changing_data`.


## Integration was tested on:
  - Ariston Clas Evo
  - Ariston Genus One with Ariston BCH cylinder
  - Ariston Nimbus Flex

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
  - Backend translation (objects within `backend.__.json` file), which forces translated values to be used during components initilization for `climate` (preset) and `water_heater` (operation). Change of language can only be changed in `configuration.yaml` and is applied during Home Assistant start. **Note that services use untranslated data, use velues specified in `services.yaml`!**

**Supported localizations**:
  - `en` - English (default)
  - `uk` - Ukrainian
  - `pl` - Polish

## Custom icons for mode sensor
Store contents of `icons` folder in `\config\www\icons` folder. Since builtin icons do not have similar representation as in Ariston app, this is an option to partly reflect the application view.

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
  - `internet_time` - turn off and on sync with internet time.
  - `internet_weather` - turn off and on fetching of weather from internet.
  - `ch_auto_function` - turn off and on Auto function.

#### Sensors
  - `account_ch_gas` - gas use summary for CH. Not supported on all models.
  - `account_ch_electricity` - electricity use summary for CH. Not supported on all models.
  - `account_dhw_gas` - gas use summary for DHW. Not supported on all models.
  - `account_dhw_electricity` - electricity use summary for DHW. Not supported on all models.
  - `ch_antifreeze_temperature` - CH antifreeze temperature.
  - `ch_detected_temperature` - temperature measured by thermostat.
  - `ch_mode` - mode of CH (`manual` or `scheduled` and others).
  - `ch_comfort_temperature` - CH comfort temperature.
  - `ch_economy_temperature` - CH economy temperature.
  - `ch_set_temperature` - set CH temperature.
  - `ch_program` - CH Time Program.
  - `dhw_comfort_function` - DHW comfort function.
  - `dhw_mode` - mode of DHW. Not supported on all models.
  - `dhw_comfort_temperature` - DHW storage comfort temperature. Not supported on all models.
  - `dhw_economy_temperature` - DHW storage economy temperature. Not supported on all models.
  - `dhw_set_temperature` - set DHW temperature.
  - `dhw_storage_temperature` - DHW storage temperature. Not supported on all models.
  - `errors` - active errors (no errors to test on)
  - `heating_last_24h` - energy use for heating in last 24 hours. Not supported on all models.
  - `heating_last_30d` - energy use for heating in last 7 days. Not supported on all models.
  - `heating_last_365d` - energy use for heating in last 30 days. Not supported on all models.
  - `heating_last_7d` - energy use for heating in last 365 days. Not supported on all models.
  - `mode` - mode of boiler (`off` or `summer` or `winter` and others).
  - `outside_temperature` - outside temperature. Not supported on all models.
  - `signal_strength` - Wifi signal strength.
  - `units` - Units of measurement
  - `water_last_24h` - energy use for water in last 24 hours. Not supported on all models.
  - `water_last_30d` - energy use for water in last 7 days. Not supported on all models.
  - `water_last_365d` - energy use for water in last 30 days. Not supported on all models.
  - `water_last_7d` - energy use for water in last 365 days. Not supported on all models.

#### Binary sensors
  - `ch_auto_function` - if CH AUTO function is enabled.
  - `ch_flame` - if CH heating is ongoing.
  - `changing_data` - if change of data via Home Assistant is ongoing.
  - `flame` - if any type of heating water (DHW or CH).
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
    - internet_time
    - internet_weather
    - ch_auto_function
  sensors:
    - account_ch_gas
    - account_ch_electricity
    - account_dhw_gas
    - account_dhw_electricity
    - ch_antifreeze_temperature
    - ch_detected_temperature
    - ch_mode
    - ch_comfort_temperature
    - ch_economy_temperature
    - ch_set_temperature
    - ch_program
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
    - units
    - water_last_24h
    - water_last_30d
    - water_last_365d
    - water_last_7d
  binary_sensors:
    - ch_auto_function
    - ch_flame
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

## New sensors/services requests
Since i use scanning of http requests towards web application and web application provides only data supported by hardware, i can mainly test what my hardwre supports, which is very limited. So if you would like new sensors or service attributes please follow guides below. 

### Sensors based on already fetched data from remote server
  - Set `store_config_files` to `true` in `configuration.yaml` to generate files within `/config` folder based on received data from the server.
  - after Home Assistant restart (when option to generate files is enabled) wait for files `data_..._get_main.json`, `data_..._get_param.json` and `data_..._get_gas.json` to be generated. Store files locally, they keep latest configuration.
  - change parameter (you are interested in) remotely and wait for new version of files to be generated (check either modification time, or delete old ones and wait for creation of new ones). Compare old and new files with same names to see if parameter is reported as changed.
  - send me information on file name, sensor name (and short description) and parameter in json file that represents parameter. If parameter has values different from true/false (for example 0, 1 ,5) please provide meaning behind each value. If my hardware does not support it i have no idea how it should be represented.

### Sensors to be based on new requests (if not covered by previous)
This case requires more actions. Since my web application does not show more options due to heater caopabilities support, there are few options:
  - install traffic analyzer (like fiddler) and connect it to web browser (like chrome) and when you refresh parameters in web application from browser request is being sent to the server. You need to find corresponding request (header request) and reply (json format). And within this json reply identify corresponding sensor you are interetsed in. See `Guide_for_new_requests.doc` for details.
  - provide me with login and password to do it myself with your heater (once again, my heater has limited capabilities and web version shows less data) and change password afterwards when i have fond corresponding requests. **Never share your password with strangers**
  
### New service request attributes
This is similar case to sensors based on new requests, but you need to find post request with corresponding data and provide me with infomrtion regarding headers and json request format. See `Guide_for_new_requests.doc` for details.

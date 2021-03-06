# THIS VERSION IS NO LONGER MAINTAINED
**New version is cretaed based on dedicated API. For details please see https://github.com/chomupashchuk/ariston-remotethermo-home-assistant-v2**.

# Ariston NET remotethermo integration for Home Assistant
Thin integration is a side project (my first integration) and was tested only with 1 zone climate. It logs in to Ariston website and fetches/sets data on that site.
You are free to modify and distribute it, but it is distributed 'as is' with no liability (see license file).

Cimate and Water Heater components have presets to switch between `off`, `summer` and `winter` in order to be able to control boiler from one entity.

## Integration slow nature
In order not to interfere with other applications (official Ariston applications via android or web, and Google Home) fetching of data has timers to read data from 1 to 16 minutes depending on specific sensor (for example errors and temperatures are fetched more often compared to gas use or time based program) and on configuration (`polling_rate`) with possible skip if some data was changed or communication error. Interfereing with other application causes their timeouts and occasionally gateway disconnection from the internet or hanging for long periods of time, thus decrease of retry intervals is not recommended.
Setting of data is perfomed immediately on request with attempts scheduled to every 1 to 2.5 minutes depending on configuration (see `polling_rate`) and if there are too many errors that decreases speed of execution. Attribute `max_retries` is used to identify how many more attempts to be done after initial one (might be useful in case of unstable connection). If new request comes during setting procedure, it shall be processed during next scheduled attempt.
Monitoring if change of configuration is being attempted can be viewed with `changing_data` binary_sensor. To reduce number of setting requests the integration waits for reading of data to determine if to stop the procedure or if to continue.


## Integration was tested on and works with:
  - Ariston Clas Evo
  - Ariston Genus One with Ariston BCH cylinder
  - Ariston Nimbus Flex

## Integration does not work with:
  - Ariston Velis Wifi

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
  - `units` - which uniots to be used. Values are: `metric` (°C-bar-kW...), `imperial` (°F-psi-kBtu/h...), `auto` (detect automatically, which takes additional time). Default is `metric`.
  - `polling_rate` - indicates timers to be used to read or set data. Values are `normal` and `long`. Long means waiting longer for http replies and longer delays between the requests, which might be beneficial in case of slow Ariston responces due to internet connection for example. Default is `normal` to have faster responces.
  - `init_during_start` - indicates if integration data shall be fetched during Home Assistant start to have valid data when Home Assistant is started (no guarantee that it will succeeed). Value `true` delays the start time for longer and `false` for lesser period of time but initially all entities will be unavailable until data is fetched. Default value is `true`.
  - `dhw_flame_unknown_as_on` - indicates if unknown value of DHW to be tretaed as ON or OFF (gateway has position for DHW flame but it is never set, so intead value is based on `ch_flame` and `dhw_flame` and storage temperature if it is valid). Default value is `false`.
  - `dhw_and_ch_simultaneously` indicates if DHW and CH flames can work together in specific hardware (Clas Evo and Genus One can heat only DHW or CH at one time). It affects if `ch_flame` shall be turned off forcefully when `dhw_flame` is suspected to be on. Default value is `false`.

#### Switches
  - `power` - turn power off and on (on value is defined by `power_on` attribute).
  - `internet_time` - turn off and on sync with internet time.
  - `internet_weather` - turn off and on fetching of weather from internet.
  - `ch_auto_function` - turn off and on Auto function.
  - `dhw_thermal_cleanse_function` - DHW thermal cleanse function enabled.

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
  - `dhw_program` - DHW Time Program.
  - `dhw_comfort_function` - DHW comfort function.
  - `dhw_mode` - mode of DHW. Not supported on all models.
  - `dhw_comfort_temperature` - DHW storage comfort temperature. Not supported on all models.
  - `dhw_economy_temperature` - DHW storage economy temperature. Not supported on all models.
  - `dhw_set_temperature` - set DHW temperature.
  - `dhw_storage_temperature` - DHW storage temperature. Not supported on all models.
  - `dhw_thermal_cleanse_cycle` - DHW thermal cleanse cycle.
  - `electricity_cost` - Electricity cost.
  - `errors` - active errors (no errors to test on).
  - `gas_type` - Gas type.
  - `gas_cost` - Gas cost.
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
  - `ch_pilot` - CH Pilot mode.
  - `changing_data` - if change of data via Home Assistant is ongoing.
  - `dhw_flame` - if DHW heating is ongoing (not fetched but calculated based on `ch_flame`, `flame`, and if valid then `dhw_storage_temperature` and `dhw_set_temperature`, and `dhw_flame_unknown_as_on` for invalid `dhw_storage_temperature`).
  - `dhw_thermal_cleanse_function` - DHW thermal cleanse function enabled.
  - `flame` - if any type of heating water (DHW or CH).
  - `heat_pump` - if heating pump is ON. Not supported on all models.
  - `holiday_mode` - if holiday mode switch on via application or site.
  - `internet_time` - if time from the internet is used.
  - `internet_weather` - if weather from the internet is used.
  - `online` - online status.
  - `update` - if update is available for the integration.


### Example of configuration.yaml entry
```
ariston:
  username: !secret ariston_user
  password: !secret ariston_password
  max_retries: 5
  localization: 'pl'
  switches:
    - internet_time
    - internet_weather
  sensors:
    - ch_detected_temperature
    - ch_mode
    - ch_comfort_temperature
    - ch_economy_temperature
    - ch_set_temperature
    - dhw_set_temperature
    - errors
    - mode
    - outside_temperature
  binary_sensors:
    - changing_data
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

## Some known issues and workarounds

### Climate and water_heater entity become unavailable
Since integration interacts with server, which interacts with boiler directly or via gateway, it is possible that some link in the chain is not working. Integration is designed to constantly retry the connection (requests are sent more reearely in case of multiple faults to reduce load on whole chain). Mostly connection recovers in time, but sometimes restart of router or boiler can help (but not always).

### Only part of data becomes unavailable after it was available
Even though many functions are not accessible via integration once boiler configuration (parameter 228 in the menu) changed from 1 (boiler with water heater sensor) to 0 (default configuration without sensor), possibly due to packets corruption on the way or some specific bit sequence. It caused Genus One model not being able to handle DHW. The solution is to enter boiler menu directly and change the value of parameter 228.
Also boiler might require restart (complete loss of power).


## Provide New localizations
Please see files under `/ariston/.translations/` and take files like `backend.en.json` and `sensor.en.json` as a base. Create files with corresponding name that represent desired language (must be compliant with BCP47) and input translated data into created files from the right side of the data (left side is internal values used by the integration and right side are the values to be shown in the frontend). Then please provide me with mentioned 2 files in order to be included in the integration (to include new language in `LANG_LIST` within `const.py` and make it available for everyone). 

## New sensors/services requests
Since I use scanning of http requests towards web application, and web application provides only data supported by hardware, I can only test what my hardwre supports, which is very limited. So if you would like new sensors or service attributes please follow guides below. 

### Sensors based on already fetched data from remote server
  - Set `store_config_files` to `true` in `configuration.yaml` to generate files within `/config` folder based on received data from the server.
  - after Home Assistant restart wait for files `data_..._get_main.json`, `data_..._get_param.json` and `data_..._get_gas.json` to be generated. Store files locally, within the files is the latest configuration.
  - change parameter that you are interested in remotely (via Ariston web or androind or by other means) and wait for new version of files to be generated (either check modification time or delete old files within `/config` and wait for creation of new files). Compare old and new files with same names to see if parameter is reported as changed.
  - send me information on file name, sensor name (and short description) and parameter in json file that represents parameter. If parameter has values different from ON/OFF or TRUE/FALSE (for example 0, 1 ,5) please provide meaning behind each value. If my hardware does not support values i have no idea of how it should be represented.

### Sensors to be based on new requests (if cannot be covered by previous)
Since my web application does not show more options due to heater capabilities support, there are few options:
  - install traffic analyzer (like fiddler) and connect it to web browser (like chrome) and follow `Guide_for_new_requests.doc`.
  - **Never share your password with strangers**. Provide me with login and password to do everything myself with your heater and change password after i have fond corresponding requests. 
  
### New service request attributes or switches
This is similar case to the sensors based on new requests, see `Guide_for_new_requests.doc` for details.

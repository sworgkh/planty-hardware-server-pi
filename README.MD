# Plant`y Hardware Contorollers software

## Configuration
### To run the scripts we need to install AWS CLI, and configure it with security keys.
### Configuration files description:
* Logging - "logger.conf" configurations for loggers used in sensors and actuatros
* Linux Services - "actuators.service", "sensors.service" these are the configurations for running python scripts as linux service
* 

## Main Routines
* sensors.py - sensors data controller
* actuators.py - actuators controller
* plotsUpdater.py - plots updates script
* dailyPicTest\cameracapture.py - daily healthcheck script
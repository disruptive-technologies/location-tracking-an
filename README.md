# Location Tracking

## What am I?
This repository contains the example code talked about in [this application note](https://support.disruptive-technologies.com/hc/en-us/articles/360016890899), presenting a method of using the Disruptive Technologies (DT) Wireless Sensors for tracking assets between different physical locations. Written in Python 3, it uses the DT Developer API to communicate with a DT Studio project and its sensors. 

## Before Running Any code
A DT Studio project containing any number of sensors should be made. Only sensors with the label 'track' will be fetched and included in the tracking scheme.

## Environment Setup
Dependencies can be installed using pip.
```
pip3 install -r requirements.txt
```

Edit *sensor_stream.py* to provide the following authentication details of your project. Information about setting up your project for API authentication can be found in this [streaming API guide](https://support.disruptive-technologies.com/hc/en-us/articles/360012377939-Using-the-stream-API).
```python
USERNAME   = "SERVICE_ACCOUNT_KEY"       # this is the key
PASSWORD   = "SERVICE_ACCOUT_SECRET"     # this is the secret
PROJECT_ID = "PROJECT_ID"                # this is the project id
```

## Usage
Running *python3 sensor_stream.py* without any arguments will start streaming connection data from each labeled sensor in the project. From looking up the predefined locations map in ./config/locations.py, a visualization is presented. Historical event data can be fetched by applying one or several or the system arguments listed below.
```
usage: sensor_stream.py [-h] [--starttime] [--endtime] [--timeout] [--no-plot]

Implementation For Tracking Assets Between Locations of Cloud Connectors.

optional arguments:
  -h, --help    show this help message and exit
  --starttime   Event history UTC starttime [YYYY-MM-DDTHH:MM:SSZ].
  --endtime     Event history UTC endtime [YYYY-MM-DDTHH:MM:SSZ].
  --timeout     Seconds before an asset is considered between location.
  --no-plot     Suppress streaming plot.
```

Note: When using the *--starttime* argument for a date far back in time, if many sensors exist in the project, the paging process might take several minutes.


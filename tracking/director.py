# packages
import os
import time
import json
import argparse
import datetime
import requests
import sseclient
import threading
import numpy             as np
import matplotlib.pyplot as plt

# project
from tracking.sensors import Sensor
from config.styling import styling_init
import tracking.helpers as hlp
import config.parameters as prm
from config.locations import locations


class Director():
    """
    Handles all API interfacing, including fetching sensors list and updating them.
    Control locations list and delegates this information to tracked sensors.
    When new event data arrives in stream, delegate to the correct sensor for update.

    """

    def __init__(self, username='', password='', project_id='', api_url_base=''):
        """
        Director class constructor.

        Parameters
        ----------
        username : str
            DT Studio service account key.
        password : str
            DT Studio service account secret.
        project_id : str
            DT Studio project identifier.
        api_url_base : str
            Endpoint for API.

        """

        # give arguments to self
        self.username     = username
        self.password     = password
        self.project_id   = project_id
        self.api_url_base = api_url_base

        # initialise variables
        self.last_update = -1

        # initialise a threading locker to avoid conflict
        self.lock = threading.Lock()

        # initialise plot styling (font size, colors etc)
        styling_init()

        # set stream endpoint for API
        self.stream_endpoint = "{}/projects/{}/devices:stream".format(self.api_url_base, self.project_id)

        # parse system arguments
        self.__parse_sysargs()

        # set history- and streaming filters
        self.__set_filters()

        # fetch list of devices in project
        self.__fetch_project_devices()

        # fetch sensors
        self.__spawn_devices()


    def __parse_sysargs(self):
        """
        Parse for command line arguments.

        """

        # create parser object
        parser = argparse.ArgumentParser(description='Implementation For Tracking Assets Between Locations of Cloud Connectors.')

        # get UTC time now
        now = (datetime.datetime.utcnow().replace(microsecond=0)).isoformat() + 'Z'

        # general arguments
        parser.add_argument('--starttime',  metavar='', help='Event history UTC starttime [YYYY-MM-DDTHH:MM:SSZ].', required=False, default=now)
        parser.add_argument('--endtime',    metavar='', help='Event history UTC endtime [YYYY-MM-DDTHH:MM:SSZ].',   required=False, default=now)
        parser.add_argument('--timeout',    metavar='', help='Seconds before an asset is considered between location.', required=False, default=60*30)

        # boolean flags
        parser.add_argument('--no-plot',   action='store_true', help='Suppress streaming plot.')

        # convert to dictionary
        self.args = vars(parser.parse_args())

        # set history flag
        if now == self.args['starttime']:
            self.fetch_history = False
        else:
            self.fetch_history = True


    def __set_filters(self):
        """
        Set filters for data fetched through API.

        """

        # historic events
        self.history_params = {
            'page_size': 1000,
            'start_time': self.args['starttime'],
            'end_time': self.args['endtime'],
            'event_types': ['networkStatus']
        }

        # stream events
        self.stream_params = {
            'event_types': ['networkStatus']
        }


    def __fetch_project_devices(self):
        """
        Fetch list of all devices in project from API.

        """

        # request list
        devices_list_url = "{}/projects/{}/devices".format(self.api_url_base,  self.project_id)
        device_listing = requests.get(devices_list_url, auth=(self.username, self.password))
        
        # remove fluff
        if device_listing.status_code < 300:
            self.project_devices = device_listing.json()['devices']
        else:
            print(device_listing.json())
            hlp.print_error('Status Code: {}'.format(device_listing.status_code), terminate=True)


    def __spawn_devices(self):
        """
        Use list of devices to spawn a Desk- and Reference object.
        One Reference object in total and one Desk object per desk sensor.

        """

        # empty lists of devices
        self.sensors    = []
        self.sensor_ids = []

        # iterate list of devices
        for device in self.project_devices:
            # get device id
            device_id = os.path.basename(device['name'])
            
            # accept only labeled devices
            if prm.project_sensor_label in device['labels'].keys():
                # append an initialised desk object
                self.sensors.append(Sensor(device, device_id))
                self.sensor_ids.append(device_id)


    def __new_event_data(self, event_data, cout=True):
        """
        Receive new event_data json and pass it along to the correct device object.

        Parameters
        ----------
        event_data : dictionary
            Data json containing new event data.
        cout : bool
            Will print event information to console if True.

        """

        # get id of source sensor
        source_id = os.path.basename(event_data['targetName'])

        # find sensor to related id
        for sensor in self.sensors:
            if sensor.sensor_id == source_id:
                # cout
                if cout: print('-- New Event for {}.'.format(source_id))
        
                # serve event to desk
                sensor.new_event_data(event_data)


    def __fetch_event_history(self):
        """
        For each sensor in project, request all events since --starttime from API.

        """

        # initialise empty event list
        self.event_history = []

        # iterate devices
        for device in self.project_devices:
            # isolate device identifier
            device_id = os.path.basename(device['name'])

            # skip if not in sensorlist
            if device_id not in self.sensor_ids:
                continue
        
            # some printing
            print('-- Getting event history for {}'.format(device_id))
        
            # initialise next page token
            self.history_params['page_token'] = None
        
            # set endpoints for event history
            event_list_url = "{}/projects/{}/devices/{}/events".format(self.api_url_base, self.project_id, device_id)
        
            # perform paging
            while self.history_params['page_token'] != '':
                event_listing = requests.get(event_list_url, auth=(self.username, self.password), params=self.history_params)
                event_json = event_listing.json()

                if event_listing.status_code < 300:
                    self.history_params['page_token'] = event_json['nextPageToken']
                    self.event_history += event_json['events']
                else:
                    print(event_json)
                    hlp.print_error('Status Code: {}'.format(event_listing.status_code), terminate=True)
        
                if self.history_params['page_token'] != '':
                    print('\t-- paging')
        
        # sort event history in time
        self.event_history.sort(key=hlp.json_sort_key, reverse=False)


    def run_history(self, plot=True):
        """
        Iterate through and calculate occupancy for event history.

        """

        # do nothing if starttime not given
        if not self.fetch_history:
            return

        # get list of hsitoric events
        self.__fetch_event_history()

        # verify any data were fetched
        if len(self.event_history) < 1:
            hlp.print_error('__fetch_event_history() returned 0 events.')
            return

        # generate unixtime axis for all events in history
        n_events               = len(self.event_history)
        event_history_unixtime = [hlp.convert_event_data_timestamp(h['data']['networkStatus']['updateTime'])[1] for h in self.event_history]

        # time parameters
        unix_start = event_history_unixtime[0]
        unix_step  = prm.streamtick
        unix_now   = unix_start
        unix_end   = event_history_unixtime[-1]

        # simulate time
        i = 0
        cc = 0
        while unix_now <= unix_end:
            cc = hlp.loop_progress(cc, i, len(self.event_history), 20, name='event history')
            # catch up with events that have "occured"
            while i < n_events and event_history_unixtime[i] < unix_now:
                # serve event to self
                self.__new_event_data(self.event_history[i], cout=False)

                # iterate
                i += 1

            # check buffering status for each sensor
            for sensor in self.sensors:
                if sensor.buffering and len(sensor.event_buffer) > 0 and unix_now - sensor.last_event > prm.buffertime:
                    sensor.update_event_data(unix_now)

                elif unix_now - sensor.last_event > self.args['timeout']:
                    sensor.update_empty(unix_now)

            # iterate time
            unix_now += unix_step
        
        # plot history results 
        if plot and not self.args['no_plot']:
            print('\nThis plot is blocking.')
            print('Closing it will start a stream with a non-blocking plot.')
            self.plot(blocking=True, show=True)


    def run_stream(self, n_reconnects=5):
        """
        Estimate occupancy on realtime stream data from sensors.

        Parameters
        ----------
        n_reconnects : int
            Number of reconnection attempts at disconnect.

        """
    
        # reinitialise plot
        if not self.args['no_plot']:
            self.plot(blocking=False)


        # listen for events in another thread
        t = threading.Thread(target=self.listen)
        t.start()

        self.new_event = False

        # check each timestep
        while True:
            now = time.time()
            print(now)
            with self.lock:
                # check buffering status for each sensor
                for sensor in self.sensors:
                    if sensor.buffering and len(sensor.event_buffer) > 0 and now - sensor.last_event > prm.buffertime:
                        sensor.update_event_data(now)
        
                        # plot progress
                        if not self.args['no_plot']:
                            self.plot(blocking=False, show=False)

                    # check for sensor timeout
                    elif now - sensor.last_event > self.args['timeout']:
                        sensor.update_empty(now)

            time.sleep(prm.streamtick)


    def listen(self):
        """
        Listen for new events from sensors in stream.
        When new event occurs, delegate data to correct sensor.

        """

        # cout
        print("Listening for events... (press CTRL-C to abort)")
    
        # loop indefinetly
        n_reconnects  = 5
        nth_reconnect = 0
        while nth_reconnect < n_reconnects:
            try:
                # reset reconnect counter
                nth_reconnect = 0
        
                # get response
                response = requests.get(self.stream_endpoint, auth=(self.username, self.password), headers={'accept':'text/event-stream'}, stream=True, params=self.stream_params)
                client = sseclient.SSEClient(response)
        
                # listen for events
                print('Connected.')
                for event in client.events():
                    # new data received
                    event_data = json.loads(event.data)['result']['event']
        
                    # serve event to director
                    with self.lock:
                        self.__new_event_data(event_data)
                        self.new_event = True
            
            # catch errors
            # Note: Some VPNs seem to cause quite a lot of packet corruption (?)
            except requests.exceptions.ConnectionError:
                nth_reconnect += 1
                print('Connection lost, reconnection attempt {}/{}'.format(nth_reconnect, n_reconnects))
            except requests.exceptions.ChunkedEncodingError:
                nth_reconnect += 1
                print('An error occured, reconnection attempt {}/{}'.format(nth_reconnect, n_reconnects))
            except KeyError:
                print('Error in event package. Skipping...')
                print(event_data)
                print()
            
            # wait 1s before attempting to reconnect
            time.sleep(1)


    def initialise_plot(self):
        """
        Initialises figure and axes used by plot().

        """

        self.fig, self.ax = plt.subplots(len(self.sensors), 1, sharex=True)
        if len(self.sensors) < 2:
            self.ax = [self.ax]


    def plot(self, blocking=True, show=True):
        """
        Visualization of asset tracking results.

        Parameters
        ----------
        blocking : boolean
            Uses blocking matplotlib functions to display an interactive plot if True.
        show : boolean
            Calls show() if True. Calls waitforbuttonpress() if False.

        """

        # initialise if not open
        if not hasattr(self, 'ax') or not plt.fignum_exists(self.fig.number):
            self.initialise_plot()

        # initialise xlim lists
        xlim = [np.inf, -np.inf]
        tlim = [np.inf, -np.inf]
        xlim_updated = [False, False]

        # legend boolean to avoid duplication
        legend_bool = [True for i in range(len(locations)+1)]

        # draw sensor data
        for s, sensor in enumerate(self.sensors):
            self.ax[s].cla()

            # update xlim
            ux = np.array(sensor.unixtime)
            ts = sensor.get_timestamps()
            if len(ux) > 1 and ux[1] < xlim[0]:
                xlim[0] = ux[1]
                tlim[0] = ts[1]
                xlim_updated[0] = True

            if len(ux) > 1 and ux[-1] > xlim[1]:
                xlim[1] = ux[-1]
                tlim[1] = ts[-1]
                xlim_updated[1] = True

            # fill between
            rr = np.array(sensor.max_rssi)
            ix = 0
            for i in range(len(ux)):
                if i == ix:
                    continue
                elif rr[ix] == None:
                    ix = i

                elif rr[i] == None or sensor.location_map[rr[i]] != sensor.location_map[rr[i-1]] or i == len(ux)-1:
                    left = ts[ix]
                    right = ts[i]
                    color = 'C{}'.format(sensor.location_map[rr[i-1]])
                    if sensor.location_map[rr[i-1]] == sensor.location_map_unknown:
                        color = 'gray'
                    # self.ax[s].fill_between([left, right], 0, len(sensor.ccons)-1, alpha=0.33, color=color)
                    zone_range = np.where(np.array(sensor.location_map)==sensor.location_map[rr[i-1]])[0]
                    zlim = [min(zone_range)-0.5, max(zone_range)+0.5]
                    if legend_bool[sensor.location_map[rr[i-1]]]:
                        label = 'Loc {}'.format(sensor.location_map[rr[i-1]])
                        if sensor.location_map[rr[i-1]] == sensor.location_map_unknown:
                            label = 'Uncategorized'
                        self.ax[s].fill_between([left, right], zlim[0], zlim[1], alpha=0.33, color=color, label=label)
                        legend_bool[sensor.location_map[rr[i-1]]] = False
                    else:
                        self.ax[s].fill_between([left, right], zlim[0], zlim[1], alpha=0.33, color=color)
                    ix = i

                

            self.ax[s].plot(ts, sensor.max_rssi, '.k')
            self.ax[s].set_yticks(np.arange(len(sensor.ccons)))
            labels = [item.get_text() for item in self.ax[s].get_yticklabels()]
            ticks  = []
            for i, key in enumerate(sensor.ccons.keys()):
                labels[i] = key[-5:]
                ticks.append(i)
            self.ax[s].set_yticks(ticks)
            self.ax[s].set_yticklabels(labels)
            self.ax[s].set_ylim([-0.5, len(sensor.ccons)-0.5])
            if xlim_updated[0] and xlim_updated[1]:
                self.ax[s].set_xlim(tlim)
            # self.ax[s].legend([sensor.sensor_id[-5:]], loc='upper left')
            
            spine = self.ax[s].spines['right']
            spine.set_visible(False)
            spine = self.ax[s].spines['top']
            spine.set_visible(False)
            # spine = self.ax[s].spines['bottom']
            # spine.set_visible(False)

            if s == len(self.sensors)-1:
                self.ax[s].set_xlabel('Timestamp')
            self.ax[s].set_ylabel('CCONs')

        # legend on top
        plt.figlegend(loc='upper center', ncol=len(legend_bool))

        if blocking:
            if show:
                plt.show()
            else:
                plt.waitforbuttonpress()
        else:
            plt.pause(0.01)

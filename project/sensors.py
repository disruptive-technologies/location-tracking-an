# project
import project.helpers as hlp
import config.parameters as prm
from config.zones import zones


class Ccon():

    def __init__(self, device_id):
        # give to self
        self.device_id = device_id


class Sensor():

    def __init__(self, device, sensor_id):
        # give to self
        self.device    = device
        self.sensor_id = sensor_id

        # initialise lists
        self.unixtime = []
        self.values   = []
        self.rssi     = []
        self.ccons    = {}
        self.ccon_ids = []
        self.max_rssi = []

        # initialise variables
        self.n_events     = 0
        self.last_event   = -1
        self.buffering    = False
        self.event_buffer = []

        # initialise ccon list with zones information
        self.__initialise_ccons_list()

    
    def __initialise_ccons_list(self):
        for zone in zones:
            for ccon in zone['ccons']:
                self.ccons[ccon] = len(self.ccons)
                self.rssi.append([None])
        self.unixtime.append(None)
        self.max_rssi.append(None)
        self.n_events += 1

        # create zone map
        self.zm = []
        for i in range(len(zones)):
            for j in range(len(zones[i]['ccons'])):
                self.zm.append(i)
                self.zm_unknown = i + 1


    def get_timestamps(self):
        return hlp.ux2tx(self.unixtime)
    

    def get_values(self):
        return self.values


    def new_event_data(self, event):
        # isolate event ccon
        ccon = event['data']['networkStatus']['cloudConnectors'][0]

        # check if ccon already in buffer
        exists = False
        for i in range(len(self.event_buffer)):
            e_ccon = self.event_buffer[i]['data']['networkStatus']['cloudConnectors'][0]
            if e_ccon['id'] == ccon['id']:
                self.event_buffer[i] = event
                exists = True

        # add to buffer
        if not exists:
            self.event_buffer.append(event)

        # get unixtime of this event
        _, ux = hlp.convert_event_data_timestamp(event['data']['networkStatus']['updateTime'])

        # update buffer timer
        self.last_event = ux
        self.buffering  = True
        

    def update_event_data(self, ux_calltime):
        # get unixtime of events
        _, ux = hlp.convert_event_data_timestamp(self.event_buffer[-1]['data']['networkStatus']['updateTime'])
        self.unixtime.append(ux_calltime)

        # update event counter
        self.n_events += 1

        # iterate each event ccon
        for event in self.event_buffer:
            # isolate ccon
            ccon = event['data']['networkStatus']['cloudConnectors'][0]

            # add new ccon if not yet known
            if ccon['id'] not in self.ccons:
                # add new row to rssi matrix
                self.rssi.append([0 for i in range(self.n_events-1)])

                # add ccon id to index lookup dictionary
                self.ccons[ccon['id']] = len(self.ccons)
                self.ccon_ids.append(ccon['id'])
                self.zm.append(self.zm_unknown)
            
            # append rssi
            self.rssi[self.ccons[ccon['id']]].append(ccon['signalStrength'])

        # append minimum value to non-talking ccon rows
        for i in range(len(self.rssi)):
            if len(self.rssi[i]) < self.n_events:
                self.rssi[i].append(0)

        # get max rssi
        argmax = -1
        valmax = -1
        for i in range(len(self.rssi)):
            if self.rssi[i][-1] > valmax:
                valmax = self.rssi[i][-1]
                argmax = i

        self.max_rssi.append(argmax)

        # reset buffer variables
        self.buffering    = False
        self.event_buffer = []


    def update_empty(self, ux_calltime):
        self.n_events += 1

        # check how much time has passed since last event
        self.unixtime.append(ux_calltime)
        self.max_rssi.append(None)

        # append minimum value to non-talking ccon rows
        for i in range(len(self.rssi)):
            if len(self.rssi[i]) < self.n_events:
                self.rssi[i].append(0)


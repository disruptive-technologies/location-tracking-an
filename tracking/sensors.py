# project
import tracking.helpers as hlp
from config.locations import locations


class Sensor():

    """
    Handles data and new events for a single sensor.
    One Sensor object per sensor in scheme.
    Handles buffering scheme for grouping CCONs.

    """

    def __init__(self, device, sensor_id):
        """
        Sensor class constructor.

        Parameters
        ----------
        device : dict
            Dictionary of device information fetched from API by Director.
        sensor_id : str
            Sensor identifier.

        """

        # give arguments to self
        self.device    = device
        self.sensor_id = sensor_id

        # initialise lists and dictionaries
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
        """
        In order to keep the order of zones, initialise internal
        CCON- and data lists in order provided by locations list.

        """

        # iterate predefined locations
        for loc in locations:
            # iterate ccons at location
            for ccon in loc['ccons']:
                # update internal ccon list
                self.ccons[ccon] = len(self.ccons)
                self.rssi.append([None])

        # update data lists with initial None value
        # this is to ensure same length in all lists
        self.unixtime.append(None)
        self.max_rssi.append(None)

        # iterate event counter to reflect initialisation
        self.n_events += 1

        # create locations map
        # this is to relate a location id to each CCON
        self.location_map = []

        # iterate locaitons
        for i in range(len(locations)):
            # iterate ccons at location
            for j in range(len(locations[i]['ccons'])):
                # update ccon with the location identifier integer
                self.location_map.append(i)

                # unknown ccons will have the the id n+1
                self.location_map_unknown = i + 1


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
                self.location_map.append(self.location_map_unknown)
            
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


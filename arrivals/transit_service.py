import asyncio
import bisect
import collections
import concurrent
import csv
import json
import re
import requests
import time
import traceback

from datetime import datetime

import config
import gtfs_realtime_pb2

Stop = collections.namedtuple('Stop', ['stop_id', 'stop_name'])
Trip = collections.namedtuple('Trip', ['trip_id', 'trip_headsign', 'route_id', 'direction_id'])
TransitLine = collections.namedtuple('TransitLine', ['key', 'name', 'description', 'etas', 'color', 'eta_threshold_min'])


class BaseTransitService:
    def get_transit_lines():
        pass

class GtfsService(BaseTransitService):
    def __init__(self):
        self.colors = {}
        self.stops = {}
        self.trips = {}

        with open(self.get_routes_path()) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            next(csv_reader) # skip header

            for row in csv_reader:
                route_id = self.get_route_id_from_routes(row)
                route_color = self.get_route_color(row)

                if route_color:
                    self.colors[route_id] = [
                        int(route_color[0:2], 16),
                        int(route_color[2:4], 16),
                        int(route_color[4:6], 16)
                    ]
                else:
                    self.colors[route_id] = [255, 255, 255]

        with open(self.get_stops_path()) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            next(csv_reader) # skip header

            for row in csv_reader:
                stop_id = self.get_stop_id(row)

                self.stops[stop_id] = Stop(
                    stop_id=stop_id,
                    stop_name=self.get_stop_name(row)
                )

        with open(self.get_trips_path()) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            next(csv_reader) # skip header

            for row in csv_reader:
                trip_id = self.get_trip_id(row)

                self.trips[trip_id] = Trip(
                    trip_id=trip_id,
                    trip_headsign=self.get_trip_headsign(row),
                    route_id=self.get_route_id_from_trips(row),
                    direction_id=self.get_direction_id(row)
                )
    
    def get_routes_path(self):
        pass

    def get_trips_path(self):
        pass

    def get_route_id_from_routes(self, row):
        pass

    def get_route_id_from_trips(self, row):
        pass

    def get_trip_id(self, row):
        pass

    def get_trip_headsign(self, row):
        pass

    def get_direction_id(self, row):
        pass

    def get_route_color(self, row):
        pass

    def get_stop_id(self, row):
        pass

    def get_stop_name(self, row):
        pass

    def get_eta(self, trip_update, stop_id):
        return next(
            (stop_time_update.arrival.time for stop_time_update in trip_update.stop_time_update if stop_time_update.stop_id == stop_id),
            None
        )
    
    def get_last_stop_name(self, trip_update):
        stop_id = sorted(trip_update.stop_time_update, key=lambda stop_time_update: -stop_time_update.arrival.time)[0].stop_id
        return self.stops[stop_id].stop_name

class MtaSubwayService(GtfsService):
    def get_routes_path(self):
        return './gtfs/mta-subway/google_transit/routes.txt'

    def get_stops_path(self):
        return './gtfs/mta-subway/google_transit/stops.txt'

    def get_trips_path(self):
        return './gtfs/mta-subway/google_transit/trips.txt'
    
    def get_route_id_from_routes(self, row):
        return row[1]

    def get_route_id_from_trips(self, row):
        return row[0]
    
    def get_trip_id(self, row):
        match = re.search(r'\d{6}_\w+\.{2}[NS]', row[1])
        return match.group() if match else '' 
    
    def get_trip_headsign(self, row):
        return row[3]

    def get_direction_id(self, row):
        return row[4]
    
    def get_route_color(self, row):
        return row[7]

    def get_stop_id(self, row):
        return row[0]

    def get_stop_name(self, row):
        return row[1]
    
    def get_transit_lines(self, stop_id, direction, gtfs_id, eta_threshold_min):
        transit_lines_by_key = {}

        response = requests.get(f'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2F{gtfs_id}', headers={
            'x-api-key': config.real_time_access_key
        })
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        trip_updates = (entity.trip_update for entity in feed.entity if entity.HasField('trip_update'))

        for trip_update in trip_updates:
            eta = self.get_eta(trip_update, stop_id)
            if not eta:
                continue

            trip = self.get_nearest_trip(trip_update.trip.trip_id, trip_update.trip.route_id)
            if not trip:
                continue

            if not direction or direction == trip.direction_id:
                route_id = trip_update.trip.route_id
                key = f'{direction}-{route_id}'
                transit_lines_by_key.setdefault(key, TransitLine(
                    key=key,
                    name=route_id,
                    description=self.get_last_stop_name(trip_update),
                    etas=[],
                    color=self.colors[route_id],
                    eta_threshold_min=eta_threshold_min
                )).etas.append(eta)

        for transit_line in transit_lines_by_key.values():
            transit_line.etas.sort()
                
        return sorted(transit_lines_by_key.values(), key=lambda transit_line: transit_line.key)
    
    def get_nearest_trip(self, trip_id, route_id):
        if (trip_id in self.trips):
            return self.trips[trip_id]
        else:
            keys = sorted(key for key in self.trips.keys() if self.is_applicable_trip(key, trip_id, route_id))
            i = bisect.bisect_left(keys, trip_id)
            if len(keys) == 0:
                print(f'invalid trip id: {trip_id}')
                return None
            nearest_trip_id = keys[min(i, len(keys) - 1)]
            return self.trips[nearest_trip_id]
    
    def is_applicable_trip(self, key, trip_id, route_id):
        suffix = r'\.{2}[NS]'
        key_match = re.search(suffix, key)
        trip_id_match = re.search(suffix, trip_id)
        return key and route_id == self.trips[key].route_id and key_match and trip_id_match and key_match.group() == trip_id_match.group()

class MtaBusService(BaseTransitService):
    def get_transit_lines(self, stop_id, direction, eta_threshold_min):
        transit_lines_by_key = {}

        response = requests.get("https://bustime.mta.info/api/siri/stop-monitoring.json", params={
            'key': config.bus_time_api_key,
            'OperatorRef': 'MTA',
            'MonitoringRef': stop_id
        })
        stop_monitoring_delivery = json.loads(response.content)['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0]
        
        if 'MonitoredStopVisit' not in stop_monitoring_delivery:
            return {}
        vehicle_journeys = (stop_visit['MonitoredVehicleJourney'] for stop_visit in stop_monitoring_delivery['MonitoredStopVisit'])

        for vehicle_journey in vehicle_journeys:
            eta = self.get_eta(vehicle_journey)

            if not direction or direction == vehicle_journey['DirectionRef']:
                published_line_name = vehicle_journey['PublishedLineName']
                key = f'{direction}-{published_line_name}'
                transit_lines_by_key.setdefault(key, TransitLine(
                    key=key,
                    name=published_line_name,
                    description=vehicle_journey['DestinationName'].title(),
                    etas=[],
                    color=[0, 57, 166],
                    eta_threshold_min=eta_threshold_min
                )).etas.append(eta)
        
        for transit_line in transit_lines_by_key.values():
            transit_line.etas.sort()
        
        return sorted(transit_lines_by_key.values(), key=lambda transit_line: transit_line.key)
    
    def get_eta(self, vehicle_journey):
        monitored_call = vehicle_journey['MonitoredCall']
        return datetime.fromisoformat(
            monitored_call['ExpectedArrivalTime'] if 'ExpectedArrivalTime' in monitored_call else monitored_call['AimedArrivalTime']
        ).timestamp()

class NycFerryService(GtfsService):
    def get_routes_path(self):
        return './gtfs/nyc-ferry/google_transit/routes.txt'

    def get_stops_path(self):
        return './gtfs/nyc-ferry/google_transit/stops.txt'

    def get_trips_path(self):
        return './gtfs/nyc-ferry/google_transit/trips.txt'
    
    def get_route_id_from_routes(self, row):
        return row[0]
    
    def get_route_id_from_trips(self, row):
        return row[0]

    def get_trip_id(self, row):
        return row[2]
    
    def get_trip_headsign(self, row):
        return row[3]

    def get_direction_id(self, row):
        return row[5]
    
    def get_route_color(self, row):
        return row[5]

    def get_stop_id(self, row):
        return row[0]

    def get_stop_name(self, row):
        return row[2]

    def get_transit_lines(self, stop_id, direction, eta_threshold_min):
        transit_lines_by_key = {}

        response = requests.get('http://nycferry.connexionz.net/rtt/public/utility/gtfsrealtime.aspx/tripupdate')
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        trip_updates = (entity.trip_update for entity in feed.entity if entity.HasField('trip_update'))

        for trip_update in trip_updates:
            eta = self.get_eta(trip_update, stop_id)
            if not eta:
                continue

            try:
                trip = self.trips[trip_update.trip.trip_id]
            except KeyError:
                traceback.print_exc()
                continue
            
            if not direction or direction == trip.direction_id:
                key = f'{direction}-{trip.route_id}'
                transit_lines_by_key.setdefault(key, TransitLine(
                    key=key,
                    name=trip.route_id,
                    description=trip.trip_headsign,
                    etas=[],
                    color=self.colors[trip.route_id],
                    eta_threshold_min=eta_threshold_min
                )).etas.append(eta)

        for transit_line in transit_lines_by_key.values():
            transit_line.etas.sort()

        return sorted(transit_lines_by_key.values(), key=lambda transit_line: transit_line.key)
    
class NjTransitService(BaseTransitService):
    def __init__(self):
        super().__init__()

        self.token = None

    def get_transit_lines(self, location, route, eta_threshold_min):
        transit_lines_by_key = {}

        if not self.token:
            token_response = requests.post(f'https://pcsdata.njtransit.com/api/BUSDV2/authenticateUser', data={
                'username': config.nj_transit_username,
                'password': config.nj_transit_password
            })
            self.token = json.loads(token_response.content)['UserToken']

        response = requests.post(f'https://pcsdata.njtransit.com/api/BUSDV2/getRouteTrips', data={
            'token': self.token,
            'location': location,
            'route': route
        })
        route_trips = json.loads(response.content)

        if 'errorMessage' in route_trips:
            # extract into helper function
            token_response = requests.post(f'https://pcsdata.njtransit.com/api/BUSDV2/authenticateUser', data={
                'username': config.nj_transit_username,
                'password': config.nj_transit_password
            })
            self.token = json.loads(token_response.content)['UserToken']

            response = requests.post(f'https://pcsdata.njtransit.com/api/BUSDV2/getRouteTrips', data={
                'token': self.token,
                'location': location,
                'route': route
            })
            route_trips = json.loads(response.content)
        
        for route_trip in route_trips:
            eta = self.get_eta(route_trip)

            key = route_trip['public_route']

            transit_lines_by_key.setdefault(key, TransitLine(
                key=key,
                name=route_trip['public_route'],
                description=re.sub('  +', ' ', route_trip['header'].strip()).title(),
                etas=[],
                color=[188, 34, 140],
                eta_threshold_min=eta_threshold_min
            )).etas.append(eta)
        
        for transit_line in transit_lines_by_key.values():
            transit_line.etas.sort()
        
        return sorted(transit_lines_by_key.values(), key=lambda transit_line: transit_line.key)
    
    def get_eta(self, route_trip):
        return datetime.strptime(
            route_trip['sched_dep_time'],
            "%m/%d/%Y %I:%M:%S %p"
        ).timestamp()

class CompositeTransitService(BaseTransitService):
    def __init__(self):
        self.mta_subway_service = MtaSubwayService()
        self.mta_bus_service = MtaBusService()
        self.nyc_ferry_service = NycFerryService()
        self.nj_transit_service = NjTransitService()
        self.transit_lines = []
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    
    def get_loop(self):
        return asyncio.get_event_loop()

    async def update_transit_lines(self):
        transit_lines = []

        futures = [
            self.get_loop().run_in_executor(
                self.executor, 
                self.mta_subway_service.get_transit_lines, 
                '626S', # 86 St
                '1', # southbound
                'gtfs', # 1234567
                7 # minutes
            ),
            self.get_loop().run_in_executor(
                self.executor, 
                self.mta_subway_service.get_transit_lines, 
                'Q05S', # 96 St
                '1', # southbound
                'gtfs-nqrw', # NQRW
                5 # minutes
            ),
            # self.get_loop().run_in_executor(
            #     self.executor, 
            #     self.mta_bus_service.get_transit_lines, 
            #     '401921', # E 86 ST/3 AV
            #     '1', # westbound
            #     0 # minutes
            # ),
            # self.get_loop().run_in_executor(
            #     self.executor, 
            #     self.mta_bus_service.get_transit_lines, 
            #     '401957', # E 96 ST/3 AV
            #     '1', # westbound
            #     0 # minutes
            # ),
            self.get_loop().run_in_executor(
                self.executor, 
                self.mta_bus_service.get_transit_lines, 
                '401718', # 1 AV/E 93 ST
                '0', # northbound
                5 # minutes
            ),
            self.get_loop().run_in_executor(
                self.executor, 
                self.mta_bus_service.get_transit_lines, 
                '404947', # LEXINGTON AV/E 92 ST
                '1', # southbound
                0 # minutes
            ),
            self.get_loop().run_in_executor(
                self.executor, 
                self.nyc_ferry_service.get_transit_lines, 
                '113', # East 90th Street
                '0', # southbound
                15 # minutes
            ),
            self.get_loop().run_in_executor(
                self.executor, 
                self.nj_transit_service.get_transit_lines, 
                'PABT',
                '166',
                25 # minutes
            ),
            # self.get_loop().run_in_executor(
            #     self.executor, 
            #     self.nj_transit_service.get_transit_lines, 
            #     '12935', # BROAD AVE AT W EDSALL BLVD
            #     '166',
            #     0 # minutes
            # ),
            # self.get_loop().run_in_executor(
            #     self.executor, 
            #     self.nj_transit_service.get_transit_lines, 
            #     '13669', # FRANK W. BURR BLVD 590'N OF GLENWOOD AVE.
            #     '167',
            #     0 # minutes
            # ),
        ]
        for response in await asyncio.gather(*futures, return_exceptions=True):
            if isinstance(response, Exception):
                transit_lines.append(TransitLine(
                    key='ERR!',
                    name='ERR!',
                    description=f'{response}',
                    etas=[time.time() + 1 + 60 * 888888888],
                    color=[255, 0, 0],
                    eta_threshold_min=0
                ))
                strftime = time.strftime('%c', time.localtime())
                print(f'{strftime} {response}')
            else:
                transit_lines.extend(response)
        
        self.transit_lines = transit_lines

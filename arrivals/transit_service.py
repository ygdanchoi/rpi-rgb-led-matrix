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
TransitLine = collections.namedtuple('TransitLine', ['key', 'name', 'description', 'etas', 'color'])


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
                route_id = self.get_route_id(row)
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
                    route_id=self.get_route_id(row),
                    direction_id=self.get_direction_id(row)
                )
    
    def get_routes_path(self):
        pass

    def get_trips_path(self):
        pass

    def get_route_id(self, row):
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
    
    def get_route_id(self, row):
        return row[0]

    def get_trip_id(self, row):
        match = re.search(r'\d{6}_\w+\.{2}[NS]', row[2])
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
        return row[2]
    
    def get_transit_lines(self, stop_id, direction, gtfs_id):
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
                    color=self.colors[route_id]
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
    def get_transit_lines(self, stop_id, direction):
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
                    description=vehicle_journey['DestinationName'],
                    etas=[],
                    color=[0, 57, 166]
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
    
    def get_route_id(self, row):
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

    def get_transit_lines(self, stop_id, direction):
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
                    color=self.colors[trip.route_id]
                )).etas.append(eta)

        for transit_line in transit_lines_by_key.values():
            transit_line.etas.sort()

        return sorted(transit_lines_by_key.values(), key=lambda transit_line: transit_line.key)

class CompositeTransitService(BaseTransitService):
    def __init__(self):
        self.mta_subway_service = MtaSubwayService()
        self.mta_bus_service = MtaBusService()
        self.nyc_ferry_service = NycFerryService()
        self.transit_lines = []
        self.loop = asyncio.get_event_loop()

    async def update_transit_lines(self):
        transit_lines = []

        try:
            with concurrent.futures.ProcessPoolExecutor(max_workers=3) as executor:
                futures = [
                    self.loop.run_in_executor(
                        executor, 
                        self.mta_subway_service.get_transit_lines, 
                        '626S', # 86 St
                        '1', # southbound
                        'gtfs' # 1234567
                    ),
                    self.loop.run_in_executor(
                        executor, 
                        self.mta_subway_service.get_transit_lines, 
                        'Q05S', # 96 St
                        '1', #? southbound
                        'gtfs-nqrw' # NQRW
                    ),
                    self.loop.run_in_executor(
                        executor, 
                        self.mta_bus_service.get_transit_lines, 
                        '401921', # E 86 ST/3 AV
                        '1' # westbound
                    ),
                    self.loop.run_in_executor(
                        executor, 
                        self.mta_bus_service.get_transit_lines, 
                        '401957', # E 96 ST/3 AV
                        '1' # westbound
                    ),
                    # self.loop.run_in_executor(
                    #     executor, 
                    #     self.mta_bus_service.get_transit_lines, 
                    #     '404947', # LEXINGTON AV/E 92 ST
                    #     '1' # southbound
                    # ),
                    self.loop.run_in_executor(
                        executor, 
                        self.nyc_ferry_service.get_transit_lines, 
                        '113', # East 90th Street
                        '0' # southbound
                    )
                ]
                for response in await asyncio.gather(*futures):
                    transit_lines.extend(response)
        except Exception as error:
            transit_lines.append(TransitLine(
                key='ERR!',
                name='ERR!',
                description=f'{type(error).__name__}: {str(error)}',
                etas=[time.time() + 1 + 60 * 888888888],
                color=[255, 0, 0]
            ))
            traceback.print_exc()

        self.transit_lines = transit_lines

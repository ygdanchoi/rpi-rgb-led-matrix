import bisect
import collections
import csv
import json
import requests
import traceback

from datetime import datetime

import gtfs_realtime_pb2
import secrets

Trip = collections.namedtuple('Trip', ['trip_id', 'trip_headsign', 'route_id', 'direction_id'])
TransitLine = collections.namedtuple('TransitLine', ['key', 'name', 'description', 'etas', 'color'])

class BaseTransitService:
    def get_transit_lines():
        pass

class GtfsService(BaseTransitService):
    def __init__(self):
        self.trips = {}
        self.colors = {}

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

    def get_eta(self, trip_update, stop_id):
        return next(
            (stop_time_update.arrival.time for stop_time_update in trip_update.stop_time_update if stop_time_update.stop_id == stop_id),
            None
        )

class MtaSubwayService(GtfsService):
    def get_routes_path(self):
        return './gtfs/mta-subway/google_transit/routes.txt'

    def get_trips_path(self):
        return './gtfs/mta-subway/google_transit/trips.txt'
    
    def get_route_id(self, row):
        return row[0]

    def get_trip_id(self, row):
        return '_'.join(row[2].split('_')[1:])[:-3]
    
    def get_trip_headsign(self, row):
        return row[3]

    def get_direction_id(self, row):
        return row[4]
    
    def get_route_color(self, row):
        return row[7]
    
    def get_transit_lines(self, stop_id, direction, gtfs_id):
        transit_lines_by_key = {}

        response = requests.get(f'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2F{gtfs_id}', headers={
            'x-api-key': secrets.real_time_access_key
        })
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        trip_updates = (entity.trip_update for entity in feed.entity if entity.HasField('trip_update'))

        for trip_update in trip_updates:
            eta = self.get_eta(trip_update, stop_id)
            if not eta:
                continue

            trip = self.get_nearest_trip(trip_update.trip.trip_id)

            if not direction or direction == trip.direction_id:
                route_id = trip_update.trip.route_id
                key = f'{direction}-{route_id}'
                transit_lines_by_key.setdefault(key, TransitLine(
                    key=key,
                    name=route_id,
                    description=trip.trip_headsign,
                    etas=[],
                    color=self.colors[route_id]
                )).etas.append(eta)

        for transit_line in transit_lines_by_key.values():
            transit_line.etas.sort()
                
        return sorted(transit_lines_by_key.values(), key=lambda transit_line: transit_line.key)
    
    def get_nearest_trip(self, trip_id):
        if (trip_id in self.trips):
            return self.trips[trip_id]
        else:
            # TODO: account for route differences between weekday/Saturday/Sunday
            keys = sorted(key for key in self.trips.keys() if '_' in key and key.split('_')[1] in trip_id.split('_')[1])
            i = bisect.bisect_left(keys, trip_id)
            nearest_trip_id = keys[min(i, len(keys) - 1)]
            return self.trips[nearest_trip_id]

class MtaBusService(BaseTransitService):
    def get_transit_lines(self, stop_id, direction):
        transit_lines_by_key = {}

        response = requests.get("https://bustime.mta.info/api/siri/stop-monitoring.json", params={
            'key': secrets.bus_time_api_key,
            'OperatorRef': 'MTA',
            'MonitoringRef': stop_id
        })
        stop_visits = json.loads(response.content)['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0]['MonitoredStopVisit']
        vehicle_journeys = (stop_visit['MonitoredVehicleJourney'] for stop_visit in stop_visits)

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

            trip = self.trips[trip_update.trip.trip_id]
            
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

    def get_transit_lines(self):
        transit_lines = []

        try:
            transit_lines.extend(self.mta_subway_service.get_transit_lines(
                '626S', # 86 St
                '1', # southbound
                'gtfs' # 1234567
            ))
            transit_lines.extend(self.mta_subway_service.get_transit_lines(
                'Q05S', # 96 St
                '1', # southbound
                'gtfs-nqrw', # NQRW
            ))
            transit_lines.extend(self.mta_bus_service.get_transit_lines(
                '404947', # LEXINGTON AV/E 92 ST
                '1' # southbound
            ))
            transit_lines.extend(self.nyc_ferry_service.get_transit_lines(
                '113', # 86 St
                '0' # southbound
            ))
        except Exception as error:
            transit_lines.append(TransitLine(
                name='ERR!',
                description=str(error),
                etas=[2147483647],
                color=[255, 0, 0]
            ))
            traceback.print_exc()

        return transit_lines

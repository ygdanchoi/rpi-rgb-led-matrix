#!/usr/bin/env python3
from datetime import datetime
from samplebase import SampleBase
from rgbmatrix import graphics

import bisect
import collections
import csv
import gtfs_realtime_pb2
import json
import requests
import secrets
import threading
import time
import traceback

Trip = collections.namedtuple('Trip', ['trip_headsign', 'route_id', 'direction_id'])
TransitLine = collections.namedtuple('TransitLine', ['route_id', 'trip_id', 'trip_headsign', 'eta', 'color'])
cached_rows = []

# class TransitLineNew:
#     def __init__(self, name, direction, description, etas, color):
#         self.name = name
#         self.direction = direction
#         self.description = description
#         self.etas = etas
#         self.color = color

#     def key(self):
#         return f'{self.name}-{self.direction}'

class TransitService:
    def get_arrivals():
        return {}

class GtfsService:
    def get_gtfs_eta(self, trip_update, stop_id, current_time):
        arrival_time = next(
            (stop_time_update.arrival.time for stop_time_update in trip_update.stop_time_update if stop_time_update.stop_id == stop_id),
            None
        )

        if arrival_time is None:
            return -1
        else:
            return int(round((arrival_time - current_time) / 60, 0))

class MtaSubwayService(GtfsService):
    def __init__(self):
        self.trips = {}
        self.colors = {}

        with open('./gtfs/mta-subway/google_transit/trips.txt') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            should_skip_header_row = True
            for row in csv_reader:
                if should_skip_header_row:
                    should_skip_header_row = False
                    continue
                route_id = row[0]
                trip_id = '_'.join(row[2].split('_')[1:])[:-3]
                trip_headsign = row[3]
                direction_id = row[4]

                self.trips[trip_id] = Trip(
                    trip_headsign=trip_headsign,
                    route_id=route_id,
                    direction_id=direction_id
                )

        with open('./gtfs/mta-subway/google_transit/routes.txt') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            should_skip_header_row = True
            for row in csv_reader:
                if should_skip_header_row:
                    should_skip_header_row = False
                    continue
                route_id = row[0]
                route_color = row[7]

                if len(route_color) == 6:
                    self.colors[route_id] = [
                        int(route_color[0:2], 16),
                        int(route_color[2:4], 16),
                        int(route_color[4:6], 16)
                    ]
                else:
                    self.colors[route_id] = [255, 255, 255]
    
    def get_arrivals(self, url, stop_id, direction, current_time):
        arrivals = {}

        response = requests.get(url, headers={
            'x-api-key': secrets.real_time_access_key
        })
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        entities = feed.entity

        for entity in filter(lambda entity: entity.HasField('trip_update'), entities):
            trip_update = entity.trip_update
            eta = self.get_gtfs_eta(trip_update, stop_id, current_time)
            trip_id = trip_update.trip.trip_id

            if eta > 0 and direction in trip_id:
                route_id = trip_update.trip.route_id
                if route_id not in arrivals:
                    arrivals[route_id] = []

                if (trip_id not in self.trips):
                    trip_keys = list(sorted(filter(lambda key: '_' in key and key.split('_')[1] in trip_id.split('_')[1], self.trips.keys())))
                    i = bisect.bisect_left(trip_keys, trip_id)
                    trip_id = trip_keys[min(i, len(trip_keys) - 1)]

                arrivals[route_id].append(TransitLine(
                    route_id=route_id,
                    trip_id=trip_id,
                    trip_headsign=self.trips[trip_id].trip_headsign,
                    eta=eta,
                    color=self.colors[route_id]
                ))
        return arrivals

class MtaBusService:
    def __init__(self):
        self.trips = {}
    
    def get_arrivals(self, stop_id, current_time):
        arrivals = {}

        response = requests.get("https://bustime.mta.info/api/siri/stop-monitoring.json", params={
            'key': secrets.bus_time_api_key,
            'OperatorRef': 'MTA',
            'MonitoringRef': stop_id
        })

        stop_visits = json.loads(response.content)['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0]['MonitoredStopVisit']
        vehicle_journeys = [stop_visit['MonitoredVehicleJourney'] for stop_visit in stop_visits]
        for vehicle_journey in sorted(vehicle_journeys, key=lambda vehicle_journey: vehicle_journey['PublishedLineName']):
            published_line_name = vehicle_journey['PublishedLineName']
            destination_name = vehicle_journey['DestinationName']
            monitored_call = vehicle_journey['MonitoredCall']
            expected_arrival_time = datetime.fromisoformat(
                monitored_call['ExpectedArrivalTime'] if 'ExpectedArrivalTime' in monitored_call else monitored_call['AimedArrivalTime']
            )
            eta = int(round((expected_arrival_time.timestamp() - current_time) / 60, 0))

            if eta > 0:
                if published_line_name not in arrivals:
                    arrivals[published_line_name] = []   
                arrivals[published_line_name].append(TransitLine(
                    route_id=published_line_name,
                    trip_id=published_line_name,
                    trip_headsign=destination_name,
                    eta=eta,
                    color=[0, 57, 166]
                ))
        
        return arrivals

class NycFerryService(GtfsService):
    def __init__(self):
        self.trips = {}
        self.colors = {}

        with open('./gtfs/nyc-ferry/google_transit/trips.txt') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            should_skip_header_row = True
            for row in csv_reader:
                if should_skip_header_row:
                    should_skip_header_row = False
                    continue
                route_id = row[0]
                trip_id = row[2]
                trip_headsign = row[3]
                direction_id = row[5]

                self.trips[trip_id] = Trip(
                    trip_headsign=trip_headsign,
                    route_id=route_id,
                    direction_id=direction_id
                )

        with open('./gtfs/nyc-ferry/google_transit/routes.txt') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            should_skip_header_row = True
            for row in csv_reader:
                if should_skip_header_row:
                    should_skip_header_row = False
                    continue
                route_id = row[0]
                route_color = row[5]

                if len(route_color) == 6:
                    self.colors[route_id] = [
                        int(route_color[0:2], 16),
                        int(route_color[2:4], 16),
                        int(route_color[4:6], 16)
                    ]
                else:
                    self.colors[route_id] = [255, 255, 255]

    def get_arrivals(self, stop_id, direction_id, current_time):
        arrivals = {}

        response = requests.get('http://nycferry.connexionz.net/rtt/public/utility/gtfsrealtime.aspx/tripupdate')
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        entities = feed.entity

        for entity in filter(lambda entity: entity.HasField('trip_update'), entities):
            trip_update = entity.trip_update
            eta = self.get_gtfs_eta(trip_update, stop_id, current_time)
            trip_id = trip_update.trip.trip_id

            if eta > 0 and self.trips[trip_id].direction_id == direction_id:
                route_id = self.trips[trip_id].route_id
                if route_id not in arrivals:
                    arrivals[route_id] = []
                arrivals[route_id].append(TransitLine(
                    route_id=route_id,
                    trip_id=trip_id,
                    trip_headsign=self.trips[trip_id].trip_headsign,
                    eta=eta,
                    color=self.colors[route_id]
                ))

        return arrivals

class FetchArrivals(threading.Thread):
    def run(self):
        self.mta_subway_service = MtaSubwayService()
        self.mta_bus_service = MtaBusService()
        self.nyc_ferry_service = NycFerryService()

        while True:
            self.fetch_arrivals()
            time.sleep(30)
    
    def fetch_arrivals(self):
        arrivals = {}
        current_time = time.time()

        try:
            arrivals.update(self.mta_subway_service.get_arrivals(
                'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs', #1234567
                '626S', # 86 St
                '..S',
                current_time
            ))
            arrivals.update(self.mta_subway_service.get_arrivals(
                'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw',
                'Q05S', # 96 St,
                '..S',
                current_time
            ))
            arrivals.update(self.mta_bus_service.get_arrivals(
                '404947',
                current_time
            ))
            arrivals.update(self.nyc_ferry_service.get_arrivals(
                '113', # 86 St
                '0', # southbound
                current_time
            ))
        except Exception as error:
            arrivals['ERR!'] = [TransitLine(
                route_id='ERR!',
                trip_id='ERR!',
                trip_headsign=str(error),
                eta=0,
                color=[255, 0, 0]
            )]
            traceback.print_exc()

        cached_rows.clear()
        cached_rows.extend(arrivals.values())

class RgbMatrixView(SampleBase):
    def __init__(self, *args, **kwargs):
        super(RgbMatrixView, self).__init__(*args, **kwargs)

    def run(self):
        offscreen_canvas = self.matrix.CreateFrameCanvas()
        font = graphics.Font()
        font.LoadFont("../../../fonts/tom-thumb.bdf")
        vertical_offset = 0
        vertical_offset_slowdown = 1
        textbox_height = 7
        dark_mode = graphics.Color(47, 0, 0)
        
        while True:
            hh = datetime.now().hour
            is_light_mode = 6 <= hh and hh < 22

            offscreen_canvas.Clear()

            for i, row in enumerate(cached_rows if len(cached_rows) < 4 else cached_rows + cached_rows):
                line = f'{row[0].route_id}'
                line += ' ' * (5 - len(line))
                line += row[0].trip_headsign[:17]
                line += ' ' * (24 - len(line))

                etas = [str(eta.eta) for eta in sorted(row)]
                line += etas[0]
                e = 1
                while (e < len(etas) and len(line) + 1 + len(etas[e]) + 1 <= 32):
                    line += ',' + etas[e]
                    e += 1
                line += 'm'
                
                graphics.DrawText(
                    offscreen_canvas,
                    font,
                    1,
                    7 + i * textbox_height - vertical_offset // vertical_offset_slowdown,
                    graphics.Color(*row[0].color) if is_light_mode else dark_mode,
                    line
                )

                for y in range(offscreen_canvas.height - 7, offscreen_canvas.height):
                    for x in range(0, offscreen_canvas.width):
                        offscreen_canvas.SetPixel(x, y, 0, 0, 0)
                
                graphics.DrawText(
                    offscreen_canvas,
                    font,
                    1,
                    offscreen_canvas.height - 1,
                    graphics.Color(255, 255, 255) if is_light_mode else dark_mode,
                    datetime.now().strftime('%a, %b %d, %Y  %-I:%M:%S %p')
                )
            
            vertical_offset += 1
            if len(cached_rows) < 4 or vertical_offset // vertical_offset_slowdown >= textbox_height * len(cached_rows):
                vertical_offset = 0
            
            offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)

            time.sleep(0.1)

# Main function
if __name__ == "__main__":
    FetchArrivals().start()
    RgbMatrixView().process()
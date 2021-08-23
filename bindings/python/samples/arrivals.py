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
import sortedcollections
import threading
import time

Trip = collections.namedtuple('Trip', ['trip_headsign', 'route_id'])
Row = collections.namedtuple('Row', ['route_id', 'trip_id', 'trip_headsign', 'etas', 'color'])

cached_arrivals = sortedcollections.OrderedDict()
trips = {}
colors = {}

with open('../../../../arrivals/google_transit/trips.txt') as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    should_skip_header_row = True
    for row in csv_reader:
        if should_skip_header_row:
            should_skip_header_row = False
            continue
        route_id = row[0]
        trip_id = '_'.join(row[2].split('_')[1:])[:-3]
        trip_headsign = row[3]

        trips[trip_id] = Trip(
            trip_headsign=trip_headsign,
            route_id=route_id
        )

with open('../../../../arrivals/google_transit/routes.txt') as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    should_skip_header_row = True
    for row in csv_reader:
        if should_skip_header_row:
            should_skip_header_row = False
            continue
        route_id = row[0]
        route_color = row[7]

        if len(route_color) == 6:
            colors[route_id] = [
                int(route_color[0:2], 16),
                int(route_color[2:4], 16),
                int(route_color[4:6], 16)
            ]
        else:
            colors[route_id] = [255, 255, 255]
        
with open('../../../../arrivals/google_transit_ferry/trips.txt') as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    should_skip_header_row = True
    for row in csv_reader:
        if should_skip_header_row:
            should_skip_header_row = False
            continue
        route_id = row[0]
        trip_id = row[2]
        trip_headsign = row[3]

        trips[trip_id] = Trip(
            trip_headsign=trip_headsign,
            route_id=route_id
        )

with open('../../../../arrivals/google_transit_ferry/routes.txt') as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    should_skip_header_row = True
    for row in csv_reader:
        if should_skip_header_row:
            should_skip_header_row = False
            continue
        route_id = row[0]
        route_color = row[5]

        if len(route_color) == 6:
            colors[route_id] = [
                int(route_color[0:2], 16),
                int(route_color[2:4], 16),
                int(route_color[4:6], 16)
            ]
        else:
            colors[route_id] = [255, 255, 255]

class FetchArrivals(threading.Thread):
    def run(self):
        while True:
            self.fetch_arrivals()
            time.sleep(30)
    
    def fetch_arrivals(self):
        arrivals = sortedcollections.OrderedDict()
        current_time = time.time()

        self.put_gtfs_arrivals(
            'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw',
            'Q05S', # 96 St,
            '..S',
            arrivals,
            current_time
        )
        self.put_gtfs_arrivals(
            'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs', #1234567
            '626S', # 86 St
            '..S',
            arrivals,
            current_time
        )
        self.put_siri_arrivals(
            '404947',
            arrivals,
            current_time
        )
        self.put_gtfs_arrivals_ferry(
            '113', # 86 St
            arrivals,
            current_time
        )

        cached_arrivals.clear()
        cached_arrivals.update(arrivals)
    
    def put_siri_arrivals(self, stop_id, arrivals, current_time):
        response = requests.get("https://bustime.mta.info/api/siri/stop-monitoring.json", params={
            'key': secrets.bus_time_api_key,
            'OperatorRef': 'MTA',
            'MonitoringRef': stop_id
        })

        stop_visits = json.loads(response.content)['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0]['MonitoredStopVisit']
        vehicle_journeys = [stop_visit['MonitoredVehicleJourney'] for stop_visit in stop_visits]
        for vehicle_journey in vehicle_journeys:
            published_line_name = vehicle_journey['PublishedLineName']
            destination_name = vehicle_journey['DestinationName']
            monitored_call = vehicle_journey['MonitoredCall']
            expected_arrival_time = datetime.fromisoformat(
                monitored_call['ExpectedArrivalTime'] if 'ExpectedArrivalTime' in monitored_call else monitored_call['AimedArrivalTime']
            )
            eta = int(round((expected_arrival_time.timestamp() - current_time) / 60, 0))

            if eta >= 0 and published_line_name not in arrivals:
                arrivals[published_line_name] = []   
                trips[published_line_name] = destination_name
                colors[published_line_name] = [0, 57, 166]
            arrivals[published_line_name].append(eta)

    def put_gtfs_arrivals(self, url, stop_id, direction, arrivals, current_time):
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

            if eta >= 0 and direction in trip_id:
                route_id = trip_update.trip.route_id
                if route_id not in arrivals:
                    arrivals[route_id] = []

                if (trip_id not in trips):
                    trip_keys = list(filter(lambda key: '_' in key and key.split('_')[1] in trip_id.split('_')[1], trips.keys()))
                    i = bisect.bisect_left(trip_keys, trip_id)
                    trip_id = trip_keys[i]

                arrivals[route_id].append(Row(
                    route_id=route_id,
                    trip_id=trip_id,
                    trip_headsign=trips[trip_id].trip_headsign,
                    etas=eta,
                    color=colors[route_id]
                ))

    def put_gtfs_arrivals_ferry(self, stop_id, arrivals, current_time):
        response = requests.get('http://nycferry.connexionz.net/rtt/public/utility/gtfsrealtime.aspx/tripupdate')
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        entities = feed.entity

        for entity in filter(lambda entity: entity.HasField('trip_update'), entities):
            trip_update = entity.trip_update
            eta = self.get_gtfs_eta(trip_update, stop_id, current_time)

            if eta >= 0:
                route_id = trips[trip_update.trip.trip_id].route_id
                if route_id not in arrivals:
                    arrivals[route_id] = []
                arrivals[route_id].append(Row(
                    route_id=route_id,
                    trip_id=trip_id,
                    trip_headsign=trips[trip_id].trip_headsign,
                    etas=eta,
                    color=colors[route_id]
                ))

    def get_gtfs_eta(self, trip_update, stop_id, current_time):
        arrival_time = next(
            (stop_time_update.arrival.time for stop_time_update in trip_update.stop_time_update if stop_time_update.stop_id == stop_id),
            None
        )

        if arrival_time is None:
            return -1
        else:
            return int(round((arrival_time - current_time) / 60, 0))

class DrawArrivals(SampleBase):
    def __init__(self, *args, **kwargs):
        super(DrawArrivals, self).__init__(*args, **kwargs)

    def run(self):
        offscreen_canvas = self.matrix.CreateFrameCanvas()
        font = graphics.Font()
        font.LoadFont("../../../fonts/tom-thumb.bdf")
        vertical_offset = 0
        vertical_offset_slowdown = 1
        textbox_height = 7
        dark_mode = graphics.Color(15, 0, 0)
        
        while True:
            hh = datetime.now().hour
            is_light_mode = 5 <= hh and hh <= 22

            offscreen_canvas.Clear()
            rows = list(cached_arrivals.items())
            print(cached_arrivals)
            for i, item in enumerate(rows + rows):
                route_id = item[0]
                row = item[1]

                line = f'{route_id}'
                line += ' ' * (5 - len(line))
                line += row.trip_headsign[:12]
                line += ' ' * (17 - len(line))
                line += ' ' + ', '.join([str(eta) for eta in row.etas[:3]]) + ' min'
                
                graphics.DrawText(
                    offscreen_canvas,
                    font,
                    1,
                    7 + i * textbox_height - vertical_offset // vertical_offset_slowdown,
                    graphics.Color(*row.color) if is_light_mode else dark_mode,
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
                    datetime.now().strftime('%a, %b %d, %Y %-I:%M:%S %p')
                )
            
            if (len(rows) > 3):
                vertical_offset += 1
                if vertical_offset // vertical_offset_slowdown >= textbox_height * len(rows):
                    vertical_offset = 0
            
            offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)

            time.sleep(0.1)

# Main function
if __name__ == "__main__":
    FetchArrivals().start()
    DrawArrivals().process()
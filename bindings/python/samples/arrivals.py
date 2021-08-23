#!/usr/bin/env python3
from datetime import datetime
from samplebase import SampleBase
from rgbmatrix import graphics

import collections
import csv
import gtfs_realtime_pb2
import json
import requests
import secrets
import sortedcollections
import threading
import time

Row = collections.namedtuple('Row', ['route_id', 'trip_headsign', 'etas', 'color'])

rows = []
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
        trip_id_digest = row[2].split('_')[2]
        trip_headsign = row[3]

        if ('..S' in trip_id_digest):
            trips[route_id] = trip_headsign

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

class FetchArrivals(threading.Thread):
    def run(self):
        while True:
            self.fetch_arrivals()
            time.sleep(30)
    
    def fetch_arrivals(self):
        arrivals = sortedcollections.OrderedDict()
        current_time = time.time()

        self.put_gtfs_arrivals(
            'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw', #NQRW
            'Q05S', # 96 St
            arrivals,
            current_time
        )
        self.put_gtfs_arrivals(
            'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs', #1234567
            '626S', # 86 St
            arrivals,
            current_time
        )
        self.put_siri_arrivals(
            '404947',
            arrivals,
            current_time
        )

        self.update_rows(arrivals)
    
    def put_siri_arrivals(self, stop_id, arrivals, current_time):
        response = requests.get("https://bustime.mta.info/api/siri/stop-monitoring.json", params={
            'key': secrets.bus_time_api_key,
            'OperatorRef': 'MTA',
            'MonitoringRef': stop_id
        })
        siri = json.loads(response)
        print(siri)

    def put_gtfs_arrivals(self, url, stop_id, arrivals, current_time):
        response = requests.get(url, headers={
            'x-api-key': secrets.real_time_access_key
        })
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        entities = feed.entity

        for entity in filter(lambda entity: entity.HasField('trip_update'), entities):
            trip_update = entity.trip_update
            eta = self.get_stfs_eta(trip_update, stop_id, current_time)

            if eta >= 0 and '..S' in trip_update.trip.trip_id:
                route_id = trip_update.trip.route_id
                if route_id not in arrivals:
                    arrivals[route_id] = []    
                arrivals[route_id].append(eta)

    def get_stfs_eta(self, trip_update, stop_id, current_time):
        arrival_time = next(
            (stop_time_update.arrival.time for stop_time_update in trip_update.stop_time_update if stop_time_update.stop_id == stop_id),
            None
        )

        if arrival_time is None:
            return -1
        else:
            return int(round((arrival_time - current_time) / 60, 0))

    def update_rows(self, arrivals):
        rows.clear()

        for item in arrivals.items():
            route_id = item[0]
            etas = ', '.join([str(eta) for eta in item[1][:3]])
            trip_headsign = trips[route_id]
            color = colors[route_id]

            rows.append(Row(
                route_id,
                trip_headsign,
                etas,
                color
            ))

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
        
        while True:
            offscreen_canvas.Clear()
            for i, row in enumerate(rows + rows):
                line = f'{row.route_id}'
                line += ' ' * (4 - len(line))
                line += row.trip_headsign[:12]
                line += ' ' * (17 - len(line))
                line += f' {row.etas} min'
                
                graphics.DrawText(
                    offscreen_canvas,
                    font,
                    1,
                    7 + i * textbox_height - vertical_offset // vertical_offset_slowdown,
                    graphics.Color(*row.color),
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
                    graphics.Color(255, 255, 255),
                    datetime.now().strftime('%a %b %d, %Y  %T %p')
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
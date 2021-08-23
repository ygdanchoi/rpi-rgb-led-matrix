#!/usr/bin/env python3
from samplebase import SampleBase
from rgbmatrix import graphics

import collections
import csv
import gtfs_realtime_pb2
import requests
import secrets
import sortedcollections
import threading
import time

Row = collections.namedtuple('Row', ['route_id', 'route_text_color', 'trip_headsign', 'etas'])

lines = []
trips = {}

with open('../../../../arrivals/google_transit/trips.txt') as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    should_skip = True
    for row in csv_reader:
        if should_skip:
            should_skip = False
            continue
        route_id = row[0]
        direction = row[2].split('_')[2].split('..')[0]
        trip_headsign = row[3]

        if (direction == '..S'):
            trips[route_id] = trip_headsign
    print(trips)

class FetchArrivals(threading.Thread):
    def run(self):
        while True:
            self.fetch_arrivals()
            time.sleep(30)
    
    def fetch_arrivals(self):
        arrivals = sortedcollections.OrderedDict()
        current_time = time.time()

        self.put_arrivals(
            'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw', #NQRW
            'Q05S', # 96 St
            arrivals,
            current_time
        )
        self.put_arrivals(
            'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs', #1234567
            '626S', # 86 St
            arrivals,
            current_time
        )

        # merged_arrivals = self.get_merged_arrivals(arrivals)
        self.update_lines(arrivals)

    def put_arrivals(self, url, stop_id, arrivals, current_time):
        response = requests.get(url, headers={
            'x-api-key': secrets.real_time_access_key
        })
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        entities = feed.entity

        for entity in filter(lambda entity: entity.HasField('trip_update'), entities):
            trip_update = entity.trip_update
            eta = self.get_eta(trip_update, stop_id, current_time)

            if eta >= 0 and '..S' in trip_update.trip.trip_id:
                route_id = trip_update.trip.route_id
                if route_id not in arrivals:
                    arrivals[route_id] = []    
                arrivals[route_id].append(eta)

    def get_eta(self, trip_update, stop_id, current_time):
        arrival_time = next(
            (stop_time_update.arrival.time for stop_time_update in trip_update.stop_time_update if stop_time_update.stop_id == stop_id),
            None
        )

        if arrival_time is None:
            return -1
        else:
            return int(round((arrival_time - current_time) / 60, 0))

    def get_merged_arrivals(self, arrivals):
        merged_arrivals = sortedcollections.OrderedDict()

        groups = [
            {'2', '4', '5'},
            {'6', '6X'},
            {'Q'},
            {} # wildcard
        ]

        for group in groups:
            keys = list(sorted(filter(lambda key: len(group) == 0 or key in group, arrivals.keys())))

            if (len(keys) == 0):
                continue

            merged_key = '/'.join(keys) if len(keys) == 2 else ''.join(keys)
            if merged_key == '245':
                merged_key = '2-5'
            elif merged_key == '2/4':
                merged_key = '2-4'
            elif merged_key == '4/5':
                merged_key = '4-5'
            merged_arrivals[merged_key] = []

            for key in keys:
                etas = arrivals[key]
                merged_arrivals[merged_key].extend(etas)
                del arrivals[key]
            
            merged_arrivals[merged_key].sort()
        
        return merged_arrivals

    def update_lines(self, arrivals):
        lines.clear()

        for item in arrivals.items():
            route_id = item[0]
            etas = ', '.join([str(eta) for eta in item[1][:4]])
            trip_headsign = trips[route_id]

            line = f'({route_id})'
            line += ' ' * (7 - len(line))
            line += f'{etas} min'
            lines.append(line)
        
        while (len(lines) < 4):
            lines.append('')

class DrawArrivals(SampleBase):
    def __init__(self, *args, **kwargs):
        super(DrawArrivals, self).__init__(*args, **kwargs)

    def run(self):
        offscreen_canvas = self.matrix.CreateFrameCanvas()
        font = graphics.Font()
        font.LoadFont("../../../fonts/5x7.bdf")
        textColor = graphics.Color(127, 0, 255)
        offset = 0
        offset_slowdown = 3
        
        while True:
            offscreen_canvas.Clear()

            for i, line in enumerate(lines + lines):
                graphics.DrawText(
                    offscreen_canvas,
                    font,
                    1,
                    7 + i * 8 - offset // offset_slowdown,
                    textColor,
                    line
                )

            if (len(lines) > 4):
                offset += 1
                if offset // offset_slowdown > 8 * len(lines):
                    offset = 0
            
            offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)

            time.sleep(0.05)

# Main function
if __name__ == "__main__":
    FetchArrivals().start()
    DrawArrivals().process()
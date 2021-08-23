#!/usr/bin/env python3
from samplebase import SampleBase
from rgbmatrix import graphics

import collections
import gtfs_realtime_pb2
import requests
import secrets
import sortedcollections
import threading
import time

lines = ['hello world', 'uwu','','']

def get_eta(trip_update, stop_id, current_time):
    arrival_time = next(
        (stop_time_update.arrival.time for stop_time_update in trip_update.stop_time_update if stop_time_update.stop_id == stop_id),
        None
    )

    if arrival_time is None:
        return -1
    else:
        return int(round((arrival_time - current_time) / 60, 0))

def put_arrivals(url, stop_id, arrivals, current_time):
    response = requests.get(url, headers={
        'x-api-key': secrets.real_time_access_key
    })
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    entities = feed.entity

    for entity in filter(lambda entity: entity.HasField('trip_update'), entities):
        trip_update = entity.trip_update
        eta = get_eta(trip_update, stop_id, current_time)

        if eta >= 0 and '..S' in trip_update.trip.trip_id:
            route_id = trip_update.trip.route_id
            arrivals[route_id].append(eta)

def get_merged_arrivals(arrivals):
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

def update_lines(arrivals):
    lines.clear()

    for item in arrivals.items():
        route_id = item[0]
        etas = ', '.join([str(eta) for eta in item[1][:4]])

        line = f'({route_id})'
        line += ' ' * (7 - len(line))
        line += f'{etas} min'
        lines.append(line)
    
    while (len(lines) < 4):
        lines.append('')

def fetch_arrivals():
    arrivals = collections.defaultdict(list)
    current_time = time.time()

    put_arrivals(
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw', #NQRW
        'Q05S', # 96 St
        arrivals,
        current_time
    )
    put_arrivals(
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs', #1234567
        '626S', # 86 St
        arrivals,
        current_time
    )

    update_lines(get_merged_arrivals(arrivals))

class FetchArrivals(threading.Thread):
    def run(self):
        while True:
            fetch_arrivals()
            time.sleep(10)

class Arrivals(SampleBase):
    def __init__(self, *args, **kwargs):
        super(Arrivals, self).__init__(*args, **kwargs)

    def run(self):
        offscreen_canvas = self.matrix.CreateFrameCanvas()
        font = graphics.Font()
        font.LoadFont("../../../fonts/5x7.bdf")
        textColor = graphics.Color(127, 0, 255)
        offset = 0
        
        while True:

            offscreen_canvas.Clear()

            for i, line in enumerate(lines + lines):
                graphics.DrawText(
                    offscreen_canvas,
                    font,
                    1,
                    7 + i * 8 - offset,
                    textColor,
                    line
                )

            offset += 1
            if offset > 8 * len(lines):
                offset = 0
            offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)

            time.sleep(0.05)

# Main function
if __name__ == "__main__":
    FetchArrivals().start()
    arrivals = Arrivals()
    if (not arrivals.process()):
        arrivals.print_help()
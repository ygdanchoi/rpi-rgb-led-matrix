#!/usr/bin/env python3
from samplebase import SampleBase
from rgbmatrix import graphics

import aiohttp
import asyncio
import collections
import gtfs_realtime_pb2
import secrets
import sortedcollections
import time

lines = ['hello world']

def get_eta(trip_update, stop_id, current_time):
    arrival_time = next(
        (stop_time_update.arrival.time for stop_time_update in trip_update.stop_time_update if stop_time_update.stop_id == stop_id),
        None
    )

    if arrival_time is None:
        return -1
    else:
        return int(round((arrival_time - current_time) / 60, 0))

async def put_arrivals(url, stop_id, arrivals, session, current_time):
    async with session.get(url, headers={
        'x-api-key': secrets.real_time_access_key
    }) as response:
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(await response.read())
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

async def fetch_arrivals():
    while True:
        async with aiohttp.ClientSession() as session:
            arrivals = collections.defaultdict(list)
            tasks = []
            current_time = time.time()

            tasks.append(asyncio.ensure_future(put_arrivals(
                'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw', #NQRW
                'Q05S', # 96 St
                arrivals,
                session,
                current_time
            )))
            tasks.append(asyncio.ensure_future(put_arrivals(
                'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs', #1234567
                '626S', # 86 St
                arrivals,
                session,
                current_time
            )))
            await asyncio.gather(*tasks)

            update_lines(get_merged_arrivals(arrivals))
            print(lines)
        await asyncio.sleep(10)

async def draw_arrivals():
    arrivals = Arrivals()
    if (not arrivals.process()):
        arrivals.print_help()
    while True:
        await arrivals.step()
        await asyncio.sleep(0.05)

class Arrivals(SampleBase):
    def __init__(self, *args, **kwargs):
        super(Arrivals, self).__init__(*args, **kwargs)
        self.offscreen_canvas = None
        self.font = None
        self.textColor = None
        self.pos = 0

    def run(self):
        self.offscreen_canvas = self.matrix.CreateFrameCanvas()
        self.font = graphics.Font()
        self.font.LoadFont("../../../fonts/5x7.bdf")
        self.textColor = graphics.Color(255, 255, 0)
    
    async def step(self):
        if (not self.offscreen_canvas):
            return
        
        print(self.offscreen_canvas)
        self.offscreen_canvas.Clear()
        for i in range(8):
            graphics.DrawText(self.offscreen_canvas, self.font, 1, 7 + i * 8 - self.pos, self.textColor, lines[i % len(lines)])
        self.pos += 1
        if (self.pos >= 8 * len(lines)):
            self.pos = 0

        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)

# Main function
if __name__ == "__main__":
    asyncio.ensure_future(fetch_arrivals())
    asyncio.ensure_future(draw_arrivals())
    asyncio.get_event_loop().run_forever()
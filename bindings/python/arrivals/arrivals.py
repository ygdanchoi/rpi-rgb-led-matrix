#!/usr/bin/env python3
from datetime import datetime

import bisect
import collections
import csv
import gtfs_realtime_pb2
import json
import os
import requests
import secrets
import threading
import time
import traceback

if os.name != 'nt':
    from samplebase import SampleBase
    from rgbmatrix import graphics

Trip = collections.namedtuple('Trip', ['trip_id', 'trip_headsign', 'route_id', 'direction_id'])
TransitLine = collections.namedtuple('TransitLine', ['route_id', 'trip_headsign', 'etas', 'color'])
Row = collections.namedtuple('Row', ['text', 'color'])

# class TransitLineNew:
#     def __init__(self, key, name, direction, description, etas, color):
#         self.key = key
#         self.name = name
#         self.direction = direction
#         self.description = description
#         self.etas = etas
#         self.color = color

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
                route_id = self.get_route_id(row)
                trip_id = self.get_trip_id(row)
                trip_headsign = self.get_trip_headsign(row)
                direction_id = self.get_direction_id(row)

                self.trips[trip_id] = Trip(
                    trip_id=trip_id,
                    trip_headsign=trip_headsign,
                    route_id=route_id,
                    direction_id=direction_id
                )

        with open(self.get_routes_path()) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            next(csv_reader) # skip header

            for row in csv_reader:
                route_id = self.get_route_id(row)
                route_color = self.get_route_color(row)

                if len(route_color) == 6:
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

    def get_gtfs_eta(self, trip_update, stop_id, current_time):
        arrival_time = next(
            (stop_time_update.arrival.time for stop_time_update in trip_update.stop_time_update if stop_time_update.stop_id == stop_id),
            None
        )

        if arrival_time is None:
            return -1
        else:
            return arrival_time

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
    
    def get_transit_lines(self, url, stop_id, direction, current_time):
        transit_lines_by_key = {}

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

            if eta > current_time and direction in trip_id:
                if (trip_id not in self.trips):
                    trip_keys = list(sorted(filter(lambda key: '_' in key and key.split('_')[1] in trip_id.split('_')[1], self.trips.keys())))
                    i = bisect.bisect_left(trip_keys, trip_id)
                    trip_id = trip_keys[min(i, len(trip_keys) - 1)]

                route_id = trip_update.trip.route_id
                if route_id not in transit_lines_by_key:
                    transit_lines_by_key[route_id] = TransitLine(
                        route_id=route_id,
                        trip_headsign=self.trips[trip_id].trip_headsign,
                        etas=[],
                        color=self.colors[route_id]
                    )

                transit_lines_by_key[route_id].etas.append(eta)
        return transit_lines_by_key.values()

class MtaBusService(BaseTransitService):
    def get_transit_lines(self, stop_id, current_time):
        transit_lines_by_key = {}

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
            eta = expected_arrival_time.timestamp()

            if eta > current_time:
                if published_line_name not in transit_lines_by_key:
                    transit_lines_by_key[published_line_name] = TransitLine(
                        route_id=published_line_name,
                        trip_headsign=destination_name,
                        etas=[],
                        color=[0, 57, 166]
                    )   
                transit_lines_by_key[published_line_name].etas.append(eta)
        
        return transit_lines_by_key.values()

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

    def get_transit_lines(self, stop_id, direction_id, current_time):
        transit_lines_by_key = {}

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
                if route_id not in transit_lines_by_key:
                    transit_lines_by_key[route_id] = TransitLine(
                    route_id=route_id,
                    trip_headsign=self.trips[trip_id].trip_headsign,
                    etas=[],
                    color=self.colors[route_id]
                )
                transit_lines_by_key[route_id].etas.append(eta)

        return transit_lines_by_key.values()

class CompositeTransitService(BaseTransitService):
    def __init__(self):
        self.mta_subway_service = MtaSubwayService()
        self.mta_bus_service = MtaBusService()
        self.nyc_ferry_service = NycFerryService()

    def get_transit_lines(self):
        transit_lines = []
        current_time = time.time()

        try:
            transit_lines.extend(self.mta_subway_service.get_transit_lines(
                'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs', #1234567
                '626S', # 86 St
                '..S',
                current_time
            ))
            transit_lines.extend(self.mta_subway_service.get_transit_lines(
                'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw',
                'Q05S', # 96 St,
                '..S',
                current_time
            ))
            transit_lines.extend(self.mta_bus_service.get_transit_lines(
                '404947',
                current_time
            ))
            transit_lines.extend(self.nyc_ferry_service.get_transit_lines(
                '113', # 86 St
                '0', # southbound
                current_time
            ))
        except Exception as error:
            transit_lines.append([TransitLine(
                route_id='ERR!',
                trip_headsign=str(error),
                etas=[current_time],
                color=[255, 0, 0]
            )])
            traceback.print_exc()

        return transit_lines

class RowFactory:
    def create_rows(self, transit_lines):
        rows = []
        current_time = time.time()

        for transit_line in transit_lines:
            text = f'{transit_line.route_id}'
            text += ' ' * (5 - len(text))
            text += transit_line.trip_headsign[:17]
            text += ' ' * (24 - len(text))

            etas = [str(int(round((eta - current_time) / 60, 0))) for eta in sorted(transit_line.etas)]
            text += etas[0]
            e = 1
            while (e < len(etas) and len(text) + 1 + len(etas[e]) + 1 <= 32):
                text += ',' + etas[e]
                e += 1
            text += 'm'
            rows.append(Row(
                text=text,
                color=transit_line.color
            ))

        return rows

class TransitFeed(threading.Thread):
    def run(self):
        self.transit_lines: list[TransitLine] = []
        self.row_factory = RowFactory()
        self.transit_service = CompositeTransitService()

        while True:
            self.transit_lines = self.transit_service.get_transit_lines()
            time.sleep(30)
    
    def get_rows(self):
        return self.row_factory.create_rows(self.transit_lines)

# Main function
if __name__ == "__main__":
    if os.name != 'nt':
        class RgbMatrixView(SampleBase):
            def __init__(self, *args, **kwargs):
                super(RgbMatrixView, self).__init__(*args, **kwargs)

            def run(self):
                transit_feed = TransitFeed()
                transit_feed.start()

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
                    rows = transit_feed.get_rows()

                    for i, row in enumerate(rows if len(rows) < 4 else rows + rows):                
                        graphics.DrawText(
                            offscreen_canvas,
                            font,
                            1,
                            7 + i * textbox_height - vertical_offset // vertical_offset_slowdown,
                            graphics.Color(*row.color) if is_light_mode else dark_mode,
                            row.text
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
                    if len(rows) < 4 or vertical_offset // vertical_offset_slowdown >= textbox_height * len(rows):
                        vertical_offset = 0
                    
                    offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)

                    time.sleep(0.1)

        RgbMatrixView().process()
    else:
        transit_service = CompositeTransitService()
        row_factory = RowFactory()
        transit_lines = transit_service.get_transit_lines()
        # for transit_line in transit_lines:
        #     print(transit_line)
        for row in row_factory.create_rows(transit_lines):
            print(row.text)

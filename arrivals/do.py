#!/usr/bin/env python3
import asyncio
import os

import config
from transit_row_factory import TransitRowFactory
from transit_service import CompositeTransitService as TransitService
from weather_point_factory import WeatherPointFactory
from weather_service import WeatherService

if __name__ == "__main__":
    transit_service = TransitService()
    transit_row_factory = TransitRowFactory()
    weather_point_factory = WeatherPointFactory()
    weather_service = WeatherService()

    if os.name == 'posix':
        if config.show_transit:
            from transit_feed_view import TransitFeedView
            TransitFeedView(
                transit_service=transit_service,
                transit_row_factory=transit_row_factory,
                weather_service=weather_service
            ).process()
        else:
            from weather_graph_view import WeatherGraphView
            WeatherGraphView(
                weather_point_factory=weather_point_factory,
                weather_service=weather_service
            ).process()

        asyncio.get_event_loop().run_forever()
    else:
        if config.show_transit:
            asyncio.get_event_loop().run_until_complete(transit_service.update_transit_lines())
            
            rows = transit_row_factory.create_rows(
                transit_lines=transit_service.transit_lines,
                vertical_offset=0,
                horizontal_offset=0,
                cell_height=7,
                cell_width=4,
                max_rows=4
            )
            for row in rows:
                print(f'{row.name[:4]:<5}{row.description[:21]:<23}{row.etas}')
        else:
            print(weather_service.get_forecast())
            print(weather_service.get_sunrise_sunset())

#!/usr/bin/env python3
import asyncio
import os

from datetime import datetime

from row_factory import RowFactory
from transit_service import CompositeTransitService as TransitService
from weather_service import WeatherService

if __name__ == "__main__":
    transit_service = TransitService()
    row_factory = RowFactory()
    weather_service = WeatherService()

    if os.name == 'posix':
        from transit_feed_view import TransitFeedView
        TransitFeedView(
            transit_service=transit_service,
            row_factory=row_factory,
            weather_service=weather_service
        ).process()
        
        # from weather_graph_view import WeatherGraphView
        # WeatherGraphView(weather_service=weather_service).process()

        asyncio.get_event_loop().run_forever()
    else:
        asyncio.get_event_loop().run_until_complete(transit_service.update_transit_lines())
        
        rows = row_factory.create_rows(
            transit_lines=transit_service.transit_lines,
            vertical_offset=0,
            horizontal_offset=0,
            cell_height=7,
            cell_width=4,
            max_rows=4
        )
        for row in rows:
            print(f'{row.name[:4]:<5}{row.description[:17]:<19}{row.etas}')
        weather_service.get_forecast()
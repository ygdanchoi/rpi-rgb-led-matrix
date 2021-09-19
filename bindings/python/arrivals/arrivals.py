#!/usr/bin/env python3
import os

from row_factory import RowFactory
from transit_service import CompositeTransitService as TransitService, TransitLine

# Main function
if __name__ == "__main__":
    transit_service = TransitService()
    row_factory = RowFactory()

    if os.name == 'posix':
        from transit_feed_view import TransitFeedView
        TransitFeedView(transit_service=transit_service, row_factory=row_factory).process()
    else:
        transit_lines = transit_service.get_transit_lines()
        for row in row_factory.create_rows(transit_lines):
            print(row.text)

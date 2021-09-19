#!/usr/bin/env python3
import os

from row_factory import RowFactory
from transit_service import CompositeTransitService as TransitService, TransitLine

# Main function
if __name__ == "__main__":
    if os.name == 'posix':
        from transit_feed_view import TransitFeedView
        TransitFeedView().process()
    else:
        transit_lines = TransitService().get_transit_lines()
        for row in RowFactory().create_rows(transit_lines):
            print(row.text)

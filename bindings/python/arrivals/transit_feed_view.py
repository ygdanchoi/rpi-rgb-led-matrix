import threading
import time

from datetime import datetime

from samplebase import SampleBase
from rgbmatrix import graphics

class TransitFeedViewModel():
    def __init__(self, transit_service, row_factory):
        self.transit_lines = []
        self.transit_service = transit_service
        self.row_factory = row_factory

        threading.Thread(target=self.run).start()

    def run(self):
        while True:
            self.transit_lines = self.transit_service.get_transit_lines()
            time.sleep(30)
    
    def get_rows(self):
        return self.row_factory.create_rows(self.transit_lines)

class TransitFeedView(SampleBase):
    def __init__(self, *args, **kwargs):
        super(TransitFeedView, self).__init__(*args, **kwargs)
        transit_service = kwargs['transit_service']
        row_factory = kwargs['row_factory']
        self.transit_feed = TransitFeedViewModel(transit_service, row_factory)

        self.font_height = 7
        self.max_rows = 4

    def run(self):
        offscreen_canvas = self.matrix.CreateFrameCanvas()
        font = graphics.Font()
        font.LoadFont("../../../fonts/tom-thumb.bdf")
        dark_mode_color = graphics.Color(47, 0, 0)
        vertical_offset = 0
        
        while True:
            rows = self.transit_feed.get_rows()
            self.render(rows, offscreen_canvas, font, dark_mode_color, vertical_offset)

            vertical_offset += 1
            if len(rows) < self.max_rows or vertical_offset >= self.font_height * len(rows):
                vertical_offset = 0

            time.sleep(0.1)

    def render(self, rows, offscreen_canvas, font, dark_mode_color, vertical_offset):
        hh = datetime.now().hour
        is_light_mode = 6 <= hh and hh < 22
        offscreen_canvas.Clear()

        for i, row in enumerate(rows if len(rows) < self.max_rows else rows + rows):                
            graphics.DrawText(
                offscreen_canvas,
                font,
                1,
                7 + i * self.font_height - vertical_offset,
                graphics.Color(*row.color) if is_light_mode else dark_mode_color,
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
                graphics.Color(255, 255, 255) if is_light_mode else dark_mode_color,
                datetime.now().strftime('%a, %b %d, %Y  %-I:%M:%S %p')
            )
        
        
        offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)

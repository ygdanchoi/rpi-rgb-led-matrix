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

        self.offscreen_canvas = self.matrix.CreateFrameCanvas()
        self.font = graphics.Font()
        self.font.LoadFont("../../../fonts/tom-thumb.bdf")

        self.vertical_offset = 0
        self.textbox_height = 7
        self.dark_mode = graphics.Color(47, 0, 0)


    def run(self):
        while True:
            rows = self.transit_feed.get_rows()
            self.render(rows)
            time.sleep(0.1)
    
    def render(self, rows):
        hh = datetime.now().hour
        is_light_mode = 6 <= hh and hh < 22

        self.offscreen_canvas.Clear()

        for i, row in enumerate(rows if len(rows) < 4 else rows + rows):                
            graphics.DrawText(
                self.offscreen_canvas,
                self.font,
                1,
                7 + i * self.textbox_height - self.vertical_offset,
                graphics.Color(*row.color) if is_light_mode else self.dark_mode,
                row.text
            )

            for y in range(self.offscreen_canvas.height - 7, self.offscreen_canvas.height):
                for x in range(0, self.offscreen_canvas.width):
                    self.offscreen_canvas.SetPixel(x, y, 0, 0, 0)
            
            graphics.DrawText(
                self.offscreen_canvas,
                self.font,
                1,
                self.offscreen_canvas.height - 1,
                graphics.Color(255, 255, 255) if is_light_mode else self.dark_mode,
                datetime.now().strftime('%a, %b %d, %Y  %-I:%M:%S %p')
            )
        
        self.vertical_offset += 1
        if len(rows) < 4 or self.vertical_offset >= self.textbox_height * len(rows):
            vertical_offset = 0
        
        offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)

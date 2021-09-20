import threading
import time

from datetime import datetime

from samplebase import SampleBase
from rgbmatrix import graphics

class TransitFeedViewModel():
    def __init__(self, transit_service, row_factory):
        self.transit_service = transit_service
        self.row_factory = row_factory
        self.vertical_offset = 0
        self.row_height = 7

        self.transit_lines = []
        self.rows = []

        threading.Thread(target=self.update_transit_lines).start()
        threading.Thread(target=self.update_rows).start()

    def update_transit_lines(self):
        while True:
            self.transit_lines = self.transit_service.get_transit_lines()
            time.sleep(30)

    def update_rows(self):
        while True:
            self.rows = self.row_factory.create_rows(self.transit_lines)
            time.sleep(1)
    
    def update_vertical_offset(self):
        self.vertical_offset += 1
        if len(self.transit_lines) < 4 or self.vertical_offset >= self.row_height * len(self.transit_lines):
            self.vertical_offset = 0
    
    def is_light_mode(self):
        hh = datetime.now().hour
        return 6 <= hh and hh < 22

class TransitFeedView(SampleBase):
    def __init__(self, *args, **kwargs):
        super(TransitFeedView, self).__init__(*args, **kwargs)
        transit_service = kwargs['transit_service']
        row_factory = kwargs['row_factory']
        self.viewmodel = TransitFeedViewModel(transit_service, row_factory)

    def run(self):
        offscreen_canvas = self.matrix.CreateFrameCanvas()
        font = graphics.Font()
        font.LoadFont("../../../fonts/tom-thumb.bdf")
        dark_mode_color = graphics.Color(47, 0, 0)
        
        while True:
            offscreen_canvas.Clear()
            rows = self.viewmodel.rows
            is_light_mode = self.viewmodel.is_light_mode

            for i, row in enumerate(rows if len(rows) < 4 else rows + rows):                
                graphics.DrawText(
                    offscreen_canvas,
                    font,
                    1,
                    7 + i * self.viewmodel.row_height - self.viewmodel.vertical_offset,
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
            self.viewmodel.update_vertical_offset()
            time.sleep(0.1)

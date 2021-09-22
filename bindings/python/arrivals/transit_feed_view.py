import threading
import time

from datetime import datetime

from samplebase import SampleBase
from rgbmatrix import graphics

class TransitFeedViewModel():
    def __init__(self, transit_service, row_factory, weather_service):
        self.transit_service = transit_service
        self.row_factory = row_factory
        self.weather_service = weather_service
        
        self.vertical_offset = 0
        self.cell_height = 7
        self.cell_width = 4
        self.max_rows = 4

        self.transit_lines = []
        self.rows = []
        self.temperature = ''

        threading.Thread(target=self.update_transit_lines).start()
        threading.Thread(target=self.update_rows).start()
        threading.Thread(target=self.update_weather).start()

    def update_transit_lines(self):
        while True:
            self.transit_lines = self.transit_service.get_transit_lines()
            time.sleep(30)

    def update_rows(self):
        while True:
            self.rows = self.row_factory.create_rows(self.transit_lines)
            time.sleep(1)

    def update_weather(self):
        while True:
            self.temperature = self.weather_service.get_weather().temperature
            time.sleep(60 * 60)
    
    def update_vertical_offset(self):
        self.vertical_offset += 1
        if len(self.rows) < self.max_rows or self.vertical_offset >= self.cell_height * len(self.rows):
            self.vertical_offset = 0
    
    def is_light_mode(self):
        hh = datetime.now().hour
        return 7 <= hh and hh < 22

class TransitFeedView(SampleBase):
    def __init__(self, *args, **kwargs):
        super(TransitFeedView, self).__init__(*args, **kwargs)
        
        self.viewmodel = TransitFeedViewModel(
            transit_service=kwargs['transit_service'],
            row_factory=kwargs['row_factory'],
            weather_service=kwargs['weather_service']
        )

    def run(self):
        offscreen_canvas = self.matrix.CreateFrameCanvas()
        font = graphics.Font()
        font.LoadFont("../../../fonts/tom-thumb.bdf")
        dark_mode_color = graphics.Color(47, 0, 0)
        light_mode_colors = {}
        
        # for true MVVM, view should observe viewmodel.vertical_offset; however, this is slow
        while True:
            offscreen_canvas.Clear()
            rows = self.viewmodel.rows
            is_light_mode = self.viewmodel.is_light_mode()

            for i, row in enumerate(rows):
                # avoid helper functions here; performance overhead is unacceptable
                y = (i + 1) * self.viewmodel.cell_height - self.viewmodel.vertical_offset
                if y < -self.viewmodel.cell_height:
                    y += len(rows) * self.viewmodel.cell_height
                
                if (y < offscreen_canvas.height):
                    if str(row.color) not in light_mode_colors:
                        light_mode_colors[str(row.color)] = graphics.Color(*row.color)
                    light_mode_color = light_mode_colors[str(row.color)]

                    should_scroll_name = len(row.name) > 4
                    should_scroll_description = len(row.description) > 17
                    # TODO: handle len(rows) < self.viewmodel.max_rows better

                    if should_scroll_name and should_scroll_description:
                        graphics.DrawText(
                            offscreen_canvas,
                            font,
                            max(
                                min(1 + 5 * self.viewmodel.cell_width, 1 + 5 * self.viewmodel.cell_width + y - 4 - 2 * self.viewmodel.cell_height),
                                1 + 5 * self.viewmodel.cell_width + (17 - len(row.description)) * self.viewmodel.cell_width
                            ),
                            y,
                            light_mode_color if is_light_mode else dark_mode_color,
                            row.description
                        )

                        for yy in range(y - self.viewmodel.cell_height + 2, y + 1):
                            for xx in range(0, 5 * self.viewmodel.cell_width):
                                offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
                        
                        for yy in range(y - self.viewmodel.cell_height + 2, y + 1):
                            for xx in range(22 * self.viewmodel.cell_width, offscreen_canvas.width):
                                offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)

                        graphics.DrawText(
                            offscreen_canvas,
                            font,
                            max(
                                min(1, 1 + y - 4 - 2 * self.viewmodel.cell_height),
                                1 + (4 - len(row.name)) * self.viewmodel.cell_width
                            ),
                            y,
                            light_mode_color if is_light_mode else dark_mode_color,
                            row.name[:(4 + max(0, 5 - y // self.viewmodel.cell_width))]
                        )

                        for yy in range(y - self.viewmodel.cell_height + 2, y + 1):
                            for xx in range(4 * self.viewmodel.cell_width, 5 * self.viewmodel.cell_width):
                                offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
                    
                        graphics.DrawText(
                            offscreen_canvas,
                            font,
                            1 + 24 * self.viewmodel.cell_width,
                            y,
                            light_mode_color if is_light_mode else dark_mode_color,
                            row.etas
                        )
                    elif should_scroll_name:
                        graphics.DrawText(
                            offscreen_canvas,
                            font,
                            max(
                                min(1, 1 + y - 4 - 2 * self.viewmodel.cell_height),
                                1 + (4 - len(row.name)) * self.viewmodel.cell_width
                            ),
                            y,
                            light_mode_color if is_light_mode else dark_mode_color,
                            row.name
                        )

                        for yy in range(y - self.viewmodel.cell_height + 2, y + 1):
                            for xx in range(4 * self.viewmodel.cell_width, offscreen_canvas.width):
                                offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
                    
                        graphics.DrawText(
                            offscreen_canvas,
                            font,
                            1 + 5 * self.viewmodel.cell_width,
                            y,
                            light_mode_color if is_light_mode else dark_mode_color,
                            f'{row.description[:17]:<19}{row.etas}'
                        )
                    elif should_scroll_description:
                        graphics.DrawText(
                            offscreen_canvas,
                            font,
                            max(
                                min(1 + 5 * self.viewmodel.cell_width, 1 + 5 * self.viewmodel.cell_width + y - 4 - 2 * self.viewmodel.cell_height),
                                1 + 5 * self.viewmodel.cell_width + (17 - len(row.description)) * self.viewmodel.cell_width
                            ),
                            y,
                            light_mode_color if is_light_mode else dark_mode_color,
                            row.description
                        )

                        for yy in range(y - self.viewmodel.cell_height + 2, y + 1):
                            for xx in range(0, 5 * self.viewmodel.cell_width):
                                offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
                        
                        for yy in range(y - self.viewmodel.cell_height + 2, y + 1):
                            for xx in range(22 * self.viewmodel.cell_width, offscreen_canvas.width):
                                offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
                        
                        graphics.DrawText(
                            offscreen_canvas,
                            font,
                            1,
                            y,
                            light_mode_color if is_light_mode else dark_mode_color,
                            f'{row.name[:4]:<24}{row.etas}'
                        )
                    else:
                        graphics.DrawText(
                            offscreen_canvas,
                            font,
                            1,
                            y,
                            light_mode_color if is_light_mode else dark_mode_color,
                            f'{row.name[:4]:<5}{row.description[:17]:<19}{row.etas}'
                        )

                for yy in range(offscreen_canvas.height - self.viewmodel.cell_height, offscreen_canvas.height):
                    for xx in range(0, offscreen_canvas.width):
                        offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
                
                graphics.DrawText(
                    offscreen_canvas,
                    font,
                    1,
                    offscreen_canvas.height - 1,
                    graphics.Color(255, 255, 255) if is_light_mode else dark_mode_color,
                    f"{datetime.now().strftime('%a, %b %-d, %-I:%M:%S %p')}  {self.viewmodel.temperature}"
                )
            
            offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
            self.viewmodel.update_vertical_offset()
            time.sleep(0.1)

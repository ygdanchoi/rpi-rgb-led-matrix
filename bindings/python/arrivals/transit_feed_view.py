import threading
import time

from datetime import datetime

from samplebase import SampleBase
from rgbmatrix import graphics

class Subject:
    def register(observer):
        pass

class Observer:
    def update():
        pass

class TransitFeedViewModel(Subject):
    def __init__(self, transit_service, row_factory, weather_service):
        self.transit_service = transit_service
        self.row_factory = row_factory
        self.weather_service = weather_service

        self.observers = []
        
        self.horizontal_offset = 0
        self.vertical_offset = 0
        self.stripes_offset = 0
        self.cell_height = 7
        self.cell_width = 4
        self.max_rows = 4
        self.stripe_divisor_light = 8
        self.stripe_divisor_dark = 16

        self.transit_lines = []
        self.rows = []
        self.temperature = ''
        self.is_light_mode = True

        threading.Thread(target=self.main_thread).start()
        threading.Thread(target=self.background_thread).start()

    def register(self, observer):
        self.observers.append(observer)
        return self
    
    def main_thread(self):
        last_ns = time.time_ns()

        while True:            
            self.rows = self.row_factory.create_rows(
                self.transit_lines,
                self.vertical_offset,
                self.horizontal_offset,
                self.cell_height
            )

            for observer in self.observers:
                observer.update()

            self.increment_offsets()
            
            last_delta_s = (time.time_ns() - last_ns) / 1_000_000_000
            s_to_wait = max(0, 0.07 - last_delta_s)
            time.sleep(s_to_wait)
            last_ns = time.time_ns()


    def background_thread(self):
        update_transit_lines_timer = 0
        update_weather_timer = 0

        while True:
            if update_transit_lines_timer == 0:
                self.transit_lines = self.transit_service.get_transit_lines()
                update_transit_lines_timer = 30

            if update_weather_timer == 0:
                self.temperature = self.weather_service.get_weather().temperature
                update_weather_timer = 60 * 60

            update_transit_lines_timer -= 1
            update_weather_timer -= 1

            hh = datetime.now().hour
            self.is_light_mode = 7 <= hh and hh < 22
            
            time.sleep(1)
    
    def increment_offsets(self):
        self.vertical_offset += 1
        self.horizontal_offset += 1
        if len(self.rows) < self.max_rows:
            self.vertical_offset = 0
        if self.vertical_offset >= self.cell_height * len(self.rows):
            self.vertical_offset = 0
            self.horizontal_offset = 0

        self.stripes_offset += 1
        if self.stripes_offset >= 32:
            self.stripes_offset = 0
    
    def is_stripe(self, x, y):
        return (x + y - self.stripes_offset // 2) // 8 % 2 == 0

class TransitFeedView(Observer, SampleBase):
    def __init__(self, *args, **kwargs):
        super(TransitFeedView, self).__init__(*args, **kwargs)
        
        self.viewmodel = TransitFeedViewModel(
            transit_service=kwargs['transit_service'],
            row_factory=kwargs['row_factory'],
            weather_service=kwargs['weather_service']
        ).register(self)

    def run(self):
        self.offscreen_canvas = self.matrix.CreateFrameCanvas()
        self.font = graphics.Font()
        self.font.LoadFont("../../../fonts/tom-thumb.bdf")
        self.dark_mode_color = graphics.Color(47, 0, 0)
        self.light_mode_colors = {}

    def update(self):
        self.offscreen_canvas.Clear()

        for row in self.viewmodel.rows:
            if (row.y < self.offscreen_canvas.height):
                if str(row.color) not in self.light_mode_colors:
                    self.light_mode_colors[str(row.color)] = graphics.Color(*row.color)
                light_mode_color = self.light_mode_colors[str(row.color)]

                should_scroll_name = len(row.name) > 4
                should_scroll_description = len(row.description) > 17
                # TODO: handle len(rows) < self.viewmodel.max_rows better

                for yy in range(row.y - self.viewmodel.cell_height + 1, min(row.y + 1, self.offscreen_canvas.height - self.viewmodel.cell_height)):
                    for xx in range(0, self.offscreen_canvas.width):
                        if not self.viewmodel.is_light_mode:
                            self.offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
                        elif self.viewmodel.is_stripe(xx, yy):
                            self.offscreen_canvas.SetPixel(
                                xx,
                                yy,
                                row.color[0] // self.viewmodel.stripe_divisor_light,
                                row.color[1] // self.viewmodel.stripe_divisor_light,
                                row.color[2] // self.viewmodel.stripe_divisor_light
                            )
                        else:
                            self.offscreen_canvas.SetPixel(
                                xx,
                                yy,
                                row.color[0] // self.viewmodel.stripe_divisor_dark,
                                row.color[1] // self.viewmodel.stripe_divisor_dark,
                                row.color[2] // self.viewmodel.stripe_divisor_dark
                            )

                if should_scroll_name and should_scroll_description:
                    self.draw_scrolled_description(row, self.offscreen_canvas, self.font, self.viewmodel.is_light_mode, light_mode_color, self.dark_mode_color)
                    self.draw_scrolled_name(row,self.offscreen_canvas, self.font, self.viewmodel.is_light_mode, light_mode_color, self.dark_mode_color)
                
                    graphics.DrawText(
                        self.offscreen_canvas,
                        self.font,
                        1 + 24 * self.viewmodel.cell_width,
                        row.y,
                        light_mode_color if self.viewmodel.is_light_mode else self.dark_mode_color,
                        row.etas
                    )
                elif should_scroll_name:
                    self.draw_scrolled_name(row, self.offscreen_canvas, self.font, self.viewmodel.is_light_mode, light_mode_color, self.dark_mode_color)
                
                    graphics.DrawText(
                        self.offscreen_canvas,
                        self.font,
                        1 + 5 * self.viewmodel.cell_width,
                        row.y,
                        light_mode_color if self.viewmodel.is_light_mode else self.dark_mode_color,
                        f'{row.description[:17]:<19}{row.etas}'
                    )
                elif should_scroll_description:
                    self.draw_scrolled_description(row, self.offscreen_canvas, self.font, self.viewmodel.is_light_mode, light_mode_color, self.dark_mode_color)
                    
                    graphics.DrawText(
                        self.offscreen_canvas,
                        self.font,
                        1,
                        row.y,
                        light_mode_color if self.viewmodel.is_light_mode else self.dark_mode_color,
                        f'{row.name[:4]:<24}{row.etas}'
                    )
                else:
                    graphics.DrawText(
                        self.offscreen_canvas,
                        self.font,
                        1,
                        row.y,
                        light_mode_color if self.viewmodel.is_light_mode else self.dark_mode_color,
                        f'{row.name[:4]:<5}{row.description[:17]:<19}{row.etas}'
                    )

            for yy in range(self.offscreen_canvas.height - self.viewmodel.cell_height, self.offscreen_canvas.height):
                for xx in range(0, self.offscreen_canvas.width):
                    if self.viewmodel.is_light_mode and self.viewmodel.is_stripe(xx, yy):
                        self.offscreen_canvas.SetPixel(
                            xx,
                            yy,
                            255 // self.viewmodel.stripe_divisor_dark,
                            255 // self.viewmodel.stripe_divisor_dark,
                            255 // self.viewmodel.stripe_divisor_dark
                        )
                    else:
                        self.offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)

            temperature = f' • {self.viewmodel.temperature}' if self.viewmodel.temperature else ''
            
            graphics.DrawText(
                self.offscreen_canvas,
                self.font,
                1,
                self.offscreen_canvas.height - 1,
                graphics.Color(255, 255, 255) if self.viewmodel.is_light_mode else self.dark_mode_color,
                f"{datetime.now().strftime('%a, %b %-d • %-I:%M:%S %p')}{temperature}"
            )
        
        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)


    def draw_scrolled_description(self, row, offscreen_canvas, font, is_light_mode, light_mode_color, dark_mode_color):
        graphics.DrawText(
            offscreen_canvas,
            font,
            1 + 5 * self.viewmodel.cell_width + max(
                min(0, row.y - 4 - 2 * self.viewmodel.cell_height),
                (17 - len(row.description)) * self.viewmodel.cell_width
            ),
            row.y,
            light_mode_color if self.viewmodel.is_light_mode else dark_mode_color,
            row.description
        )

        for yy in range(row.y - self.viewmodel.cell_height + 2, row.y + 1):
            for xx in range(0, 5 * self.viewmodel.cell_width):
                if not self.viewmodel.is_light_mode:
                    offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
                elif self.viewmodel.is_stripe(xx, yy):
                    offscreen_canvas.SetPixel(
                        xx,
                        yy,
                        row.color[0] // self.viewmodel.stripe_divisor_light,
                        row.color[1] // self.viewmodel.stripe_divisor_light,
                        row.color[2] // self.viewmodel.stripe_divisor_light
                    )
                else:
                    offscreen_canvas.SetPixel(
                        xx,
                        yy,
                        row.color[0] // self.viewmodel.stripe_divisor_dark,
                        row.color[1] // self.viewmodel.stripe_divisor_dark,
                        row.color[2] // self.viewmodel.stripe_divisor_dark
                    )
        
        for yy in range(row.y - self.viewmodel.cell_height + 2, row.y + 1):
            for xx in range(22 * self.viewmodel.cell_width, offscreen_canvas.width):
                if not self.viewmodel.is_light_mode:
                    offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
                elif self.viewmodel.is_stripe(xx, yy):
                    offscreen_canvas.SetPixel(
                        xx,
                        yy,
                        row.color[0] // self.viewmodel.stripe_divisor_light,
                        row.color[1] // self.viewmodel.stripe_divisor_light,
                        row.color[2] // self.viewmodel.stripe_divisor_light
                    )
                else:
                    offscreen_canvas.SetPixel(
                        xx,
                        yy,
                        row.color[0] // self.viewmodel.stripe_divisor_dark,
                        row.color[1] // self.viewmodel.stripe_divisor_dark,
                        row.color[2] // self.viewmodel.stripe_divisor_dark
                    )


    def draw_scrolled_name(self, row, offscreen_canvas, font, is_light_mode, light_mode_color, dark_mode_color):
        graphics.DrawText(
            offscreen_canvas,
            font,
            1 + max(
                min(0, row.y - 4 - 2 * self.viewmodel.cell_height),
                (4 - len(row.name)) * self.viewmodel.cell_width
            ),
            row.y,
            light_mode_color if is_light_mode else dark_mode_color,
            row.name[:(4 + max(0, 5 - row.y // self.viewmodel.cell_width))]
        )

        for yy in range(row.y - self.viewmodel.cell_height + 2, row.y + 1):
            for xx in range(4 * self.viewmodel.cell_width, 5 * self.viewmodel.cell_width):
                if not is_light_mode:
                    offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
                elif self.viewmodel.is_stripe(xx, yy):
                    offscreen_canvas.SetPixel(
                        xx,
                        yy,
                        row.color[0] // self.viewmodel.stripe_divisor_light,
                        row.color[1] // self.viewmodel.stripe_divisor_light,
                        row.color[2] // self.viewmodel.stripe_divisor_light
                    )
                else:
                    offscreen_canvas.SetPixel(
                        xx,
                        yy,
                        row.color[0] // self.viewmodel.stripe_divisor_dark,
                        row.color[1] // self.viewmodel.stripe_divisor_dark,
                        row.color[2] // self.viewmodel.stripe_divisor_dark
                    )

    
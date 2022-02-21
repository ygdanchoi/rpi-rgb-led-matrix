import asyncio
import bisect
import math
import random
import time

from datetime import datetime

from rgbmatrix import graphics
from samplebase import SampleBase


class Observable:
    def __init__(self):
        self.observers = []
    
    def add_observer(self, observer):
        self.observers.append(observer)
        return self

    def notify_observers(self):
        for observer in self.observers:
            observer.update()

class Observer:
    def update():
        pass

class WeatherGraphViewModel(Observable):
    def __init__(self, weather_point_factory, weather_service):
        super().__init__()

        self.weather_point_factory = weather_point_factory
        self.weather_service = weather_service

        self.matrix_h = 32
        self.matrix_w = 128
        self.cell_height = 7
        self.cell_width = 4
        self.stripe_divisor_light = 8
        self.stripe_divisor_dark = 16

        self.vertical_offset = 0
        self.stripes_offset = 0

        self.weather_points = []
        self.sunrises_x = []
        self.sunsets_x = []
        self.is_light_mode = True

        # min value is -64, but for some reason, -255 makes everything run faster
        self.gol_matrix = [[-255]*self.matrix_w for i in range(self.matrix_h)]
        self.new_gol_matrix = [[-255]*self.matrix_w for i in range(self.matrix_h)]

        asyncio.ensure_future(self.main_thread())
        asyncio.ensure_future(self.background_thread())
    
    async def main_thread(self):
        last_ns = time.time_ns()

        while True:            
            self.notify_observers()
            self.increment_offsets()
            
            last_delta_s = (time.time_ns() - last_ns) / 1_000_000_000
            s_to_wait = max(0, 0.055 - last_delta_s)
            await asyncio.sleep(s_to_wait)
            last_ns = time.time_ns()

    async def background_thread(self):
        update_weather_timer = 0

        while True:
            hh = datetime.now().hour
            self.is_light_mode = 7 <= hh and hh < 22

            if update_weather_timer == 0:
                forecast = self.weather_service.get_forecast()
                self.weather_points = self.weather_point_factory.create_points(forecast, self.cell_height, self.matrix_h)

                sunrise_sunset = self.weather_service.get_sunrise_sunset()
                self.sunrises_x = self.weather_point_factory.get_sunrises_x(self.weather_points, sunrise_sunset, self.matrix_w)
                self.sunsets_x = self.weather_point_factory.get_sunsets_x(self.weather_points, sunrise_sunset, self.matrix_w)

                update_weather_timer = 60 * 60

            update_weather_timer -= 1
            await asyncio.sleep(1)

    
    def increment_offsets(self):
        self.stripes_offset += 1
        if self.stripes_offset >= 32:
            self.stripes_offset = 0

        self.vertical_offset += 1
        if self.vertical_offset >= 360:
            self.vertical_offset = 0

        for c in range(self.matrix_w):
            self.new_gol_matrix[self.matrix_h - 1][c] = 0 if random.randint(0, 2) == 0 else -1

        for r in range(self.matrix_h - 1):
            for c in range(self.matrix_w):
                num = self.num_alive_neighbors(r, c)
                if self.gol_matrix[r][c]: # dead
                    if num == 3:
                        self.new_gol_matrix[r][c] = 0 # live
                    elif self.gol_matrix[r][c] > -255:
                        self.new_gol_matrix[r][c] = self.gol_matrix[r][c] - 1 # stay dead
                else: # alive
                    if num < 2 or num > 3:
                        self.new_gol_matrix[r][c] = -1 # die
                    else:
                        self.new_gol_matrix[r][c] = 0 # stay alive
        
        swap = self.gol_matrix
        self.gol_matrix = self.new_gol_matrix
        self.new_gol_matrix = swap
    
    def num_alive_neighbors(self, r, c):
        num = 0

        if c > 0:
            if r > 0:
                num += self.gol_matrix[r - 1][c - 1] == 0
            if r < self.matrix_h - 1:
                num += self.gol_matrix[r + 1][c - 1] == 0
                num += self.gol_matrix[r + 0][c - 1] == 0
        if c < self.matrix_w - 1:
            if r > 0:
                num += self.gol_matrix[r - 1][c + 1] == 0
            if r < self.matrix_h - 1:
                num += self.gol_matrix[r + 1][c + 1] == 0
                num += self.gol_matrix[r + 0][c + 1] == 0
        if r > 0:
            num += self.gol_matrix[r - 1][c] == 0
        if r < self.matrix_h - 1:
            num += self.gol_matrix[r + 1][c] == 0

        return num
    
    def is_stripe(self, x, y):
        return (x + y - self.stripes_offset // 2) // 8 % 2 == 0

    def get_gol_safe(self, r, c):
        if 0 <= r and r < self.matrix_h and 0 <= c and c < self.matrix_w:
            return self.gol_matrix[r][c]
        else:
            return -255

class WeatherGraphView(Observer, SampleBase):
    def __init__(self, *args, **kwargs):
        super(WeatherGraphView, self).__init__(*args, **kwargs)
        
        self.viewmodel = WeatherGraphViewModel(
            weather_point_factory=kwargs['weather_point_factory'],
            weather_service=kwargs['weather_service']
        )

    def run(self):
        self.offscreen_canvas = self.matrix.CreateFrameCanvas()
        self.font = graphics.Font()
        self.font.LoadFont('../fonts/tom-thumb.bdf')
        self.dark_mode_color = graphics.Color(47, 0, 0)
        self.light_mode_colors = {}

        self.viewmodel.add_observer(self)

    def update(self):
        self.offscreen_canvas.Clear()

        points = self.viewmodel.weather_points

        for i, point in enumerate(points):
            color = point.color if self.viewmodel.is_light_mode else [47, 0, 0]

            for (x, y) in point.coords:
                for yy in range(0, y - 1):
                    self.draw_stripe_pixel(x, yy, [31, 31, 31])
                self.offscreen_canvas.SetPixel(
                    x,
                    y,
                    color[0],
                    color[1],
                    color[2]
                )
                for yy in range(y + 1, self.offscreen_canvas.height): 
                    if self.should_draw_day_boundary(point, i, x, y, yy) or self.should_draw_chevron(x, yy):
                        self.offscreen_canvas.SetPixel(
                            x,
                            yy,
                            color[0],
                            color[1],
                            color[2]
                        )
                    else:
                        self.draw_stripe_pixel(x, yy, point.color)
                                            
        for i, point in enumerate(points[2:27:4]):
            p_i = 2 + i * 4

            self.draw_text(
                7 + i * 19 - len(point.temp) * self.viewmodel.cell_width / 2,
                min([pt.y - 1 for pt in points[(p_i - 1):(p_i + 1)]]),
                point.temp,
                point.color
            )

            self.draw_text(
                7 + i * 19 - len(point.hr) * self.viewmodel.cell_width / 2,
                self.offscreen_canvas.height - 1,
                point.hr,
                [255, 255, 255]
            )

            self.draw_text(
                7 + i * 19 - len(point.pop) * self.viewmodel.cell_width / 2,
                self.offscreen_canvas.height - 1 - self.viewmodel.cell_height,
                point.pop,
                [81, 121, 243]
            )

        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)

    def should_draw_day_boundary(self, point, i, x, y, yy):
        return x == point.x and point.hr == '12a' and yy % 2 == y % 2 and (i % 4 != 2 or yy < self.offscreen_canvas.height - 13)
    
    def should_draw_chevron(self, x, yy):
        return (
            x - 1 in self.viewmodel.sunrises_x and (yy - 1 + self.viewmodel.vertical_offset // 4) % 4 == 0 or
            x + 0 in self.viewmodel.sunrises_x and (yy + 0 + self.viewmodel.vertical_offset // 4) % 4 == 0 or
            x + 1 in self.viewmodel.sunrises_x and (yy - 1 + self.viewmodel.vertical_offset // 4) % 4 == 0 or
            x - 1 in self.viewmodel.sunsets_x and (yy + 1 - self.viewmodel.vertical_offset // 4) % 4 == 0 or
            x + 0 in self.viewmodel.sunsets_x and (yy + 0 - self.viewmodel.vertical_offset // 4) % 4 == 0 or
            x + 1 in self.viewmodel.sunsets_x and (yy + 1 - self.viewmodel.vertical_offset // 4) % 4 == 0
        )
    
    def draw_text(self, x, y, text, color):
        graphics.DrawText(
            self.offscreen_canvas,
            self.font,
            x,
            y,
            self.get_text_color(color),
            text
        )

    def get_text_color(self, color):
        if self.viewmodel.is_light_mode:
            key = str(color)
            if key not in self.light_mode_colors:
                self.light_mode_colors[key] = graphics.Color(*color)
            return self.light_mode_colors[key]
        else:
            return self.dark_mode_color

    def draw_stripe_pixel(self, xx, yy, color):
        if not self.viewmodel.is_light_mode:
            self.offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
        else:
            if self.viewmodel.is_stripe(xx, yy):
                stripe_divisor = self.viewmodel.stripe_divisor_light
            else:
                stripe_divisor = self.viewmodel.stripe_divisor_dark

            if self.viewmodel.get_gol_safe(yy, xx) < -64:
                self.offscreen_canvas.SetPixel(
                    xx,
                    yy,
                    color[0] // stripe_divisor,
                    color[1] // stripe_divisor,
                    color[2] // stripe_divisor
                )
            else:
                self.offscreen_canvas.SetPixel(
                    xx,
                    yy,
                    max(
                        color[0] // 2 + self.viewmodel.get_gol_safe(yy, xx) * 8,
                        color[0] // stripe_divisor
                    ),
                    max(
                        color[1] // 2 + self.viewmodel.get_gol_safe(yy, xx) * 16,
                        color[1] // stripe_divisor
                    ),
                    max(
                        color[2] // 2 + self.viewmodel.get_gol_safe(yy, xx) * 4,
                        color[2] // stripe_divisor
                    )
                )

    
import asyncio
import collections
import math
import random
import time

from datetime import datetime

from samplebase import SampleBase
from rgbmatrix import graphics

WeatherPoint = collections.namedtuple('WeatherPoint', ['time', 'x', 'y', 'color', 'temp'])

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
    def __init__(self, weather_service):
        super().__init__()

        self.weather_service = weather_service

        self.matrix_h = 32
        self.matrix_w = 128
        self.cell_height = 7
        self.cell_width = 4
        self.stripe_divisor_light = 8
        self.stripe_divisor_dark = 16
        
        self.stripes_offset = 0

        self.forecast = []
        self.is_light_mode = True

        self.gol_matrix = [[0]*self.matrix_w for i in range(self.matrix_h)]
        self.new_gol_matrix = [[0]*self.matrix_w for i in range(self.matrix_h)]

        asyncio.ensure_future(self.main_thread())
        asyncio.ensure_future(self.background_thread())
    
    async def main_thread(self):
        last_ns = time.time_ns()

        while True:            
            self.notify_observers()
            self.increment_offsets()
            
            last_delta_s = (time.time_ns() - last_ns) / 1_000_000_000
            s_to_wait = max(0, 0.07 - last_delta_s)
            await asyncio.sleep(s_to_wait)
            last_ns = time.time_ns()


    async def background_thread(self):
        update_weather_timer = 0

        while True:
            hh = datetime.now().hour
            self.is_light_mode = 7 <= hh and hh < 22

            if update_weather_timer == 0:
                self.forecast = self.weather_service.get_forecast()
                update_weather_timer = 4 * 60 * 60

            update_weather_timer -= 1
            
            await asyncio.sleep(1)
    
    def increment_offsets(self):
        self.stripes_offset += 1

        if self.stripes_offset >= 32:
            self.stripes_offset = 0
        
        self.step_gol()
    
    def step_gol(self):
        for r in range(self.matrix_h):
            for c in range(self.matrix_w):
                self.new_gol_matrix[r][c] = self.gol_matrix[r][c]
        
        for r in range(self.matrix_h):
            for c in range(self.matrix_w):
                num = self.num_alive_neighbors(r, c)
                if self.gol_matrix[r][c]:
                    # cell is dead
                    self.new_gol_matrix[r][c] = self.gol_matrix[r][c] - 1
                    if num == 3:
                        self.new_gol_matrix[r][c] = 0
                else:
                    # cell is alive
                    if num < 2 or num > 3:
                        self.new_gol_matrix[r][c] = -1
        
        for r in range(self.matrix_h):
            for c in range(self.matrix_w):
                self.gol_matrix[r][c] = self.new_gol_matrix[r][c]
        
        for c in range(self.matrix_w):
            self.gol_matrix[self.matrix_h - 1][c] = -1 if random.randint(0, 2) == 0 else 0
    
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
            weather_service=kwargs['weather_service']
        )

    def run(self):
        self.offscreen_canvas = self.matrix.CreateFrameCanvas()
        self.font = graphics.Font()
        self.font.LoadFont('../../../fonts/tom-thumb.bdf')
        self.dark_mode_color = graphics.Color(47, 0, 0)
        self.light_mode_colors = {}

        self.viewmodel.add_observer(self)

    def update(self):
        self.offscreen_canvas.Clear()

        points = self.create_weather_points()
        for i, point in enumerate(points):
            for yy in range(0, point.y - 1):
                self.draw_stripe_pixel(point.x, yy, [31, 31, 31])
            self.offscreen_canvas.SetPixel(
                point.x,
                point.y,
                point.color[0],
                point.color[1],
                point.color[2]
            )
            for yy in range(point.y + 1, self.offscreen_canvas.height):
                if (point.time == '12a'):
                    if (yy % 2 == point.y % 2):
                        self.offscreen_canvas.SetPixel(
                            point.x,
                            yy,
                            point.color[0],
                            point.color[1],
                            point.color[2]
                        )
                else:
                    self.draw_stripe_pixel(point.x, yy, point.color)
                    
            if i < len(points) - 1:
                for x in range(math.floor(point.x) + 1, math.floor(points[i + 1].x)):
                    m = (point.y - points[i + 1].y) / (point.x - points[i + 1].x)
                    b = point.y - m * point.x
                    y = math.floor(m * x + b)

                    for yy in range(0, y - 1):
                        self.draw_stripe_pixel(x, yy, [31, 31, 31])
                    self.offscreen_canvas.SetPixel(
                        x,
                        y,
                        point.color[0],
                        point.color[1],
                        point.color[2]
                    )
                    for yy in range(y + 1, self.offscreen_canvas.height):
                        self.draw_stripe_pixel(x, yy, point.color)
        for i, point in enumerate(points[2:27:4]):
            p_i = 2 + i * 4
            label = f"{int(round(point.temp, 0))}°"
            self.draw_text(
                7 + i * 19 - len(label) * self.viewmodel.cell_width / 2,
                min([pt.y - 1 for pt in points[(p_i - 1):(p_i + 1)]]),
                label,
                point.color
            )

        self.draw_footer()
        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
    
    def create_weather_points(self):
        points = []

        min_temp = float('inf')
        max_temp = float('-inf')
        for weather_hour in self.viewmodel.forecast[0:28]:
            min_temp = min(min_temp, weather_hour.temp)
            max_temp = max(max_temp, weather_hour.temp)

        for i, weather_hour in enumerate(self.viewmodel.forecast[0:1] + self.viewmodel.forecast[0:28]):
            hr = datetime.fromtimestamp(weather_hour.ts)
            
            points.append(WeatherPoint(
                time = f"{hr.strftime('%-I')}{hr.strftime('%p')[0].lower()}",
                x = int(i / 24 * 114 - 3),
                y = int(self.viewmodel.cell_height + (self.offscreen_canvas.height - 22) * (max_temp - weather_hour.temp) / (max_temp - min_temp)),
                color = self.get_color(weather_hour),
                temp = weather_hour.temp,
            ))

        return points

    # https://www.weatherbit.io/api/codes
    def get_color(self, weather_hour):
        code = weather_hour.code

        if 200 <= code and code <= 299: # thunderstorm
            return [243, 121, 203] # unseen
        elif 300 <= code and code <= 399: # drizzle
            return [81, 121, 203]
        elif 500 <= code and code <= 599: # rain
            return [81, 121, 203]
        elif 600 <= code and code <= 699: # snow
            return [250, 250, 250]
        elif 700 <= code and code <= 799: # fog
            return [50, 182, 122] # unseen
        elif 800 <= code and code <= 802: # clear
            return [243, 179, 67]
        elif 803 <= code and code <= 899: # clouds
            return [139, 145, 158]
        else:
            return [
                random.randint(64, 255),
                random.randint(64, 255),
                random.randint(64, 255)
        ]

    def draw_footer(self):
        for i, weather_hour in enumerate(self.viewmodel.forecast[1:26:4]):
            hr = datetime.fromtimestamp(weather_hour.ts)
            label = f"{hr.strftime('%-I')}{hr.strftime('%p')[0].lower()}"
            self.draw_text(
                7 + i * 19 - len(label) * self.viewmodel.cell_width / 2,
                self.offscreen_canvas.height - 1,
                label,
                [255, 255, 255]
            )
            self.draw_text(
                7 + i * 19 - len(f'{weather_hour.pop}%') * self.viewmodel.cell_width / 2,
                self.offscreen_canvas.height - 1 - self.viewmodel.cell_height,
                f'{weather_hour.pop}%',
                [63, 127, 255]
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

    def draw_row_mask(self, row, x_start, x_end):
        for yy in range(row.y - self.viewmodel.cell_height + 1, min(row.y + 1, self.offscreen_canvas.height - self.viewmodel.cell_height)):
            for xx in range(x_start, x_end):
                self.draw_stripe_pixel(xx, yy, row.color)

    def draw_stripe_pixel(self, xx, yy, color):
        if not self.viewmodel.is_light_mode:
            self.offscreen_canvas.SetPixel(xx, yy, 0, 0, 0)
        else:
            is_stripe = self.viewmodel.is_stripe(xx, yy)

            if color == [255, 255, 255]:
                self.offscreen_canvas.SetPixel(
                    xx,
                    yy,
                    15 if is_stripe else 0,
                    15 if is_stripe else 0,
                    15 if is_stripe else 0
                )
            else:
                if is_stripe:
                    stripe_divisor = self.viewmodel.stripe_divisor_light
                else:
                    stripe_divisor = self.viewmodel.stripe_divisor_dark
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
                        color[2] // 2 + self.viewmodel.get_gol_safe(yy, xx) * 2,
                        color[2] // stripe_divisor
                    )
                )

    
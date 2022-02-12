import asyncio
import collections
import math
import random
import time

from datetime import datetime

from samplebase import SampleBase
from rgbmatrix import graphics

WeatherPoint = collections.namedtuple('WeatherPoint', ['x', 'y', 'color', 'temp'])

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

        self.cell_height = 7
        self.cell_width = 4
        self.stripe_divisor_light = 4
        self.stripe_divisor_dark = 8
        
        self.stripes_offset = 0

        self.forecast = []
        self.is_light_mode = True

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
    
    def is_stripe(self, x, y):
        return (x + y - self.stripes_offset // 2) // 8 % 2 == 0

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
            points.append(WeatherPoint(
                x = i / 24 * 114 - 3,
                y = math.floor(self.viewmodel.cell_height + (self.offscreen_canvas.height - 22) * (max_temp - weather_hour.temp) / (max_temp - min_temp)),
                color = self.get_color(weather_hour),
                temp = weather_hour.temp,
            ))

        return points

    def get_color(self, weather_hour):
        if (weather_hour.code):
            return [255, 192, 64]
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
                    color[0] // stripe_divisor,
                    color[1] // stripe_divisor,
                    color[2] // stripe_divisor
                )

    
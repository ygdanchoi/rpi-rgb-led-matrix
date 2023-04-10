import asyncio
import json
import math
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

class TransitFeedViewModel(Observable):
    def __init__(self, transit_service, transit_row_factory, weather_service):
        super().__init__()

        self.transit_service = transit_service
        self.transit_row_factory = transit_row_factory
        self.weather_service = weather_service

        self.cell_height = 7
        self.cell_width = 4
        self.max_rows = 4
        self.stripe_divisor_light = 8
        self.stripe_divisor_dark = 16
        self.idx_desc = 5
        self.idx_etas = 24
        
        self.horizontal_offset = 0
        self.vertical_offset = 0
        self.stripes_offset = 0

        self.transit_lines = []
        self.rows = []
        self.weather_hour = None
        self.is_light_mode = True

        self.google_directions = ''
        self.google_directions_offset = 0

        asyncio.ensure_future(self.main_thread())
        asyncio.ensure_future(self.background_thread())
    
    async def main_thread(self):
        last_ns = time.time_ns()

        while True:            
            self.rows = self.transit_row_factory.create_rows(
                transit_lines=self.transit_lines,
                vertical_offset=self.vertical_offset,
                horizontal_offset=self.horizontal_offset,
                cell_height=self.cell_height,
                cell_width=self.cell_width,
                max_rows=self.max_rows
            )

            self.notify_observers()
            self.increment_offsets()
            
            last_delta_s = (time.time_ns() - last_ns) / 1_000_000_000
            # print(last_delta_s)
            s_to_wait = max(0, 0.060 - last_delta_s)
            await asyncio.sleep(s_to_wait)
            last_ns = time.time_ns()


    async def background_thread(self):
        update_transit_lines_timer = 0
        update_weather_timer = 0

        while True:
            hh = datetime.now().hour
            self.is_light_mode = 7 <= hh and hh < 22

            if update_transit_lines_timer == 0:
                await self.transit_service.update_transit_lines()
                self.transit_lines = self.transit_service.transit_lines
                update_transit_lines_timer = 30

            if update_weather_timer == 0:
                self.weather_hour = self.weather_service.get_weather()
                update_weather_timer = 60 * 60 if self.is_light_mode else 4 * 60 * 60

            update_transit_lines_timer -= 1
            update_weather_timer -= 1

            self.google_directions = json.loads(open('transit_mock_directions.json').read())
            
            await asyncio.sleep(1)
    
    def increment_offsets(self):
        self.stripes_offset += 1

        if self.stripes_offset >= 32:
            self.stripes_offset = 0

        if len(self.rows) < self.max_rows:
            if self.vertical_offset > 0:
                self.horizontal_offset = 0
            self.vertical_offset = 0
        else:
            self.vertical_offset += 1
        self.horizontal_offset += 1

        if self.vertical_offset >= self.cell_height * len(self.rows):
            self.vertical_offset = 0
            self.horizontal_offset = 0

        self.google_directions_offset += 1
    
    def is_stripe(self, x, y):
        return (x + y - self.stripes_offset // 2) // 8 % 2 == 0

class TransitFeedView(Observer, SampleBase):
    def __init__(self, *args, **kwargs):
        super(TransitFeedView, self).__init__(*args, **kwargs)
        
        self.viewmodel = TransitFeedViewModel(
            transit_service=kwargs['transit_service'],
            transit_row_factory=kwargs['transit_row_factory'],
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

        if len(self.viewmodel.rows) < self.viewmodel.max_rows:
            for xx in range(0, self.offscreen_canvas.width):
                self.draw_stripe_pixel(xx, 0, [31, 31, 31])

        for row in self.viewmodel.rows:
            if row.y < self.offscreen_canvas.height:
                # optimization to minimize number of textboxes to draw
                if row.dx_name == 0 and row.dx_description == 0:
                    self.draw_unscrolled_name_and_description_and_etas(row)
                elif row.dx_name == 0:
                    self.draw_scrolled_description(row)
                    self.draw_unscrolled_name_and_etas(row)
                elif row.dx_description == 0:
                    self.draw_scrolled_name(row)
                    self.draw_unscrolled_description_and_etas(row)
                else:
                    self.draw_scrolled_description(row)
                    self.draw_scrolled_name(row)
                    self.draw_unscrolled_etas(row)

        for yy in range(len(self.viewmodel.rows) * self.viewmodel.cell_height + 1, self.offscreen_canvas.height - self.viewmodel.cell_height):
            for xx in range(0, self.offscreen_canvas.width):
                self.draw_stripe_pixel(xx, yy, [31, 31, 31])

        self.draw_header()
        self.draw_footer()
        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)

    def draw_scrolled_description(self, row):
        self.draw_row_mask(row, self.viewmodel.idx_desc * self.viewmodel.cell_width, (self.viewmodel.idx_etas - 2) * self.viewmodel.cell_width)
        self.draw_text(
            row,
            1 + self.viewmodel.idx_desc * self.viewmodel.cell_width + row.dx_description,
            row.description
        )
        self.draw_row_mask(row, 0, self.viewmodel.idx_desc * self.viewmodel.cell_width)
        self.draw_row_mask(row, (self.viewmodel.idx_etas - 2) * self.viewmodel.cell_width, self.offscreen_canvas.width)

    def draw_scrolled_name(self, row):
        self.draw_text(
            row,
            1 + row.dx_name,
            row.name[:(self.viewmodel.idx_desc - 1 + max(0, 1 - (row.dx_name + 3) // self.viewmodel.cell_width))]
        )
        self.draw_row_mask(row, (self.viewmodel.idx_desc - 1) * self.viewmodel.cell_width, self.viewmodel.idx_desc * self.viewmodel.cell_width)

    def draw_unscrolled_etas(self, row):
        self.draw_text(
            row,
            1 + self.viewmodel.idx_etas * self.viewmodel.cell_width,
            row.etas
        )

    def draw_unscrolled_description_and_etas(self, row):
        self.draw_text(
            row,
            1 + self.viewmodel.idx_desc * self.viewmodel.cell_width,
            f'{row.description[:(self.viewmodel.idx_etas - self.viewmodel.idx_desc - 2)]:<{self.viewmodel.idx_etas - self.viewmodel.idx_desc}}{row.etas}'
        )
    
    def draw_unscrolled_name_and_etas(self, row):
        self.draw_text(
            row,
            1,
            f'{row.name[:(self.viewmodel.idx_desc - 1)]:<{self.viewmodel.idx_etas}}{row.etas}'
        )
    
    def draw_unscrolled_name_and_description_and_etas(self, row):
        self.draw_row_mask(row, 0, self.offscreen_canvas.width)
        self.draw_text(
            row,
            1,
            f'{row.name[:(self.viewmodel.idx_desc - 1)]:<{self.viewmodel.idx_desc}}{row.description[:(self.viewmodel.idx_etas - self.viewmodel.idx_desc - 2)]:<{self.viewmodel.idx_etas - self.viewmodel.idx_desc}}{row.etas}'
        )

    def draw_header(self):
        if not self.viewmodel.google_directions:
            return
        
        for yy in range(0, self.viewmodel.cell_height + 2):
            for xx in range(0, self.offscreen_canvas.width):
                self.draw_stripe_pixel(xx, yy, [255, 255, 255])

        route = self.viewmodel.google_directions['routes'][(self.viewmodel.google_directions_offset // 64) % len(self.viewmodel.google_directions['routes'])]
        leg = route['legs'][0]
        departure_time = leg['departure_time']['value']
        arrival_time = leg['arrival_time']['value']

        lines_to_draw = []

        def parse_step(step):
            if step['travel_mode'] == 'TRANSIT':
                line = step['transit_details']['line']
                name = line['short_name'] if 'short_name' in line else line['name']
                color = step['transit_details']['line']['color']
                lines_to_draw.append((
                    step['transit_details']['departure_time']['value'],
                    step['transit_details']['arrival_time']['value'],
                    [
                        int(color[1:3], 16),
                        int(color[3:5], 16),
                        int(color[5:7], 16)
                    ]
                ))
                return name + '|' + str(math.ceil(step['duration']['value'] / 60)) + 'm'
            else:
                return ' '
            
        text = datetime.fromtimestamp(departure_time).strftime('%-I:%M') + ''.join([parse_step(step) for step in leg['steps']]) + datetime.fromtimestamp(arrival_time).strftime('%-I:%M')

        incr = (arrival_time - departure_time) / 128
        for x in range(1, 128):
            t = departure_time + incr * x
            # print(t, lines_to_draw[0])
            for line_to_draw in lines_to_draw:
                if (line_to_draw[0] <= t and t <= line_to_draw[1]):
                    self.offscreen_canvas.SetPixel(
                        x,
                        1,
                        line_to_draw[2][0] if line_to_draw[2][0] > 0 else 255,
                        line_to_draw[2][1] if line_to_draw[2][1] > 0 else 255,
                        line_to_draw[2][2] if line_to_draw[2][2] > 0 else 255
                    )

        graphics.DrawText(
            self.offscreen_canvas,
            self.font,
            -self.viewmodel.transit_row_factory.beveled_zigzag(
                1 + self.viewmodel.google_directions_offset,
                len(text) * self.viewmodel.cell_width - self.offscreen_canvas.width,
                2 * self.viewmodel.cell_height
            ),
            self.viewmodel.cell_height + 1,
            self.get_text_color([255, 255, 255]),
            text
        )

    def draw_footer(self):
        for yy in range(self.offscreen_canvas.height - self.viewmodel.cell_height, self.offscreen_canvas.height):
            for xx in range(0, self.offscreen_canvas.width):
                self.draw_stripe_pixel(xx, yy, [255, 255, 255])

        temperature = f' • {int(round(self.viewmodel.weather_hour.temp, 0))}°F' if self.viewmodel.weather_hour else ''
        
        self.draw_text(
            None,
            1,
            f"{datetime.now().strftime('%a, %b %-d • %-I:%M:%S %p')}{temperature}" if temperature else datetime.now().strftime('%a, %b %-d, %Y • %-I:%M:%S %p')
        )

    def draw_text(self, row, x, text):
        graphics.DrawText(
            self.offscreen_canvas,
            self.font,
            x,
            row.y if row else self.offscreen_canvas.height - 1,
            self.get_text_color(row.color if row else [255, 255, 255]),
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

    
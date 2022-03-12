import bisect
import collections
import random

from datetime import datetime

WeatherPoint = collections.namedtuple('WeatherPoint', ['ts', 'hr', 'x', 'y', 'color', 'temp', 'pop', 'coords'])


class WeatherPointFactory:
    def create_points(self, forecast, cell_height, matrix_h):
        points = []

        weather_hours = forecast[0:1] + forecast[0:28]

        min_temp = float('inf')
        max_temp = float('-inf')
        for weather_hour in weather_hours:
            min_temp = min(min_temp, weather_hour.temp)
            max_temp = max(max_temp, weather_hour.temp)
        
        for i, weather_hour in enumerate(weather_hours):
            x = self.get_x(i)
            y = self.get_y(i, weather_hours, min_temp, max_temp, cell_height, matrix_h)

            coords = []

            if i < len(weather_hours) - 1:
                next_x = self.get_x(i + 1)
                next_y = self.get_y(i + 1, weather_hours, min_temp, max_temp, cell_height, matrix_h)
                mm = (y - next_y) / (x - next_x)
                bb = y - mm * x

                for xx in range(x, next_x):
                    yy = int(mm * xx + bb)
                    coords.append((xx, yy))

            points.append(WeatherPoint(
                ts = weather_hour.ts,
                hr = datetime.fromtimestamp(weather_hour.ts).strftime('%-I%p')[0:-1].lower(),
                x = x,
                y = y,
                color = self.get_color(weather_hour),
                temp = f'{int(round(weather_hour.temp, 0))}°',
                pop = f'{weather_hour.pop}%',
                coords = coords
            ))

        return points

    def get_x(self, i):
        return int(i / 24 * 114 - 3)
    
    def get_y(self, i, weather_hours, min_temp, max_temp, cell_height, matrix_h):
        return int(cell_height + (matrix_h - 22) * (max_temp - weather_hours[i].temp) / (max_temp - min_temp))
    
    # https://www.weatherbit.io/api/codes
    def get_color(self, weather_hour):
        code = weather_hour.code

        if 200 <= code and code <= 299: # thunderstorm
            return [203, 50, 121]
        elif 300 <= code and code <= 399: # drizzle
            return [81, 121, 243]
        elif 500 <= code and code <= 599: # rain
            return [81, 121, 243]
        elif 600 <= code and code <= 699: # snow
            return [231, 231, 231]
        elif 700 <= code and code <= 799: # fog
            return [50, 182, 122]
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

    def get_sunrises_x(self, points, sunrise_sunset, matrix_w):
        if len(points) == 0:
            return set()

        sunrises_x = set()

        m_ts = (points[1].x - points[-1].x) / (points[1].ts - points[-1].ts)
        b_ts = points[1].x - m_ts * points[1].ts
        
        for sunrise_ts in sunrise_sunset.sunrises:
            x = int(m_ts * sunrise_ts + b_ts)
            sunrises_x.add(x)
        
        return sunrises_x

    def get_sunsets_x(self, points, sunrise_sunset, matrix_w):
        if len(points) == 0:
            return set()

        sunsets_x = set()

        m_ts = (points[1].x - points[-1].x) / (points[1].ts - points[-1].ts)
        b_ts = points[1].x - m_ts * points[1].ts
        
        for sunset_ts in sunrise_sunset.sunsets:
            x = int(m_ts * sunset_ts + b_ts)
            sunsets_x.add(x)
        
        return sunsets_x

    def get_date_boundaries_x(self, points):
        if len(points) == 0:
            return set()

        date_boundaries_x = set()

        for point in points:
            if point.hr == '12a':
                date_boundaries_x.add(point.x)

        return date_boundaries_x



import collections
import random

from datetime import datetime

WeatherPoint = collections.namedtuple('WeatherPoint', ['ts', 'hr', 'x', 'y', 'color', 'temp', 'pop'])


class WeatherPointFactory:
    def create_points(self, forecast, cell_height, matrix_h):
        points = []

        min_temp = float('inf')
        max_temp = float('-inf')
        for weather_hour in forecast[0:28]:
            min_temp = min(min_temp, weather_hour.temp)
            max_temp = max(max_temp, weather_hour.temp)

        for i, weather_hour in enumerate(forecast[0:1] + forecast[0:28]):
            points.append(WeatherPoint(
                ts = weather_hour.ts,
                hr = datetime.fromtimestamp(weather_hour.ts).strftime('%-I%p')[0:-1].lower(),
                x = int(i / 24 * 114 - 3),
                y = int(cell_height + (matrix_h - 22) * (max_temp - weather_hour.temp) / (max_temp - min_temp)),
                color = self.get_color(weather_hour),
                temp = f'{int(round(weather_hour.temp, 0))}°',
                pop = f'{weather_hour.pop}%'
            ))

        return points

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
            return [215, 215, 216]
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

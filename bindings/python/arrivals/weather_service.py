import collections
import json
import requests
import traceback

from datetime import datetime, timedelta

import config

Weather = collections.namedtuple('Weather', ['temperature'])
WeatherHour = collections.namedtuple('WeatherHour', ['ts', 'temp', 'pop', 'icon', 'code', 'description'])
SunriseSunset = collections.namedtuple('SunriseSunset', ['sunrises', 'sunsets'])

class WeatherService:
    def __init__(self):
        self.empty_sunrise_sunset = SunriseSunset(sunrises=set(), sunsets=set())

    def get_weather(self):
        try:
            # raise Exception('Disabled weather API')

            response = requests.get('https://weatherbit-v1-mashape.p.rapidapi.com/current', params={
                'lat': 40.782,
                'lon': -73.954,
                'units': 'imperial'
            }, headers={
                'x-rapidapi-key': config.weather_api_key_backup,
                'x-rapidapi-host': 'weatherbit-v1-mashape.p.rapidapi.com',
                'useQueryString': 'true'
            })
            weather = json.loads(response.content)['data'][0]        
            return Weather(temperature=f"{int(round(weather['temp'], 0))}°F")
        except Exception as error:
            traceback.print_exc()
            return Weather(temperature='') 

    def get_forecast(self):
        try:
            live_weather = True

            if live_weather:
                response = requests.get('https://weatherbit-v1-mashape.p.rapidapi.com/forecast/hourly', params={
                    'lat': 40.782,
                    'lon': -73.954,
                    'units': 'imperial'
                }, headers={
                    'x-rapidapi-key': config.weather_api_key,
                    'x-rapidapi-host': 'weatherbit-v1-mashape.p.rapidapi.com',
                    'useQueryString': 'true'
                })
                content = response.content
                print(response.content)
            else:
                content = open('weather_mock_forecast.json').read()
            
            weather_hours = []
            for datum in json.loads(content)['data']:
                weather_hours.append(WeatherHour(
                    ts=datum['ts'],
                    temp=datum['temp'],
                    pop=datum['pop'],
                    icon=datum['weather']['icon'],
                    code=datum['weather']['code'],
                    description=datum['weather']['description']
                ))
            
            return weather_hours
        except Exception as error:
            traceback.print_exc()
            return []

    def get_sunrise_sunset(self):
        try:
            response_today = requests.get('https://api.sunrise-sunset.org/json', params={
                'lat': 40.782,
                'lng': -73.954,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'formatted': 0
            })
            response_tomorrow = requests.get('https://api.sunrise-sunset.org/json', params={
                'lat': 40.782,
                'lng': -73.954,
                'date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
                'formatted': 0
            })

            today = json.loads(response_today.content)['results']
            tomorrow = json.loads(response_tomorrow.content)['results']

            return SunriseSunset(
                sunrises={
                    self.parse_timestamp(today['sunrise']),
                    self.parse_timestamp(tomorrow['sunrise'])
                },
                sunsets={
                    self.parse_timestamp(today['sunset']),
                    self.parse_timestamp(tomorrow['sunset'])
                }
            )
        except Exception as error:
            traceback.print_exc()
            return self.empty_sunrise_sunset
    
    def parse_timestamp(self, isoformat):
        return int(datetime.fromisoformat(isoformat).timestamp())
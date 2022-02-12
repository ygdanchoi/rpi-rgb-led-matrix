import collections
import json
import requests
import traceback

import config

Weather = collections.namedtuple('Weather', ['temperature'])
WeatherHour = collections.namedtuple('WeatherHour', ['ts', 'timestamp_local', 'temp', 'pop', 'icon', 'code', 'description'])

class WeatherService:
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
            response = requests.get('https://weatherbit-v1-mashape.p.rapidapi.com/forecast/hourly', params={
                'lat': 40.782,
                'lon': -73.954,
                'units': 'imperial'
            }, headers={
                'x-rapidapi-key': config.weather_api_key,
                'x-rapidapi-host': 'weatherbit-v1-mashape.p.rapidapi.com',
                'useQueryString': 'true'
            })
            weather_hours = []

            for datum in json.loads(response.content)['data']:
                weather_hours.append(WeatherHour(
                    ts=datum['ts'],
                    timestamp_local=datum['timestamp_local'],
                    temp=datum['temp'],
                    pop=datum['pop'],
                    icon=datum['weather']['icon'],
                    code=datum['weather']['code'],
                    description=datum['weather']['description']
                ))
                print(weather_hours[-1])
            
            return weather_hours
        except Exception as error:
            traceback.print_exc()
            return []


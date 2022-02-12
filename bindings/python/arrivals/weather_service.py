import collections
import json
import requests
import traceback

import config

Weather = collections.namedtuple('Weather', ['temperature'])
WeatherHour = collections.namedtuple('WeatherHour', ['ts', 'temp', 'pop', 'icon', 'code', 'description'])

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
            content = response.content
            print(response.content)
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


import collections
import json
import requests
import traceback

import config

Weather = collections.namedtuple('Weather', ['temperature'])

class WeatherService:
    def get_weather(self):
        try:
            raise Exception('Disabled weather API')

            response = requests.get('https://weatherbit-v1-mashape.p.rapidapi.com/current', params={
                'lat': 40.782,
                'lon': -73.954,
                'units': 'imperial'
            }, headers={
                'x-rapidapi-key': config.weather_api_key_backup,
                'x-rapidapi-host': 'weatherbit-v1-mashape.p.rapidapi.com',
                'useQueryString': 'true'
            })
            print(response.content)
            weather = json.loads(response.content)['data'][0]        
            return Weather(temperature=f"{int(round(weather['temp'], 0))}°F")
        except Exception as error:
            traceback.print_exc()
            return Weather(temperature='') 

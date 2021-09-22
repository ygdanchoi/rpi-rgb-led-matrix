import collections
import json
import requests
import secrets
import traceback

Weather = collections.namedtuple('Weather', ['temperature'])

class WeatherService:
    def get_weather(self):
        try:
            response = requests.get('https://weatherbit-v1-mashape.p.rapidapi.com/current', params={
                'lat': 40.782,
                'lon': -73.954,
                'units': 'imperial'
            }, headers={
                'x-rapidapi-key': secrets.weather_api_key,
                'x-rapidapi-host': 'weatherbit-v1-mashape.p.rapidapi.com',
                'useQueryString': 'true'
            })
            weather = json.loads(response.content)['data'][0]        
            return Weather(temperature=f" • {weather['temp']}°F")
        except Exception as error:
            traceback.print_exc()
            return Weather(temperature='')

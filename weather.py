import openmeteo_requests
import requests_cache
from retry_requests import retry

def get_weather(latitude=47.5596, longitude=7.5886, timezone="Europe/Berlin"):

    cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    url = f"https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude" : latitude,
        "longitude" : longitude,
        "current" : "weather_code",
        "daily" : "temperature_2m_max",
        "timezone" : timezone,
        "forecast_days" : 1,
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]

    current = response.Current()
    weather_code = current.Variables(0).Value()
    

    daily = response.Daily()
    max_temp = round(daily.Variables(0).ValuesAsNumpy()[0], 0)

    weather_map = {
        0: "☀️ Clear",
        1: "🌤️ Mostly Clear",
        2: "⛅ Partly Cloudy",
        3: "☁️ Overcast",
        45: "🌫️ Fog",
        51: "🌧️ Drizzle",
        61: "☔ Rain",
        71: "❄️ Snow",
        95: "⛈️ Thunderstorm"
    }

    condition = weather_map.get(weather_code, "🌍\tUnknown")
    
    return f"{condition}, {max_temp} °C"
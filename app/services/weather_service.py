import requests

from app.services.cities import lookup_city

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# (连接超时, 读取超时) 秒
TIMEOUT = (3, 10)
RETRIES = 1


WMO_CODE_MAP = {
    0:  ("晴天", "sunny"),
    1:  ("主要晴朗", "partly"),
    2:  ("部分多云", "partly"),
    3:  ("多云 / 阴天", "cloudy"),
    45: ("雾", "fog"),
    48: ("雾凇", "fog"),
    51: ("小毛毛雨", "rain_light"),
    53: ("毛毛雨", "rain_light"),
    55: ("大毛毛雨", "rain_moderate"),
    56: ("冻毛毛雨", "rain_light"),
    57: ("强冻毛毛雨", "rain_moderate"),
    61: ("小雨", "rain_light"),
    63: ("中雨", "rain_moderate"),
    65: ("大雨", "rain_heavy"),
    66: ("冻雨", "rain_light"),
    67: ("强冻雨", "rain_moderate"),
    71: ("小雪", "snow_light"),
    73: ("中雪", "snow_light"),
    75: ("大雪", "snow_heavy"),
    77: ("米雪", "snow_light"),
    80: ("小阵雨", "rain_light"),
    81: ("中阵雨", "rain_moderate"),
    82: ("强阵雨", "rain_heavy"),
    85: ("小阵雪", "snow_light"),
    86: ("大阵雪", "snow_heavy"),
    95: ("雷暴", "thunder"),
    96: ("雷暴伴小冰雹", "thunder"),
    99: ("雷暴伴大冰雹", "thunder"),
}


def describe_weather(code: int) -> tuple[str, str]:
    """返回 (中文描述, 图标类型键)。未知代码回退为多云。"""
    return WMO_CODE_MAP.get(code, ("未知天气", "cloudy"))


def _request_json(url: str, params: dict) -> dict | None:
    """带重试的 GET，失败返回 None，绝不抛异常给调用方。"""
    for _ in range(RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError):
            continue
    return None


def geocode_city(city_name: str, language: str = "zh") -> dict | None:
    """城市名 → 经纬度。先查本地字典，未命中再走在线 Geocoding。"""
    local = lookup_city(city_name)
    if local:
        return local

    data = _request_json(GEOCODING_URL, {
        "name": city_name,
        "count": 1,
        "language": language,
        "format": "json",
    })
    if not data:
        return None
    results = data.get("results")
    if not results:
        return None
    first = results[0]
    return {
        "name": first.get("name", city_name),
        "latitude": first["latitude"],
        "longitude": first["longitude"],
        "country": first.get("country", ""),
        "admin1": first.get("admin1", ""),
    }


def fetch_daily_forecast(latitude: float, longitude: float, days: int = 7) -> dict | None:
    data = _request_json(FORECAST_URL, {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "wind_speed_10m_max,precipitation_sum",
        "forecast_days": days,
        "timezone": "auto",
    })
    if not data:
        return None
    daily = data.get("daily")
    if not daily:
        return None
    return {
        "time": daily.get("time", []),
        "weather_code": daily.get("weather_code", []),
        "temp_max": daily.get("temperature_2m_max", []),
        "temp_min": daily.get("temperature_2m_min", []),
        "wind_max": daily.get("wind_speed_10m_max", []),
        "precip_sum": daily.get("precipitation_sum", []),
    }
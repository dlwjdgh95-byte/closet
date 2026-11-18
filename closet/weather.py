"""오늘 날씨 가져오기 (Open-Meteo, 키 불필요)."""
import json
import urllib.parse
import urllib.request

SEOUL = (37.5665, 126.9780)
URL = "https://api.open-meteo.com/v1/forecast"


def parse(payload, rain_probability=50):
    """Open-Meteo 응답에서 (체감기온, 비 여부)를 뽑습니다.

    하루 중 밖에 있는 시간대를 모르므로 체감 최고·최저의 평균을 씁니다.
    """
    daily = payload["daily"]
    temp = (daily["apparent_temperature_max"][0] + daily["apparent_temperature_min"][0]) / 2
    rain = (daily["precipitation_probability_max"][0] or 0) >= rain_probability
    return round(temp, 1), rain


def today(lat=SEOUL[0], lon=SEOUL[1], rain_probability=50, timeout=10):
    query = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "daily": "apparent_temperature_max,apparent_temperature_min,precipitation_probability_max",
        "timezone": "auto", "forecast_days": 1,
    })
    with urllib.request.urlopen(f"{URL}?{query}", timeout=timeout) as res:
        return parse(json.load(res), rain_probability)

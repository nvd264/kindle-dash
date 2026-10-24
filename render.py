#!/usr/bin/env python3
"""Render a weather dashboard PNG for Kindle Paperwhite 4 (1072x1448, grayscale)."""
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, M = 1072, 1448, 56
PLACE = "District 9 · Ho Chi Minh City"
URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=10.84&longitude=106.83&timezone=Asia/Ho_Chi_Minh&forecast_days=7"
    "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m"
    "&hourly=temperature_2m,precipitation_probability"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset"
)
AQ_URL = (
    "https://air-quality-api.open-meteo.com/v1/air-quality"
    "?latitude=10.84&longitude=106.83&timezone=Asia/Ho_Chi_Minh&current=us_aqi,pm2_5"
)
# US AQI bands (upper bound, label)
AQI_BANDS = [(50, "Good"), (100, "Moderate"), (150, "Poor"), (200, "Unhealthy"), (300, "Very poor"), (9999, "Hazardous")]
# WMO weather codes (snow codes omitted: not happening in Saigon)
WMO = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Drizzle", 57: "Drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Rain", 67: "Heavy rain",
    80: "Light showers", 81: "Showers", 82: "Violent showers", 95: "Thunderstorm", 96: "Storm, hail", 99: "Storm, hail",
}
# e-ink has 16 gray levels; multiples of 17 map exactly
DARK, MID, LIGHT = 0x44, 0x88, 0xCC

FONTS = Path(__file__).parent / "fonts"


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / f"BeVietnamPro-{'Bold' if bold else 'Regular'}.ttf"), size)


def render(data, aq=None):
    cur, hourly, daily = data["current"], data["hourly"], data["daily"]
    now = datetime.fromisoformat(cur["time"])
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)

    d.text((M, 48), PLACE, font=font(36), fill=DARK)
    d.text((W - M, 56), f"Updated {now:%H:%M}", font=font(30), fill=MID, anchor="ra")
    d.text((M, 96), f"{now:%A}, {now.day} {now:%b}", font=font(64, True), fill=0)

    d.text((M, 190), f"{round(cur['temperature_2m'])}°", font=font(240, True), fill=0)
    x = 580
    d.text((x, 230), WMO.get(cur["weather_code"], "—"), font=font(52, True), fill=0)
    lines = [
        f"Feels like {round(cur['apparent_temperature'])}°",
        f"Humidity {cur['relative_humidity_2m']}%",
        f"Wind {round(cur['wind_speed_10m'])} km/h",
    ]
    if aq:
        aqi = aq["us_aqi"]
        label = next(name for top, name in AQI_BANDS if aqi <= top)
        lines.append(f"AQI {aqi} · {label}")
    for i, line in enumerate(lines):
        d.text((x, 310 + i * 52), line, font=font(38), fill=DARK)

    d.line((M, 530, W - M, 530), fill=LIGHT, width=3)
    d.text((M, 556), "Next 12 hours · chance of rain", font=font(32), fill=MID)
    start = hourly["time"].index(cur["time"][:13] + ":00")
    col = (W - 2 * M) / 12
    bar_top, bar_bottom = 706, 840
    for i in range(12):
        h = start + i
        cx = M + col * (i + 0.5)
        d.text((cx, 612), f"{datetime.fromisoformat(hourly['time'][h]):%-I%p}".lower(), font=font(28), fill=DARK, anchor="ma")
        d.text((cx, 652), f"{round(hourly['temperature_2m'][h])}°", font=font(32, True), fill=0, anchor="ma")
        p = hourly["precipitation_probability"][h] or 0
        y = bar_bottom - (bar_bottom - bar_top) * p / 100
        d.rectangle((cx - 22, bar_top, cx + 22, bar_bottom), outline=LIGHT, width=2)
        if p:
            d.rectangle((cx - 22, y, cx + 22, bar_bottom), fill=MID)
        d.text((cx, 852), f"{p}%", font=font(24), fill=DARK, anchor="ma")

    d.line((M, 905, W - M, 905), fill=LIGHT, width=3)
    d.text((W - M - 190, 928), "Temp", font=font(28), fill=MID, anchor="ra")
    d.text((W - M, 928), "Rain", font=font(28), fill=MID, anchor="ra")
    for i, day in enumerate(daily["time"]):
        y = 976 + i * 54
        date = datetime.fromisoformat(day)
        label = "Today" if i == 0 else f"{date:%a} {date.day}"
        d.text((M, y), label, font=font(34, True), fill=0)
        d.text((M + 230, y), WMO.get(daily["weather_code"][i], "—"), font=font(34), fill=DARK)
        temps = f"{round(daily['temperature_2m_min'][i])}° – {round(daily['temperature_2m_max'][i])}°"
        d.text((W - M - 190, y), temps, font=font(34, True), fill=0, anchor="ra")
        d.text((W - M, y), f"{daily['precipitation_probability_max'][i] or 0}%", font=font(34), fill=DARK, anchor="ra")

    sun = f"Sunrise {daily['sunrise'][0][11:]} · Sunset {daily['sunset'][0][11:]}"
    d.text((M, H - 56), sun, font=font(28), fill=MID, anchor="ls")
    d.text((W - M, H - 56), "Open-Meteo", font=font(28), fill=MID, anchor="rs")
    return img


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out/dash.png")
    with urllib.request.urlopen(URL, timeout=30) as r:
        data = json.load(r)
    try:
        with urllib.request.urlopen(AQ_URL, timeout=30) as r:
            aq = json.load(r)["current"]
    except Exception as e:  # air quality is optional; never lose the weather over it
        print("air quality unavailable:", e)
        aq = None
    out.parent.mkdir(parents=True, exist_ok=True)
    render(data, aq).save(out)
    print(out)

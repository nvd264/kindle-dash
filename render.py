#!/usr/bin/env python3
"""Render a weather dashboard PNG for Kindle Paperwhite 4 (1072x1448, grayscale).

From 23:00 to 06:00 it shows a public-domain artwork instead. --night forces that.
"""
import io
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

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

# one artist per night, rotating; all have public-domain portrait-format works at the Art Institute of Chicago
ARTISTS = ["Katsushika Hokusai", "Utagawa Hiroshige", "Rembrandt van Rijn", "Kitagawa Utamaro",
           "Albrecht Dürer", "James McNeill Whistler", "Vincent van Gogh", "Utagawa Kuniyoshi"]
# AIC returns 403 unless both headers are set
AIC_HEADERS = {"User-Agent": "kindle-dash (github.com/nvd264/kindle-dash)", "AIC-User-Agent": "kindle-dash (github.com/nvd264/kindle-dash)"}
GRAYS = Image.new("P", (1, 1))
GRAYS.putpalette([v for i in range(16) for v in (i * 17,) * 3])


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / f"BeVietnamPro-{'Bold' if bold else 'Regular'}.ttf"), size)


def fit(text, f, width):
    if f.getlength(text) <= width:
        return text
    while f.getlength(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=AIC_HEADERS), timeout=30) as r:
        return r.read()


def night_art(night):
    artist = ARTISTS[night % len(ARTISTS)]
    query = urllib.parse.urlencode({"q": artist, "query[term][is_public_domain]": "true", "limit": 100,
                                    "fields": "title,artist_title,date_display,image_id,thumbnail"})
    works = [a for a in json.loads(fetch("https://api.artic.edu/api/v1/artworks/search?" + query))["data"]
             if a.get("image_id") and a.get("artist_title") == artist
             and (a.get("thumbnail") or {}).get("height", 0) > (a.get("thumbnail") or {}).get("width", 1)]
    art = works[night // len(ARTISTS) % len(works)]
    img = Image.open(io.BytesIO(fetch(f"https://www.artic.edu/iiif/2/{art['image_id']}/full/1686,/0/default.jpg")))
    return art, img


def render_art(art, img, cur):
    canvas = Image.new("L", (W, H), 255)
    img = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    img.thumbnail((W - 80, H - 220))
    # dither to the panel's 16 grays so gradients don't band
    img = img.convert("RGB").quantize(palette=GRAYS, dither=Image.Dither.FLOYDSTEINBERG).convert("L")
    canvas.paste(img, ((W - img.width) // 2, 40 + (H - 220 - img.height) // 2))
    d = ImageDraw.Draw(canvas)
    title = art["title"].split(" (")[0]
    d.text((M, H - 150), fit(title, font(34, True), W - 2 * M), font=font(34, True), fill=0)
    credit = f"{art['artist_title']} · {art['date_display']}"
    d.text((M, H - 100), fit(credit, font(28), W - 2 * M - 120), font=font(28), fill=DARK)
    d.text((W - M, H - 100), f"{round(cur['temperature_2m'])}°", font=font(28, True), fill=0, anchor="ra")
    return canvas


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
    args = [a for a in sys.argv[1:] if a != "--night"]
    out = Path(args[0] if args else "out/dash.png")
    with urllib.request.urlopen(URL, timeout=30) as r:
        data = json.load(r)
    try:
        with urllib.request.urlopen(AQ_URL, timeout=30) as r:
            aq = json.load(r)["current"]
    except Exception as e:  # air quality is optional; never lose the weather over it
        print("air quality unavailable:", e)
        aq = None
    now = datetime.fromisoformat(data["current"]["time"])
    img = None
    if now.hour >= 23 or now.hour < 6 or "--night" in sys.argv:
        try:
            # shift by 6h so the whole night (23:00-06:00) keeps one artwork
            img = render_art(*night_art((now - timedelta(hours=6)).toordinal()), data["current"])
        except Exception as e:  # museum down: show the weather instead
            print("night art unavailable:", e)
    out.parent.mkdir(parents=True, exist_ok=True)
    (img or render(data, aq)).save(out)
    print(out)

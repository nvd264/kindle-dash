#!/usr/bin/env python3
"""Render a weather dashboard PNG for Kindle Paperwhite 4 (1072x1448, grayscale)."""
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, M = 1072, 1448, 56
PLACE = "Quận 9 · TP.HCM"
URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=10.84&longitude=106.83&timezone=Asia/Ho_Chi_Minh&forecast_days=7"
    "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m"
    "&hourly=temperature_2m,precipitation_probability"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset"
)
# WMO weather codes (snow codes omitted: not happening in Saigon)
WMO = {
    0: "Trời quang", 1: "Ít mây", 2: "Mây rải rác", 3: "Nhiều mây", 45: "Sương mù", 48: "Sương mù",
    51: "Mưa phùn nhẹ", 53: "Mưa phùn", 55: "Mưa phùn dày", 56: "Mưa phùn", 57: "Mưa phùn",
    61: "Mưa nhỏ", 63: "Mưa vừa", 65: "Mưa to", 66: "Mưa", 67: "Mưa to",
    80: "Mưa rào nhẹ", 81: "Mưa rào", 82: "Mưa rào rất to", 95: "Dông", 96: "Dông, mưa đá", 99: "Dông, mưa đá",
}
WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
SHORT = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
# e-ink has 16 gray levels; multiples of 17 map exactly
DARK, MID, LIGHT = 0x44, 0x88, 0xCC

FONTS = Path(__file__).parent / "fonts"


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / f"BeVietnamPro-{'Bold' if bold else 'Regular'}.ttf"), size)


def render(data):
    cur, hourly, daily = data["current"], data["hourly"], data["daily"]
    now = datetime.fromisoformat(cur["time"])
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)

    d.text((M, 48), PLACE, font=font(36), fill=DARK)
    d.text((W - M, 56), f"Cập nhật {now:%H:%M}", font=font(30), fill=MID, anchor="ra")
    d.text((M, 96), f"{WEEKDAYS[now.weekday()]}, {now:%d/%m}", font=font(64, True), fill=0)

    d.text((M, 190), f"{round(cur['temperature_2m'])}°", font=font(240, True), fill=0)
    x = 580
    d.text((x, 240), WMO.get(cur["weather_code"], "—"), font=font(52, True), fill=0)
    for i, line in enumerate([
        f"Cảm giác {round(cur['apparent_temperature'])}°",
        f"Độ ẩm {cur['relative_humidity_2m']}%",
        f"Gió {round(cur['wind_speed_10m'])} km/h",
    ]):
        d.text((x, 330 + i * 56), line, font=font(38), fill=DARK)

    d.line((M, 530, W - M, 530), fill=LIGHT, width=3)
    d.text((M, 556), "12 giờ tới · khả năng mưa", font=font(32), fill=MID)
    start = hourly["time"].index(cur["time"][:13] + ":00")
    col = (W - 2 * M) / 12
    bar_top, bar_bottom = 706, 840
    for i in range(12):
        h = start + i
        cx = M + col * (i + 0.5)
        d.text((cx, 612), f"{hourly['time'][h][11:13]}h", font=font(28), fill=DARK, anchor="ma")
        d.text((cx, 652), f"{round(hourly['temperature_2m'][h])}°", font=font(32, True), fill=0, anchor="ma")
        p = hourly["precipitation_probability"][h] or 0
        y = bar_bottom - (bar_bottom - bar_top) * p / 100
        d.rectangle((cx - 22, bar_top, cx + 22, bar_bottom), outline=LIGHT, width=2)
        if p:
            d.rectangle((cx - 22, y, cx + 22, bar_bottom), fill=MID)
        d.text((cx, 852), f"{p}%", font=font(24), fill=DARK, anchor="ma")

    d.line((M, 905, W - M, 905), fill=LIGHT, width=3)
    d.text((W - M - 190, 928), "Nhiệt độ", font=font(28), fill=MID, anchor="ra")
    d.text((W - M, 928), "Mưa", font=font(28), fill=MID, anchor="ra")
    for i, day in enumerate(daily["time"]):
        y = 976 + i * 54
        date = datetime.fromisoformat(day)
        label = "Hôm nay" if i == 0 else f"{SHORT[date.weekday()]} {date:%d/%m}"
        d.text((M, y), label, font=font(34, True), fill=0)
        d.text((M + 230, y), WMO.get(daily["weather_code"][i], "—"), font=font(34), fill=DARK)
        temps = f"{round(daily['temperature_2m_min'][i])}° – {round(daily['temperature_2m_max'][i])}°"
        d.text((W - M - 190, y), temps, font=font(34, True), fill=0, anchor="ra")
        d.text((W - M, y), f"{daily['precipitation_probability_max'][i] or 0}%", font=font(34), fill=DARK, anchor="ra")

    sun = f"Mặt trời mọc {daily['sunrise'][0][11:]} · lặn {daily['sunset'][0][11:]}"
    d.text((M, H - 56), sun, font=font(28), fill=MID, anchor="ls")
    d.text((W - M, H - 56), "Open-Meteo", font=font(28), fill=MID, anchor="rs")
    return img


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out/dash.png")
    with urllib.request.urlopen(URL, timeout=30) as r:
        data = json.load(r)
    out.parent.mkdir(parents=True, exist_ok=True)
    render(data).save(out)
    print(out)

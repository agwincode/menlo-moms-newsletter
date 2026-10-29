"""Weekend forecast for Menlo Park.

National Weather Service first (matches what readers see on their phones).
NWS only reaches ~7 days out, so any day it doesn't cover falls back to
Open-Meteo and is marked "early" (Open-Meteo has run ~10°F hot here).
A day with no data is marked unavailable. Nothing is ever guessed.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta

import requests

LAT, LON = 37.4530, -122.1817
NWS_HEADERS = {"User-Agent": "MenloMomsWeekendGuide/2.0 (github.com/agwincode)",
               "Accept": "application/geo+json"}
WMO = {0: "sunny", 1: "mostly sunny", 2: "partly cloudy", 3: "cloudy", 45: "foggy", 48: "foggy",
       51: "light drizzle", 53: "drizzle", 55: "drizzle", 61: "light rain", 63: "rain",
       65: "heavy rain", 80: "showers", 81: "showers", 82: "heavy showers", 95: "thunderstorms"}
DAYS = ("Friday", "Saturday", "Sunday")

WEATHER_START = "<!-- weather -->"
WEATHER_END = "<!-- /weather -->"


def _get_json(url, headers=None, tries=4):
    err = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            err = e
            time.sleep(1.5 * (i + 1))
    raise err


def _nws(dates):
    out = {}
    try:
        fc = _get_json(f"https://api.weather.gov/points/{LAT},{LON}", NWS_HEADERS)["properties"]["forecast"]
        for p in _get_json(fc, NWS_HEADERS)["properties"]["periods"]:
            d = p["startTime"][:10]
            if d not in dates:
                continue
            day = out.setdefault(d, {})
            if p.get("isDaytime"):
                day["high"] = p["temperature"]
                day["condition"] = p["shortForecast"]
            else:
                day["low"] = p["temperature"]
    except Exception as e:
        logging.warning("NWS failed: %r", e)
    return {d: v for d, v in out.items() if "high" in v}


def _open_meteo(dates):
    out = {}
    try:
        data = _get_json(
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT}&longitude={LON}&daily=temperature_2m_max,temperature_2m_min,weathercode"
            "&temperature_unit=fahrenheit&timezone=America%2FLos_Angeles"
            f"&start_date={min(dates)}&end_date={max(dates)}")["daily"]
        for i, d in enumerate(data["time"]):
            if data["temperature_2m_max"][i] is None:
                continue
            out[d] = {"high": round(data["temperature_2m_max"][i]),
                      "low": round(data["temperature_2m_min"][i]),
                      "condition": WMO.get(data["weathercode"][i], "mixed conditions")}
    except Exception as e:
        logging.warning("Open-Meteo failed: %r", e)
    return out


def _tidy(cond: str) -> str:
    c = cond.lower().replace(" then ", ", ")
    c = c.replace("slight chance ", "slight chance of ").replace("chance ", "chance of ")
    return c.replace("of of", "of")


def forecast(friday: date) -> dict:
    dates = [(friday + timedelta(days=i)).isoformat() for i in range(3)]
    nws = _nws(set(dates))
    missing = [d for d in dates if d not in nws]
    om = _open_meteo(missing) if missing else {}
    days = []
    for label, d in zip(DAYS, dates):
        if d in nws:
            days.append({"label": label, "date": d, "source": "nws", **nws[d]})
        elif d in om:
            days.append({"label": label, "date": d, "source": "open-meteo (early)", **om[d]})
        else:
            days.append({"label": label, "date": d, "source": "unavailable"})
    return {"friday": friday.isoformat(), "fetched": date.today().isoformat(),
            "days": days, "line": weather_line(days)}


def weather_line(days) -> str:
    have = [d for d in days if d["source"] != "unavailable"]
    if not have:
        return "**[Weather unavailable. It refreshes every morning; check before sending.]**"
    parts = [f"{d['label']} {_tidy(d['condition'])} ({d['high']}°F)" for d in have]
    line = "Forecast: " + ", ".join(parts) + "."
    gaps = [d["label"] for d in days if d["source"] == "unavailable"]
    if gaps:
        line += f" **[{' and '.join(gaps)} forecast not out yet.]**"
    return line


def replace_block(text: str, line: str) -> str:
    s, e = text.find(WEATHER_START), text.find(WEATHER_END)
    if s == -1 or e == -1 or e < s:
        return text
    return text[: s + len(WEATHER_START)] + line + text[e:]


if __name__ == "__main__":
    import sys
    f = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    print(json.dumps(forecast(f), indent=2))

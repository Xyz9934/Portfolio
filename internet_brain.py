import csv
import io
import re
import webbrowser
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import requests


USER_AGENT = "FRIDAY-AI/1.0"


def can_handle_live_query(question):
    text = normalize(question)
    return any(
        (
            is_weather_query(text),
            is_news_query(text),
            is_stock_query(text),
            is_google_search_query(text),
        )
    )


def handle_live_query(question):
    text = normalize(question)

    if is_weather_query(text):
        location = extract_weather_location(question)
        return get_weather(location)

    if is_news_query(text):
        topic = extract_news_topic(question)
        return get_news(topic)

    if is_stock_query(text):
        symbol = extract_stock_symbol(question)
        if not symbol:
            return "Tell me the stock symbol, like `AAPL` or `RELIANCE`."
        return get_stock_price(symbol)

    if is_google_search_query(text):
        search_text = extract_search_query(question)
        if not search_text:
            return "Tell me what you want me to search on Google."
        return google_search(search_text)

    return None


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_weather_query(text):
    return "weather" in text or "temperature" in text or "forecast" in text


def is_news_query(text):
    return "news" in text or "headline" in text or "headlines" in text


def is_stock_query(text):
    return "stock" in text or "share price" in text or "market price" in text or "ticker" in text


def is_google_search_query(text):
    patterns = (
        "google ",
        "search google for ",
        "search the web for ",
        "search for ",
        "look up ",
    )
    return any(pattern in text for pattern in patterns)


def extract_weather_location(question):
    lower = normalize(question)

    patterns = [
        r"(?:weather|forecast|temperature)(?: in| at| for)? (.+)$",
        r"how is the weather(?: in| at| for)? (.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            location = match.group(1).strip(" ?.!")
            if location:
                return location

    return ""


def extract_news_topic(question):
    lower = normalize(question)
    patterns = [
        r"(?:latest|today'?s|top)? ?news(?: about| on| for)? (.+)$",
        r"headlines(?: about| on| for)? (.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            topic = match.group(1).strip(" ?.!")
            if topic:
                return topic

    return ""


def extract_stock_symbol(question):
    match = re.search(r"\b([A-Z]{1,8})(?:\.NS|\.BO)?\b", question or "")
    if match:
        return match.group(1).lower()

    lower = normalize(question)
    patterns = [
        r"(?:stock|share price|market price|ticker)(?: of| for)? ([a-z0-9._-]+)",
        r"price of ([a-z0-9._-]+) stock",
    ]

    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return match.group(1).strip(" ?.!")

    return ""


def extract_search_query(question):
    lower = normalize(question)
    patterns = [
        r"search google for (.+)$",
        r"search the web for (.+)$",
        r"search for (.+)$",
        r"look up (.+)$",
        r"google (.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return match.group(1).strip(" ?.!")

    return ""


def get_weather(location):
    target = location or "your location"
    url = f"https://wttr.in/{quote_plus(location)}?format=j1" if location else "https://wttr.in/?format=j1"

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return f"I couldn't fetch live weather right now: {exc}"

    current = data.get("current_condition", [{}])[0]
    area = data.get("nearest_area", [{}])[0]
    resolved_location = area.get("areaName", [{}])[0].get("value") or target
    temp_c = current.get("temp_C", "?")
    feels_c = current.get("FeelsLikeC", "?")
    humidity = current.get("humidity", "?")
    description = current.get("weatherDesc", [{}])[0].get("value", "Unavailable")

    return (
        f"Live weather for {resolved_location}: {description}, {temp_c}°C, "
        f"feels like {feels_c}°C, humidity {humidity}%."
    )


def get_news(topic=""):
    if topic:
        rss_url = f"https://news.google.com/rss/search?q={quote_plus(topic)}&hl=en-IN&gl=IN&ceid=IN:en"
        label = topic
    else:
        rss_url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
        label = "top headlines"

    try:
        response = requests.get(rss_url, headers={"User-Agent": USER_AGENT}, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except Exception as exc:
        return f"I couldn't fetch live news right now: {exc}"

    items = root.findall("./channel/item")[:3]
    if not items:
        return "I couldn't find any live headlines right now."

    headlines = []
    for index, item in enumerate(items, start=1):
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        if source:
            headlines.append(f"{index}. {title} ({source})")
        else:
            headlines.append(f"{index}. {title}")

    return "Live news for " + label + ":\n" + "\n".join(headlines)


def get_stock_price(symbol):
    lookup = symbol.lower()
    url = f"https://stooq.com/q/l/?s={quote_plus(lookup)}&f=sd2t2ohlcvn&e=csv"

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        response.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(response.text)))
    except Exception as exc:
        return f"I couldn't fetch the live stock price right now: {exc}"

    if not rows:
        return f"I couldn't find live market data for {symbol.upper()}."

    row = rows[0]
    if (row.get("close") or "").lower() in {"", "n/d"}:
        return f"I couldn't find live market data for {symbol.upper()}."

    name = row.get("name") or symbol.upper()
    close = row.get("close", "?")
    date = row.get("date", "unknown date")
    time_value = row.get("time", "unknown time")
    open_price = row.get("open", "?")
    high = row.get("high", "?")
    low = row.get("low", "?")
    volume = row.get("volume", "?")

    return (
        f"Live market snapshot for {name}: last price {close}, open {open_price}, "
        f"high {high}, low {low}, volume {volume}, updated {date} {time_value}."
    )


def google_search(query):
    url = f"https://www.google.com/search?q={quote_plus(query)}"

    try:
        webbrowser.open(url)
    except Exception as exc:
        return f"I couldn't open Google search automatically: {exc}"

    return f"Opened Google search for {query}."

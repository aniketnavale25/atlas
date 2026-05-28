"""
tools.py
--------
Tool definitions for the Atlas agent.

DESIGN PRINCIPLE: This module makes REAL API calls only. There are no mock
fallbacks. If an API is not configured or its call fails, the tool returns
a structured "unavailable" response that the agent can reason about and
either skip or surface in the final plan.

This makes the agent's behavior honest:
  - "I couldn't get weather data" instead of inventing a forecast.
  - "Hotel search is unavailable" instead of fabricating hotels.

The trade-off: you need API keys to get real data. Without them, the agent
will openly report which data sources are missing.

Each tool returns a dict with one of these shapes:

  Success:
    {"status": "ok", "source": "amadeus", "results": [...]}

  Tool not configured (missing API key):
    {"status": "unavailable", "tool": "search_flights",
     "reason": "Amadeus API credentials not configured. Set
                AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET in .env."}

  Call failed (network, rate limit, bad params, etc):
    {"status": "error", "tool": "search_flights",
     "reason": "API returned 429: rate limit exceeded"}

  Valid call but no results:
    {"status": "no_results", "tool": "search_flights", "results": []}
"""

from __future__ import annotations
import json
from datetime import datetime
from collections import defaultdict
from typing import Any

import requests

from config import CONFIG


# ---------------------------------------------------------------------------
# TOOL SCHEMAS - what the LLM sees and uses to decide when to call each tool
# ---------------------------------------------------------------------------
# OpenAI format: each tool is wrapped in {"type": "function", "function": ...}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": (
                "Search for real flights via SerpAPI's Google Flights engine. "
                "Returns flight options with price, duration, airline, and stops. "
                "If you provide return_date, this becomes a ROUND-TRIP search "
                "(usually 20-40% cheaper than two one-way tickets — prefer this "
                "for typical trips). Only omit return_date if the user explicitly "
                "wants one-way or open-jaw."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Origin IATA airport code (e.g. 'BOS', 'JFK', 'LIS').",
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination IATA airport code.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Outbound departure date in YYYY-MM-DD format.",
                    },
                    "return_date": {
                        "type": "string",
                        "description": (
                            "Return date in YYYY-MM-DD format. When set, the "
                            "search is round-trip and the returned price covers "
                            "BOTH legs. Highly recommended for trips with a "
                            "fixed end date — round-trip pricing is typically "
                            "20-40% cheaper than booking two one-ways."
                        ),
                    },
                    "passengers": {
                        "type": "integer",
                        "description": "Number of adult passengers. Defaults to 1.",
                    },
                    "max_price_usd": {
                        "type": "number",
                        "description": "Optional. Filter to flights under this price per passenger.",
                    },
                },
                "required": ["origin", "destination", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": (
                "Search hotels in a city for a given date range using "
                "SerpAPI's Google Hotels engine. Returns options with "
                "nightly rate, total cost, rating, and amenities."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "check_in": {"type": "string", "description": "YYYY-MM-DD"},
                    "check_out": {"type": "string", "description": "YYYY-MM-DD"},
                    "guests": {"type": "integer"},
                    "max_nightly_usd": {
                        "type": "number",
                        "description": "Optional nightly price ceiling.",
                    },
                    "min_rating": {
                        "type": "number",
                        "description": "Optional minimum star rating (1-5).",
                    },
                },
                "required": ["city", "check_in", "check_out"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_forecast",
            "description": (
                "Get a real daily weather forecast for a city using "
                "OpenWeatherMap. NOTE: free tier only forecasts up to 5 "
                "days into the future from today. Dates further out will "
                "return unavailable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["city", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_activities",
            "description": (
                "Find activities, attractions, tours, or experiences in a "
                "city via SerpAPI's Google Maps engine."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "interest": {
                        "type": "string",
                        "description": "Category of activity (e.g. 'museums', 'food tours').",
                    },
                    "max_price_usd": {"type": "number"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": (
                "Find restaurants in a city via SerpAPI's Google Maps "
                "engine, optionally filtered by cuisine or dietary needs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "cuisine": {"type": "string"},
                    "dietary": {
                        "type": "string",
                        "description": "e.g. 'vegetarian', 'vegan', 'halal', 'gluten-free'",
                    },
                    "price_tier": {
                        "type": "string",
                        "enum": ["$", "$$", "$$$", "$$$$"],
                    },
                },
                "required": ["city"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Standard response helpers
# ---------------------------------------------------------------------------

def _unavailable(tool: str, reason: str) -> dict:
    return {"status": "unavailable", "tool": tool, "reason": reason}


def _error(tool: str, reason: str) -> dict:
    return {"status": "error", "tool": tool, "reason": reason}


def _ok(source: str, results: list) -> dict:
    if not results:
        return {"status": "no_results", "results": []}
    return {"status": "ok", "source": source, "results": results}


# ---------------------------------------------------------------------------
# FLIGHTS - SerpAPI Google Flights
# ---------------------------------------------------------------------------
# Why SerpAPI instead of Amadeus? Amadeus shut down their self-service
# developer portal in 2025 - new individual developers can no longer sign up.
# SerpAPI's Google Flights engine gives equivalent (arguably better) data
# with one less signup, since SerpAPI is already powering hotels/activities/
# restaurants. Trade-off: each flight search consumes one of your 100/month
# SerpAPI calls, so be deliberate about test runs.

def _impl_search_flights(origin: str, destination: str, date: str,
                         return_date: str | None = None,
                         passengers: int = 1,
                         max_price_usd: float | None = None) -> dict:
    if not CONFIG.serpapi_key:
        return _unavailable(
            "search_flights",
            "SerpAPI key not configured. Set SERPAPI_KEY in .env to enable "
            "real flight search.",
        )
    # Reject past dates BEFORE calling the API. SerpAPI returns a 400 for
    # past dates which wastes one of our 100/month searches and confuses
    # the agent. Return a helpful error instead so the agent picks a
    # future date on retry.
    try:
        target = datetime.fromisoformat(date).date()
    except (ValueError, TypeError):
        return _error("search_flights",
                      f"Invalid date format: {date!r}. Use YYYY-MM-DD.")
    today = datetime.utcnow().date()
    if target < today:
        return _error(
            "search_flights",
            f"Cannot search flights for {date} — that date is in the past. "
            f"Today is {today.isoformat()}. Pick a future date and try again.",
        )

    # Validate return_date if provided. type=1 (round-trip) requires it.
    if return_date is not None:
        try:
            ret_target = datetime.fromisoformat(return_date).date()
        except (ValueError, TypeError):
            return _error("search_flights",
                          f"Invalid return_date format: {return_date!r}. Use YYYY-MM-DD.")
        if ret_target <= target:
            return _error(
                "search_flights",
                f"Return date ({return_date}) must be after outbound ({date}).",
            )

    # Build params: type=1 (round-trip) if return_date given, else type=2 (one-way).
    # Round-trip pricing covers both legs and is usually significantly cheaper.
    params: dict = {
        "engine": "google_flights",
        "departure_id": origin.upper()[:3],
        "arrival_id": destination.upper()[:3],
        "outbound_date": date,
        "adults": passengers,
        "currency": "USD",
        "hl": "en",
        "api_key": CONFIG.serpapi_key,
    }
    if return_date:
        params["type"] = "1"
        params["return_date"] = return_date
    else:
        params["type"] = "2"

    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        # Google Flights returns "best_flights" and "other_flights" arrays
        candidates = (data.get("best_flights") or []) + \
            (data.get("other_flights") or [])

        # First pass: parse ALL candidates with their real prices, ignoring filter.
        # We need this to detect "results exist but they're over budget" — that's
        # very different from "no flights exist for this route/date" and the
        # agent needs to react to it differently.
        all_offers = []
        for offer in candidates[:8]:
            price = offer.get("price")
            if price is None:
                continue
            flights = offer.get("flights", [])
            if not flights:
                continue
            first_leg = flights[0]
            last_leg = flights[-1]
            all_offers.append({
                "airline": first_leg.get("airline"),
                "price_usd": price,
                "stops": len(flights) - 1,
                "total_duration_min": offer.get("total_duration"),
                "departure": first_leg.get("departure_airport", {}).get("time"),
                "arrival": last_leg.get("arrival_airport", {}).get("time"),
                "from": first_leg.get("departure_airport", {}).get("id"),
                "to": last_leg.get("arrival_airport", {}).get("id"),
                "booking_token": offer.get("booking_token"),
            })

        if not all_offers:
            # Truly nothing — route/date issue, not a budget issue
            return _ok("serpapi_google_flights", [])

        # Apply the budget filter
        if max_price_usd:
            in_budget = [
                o for o in all_offers if o["price_usd"] <= max_price_usd]
            if not in_budget:
                # Real-market results exist but all exceed the budget.
                # Return them anyway WITH a status flag so the agent knows
                # the market price and can give an honest answer (e.g.
                # "cheapest is $X, which exceeds your $Y budget"). This
                # is the critical fix: we don't pretend no flights exist.
                cheapest = min(all_offers, key=lambda o: o["price_usd"])
                return {
                    "status": "over_budget",
                    "source": "serpapi_google_flights",
                    "max_price_usd": max_price_usd,
                    "cheapest_market_price_usd": cheapest["price_usd"],
                    "results": all_offers,
                    "message": (
                        f"No flights under ${max_price_usd}. "
                        f"Cheapest available is ${cheapest['price_usd']} "
                        f"on {cheapest['airline']}. "
                        f"All {len(all_offers)} real options are returned "
                        "so you can show the user the actual market price."
                    ),
                }
            return _ok("serpapi_google_flights", in_budget)

        return _ok("serpapi_google_flights", all_offers)
    except requests.HTTPError as e:
        return _error("search_flights", f"SerpAPI returned {e.response.status_code}.")
    except Exception as e:
        return _error("search_flights", f"Flight search failed: {e}")


# ---------------------------------------------------------------------------
# HOTELS - SerpAPI Google Hotels
# ---------------------------------------------------------------------------

def _impl_search_hotels(city: str, check_in: str, check_out: str,
                        guests: int = 1,
                        max_nightly_usd: float | None = None,
                        min_rating: float | None = None) -> dict:
    if not CONFIG.serpapi_key:
        return _unavailable(
            "search_hotels",
            "SerpAPI key not configured. Set SERPAPI_KEY in .env to enable "
            "real hotel search.",
        )
    # Reject past dates before hitting the API (same rationale as flights)
    try:
        ci = datetime.fromisoformat(check_in).date()
        co = datetime.fromisoformat(check_out).date()
    except (ValueError, TypeError):
        return _error("search_hotels",
                      f"Invalid date format. Use YYYY-MM-DD.")
    today = datetime.utcnow().date()
    if ci < today:
        return _error(
            "search_hotels",
            f"Cannot search hotels for check-in {check_in} — that date is "
            f"in the past. Today is {today.isoformat()}. Pick a future date.",
        )
    if co <= ci:
        return _error("search_hotels",
                      f"Check-out ({check_out}) must be after check-in ({check_in}).")
    try:
        nights = (datetime.fromisoformat(check_out) -
                  datetime.fromisoformat(check_in)).days
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_hotels",
                "q": f"{city} hotels",
                "check_in_date": check_in,
                "check_out_date": check_out,
                "adults": guests,
                "currency": "USD",
                "gl": "us",
                "hl": "en",
                "api_key": CONFIG.serpapi_key,
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        # First pass: parse ALL properties, ignoring filters. Same rationale
        # as in _impl_search_flights — we never want to return "no_results"
        # when the truth is "results exist but they don't match the filter."
        # That distinction matters for the agent's reasoning.
        all_props = []
        for prop in data.get("properties", [])[:10]:
            rate = prop.get("rate_per_night", {}).get("extracted_lowest")
            if rate is None:
                continue
            rating = prop.get("overall_rating")
            all_props.append({
                "name": prop.get("name"),
                "rating": rating,
                "nightly_usd": rate,
                "total_usd": rate * nights,
                "nights": nights,
                "amenities": prop.get("amenities", [])[:6],
                "link": prop.get("link"),
            })

        if not all_props:
            return _ok("serpapi_google_hotels", [])

        # Apply filters
        filtered = all_props
        if max_nightly_usd:
            filtered = [p for p in filtered if p["nightly_usd"]
                        <= max_nightly_usd]
        if min_rating:
            filtered = [p for p in filtered
                        if p["rating"] is not None and p["rating"] >= min_rating]

        if not filtered and max_nightly_usd:
            # Real market has hotels, but all are over the per-night cap.
            # Return them with over_budget status so the agent gets the real
            # market price and can respond honestly. (We only do this when
            # the budget was the binding filter — if min_rating was the
            # issue, just return empty.)
            cheapest = min(all_props, key=lambda p: p["nightly_usd"])
            return {
                "status": "over_budget",
                "source": "serpapi_google_hotels",
                "max_nightly_usd": max_nightly_usd,
                "cheapest_market_nightly_usd": cheapest["nightly_usd"],
                "results": all_props,
                "message": (
                    f"No hotels under ${max_nightly_usd}/night. "
                    f"Cheapest available is ${cheapest['nightly_usd']}/night "
                    f"at {cheapest['name']}. "
                    f"All {len(all_props)} real options are returned "
                    "so you can show the user the actual market price."
                ),
            }

        return _ok("serpapi_google_hotels", filtered)
    except requests.HTTPError as e:
        return _error("search_hotels", f"SerpAPI returned {e.response.status_code}.")
    except Exception as e:
        return _error("search_hotels", f"SerpAPI hotel call failed: {e}")


# ---------------------------------------------------------------------------
# WEATHER - OpenWeatherMap 5-day/3-hour forecast
# ---------------------------------------------------------------------------

def _impl_get_weather_forecast(city: str, start_date: str, end_date: str) -> dict:
    if not CONFIG.openweather_api_key:
        return _unavailable(
            "get_weather_forecast",
            "OpenWeatherMap API key not configured. Set OPENWEATHER_API_KEY "
            "in .env to enable weather forecasts.",
        )

    # Free tier only forecasts ~5 days out. Reject distant dates honestly.
    today = datetime.utcnow().date()
    try:
        target = datetime.fromisoformat(start_date).date()
    except ValueError:
        return _error("get_weather_forecast", f"Invalid start_date: {start_date}")
    days_ahead = (target - today).days
    if days_ahead > 5:
        return _unavailable(
            "get_weather_forecast",
            f"Trip starts {days_ahead} days from today; OpenWeatherMap free "
            "tier only forecasts up to 5 days ahead. For trips further out, "
            "skip weather details in the plan or note the gap to the user.",
        )
    if days_ahead < 0:
        return _unavailable(
            "get_weather_forecast",
            "Requested date is in the past.",
        )

    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={
                "q": city,
                "appid": CONFIG.openweather_api_key,
                "units": "imperial",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        # The 3-hour-interval list -> aggregate by date into daily summaries
        by_day: dict[str, list[dict]] = defaultdict(list)
        for entry in data.get("list", []):
            d = entry["dt_txt"][:10]
            by_day[d].append(entry)

        results = []
        for d in sorted(by_day.keys()):
            if d < start_date or d > end_date:
                continue
            entries = by_day[d]
            temps = [e["main"]["temp"] for e in entries]
            conditions = [e["weather"][0]["main"] for e in entries]
            precip = max((e.get("pop", 0) * 100 for e in entries), default=0)
            # Take the most common condition through the day
            cond = max(set(conditions), key=conditions.count)
            results.append({
                "date": d,
                "condition": cond,
                "high_f": round(max(temps)),
                "low_f": round(min(temps)),
                "precip_chance": round(precip),
            })
        return _ok("openweathermap", results)
    except requests.HTTPError as e:
        return _error("get_weather_forecast",
                      f"OpenWeatherMap returned {e.response.status_code}.")
    except Exception as e:
        return _error("get_weather_forecast", f"Weather call failed: {e}")


# ---------------------------------------------------------------------------
# ACTIVITIES & RESTAURANTS - SerpAPI Google Maps
# ---------------------------------------------------------------------------

def _serpapi_maps_search(query: str) -> list[dict]:
    """Helper for activities/restaurants via Google Maps engine."""
    resp = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google_maps",
            "q": query,
            "type": "search",
            "api_key": CONFIG.serpapi_key,
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("local_results", []) or []


def _impl_search_activities(city: str, interest: str | None = None,
                            max_price_usd: float | None = None) -> dict:
    if not CONFIG.serpapi_key:
        return _unavailable(
            "search_activities",
            "SerpAPI key not configured. Set SERPAPI_KEY in .env to enable "
            "real activity search.",
        )
    try:
        query = f"{interest} in {city}" if interest else f"things to do in {city}"
        raw = _serpapi_maps_search(query)
        results = []
        for place in raw[:10]:
            results.append({
                "name": place.get("title"),
                "category": place.get("type") or place.get("category"),
                "rating": place.get("rating"),
                "reviews": place.get("reviews"),
                "address": place.get("address"),
                "price_tier": place.get("price"),
                "description": place.get("description"),
            })
        return _ok("serpapi_google_maps", results)
    except requests.HTTPError as e:
        return _error("search_activities", f"SerpAPI returned {e.response.status_code}.")
    except Exception as e:
        return _error("search_activities", f"Activity search failed: {e}")


def _impl_search_restaurants(city: str, cuisine: str | None = None,
                             dietary: str | None = None,
                             price_tier: str | None = None) -> dict:
    if not CONFIG.serpapi_key:
        return _unavailable(
            "search_restaurants",
            "SerpAPI key not configured. Set SERPAPI_KEY in .env to enable "
            "real restaurant search.",
        )
    try:
        parts = []
        if dietary:
            parts.append(dietary)
        if cuisine:
            parts.append(cuisine)
        parts.append("restaurants in")
        parts.append(city)
        query = " ".join(parts)

        raw = _serpapi_maps_search(query)
        results = []
        for place in raw[:10]:
            tier = place.get("price")
            if price_tier and tier != price_tier:
                continue
            results.append({
                "name": place.get("title"),
                "cuisine": place.get("type") or place.get("category"),
                "rating": place.get("rating"),
                "reviews": place.get("reviews"),
                "price_tier": tier,
                "address": place.get("address"),
            })
        return _ok("serpapi_google_maps", results)
    except requests.HTTPError as e:
        return _error("search_restaurants", f"SerpAPI returned {e.response.status_code}.")
    except Exception as e:
        return _error("search_restaurants", f"Restaurant search failed: {e}")


# ---------------------------------------------------------------------------
# DISPATCHER - the function the agent loop calls
# ---------------------------------------------------------------------------

_IMPL_MAP = {
    "search_flights": _impl_search_flights,
    "search_hotels": _impl_search_hotels,
    "get_weather_forecast": _impl_get_weather_forecast,
    "search_activities": _impl_search_activities,
    "search_restaurants": _impl_search_restaurants,
}


def run_tool(name: str, inputs: dict[str, Any]) -> str:
    """
    Dispatch a tool call from the LLM to its real implementation.
    Returns a JSON string (OpenAI API requirement for tool message content).
    All results are structured dicts with an explicit 'status' field so the
    agent can distinguish success / no_results / unavailable / error.
    """
    impl = _IMPL_MAP.get(name)
    if impl is None:
        return json.dumps({"status": "error", "tool": name,
                           "reason": f"Unknown tool: {name}"})
    try:
        return json.dumps(impl(**inputs))
    except TypeError as e:
        # Defensive: the LLM passed bad arguments to the tool
        return json.dumps({"status": "error", "tool": name,
                           "reason": f"Invalid arguments: {e}"})

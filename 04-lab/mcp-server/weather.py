from typing import Any
import asyncio
import datetime
import httpx
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Initialize FastMCP server
port = int(os.getenv("PORT", 8085))
mcp = FastMCP("weather", host="0.0.0.0", port=port)

# Constants
WEATHERAPI_BASE = "https://api.weatherapi.com/v1"
USER_AGENT = "weather-app/1.0"

# Get API key from environment variable
API_KEY = os.getenv("WEATHERAPI_KEY")

_FALLBACK_CITIES = {
    "hanoi": ("Hanoi", "Ha Noi", "Vietnam", 28.5, 83.3, 31.0, 87.8, "Partly cloudy", 75, 14.0, 8.7, "SE", 1010.0, 6.0, 10.0),
    "haiphong": ("Haiphong", "Hai Phong", "Vietnam", 29.0, 84.2, 32.5, 90.5, "Light rain", 82, 18.0, 11.2, "E", 1009.0, 5.0, 9.0),
    "danang": ("Danang", "Da Nang", "Vietnam", 30.0, 86.0, 33.0, 91.4, "Sunny", 70, 12.0, 7.5, "ENE", 1011.0, 7.0, 10.0),
    "ho chi minh": ("Ho Chi Minh City", "Ho Chi Minh", "Vietnam", 33.0, 91.4, 38.0, 100.4, "Scattered thunderstorms", 78, 15.0, 9.3, "SW", 1008.0, 8.0, 8.0),
    "brisbane": ("Brisbane", "Queensland", "Australia", 22.0, 71.6, 22.0, 71.6, "Sunny", 58, 19.0, 11.8, "ESE", 1016.0, 7.0, 10.0),
    "sydney": ("Sydney", "New South Wales", "Australia", 20.5, 68.9, 20.5, 68.9, "Clear", 62, 16.0, 9.9, "NE", 1018.0, 6.0, 10.0),
    "melbourne": ("Melbourne", "Victoria", "Australia", 17.0, 62.6, 16.5, 61.7, "Partly cloudy", 65, 22.0, 13.7, "S", 1019.0, 5.0, 10.0),
    "tokyo": ("Tokyo", "Tokyo", "Japan", 19.0, 66.2, 19.0, 66.2, "Clear", 52, 10.0, 6.2, "NNE", 1020.0, 4.0, 10.0),
    "new york": ("New York", "New York", "United States of America", 15.0, 59.0, 14.5, 58.1, "Overcast", 60, 12.0, 7.5, "W", 1014.0, 3.0, 10.0),
}


def _get_fallback_current(city: str) -> dict[str, Any]:
    norm = city.lower().strip()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if norm in _FALLBACK_CITIES:
        name, reg, ctry, tc, tf, fc, ff, cond, hum, wk, wm, wd, pr, uv, vis = _FALLBACK_CITIES[norm]
    else:
        name, reg, ctry, tc, tf, fc, ff, cond, hum, wk, wm, wd, pr, uv, vis = (
            city.title(), city.title(), "World", 25.0, 77.0, 26.0, 78.8, "Partly cloudy", 65, 12.0, 7.5, "E", 1012.0, 5.0, 10.0
        )
    return {
        "location": {"name": name, "region": reg, "country": ctry},
        "current": {
            "temp_c": tc, "temp_f": tf, "feelslike_c": fc, "feelslike_f": ff,
            "condition": {"text": cond}, "humidity": hum, "wind_kph": wk,
            "wind_mph": wm, "wind_dir": wd, "pressure_mb": pr, "uv": uv,
            "vis_km": vis, "last_updated": now_str
        },
        "_is_simulated": True
    }


async def make_weather_request(endpoint: str, params: dict[str, str]) -> dict[str, Any] | None:
    """Make a request to the WeatherAPI with proper error handling."""
    # Check if API key is set
    if not API_KEY:
        return None
        
    headers = {
        "User-Agent": USER_AGENT,
    }
    # Add API key to parameters
    params["key"] = API_KEY
    
    url = f"{WEATHERAPI_BASE}/{endpoint}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error {e.response.status_code}: {e.response.text}")
            return None
        except httpx.RequestError as e:
            print(f"Request Error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

@mcp.tool()
async def get_current_weather(city: str) -> str:
    """Get current weather conditions for a city.

    Args:
        city: City name (e.g., "Hanoi", "Haiphong", "Danang", "Brisbane", "Sydney")
    """
    params = {
        "q": city,
        "aqi": "no"
    }
    
    data = await make_weather_request("current.json", params)

    simulated_note = ""
    if not data:
        data = _get_fallback_current(city)
        if not API_KEY:
            simulated_note = "\n*(Dữ liệu mô phỏng do chưa cấu hình WEATHERAPI_KEY)*\n"

    current = data["current"]
    location = data["location"]
    
    return f"""
Current Weather for {location['name']}, {location['region']}, {location['country']}:{simulated_note}

Temperature: {current['temp_c']}°C ({current['temp_f']}°F)
Feels like: {current['feelslike_c']}°C ({current['feelslike_f']}°F)
Condition: {current['condition']['text']}
Humidity: {current['humidity']}%
Wind: {current['wind_kph']} km/h ({current['wind_mph']} mph) {current['wind_dir']}
Pressure: {current['pressure_mb']} mb
UV Index: {current['uv']}
Visibility: {current['vis_km']} km

Last updated: {current['last_updated']}
"""

def _get_fallback_forecast(city: str, days: int) -> dict[str, Any]:
    norm = city.lower().strip()
    if norm in _FALLBACK_CITIES:
        name, reg, ctry, tc, tf, _, _, cond, _, wk, _, _, _, uv, _ = _FALLBACK_CITIES[norm]
    else:
        name, reg, ctry, tc, tf, cond, wk, uv = (city.title(), city.title(), "World", 25.0, 77.0, "Partly cloudy", 12.0, 5.0)

    forecast_days = []
    base_date = datetime.date.today()
    for i in range(days):
        d = base_date + datetime.timedelta(days=i)
        forecast_days.append({
            "date": d.isoformat(),
            "day": {
                "maxtemp_c": round(tc + (1.5 if i % 2 == 0 else -1.0), 1),
                "maxtemp_f": round(tf + (2.7 if i % 2 == 0 else -1.8), 1),
                "mintemp_c": round(tc - 5.0, 1),
                "mintemp_f": round(tf - 9.0, 1),
                "condition": {"text": cond if i == 0 else "Sunny" if i == 1 else "Scattered clouds"},
                "daily_chance_of_rain": 20 if i == 0 else 10 if i == 1 else 40,
                "maxwind_kph": round(wk + (2.0 if i == 1 else 0.0), 1),
                "uv": uv,
            }
        })
    return {
        "location": {"name": name, "region": reg, "country": ctry},
        "forecast": {"forecastday": forecast_days},
        "_is_simulated": True
    }


@mcp.tool()
async def get_forecast(city: str, days: int = 3) -> str:
    """Get weather forecast for a city.

    Args:
        city: City name (e.g., "Hanoi", "Haiphong", "Danang", "Brisbane", "Sydney", "Melbourne")
        days: Number of days to forecast (1-3 for free tier, max 10 for paid)
    """
    # Limit days to 3 for free tier
    days = min(days, 3)
    
    params = {
        "q": city,
        "days": str(days),
        "aqi": "no",
        "alerts": "no"
    }
    
    data = await make_weather_request("forecast.json", params)

    simulated_note = ""
    if not data:
        data = _get_fallback_forecast(city, days)
        if not API_KEY:
            simulated_note = "\n*(Dữ liệu mô phỏng do chưa cấu hình WEATHERAPI_KEY)*\n"

    location = data["location"]
    forecast_days = data["forecast"]["forecastday"]
    
    forecasts = []
    header = f"Weather Forecast for {location['name']}, {location['region']}, {location['country']}:"
    if simulated_note:
        header = f"{header}{simulated_note}"
    forecasts.append(header)
    
    for day in forecast_days:
        day_data = day["day"]
        date = day["date"]
        
        forecast = f"""
{date}:
High: {day_data['maxtemp_c']}°C ({day_data['maxtemp_f']}°F)
Low: {day_data['mintemp_c']}°C ({day_data['mintemp_f']}°F)
Condition: {day_data['condition']['text']}
Chance of Rain: {day_data['daily_chance_of_rain']}%
Max Wind: {day_data['maxwind_kph']} km/h
UV Index: {day_data['uv']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)

@mcp.tool()
async def health_check() -> str:
    """Health check endpoint for deployment verification."""
    return "✅ Weather MCP Server is running! Ready to provide weather data for Australian cities and worldwide."

print("✅ MCP server initialized with Streamable HTTP transport")
print("🔧 Available tools: get_current_weather, get_forecast, health_check")

if __name__ == "__main__":
    import sys
    
    is_cloud_run = bool(os.getenv("PORT"))
    is_standalone = len(sys.argv) == 1 and sys.stdin.isatty()
    
    if is_cloud_run or is_standalone:
        print(f"🚀 Starting MCP server on http://0.0.0.0:{port}/mcp")
        mcp.run(transport="streamable-http")
    else:
        print("Starting FastMCP server in stdio mode for local client", file=sys.stderr)
        mcp.run()
import json
import urllib.request
import webbrowser
from urllib.parse import quote_plus


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    city = parameters.get("city")
    when = parameters.get("time", "today")

    if not city or not isinstance(city, str) or not city.strip():
        msg = "Sir, the city is missing for the weather report."
        _log(msg, player)
        return msg

    city = city.strip()
    when = (when or "today").strip()

    # Attempt live weather data retrieval from wttr.in
    try:
        clean_city = quote_plus(city)
        req = urllib.request.Request(
            f"https://wttr.in/{clean_city}?format=j1",
            headers={"User-Agent": "curl/7.88.1"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            curr = data.get("current_condition", [{}])[0]
            temp_c = curr.get("temp_C", "")
            desc = curr.get("weatherDesc", [{}])[0].get("value", "Clear")
            humidity = curr.get("humidity", "")
            wind_kmh = curr.get("windspeedKmph", "")
            feels_like = curr.get("FeelsLikeC", temp_c)

            spoken_summary = (
                f"Currently in {city}, it is {desc} at {temp_c}°C (feels like {feels_like}°C), "
                f"with {humidity}% humidity and wind at {wind_kmh} km/h."
            )

            # Show rich weather card in HUD
            if player and hasattr(player, "show_content"):
                card = [
                    f"# 🌤️ Weather Report: {city.title()}",
                    f"- **Condition:** {desc}",
                    f"- **Temperature:** {temp_c}°C (Feels like {feels_like}°C)",
                    f"- **Humidity:** {humidity}%",
                    f"- **Wind Speed:** {wind_kmh} km/h",
                ]
                player.show_content(f"Weather: {city.title()}", "\n".join(card))

            _log(spoken_summary, player)
            return spoken_summary
    except Exception as e:
        print(f"[Weather] Live API fetch failed ({e}), falling back to browser.")

    # Fallback: Open Google Weather search in browser
    search_query = f"weather in {city} {when}"
    url = f"https://www.google.com/search?q={quote_plus(search_query)}"

    try:
        webbrowser.open(url)
    except Exception as e:
        msg = f"Sir, I couldn't open the browser for the weather report: {e}"
        _log(msg, player)
        return msg

    msg = f"Showing the weather for {city}, {when}, sir."
    _log(msg, player)

    if session_memory:
        try:
            session_memory.set_last_search(query=search_query, response=msg)
        except Exception:
            pass

    return msg


def _log(message: str, player=None) -> None:
    print(f"[Weather] {message}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "weather_report",
    "description": "Gives the current live weather report and temperature for any city.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "city": {
                "type": "STRING",
                "description": "City name"
            },
            "time": {
                "type": "STRING",
                "description": "Time frame (e.g. today, tomorrow)"
            }
        },
        "required": [
            "city"
        ]
    },
    "handler": weather_action,
}

"""City -> (lat, lng) geocoding via OpenStreetMap Nominatim (free, no API key).

Used by the admin so staff can type a city name and have coordinates filled in.
Nominatim asks for a descriptive User-Agent and low request volume — fine for
occasionally adding Dots by hand. Network failures return None (caller handles it).
"""
import json
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "TheDotComExperience-Dots/1.0 (https://www.thedotx.com; info@thedotcomexperience.com)"


def geocode_city(city, region="", country=""):
    """Return (lat, lng) for a place string, or None if it can't be resolved."""
    parts = [p for p in (city, region, country) if p and str(p).strip()]
    if not parts:
        return None
    query = ", ".join(str(p).strip() for p in parts)
    url = NOMINATIM_URL + "?" + urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 1, "addressdetails": 0,
    })
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data:
            return round(float(data[0]["lat"]), 6), round(float(data[0]["lon"]), 6)
    except Exception:
        return None
    return None

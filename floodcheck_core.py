"""
floodcheck_core.py
Address -> flood zone -> expected loss -> premium comparison.
No side effects on import. All testing happens in app.py or external scripts.
"""

import requests
from typing import Optional


# ---------- Constants ----------

CENSUS_GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
LAYER_ID = 28

# Try multiple FEMA-hosted endpoints. They mirror the same NFHL data but
# have independent uptime. Order = preference (fastest/most reliable first).
FEMA_NFHL_ENDPOINTS = [
    f"https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/{LAYER_ID}/query",
    f"https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/{LAYER_ID}/query",
]


# ---------- Exceptions ----------

class GeocodeError(Exception):
    pass


class FloodLookupError(Exception):
    pass


# ---------- Lookup tables ----------

# Annual probability of a flood event by zone family.
# Sources: FEMA NFIP regulations (44 CFR 59.1), Risk Rating 2.0 methodology.
ANNUAL_FLOOD_PROBABILITY = {
    "A":  0.01, "AE": 0.01, "AH": 0.01, "AO": 0.01,
    "V":  0.01, "VE": 0.01,
    "X":  0.0002,
    "D":  0.005,
}

# Conditional expected damage fraction given a flood occurs.
# Derived from HAZUS-MH depth-damage curves for typical 1-story residential.
DAMAGE_FRACTION = {
    "A":  0.27, "AE": 0.27, "AH": 0.20, "AO": 0.13,
    "V":  0.40, "VE": 0.40,
    "X":  0.10,
    "D":  0.20,
}

SUBTYPE_OVERRIDES = {
    "AREA WITH REDUCED FLOOD RISK DUE TO LEVEE": {
        "probability": 0.004,
        "damage_fraction": 0.35,
        "confidence": "levee_dependent",
    },
    "0.2 PCT ANNUAL CHANCE FLOOD HAZARD": {
        "probability": 0.002,
        "damage_fraction": 0.18,
        "confidence": "moderate",
    },
    "AREA OF MINIMAL FLOOD HAZARD": {
        "probability": 0.0002,
        "damage_fraction": 0.10,
        "confidence": "low_risk",
    },
}

# NFIP premium estimates (FEMA Risk Rating 2.0 averages, FY2024).
NFIP_PREMIUMS = {
    ("FL", "SFHA"): (1800, 3200),  ("FL", "X"): (650, 1100),
    ("LA", "SFHA"): (2200, 3800),  ("LA", "X"): (700, 1300),
    ("TX", "SFHA"): (1400, 2400),  ("TX", "X"): (550, 950),
    ("MS", "SFHA"): (1700, 2900),  ("MS", "X"): (600, 1000),
    ("AL", "SFHA"): (1500, 2600),  ("AL", "X"): (550, 950),
    ("NC", "SFHA"): (1300, 2100),  ("NC", "X"): (550, 950),
    ("SC", "SFHA"): (1500, 2500),  ("SC", "X"): (600, 1000),
    ("GA", "SFHA"): (1200, 2000),  ("GA", "X"): (500, 850),
    ("VA", "SFHA"): (1100, 1900),  ("VA", "X"): (500, 850),
    ("NJ", "SFHA"): (1700, 2900),  ("NJ", "X"): (650, 1100),
    ("NY", "SFHA"): (1600, 2800),  ("NY", "X"): (650, 1100),
    ("MA", "SFHA"): (1400, 2400),  ("MA", "X"): (600, 1000),
    ("MO", "SFHA"): (1100, 1800),  ("MO", "X"): (450, 750),
    ("IA", "SFHA"): (1000, 1700),  ("IA", "X"): (400, 700),
    ("IL", "SFHA"): (1100, 1900),  ("IL", "X"): (450, 750),
    ("TN", "SFHA"): (1000, 1700),  ("TN", "X"): (450, 750),
    ("KY", "SFHA"): (1100, 1800),  ("KY", "X"): (450, 750),
    ("CA", "SFHA"): (1200, 2200),  ("CA", "X"): (500, 900),
    ("WA", "SFHA"): (1000, 1700),  ("WA", "X"): (400, 700),
    ("OR", "SFHA"): (1000, 1700),  ("OR", "X"): (400, 700),
    ("DC", "SFHA"): (1500, 2400),  ("DC", "X"): (600, 1000),
}

NATIONAL_FALLBACK = {
    "SFHA": (1200, 2200),
    "X":    (550, 950),
}

SFHA_ZONES = {"A", "AE", "AH", "AO", "V", "VE", "A1-A30", "A99"}


# ---------- Core functions ----------

def geocode(address: str) -> dict:
    """
    Convert a US address to lat/lon plus address components.
    Returns dict with lat, lon, state, city, zip, matched_address.
    """
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "format": "json",
    }
    try:
        r = requests.get(CENSUS_GEOCODER, params=params, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        raise GeocodeError(f"Geocoder request failed: {e}")

    matches = r.json().get("result", {}).get("addressMatches", [])
    if not matches:
        raise GeocodeError(f"No match found for: {address}")

    match = matches[0]
    coords = match["coordinates"]
    components = match.get("addressComponents", {})

    return {
        "lat": coords["y"],
        "lon": coords["x"],
        "state": components.get("state"),
        "city": components.get("city"),
        "zip": components.get("zip"),
        "matched_address": match.get("matchedAddress"),
    }


def get_flood_zone(lat: float, lon: float) -> dict:
    """
    Lat/lon -> flood zone info from FEMA NFHL.
    Tries multiple FEMA endpoints; uses the first one that responds.
    """
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY,STATIC_BFE",
        "returnGeometry": "false",
        "f": "json",
    }

    last_error = None
    for endpoint in FEMA_NFHL_ENDPOINTS:
        try:
            r = requests.get(endpoint, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            last_error = e
            continue  # try the next endpoint
        except ValueError as e:
            # JSON decode error - endpoint returned HTML or garbage
            last_error = e
            continue

        if "error" in data:
            last_error = f"FEMA returned error: {data['error']}"
            continue

        features = data.get("features", [])
        if not features:
            return {
                "flood_zone": "X",
                "zone_subtype": None,
                "base_flood_elevation": None,
                "in_mapped_hazard_area": False,
            }

        attrs = features[0]["attributes"]
        return {
            "flood_zone": attrs.get("FLD_ZONE"),
            "zone_subtype": attrs.get("ZONE_SUBTY"),
            "base_flood_elevation": attrs.get("STATIC_BFE"),
            "in_mapped_hazard_area": True,
        }

    # All endpoints failed
    raise FloodLookupError(
        f"All FEMA NFHL endpoints unreachable. Last error: {last_error}"
    )


def expected_loss(
    flood_zone: Optional[str],
    zone_subtype: Optional[str],
    base_flood_elevation: Optional[float],
    structure_value: float = 300_000,
) -> dict:
    """Translate a flood zone + subtype into an annualized expected loss estimate."""
    if base_flood_elevation in (-9999.0, -9999):
        base_flood_elevation = None

    confidence = "standard"
    interpretation_notes = []

    if zone_subtype and zone_subtype.strip() in SUBTYPE_OVERRIDES:
        override = SUBTYPE_OVERRIDES[zone_subtype.strip()]
        prob = override["probability"]
        damage_frac = override["damage_fraction"]
        confidence = override["confidence"]
        if confidence == "levee_dependent":
            interpretation_notes.append(
                "This area is mapped as low-risk because of levee protection. "
                "Historical events (Hurricane Katrina, 2005) have shown that "
                "levee failure can cause catastrophic damage in areas designated "
                "this way. The residual risk is real and not fully captured by "
                "the zone code alone."
            )
    else:
        zone_key = (flood_zone or "X").strip().upper()
        prob = ANNUAL_FLOOD_PROBABILITY.get(zone_key, 0.0002)
        damage_frac = DAMAGE_FRACTION.get(zone_key, 0.10)

    expected_damage_dollars = prob * damage_frac * structure_value

    if flood_zone in ("A", "AE", "AH"):
        interpretation_notes.append(
            f"This address is in a Special Flood Hazard Area with a 1% annual "
            f"flood probability. Over a 30-year mortgage, the cumulative "
            f"probability of at least one flood is approximately "
            f"{(1 - (1 - prob) ** 30) * 100:.0f}%."
        )
    elif flood_zone == "AO":
        interpretation_notes.append(
            "This area is subject to shallow sheet-flow flooding, typically "
            "1-3 feet deep. Damage per event is lower than deep flooding, "
            "but frequency is comparable to AE zones."
        )
    elif flood_zone in ("V", "VE"):
        interpretation_notes.append(
            "This is a coastal high-hazard area with wave action. Damage per "
            "event is significantly higher than riverine flooding due to "
            "structural forces from waves, not just water depth."
        )
    elif flood_zone == "X" and confidence == "low_risk":
        interpretation_notes.append(
            "This area is outside mapped flood hazard zones. Risk is low but "
            "not zero — roughly 20% of NFIP claims come from areas outside "
            "Special Flood Hazard Areas."
        )

    return {
        "flood_zone": flood_zone,
        "zone_subtype": zone_subtype,
        "base_flood_elevation": base_flood_elevation,
        "annual_flood_probability": prob,
        "damage_fraction_given_flood": damage_frac,
        "structure_value": structure_value,
        "annual_expected_loss_dollars": round(expected_damage_dollars, 2),
        "thirty_year_flood_probability": round(1 - (1 - prob) ** 30, 4),
        "confidence_flag": confidence,
        "interpretation": " ".join(interpretation_notes) if interpretation_notes else None,
    }


def estimate_nfip_premium(state_code: Optional[str], flood_zone: Optional[str]) -> dict:
    """Return estimated annual NFIP premium range for a given state and zone."""
    if not state_code or not flood_zone:
        return {
            "low": None, "high": None,
            "source": "unavailable",
            "note": "Insufficient address or zone information.",
        }

    zone_family = "SFHA" if flood_zone in SFHA_ZONES else "X"
    key = (state_code.upper(), zone_family)

    if key in NFIP_PREMIUMS:
        low, high = NFIP_PREMIUMS[key]
        source = "state_average"
    else:
        low, high = NATIONAL_FALLBACK[zone_family]
        source = "national_fallback"

    return {
        "low": low,
        "high": high,
        "midpoint": (low + high) // 2,
        "zone_family": zone_family,
        "source": source,
        "note": (
            "Estimated state-average NFIP premium under Risk Rating 2.0. "
            "Actual premiums depend on structure elevation, foundation type, "
            "replacement cost, deductible, and coverage limits."
        ),
    }


def compare_loss_vs_premium(annual_expected_loss: float, premium_low, premium_high) -> dict:
    """Frame the comparison between expected loss and insurance premium."""
    if premium_low is None or premium_high is None:
        return {
            "ratio_to_midpoint": None,
            "framing": "Premium data unavailable for this state.",
        }

    premium_mid = (premium_low + premium_high) / 2
    ratio = annual_expected_loss / premium_mid if premium_mid > 0 else 0

    if ratio < 0.3:
        framing = (
            f"Your estimated annual expected loss (\\${annual_expected_loss:.0f}) "
            f"is significantly lower than typical NFIP premiums "
            f"(\\${premium_low:,}–\\${premium_high:,}). This is normal: insurance "
            f"includes loading for administrative costs, profit, and — most "
            f"importantly — protection against catastrophic single events that "
            f"could exceed many years of premium payments."
        )
    elif ratio < 0.7:
        framing = (
            f"Your estimated annual expected loss (\\${annual_expected_loss:.0f}) "
            f"is in the same order of magnitude as typical NFIP premiums "
            f"(\\${premium_low:,}–\\${premium_high:,}). Insurance is likely a "
            f"reasonable value here, particularly because it protects against "
            f"tail risk that the expected-loss number understates."
        )
    elif ratio < 1.5:
        framing = (
            f"Your estimated annual expected loss (\\${annual_expected_loss:.0f}) "
            f"is roughly comparable to typical NFIP premiums "
            f"(\\${premium_low:,}–\\${premium_high:,}). For an actuarially average "
            f"property, insurance pays for itself in expectation."
        )
    else:
        framing = (
            f"Your estimated annual expected loss (\\${annual_expected_loss:.0f}) "
            f"**exceeds** typical NFIP premiums (\\${premium_low:,}–\\${premium_high:,}). "
            f"NFIP coverage appears underpriced relative to your specific risk. "
            f"You may also want to verify whether private flood insurance offers "
            f"additional coverage above NFIP's \\$250K building limit."
        )

    return {
        "ratio_to_midpoint": round(ratio, 2),
        "premium_midpoint": round(premium_mid, 0),
        "framing": framing,
    }



def lookup_full(address: str, structure_value: float = 300_000) -> dict:
    """Complete pipeline: address -> zone -> expected loss -> premium comparison."""
    geo = geocode(address)
    zone_info = get_flood_zone(geo["lat"], geo["lon"])
    loss_info = expected_loss(
        flood_zone=zone_info["flood_zone"],
        zone_subtype=zone_info["zone_subtype"],
        base_flood_elevation=zone_info["base_flood_elevation"],
        structure_value=structure_value,
    )
    premium_info = estimate_nfip_premium(
        state_code=geo["state"],
        flood_zone=zone_info["flood_zone"],
    )
    comparison = compare_loss_vs_premium(
        annual_expected_loss=loss_info["annual_expected_loss_dollars"],
        premium_low=premium_info["low"],
        premium_high=premium_info["high"],
    )

    return {
        "address": address,
        "matched_address": geo["matched_address"],
        "state": geo["state"],
        "latitude": geo["lat"],
        "longitude": geo["lon"],
        **loss_info,
        "premium_low": premium_info["low"],
        "premium_high": premium_info["high"],
        "premium_source": premium_info["source"],
        "comparison": comparison["framing"],
        "loss_to_premium_ratio": comparison["ratio_to_midpoint"],
    }


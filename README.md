# 🌊 FloodCheck

A free, transparent flood risk estimator for US addresses.

**Live demo:** [your-url-will-go-here-after-deploy](#)

## What it does

Enter a US address. Get:
- Your FEMA flood zone (with subtype handling for levee-protected areas)
- Your estimated annual flood probability
- Your estimated annual expected loss in dollars
- A comparison to typical NFIP flood insurance premiums in your state
- Every assumption made, transparently documented

## Why this exists

FEMA publishes flood zones. They tell you a code like "AE" or "X." They don't tell you the expected dollar loss, or how that compares to insurance. Private services like First Street Foundation do this with proprietary models and increasingly paywalled access. **FloodCheck is the open-source, transparent alternative.**

## The Canal Street example

Address: 500 Canal St, New Orleans, LA
- FEMA zone: **X** (looks low-risk at first glance!)
- FEMA subtype: **AREA WITH REDUCED FLOOD RISK DUE TO LEVEE**
- Annual expected loss: meaningfully higher than other "Zone X" addresses

This address looks safe based on the zone code alone. The subtype reveals it's only safe *because of levee protection* — and Katrina (2005) showed what happens when that assumption fails. FloodCheck surfaces this; FEMA's official map portal hides it behind a footnote.

## Data sources

- US Census Bureau Geocoder (TIGER/Line)
- FEMA National Flood Hazard Layer (NFHL)
- HAZUS-MH depth-damage curves
- FEMA Risk Rating 2.0 state-average premiums (FY2024)

## Limitations

- Single-hazard (flood only) — wildfire, tornado, hurricane not yet included
- Population-average damage fractions; actual structures vary
- Regulatory probabilities, not empirical frequencies
- Does not account for sea level rise or climate-driven non-stationarity
- State-average premium estimates, not actual quotes

## Run locally

```bash
git clone https://github.com/yourusername/floodcheck.git
cd floodcheck
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## License

MIT
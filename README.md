# 🌊 FloodCheck

A free, transparent flood risk estimator for US addresses.

**Live demo:** [https://floodchecks.streamlit.app/](#)

## What it does

Enter a US address. Get:
- Your FEMA flood zone (with subtype handling for levee-protected areas)
- Your estimated annual flood probability
- Your estimated annual expected loss in dollars
- A comparison to typical NFIP flood insurance premiums in your state
- Every assumption made, transparently documented

## Why this exists

FEMA publishes flood zones. They tell you a code like "AE" or "X." They don't tell you the expected dollar loss, or how that compares to insurance. Some private services do this, but with proprietary models and paywalls. FloodCheck is an open source and transparent alternative.

## The Canal Street example

Address: 500 Canal St, New Orleans, LA
- FEMA zone: **X** (looks low-risk at first glance!)
- FEMA subtype: **AREA WITH REDUCED FLOOD RISK DUE TO LEVEE**
- Annual expected loss: meaningfully higher than other "Zone X" addresses

This address looks safe based on the zone code alone. The subtype reveals it's only safe *because of levee protection* — and Katrina (2005) showed what happens when that assumption fails. FloodCheck surfaces this detail. 

## Data sources

- US Census Bureau Geocoder (TIGER/Line)
- FEMA National Flood Hazard Layer (NFHL)
- HAZUS-MH depth-damage curves
- FEMA Risk Rating 2.0 state-average premiums (FY2024)

## Limitations

- Only accounts for floods
- It is an estimate 
- Does not account for sea level rise or climate driven changes
- Premium estimates based on state averages

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

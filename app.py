"""
FloodCheck: a free, transparent flood risk estimator for US addresses.
"""
import streamlit as st
from floodcheck_core import (
    lookup_full,
    GeocodeError,
    FloodLookupError,
)

# ---------- Page setup ----------
st.set_page_config(
    page_title="FloodCheck",
    page_icon="🌊",
    layout="centered",
)

# Hide Streamlit's default chrome
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ---------- Cached lookup ----------
@st.cache_data(show_spinner=False)
def cached_lookup(address: str, structure_value: int) -> dict:
    """Wrap lookup_full with caching so repeat queries don't re-hit FEMA."""
    return lookup_full(address, structure_value=structure_value)


# ---------- Disclaimer (always visible) ----------
st.warning(
    "**Educational tool — not insurance advice.** "
    "Estimates use simplified depth-damage curves and FEMA zone averages. "
    "Real premiums and damages depend on specific structural details. "
    "Always consult a licensed agent before making coverage decisions."
)

# ---------- Header ----------
st.title("🌊 FloodCheck")
st.markdown(
    "Get a transparent estimate of your annual flood risk in dollars, "
    "with a comparison to typical NFIP flood insurance premiums. "
    "Free, open-source, no email required."
)

# ---------- Example buttons ----------
st.markdown("---")
st.markdown("**Try an example:**")

example_col1, example_col2, example_col3 = st.columns(3)
if "example_address" not in st.session_state:
    st.session_state.example_address = ""

if example_col1.button("Coastal Miami"):
    st.session_state.example_address = "100 Biscayne Blvd, Miami, FL"
if example_col2.button("New Orleans (levee)"):
    st.session_state.example_address = "500 Canal St, New Orleans, LA"
if example_col3.button("Inland low-risk"):
    st.session_state.example_address = "400 S Tryon St, Charlotte, NC"


# ---------- Input form ----------
st.markdown("---")
st.subheader("Check an address")

with st.form("lookup_form"):
    address = st.text_input(
        "US street address",
        value=st.session_state.example_address,
        placeholder="100 Biscayne Blvd, Miami, FL",
        help="Include city and state. Census-style addresses work best.",
    )
    structure_value = st.number_input(
        "Estimated structure value (replacement cost, not market value)",
        min_value=50_000,
        max_value=2_000_000,
        value=300_000,
        step=25_000,
        help="Roughly what it would cost to rebuild. Use ~$150-250/sqft as a starting point.",
    )
    submitted = st.form_submit_button("Estimate flood risk", type="primary")


# ---------- Run lookup and display results ----------
if submitted:
    if not address.strip():
        st.error("Please enter an address.")
        st.stop()

    with st.spinner("Looking up flood zone..."):
        try:
            result = cached_lookup(address, int(structure_value))
        except GeocodeError as e:
            st.error(
                f"**Couldn't find that address.** The Census Bureau geocoder "
                f"sometimes misses newer addresses or non-standard formats. "
                f"Try a more specific street address.\n\n*Technical detail: {e}*"
            )
            st.stop()
        except FloodLookupError as e:
            st.error(
                f"**Couldn't reach FEMA's flood data service right now.** "
                f"FEMA's National Flood Hazard Layer API has been experiencing "
                f"intermittent outages. Please try again in a few minutes — "
                f"this typically resolves within hours.\n\n*Technical detail: {e}*"
            )
            st.stop()
        except Exception as e:
            st.error(f"Unexpected error: {e}")
            st.stop()

    # ----- Results -----
    st.markdown("---")

    # Determine risk level from the zone for color/messaging
    sfha_zones = {"A", "AE", "AH", "AO", "V", "VE"}
    is_sfha = result["flood_zone"] in sfha_zones
    is_levee = result.get("confidence_flag") == "levee_dependent"
    is_high_coastal = result["flood_zone"] in {"V", "VE"}

    if is_high_coastal:
        risk_color = "#b91c1c"  # dark red
        risk_bg = "#fef2f2"
        risk_label = "HIGH RISK"
        risk_emoji = "🌊"
    elif is_sfha:
        risk_color = "#c2410c"  # dark orange
        risk_bg = "#fff7ed"
        risk_label = "ELEVATED RISK"
        risk_emoji = "⚠️"
    elif is_levee:
        risk_color = "#a16207"  # dark amber
        risk_bg = "#fefce8"
        risk_label = "LEVEE-DEPENDENT"
        risk_emoji = "🛡️"
    else:
        risk_color = "#15803d"  # green
        risk_bg = "#f0fdf4"
        risk_label = "LOW RISK"
        risk_emoji = "✓"

    # ---- Hero result card ----
    st.markdown(
        f"""
        <div style="
            background: {risk_bg};
            border-left: 6px solid {risk_color};
            border-radius: 6px;
            padding: 24px 28px;
            margin: 16px 0;
        ">
            <div style="color: {risk_color}; font-size: 13px;
                        font-weight: 700; letter-spacing: 1px; margin-bottom: 4px;">
                {risk_emoji} &nbsp; {risk_label} &nbsp;·&nbsp; FEMA ZONE {result['flood_zone'] or 'N/A'}
            </div>
            <div style="color: #111; font-size: 13px; margin-bottom: 18px;">
                {result['matched_address']}
            </div>
            <div style="color: #555; font-size: 13px; text-transform: uppercase;
                        letter-spacing: 1px; margin-bottom: 4px;">
                Estimated annual expected loss
            </div>
            <div style="color: {risk_color}; font-size: 44px; font-weight: 700;
                        line-height: 1;">
                ${result['annual_expected_loss_dollars']:,.0f}
                <span style="font-size: 18px; color: #555; font-weight: 400;">/ year</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Three context numbers below the hero ----
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Annual flood probability",
        f"{result['annual_flood_probability']*100:.2f}%",
    )
    col2.metric(
        "30-yr cumulative probability",
        f"{result['thirty_year_flood_probability']*100:.1f}%",
        help="Probability of at least one flood event during a 30-year mortgage.",
    )
    col3.metric(
        "Base flood elevation",
        f"{result['base_flood_elevation']} ft" if result.get("base_flood_elevation") else "N/A",
        help="Regulatory floor elevation required to comply with NFIP standards.",
    )

    # ---- Subtype callout ----
    if result.get("zone_subtype"):
        if is_levee:
            st.markdown(
                f"""
                <div style="background: #fefce8; border: 1px solid #fde047;
                            border-radius: 6px; padding: 14px 18px; margin-top: 12px;">
                    <div style="font-weight: 600; color: #854d0e; margin-bottom: 4px;">
                        🛡️ Levee-protected — read carefully
                    </div>
                    <div style="color: #444; font-size: 14px;">
                        FEMA subtype: <em>{result['zone_subtype']}</em>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div style="background: #f3f4f6; border-radius: 6px;
                            padding: 12px 16px; margin-top: 12px; font-size: 14px;">
                    <strong>FEMA subtype:</strong> {result['zone_subtype']}
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ---- Interpretation ----
    if result.get("interpretation"):
        st.markdown("##### What this means")
        st.markdown(result["interpretation"])

    # ---- Insurance comparison section ----
    st.markdown("---")
    st.markdown("### How does this compare to flood insurance?")

    if result.get("premium_low") and result.get("premium_high"):
        # Visual bar showing where expected loss sits relative to premium range
        el = result["annual_expected_loss_dollars"]
        p_low = result["premium_low"]
        p_high = result["premium_high"]
        bar_max = max(p_high * 1.3, el * 1.2)
        el_pct = (el / bar_max) * 100
        p_low_pct = (p_low / bar_max) * 100
        p_high_pct = (p_high / bar_max) * 100

        st.markdown(
            f"""
            <div style="margin: 20px 0 12px 0;">
                <div style="position: relative; height: 50px; background: #f3f4f6;
                            border-radius: 6px; overflow: hidden;">
                    <div style="position: absolute; left: {p_low_pct}%;
                                width: {p_high_pct - p_low_pct}%; height: 100%;
                                background: #dbeafe;"></div>
                    <div style="position: absolute; left: {el_pct}%; top: 0;
                                width: 3px; height: 100%; background: {risk_color};"></div>
                </div>
                <div style="display: flex; justify-content: space-between;
                            font-size: 12px; color: #555; margin-top: 6px;">
                    <span>$0</span>
                    <span style="color: {risk_color}; font-weight: 600;">
                        Your expected loss: ${el:,.0f}
                    </span>
                    <span style="color: #1e40af;">
                        NFIP premium range: ${p_low:,}–${p_high:,}
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(result["comparison"])
    else:
        st.info("Premium estimate unavailable for this state.")

    # Coverage limit warning
    if structure_value > 250_000:
        st.warning(
            f"⚠️ Your structure value (\\${int(structure_value):,}) exceeds NFIP's "
            f"\\$250,000 building coverage limit. NFIP alone would not fully "
            f"replace your structure after a total loss. Consider excess "
            f"flood coverage from a private insurer."
        )

    # ---- Methodology ----
    with st.expander("How is this calculated?"):
        st.markdown(f"""
        **Geocoding:** US Census Bureau Geocoder (TIGER/Line based, free).

        **Flood zone:** FEMA National Flood Hazard Layer via ArcGIS REST API.

        **Annual flood probability:** {result['annual_flood_probability']*100:.2f}%
        for zone {result['flood_zone']}. Follows FEMA regulatory definitions —
        SFHA zones are 1% annual chance, shaded X is 0.2%, levee-protected zones
        use a midpoint to reflect residual risk.

        **Damage given flood:** {result['damage_fraction_given_flood']*100:.0f}%
        of structure value. Based on HAZUS-MH depth-damage curves for typical
        1-story residential structures.

        **Expected loss formula:** P(flood) × E(damage | flood) × structure value
        = {result['annual_flood_probability']*100:.2f}% × {result['damage_fraction_given_flood']*100:.0f}%
        × \\${int(result['structure_value']):,} = **\\${result['annual_expected_loss_dollars']:,.0f}/yr**.

        **NFIP premium estimates:** FEMA Risk Rating 2.0 published state averages,
        FY2024. Real premiums vary substantially by structure characteristics.

        **Caveats:**
        - Population-average damage fractions; your house may differ
        - Regulatory probabilities, not empirical frequencies
        - Levee residual risk modeled with educated midpoints
        - Does not account for sea level rise or climate-driven changes
        """)

    with st.expander("Raw data"):
        st.json(result)

# ---------- Footer ----------
st.markdown("---")
st.markdown(
    "Open source on [GitHub](https://github.com/glitching-pineapple/floodcheck). "
    "Data: FEMA NFHL, US Census Geocoder, FEMA Risk Rating 2.0. "
    "Not affiliated with FEMA, NFIP, or any insurance provider."
)

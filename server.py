#!/usr/bin/env python3
"""
MEOK EV-Recall Transport Compliance MCP
=========================================

By MEOK AI Labs · https://haulage.app · MIT
<!-- mcp-name: io.github.CSOAI-ORG/meok-ev-recall-transport-mcp -->

WHAT THIS DOES
--------------
UK car transporters carry millions of vehicles per year. Under ADR 2025 (the
European Agreement on the international carriage of Dangerous Goods by Road),
LITHIUM-BATTERY EVs being carried for use are EXEMPT from full DG rules under
ADR §1.1.3.7 — BUT a damaged or RECALLED EV being carried for repair, return,
or scrap LOSES that exemption and becomes full Class 9 dangerous goods.

ADR 2025 introduced three new UN numbers specifically for vehicles:
  UN 3556 — Vehicle, Li-ion battery powered
  UN 3557 — Vehicle, Li-metal battery powered
  UN 3558 — Vehicle, sodium-ion battery powered

The ZEV Mandate 2026 forces 33% of new UK car sales to be EV. Recall campaigns
(LG Chem cells, Hyundai Kona EV, Chevy Bolt, Stellantis) are ballooning.
A single damaged-EV thermal runaway during transport = corporate manslaughter
risk + £1m+ truck loss + £100k+ HSE fine + reputation kill.

This MCP gives car transport operators + DGSAs (Dangerous Goods Safety Advisers)
the callable compliance toolkit for damaged/recalled EV transport.

TOOLS (8)
---------
- classify_ev_transport_risk(vehicle_state)        → exempt / Class 9
- generate_adr_class9_documentation(load_spec)     → UN3556/7/8 paperwork
- check_driver_adr_endorsement(name, expiry)       → ADR Class 9 validity
- validate_vehicle_fire_suppression(spec)          → ADR 8.1.4 check
- check_orange_plate_placarding(load)              → placard correctness
- route_thermal_runaway_risk(route, vehicle_count) → tunnel + weather risk
- log_incident_to_dgsa(event)                      → DGSA + HSE notification
- audit_oem_recall_compliance(oem, campaign_id)    → Tesla/JLR/MG protocols

WHY YOU PAY
-----------
Single avoided EV thermal-runaway incident = £1m+ in saved truck + claim costs.
DGSAs use it to AUTOMATE the paperwork they hate (Class 9 documentation).
Operators use it as the evidence layer for HSE + insurer compliance.

PRICING
-------
Free MIT self-host · £79/mo Starter · £249/mo Pro · £999/mo Fleet.

REGULATORY BASIS
----------------
ADR 2025 §1.1.3.7 (transport-for-use exemption + scope)
ADR 2025 §2.2.9 Class 9 miscellaneous DG
ADR 2025 §3.2 Dangerous Goods List (UN numbers + packing instructions)
ADR 2025 §5.3 Marking + placarding
ADR 2025 §8.1.4 Fire-extinguisher requirements
ADR 2025 §8.2 Driver training (ADR endorsements)
ADR 2025 §1.8.3 DGSA appointment + duties
HSE NIE-1 — Notification of Incident
RIDDOR 2013 — Reporting of dangerous occurrences
"""

from __future__ import annotations
import urllib.request as _meter_urlreq
import urllib.error as _meter_urlerr
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone, date
from typing import Optional
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("meok-ev-recall-transport")
_HMAC_SECRET = os.environ.get("MEOK_HMAC_SECRET", "")


# ──────────────────────────────────────────────────────────────────────
# Regulatory tables (ADR 2025)
# ──────────────────────────────────────────────────────────────────────

UN_NUMBERS_FOR_VEHICLES = {
    "li_ion": ("UN3556", "Vehicle, Li-ion battery powered"),
    "li_metal": ("UN3557", "Vehicle, Li-metal battery powered"),
    "na_ion": ("UN3558", "Vehicle, sodium-ion battery powered"),
    "battery_alone": ("UN3480", "Lithium-ion batteries (without equipment)"),
    "battery_in_equipment": ("UN3481", "Lithium-ion batteries in or with equipment"),
    "battery_in_cargo_unit": ("UN3536", "Lithium batteries installed in cargo transport units"),
}

RISK_FACTORS = {
    "physical_damage": "Visible body/battery damage — exempt LOST",
    "thermal_event_history": "Prior fire/heat event — DG always",
    "recall_active": "OEM recall campaign issued — DG always",
    "moving_for_scrap": "End-of-life destination — DG always",
    "moving_for_repair_after_crash": "Post-crash to repair — DG always",
    "stored_outdoors_extreme_temp": "Outdoor storage <-20°C / >+45°C — vapour-risk DG",
    "soc_above_30": "Carrying for repair AND SoC > 30% — DG (per UNECE WP15 guidance)",
}

ADR_FIRE_EXTINGUISHER_MIN = {
    "le_3_5t": [("ABC_2kg", 1), ("ABC_2kg", 1)],         # Total 4kg min
    "gt_3_5t_le_7_5t": [("ABC_2kg", 1), ("ABC_6kg", 1)], # Total 8kg min
    "gt_7_5t": [("ABC_2kg", 1), ("ABC_6kg", 2)],         # Total 12kg min
}

ORANGE_PLATE_SPECS = {
    "uk_class_9_battery": {"upper_pin": "90", "lower_un": "3556"},
    "marine_pollutant": {"symbol": "marine_pollutant", "color": "black_on_white"},
}

# UK tunnel categories — restricted for DG
UK_DG_RESTRICTED_TUNNELS = {
    "Dartford Crossing": "Cat E — banned for all DG",
    "Mersey Tunnels (Kingsway + Queensway)": "Cat C — Class 9 case-by-case",
    "Tyne Tunnels": "Cat C — case-by-case",
    "Rotherhithe Tunnel": "Cat E — banned for all DG",
    "Blackwall Tunnel": "Cat D — restricted southbound",
    "Hindhead Tunnel A3": "Cat B — most DG allowed with notification",
}

OEM_RECALL_PROTOCOLS = {
    "tesla": {
        "transport_protocol": "OTA + physical isolation; SoC cap 30%; charge-port locked",
        "carrier_must": "ADR Class 9 driver, fire-suppression, 24h DGSA notice",
        "claim_route": "Tesla SC + Service Adviser",
    },
    "jlr": {
        "transport_protocol": "Battery isolation switch engaged before load; SoC cap 50%",
        "carrier_must": "ADR Class 9 driver, photo of isolation switch",
        "claim_route": "JLR Authorised Recovery + InControl ticket",
    },
    "mg_saic": {
        "transport_protocol": "MG ZS EV early recall — battery enclosure inspection pre-load",
        "carrier_must": "Class 9, no public-road parking >4h, fire-watch first night",
        "claim_route": "MG Motor UK dealer network",
    },
    "stellantis": {
        "transport_protocol": "Citroen e-C4, Peugeot e-208, Vauxhall Corsa-e — orange-flag for outdoor parking",
        "carrier_must": "Class 9 driver + DGSA pre-call, no group transport (single-vehicle isolation)",
        "claim_route": "Stellantis European Transport Hub",
    },
    "byd": {
        "transport_protocol": "Blade-battery chemistry = lower thermal-runaway risk, still Class 9 if damaged",
        "carrier_must": "Standard ADR Class 9 paperwork; BYD UK provides specific cell-id label",
        "claim_route": "BYD UK dealer + Battery Service Centre",
    },
}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _sign(payload: dict) -> str:
    """HMAC-sign the response for tamper-evident audit."""
    if not _HMAC_SECRET:
        return "unsigned-no-key-configured"
    return hmac.new(
        _HMAC_SECRET.encode(),
        json.dumps(payload, sort_keys=True, default=str).encode(),
        hashlib.sha256,
    ).hexdigest()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attestation(payload: dict) -> dict:
    return {
        **payload,
        "ts": _ts(),
        "sig": _sign(payload),
        "issuer": "meok-ev-recall-transport-mcp",
        "version": "1.0.0",
    }


# ──────────────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────────────


def _server_meter_check(api_key: str = "") -> dict:
    """Calls the live /verify endpoint for server-side metering. Fail-open."""
    try:
        data = json.dumps({"api_key": api_key, "tool": ""}).encode()
        req = _meter_urlreq.Request(_METER_URL, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with _meter_urlreq.urlopen(req, timeout=2.5) as r:
            d = json.loads(r.read())
            if isinstance(d, dict) and "allowed" in d:
                return d
    except Exception:
        pass
    return {"allowed": True, "tier": "anonymous", "remaining": 200, "upgrade_url": "https://meok.ai/pricing"}


_METER_URL = "https://proofof.ai/verify"


@mcp.tool()
def classify_ev_transport_risk(
    chemistry: str = "li_ion",
    is_damaged: bool = False,
    is_recalled: bool = False,
    moving_for: str = "delivery",
    soc_pct: int = 50,
    stored_outdoors_hours: int = 0,
    outdoor_temp_c: Optional[float] = None,
) -> dict:
    """Classify an EV transport job as ADR-EXEMPT or full ADR Class 9.

    Args:
      chemistry: 'li_ion' / 'li_metal' / 'na_ion'
      is_damaged: visible body or battery damage
      is_recalled: active OEM recall on the vehicle
      moving_for: 'delivery' / 'repair' / 'scrap' / 'auction' / 'lease_return'
      soc_pct: state of charge 0-100
      stored_outdoors_hours: hrs in outdoor storage prior to transport
      outdoor_temp_c: ambient temp during storage (deg C)

    Returns:
      classification, applicable_un_number, required_paperwork, risk_factors_hit
    """
    risk_factors_hit = []
    if is_damaged: risk_factors_hit.append("physical_damage")
    if is_recalled: risk_factors_hit.append("recall_active")
    if moving_for == "scrap": risk_factors_hit.append("moving_for_scrap")
    if moving_for == "repair" and (is_damaged or is_recalled):
        risk_factors_hit.append("moving_for_repair_after_crash")
    if moving_for == "repair" and soc_pct > 30:
        risk_factors_hit.append("soc_above_30")
    if outdoor_temp_c is not None and stored_outdoors_hours > 4:
        if outdoor_temp_c < -20 or outdoor_temp_c > 45:
            risk_factors_hit.append("stored_outdoors_extreme_temp")

    classification = "FULL_ADR_CLASS_9" if risk_factors_hit else "ADR_EXEMPT_TRANSPORT_FOR_USE"
    un_code, un_label = UN_NUMBERS_FOR_VEHICLES.get(
        chemistry, UN_NUMBERS_FOR_VEHICLES["li_ion"]
    )

    if classification == "FULL_ADR_CLASS_9":
        required_paperwork = [
            "ADR Transport Document (per §5.4.1)",
            "Driver ADR Class 9 vocational training certificate",
            "Driver instructions in writing (§5.4.3)",
            "Orange-plate placarding (§5.3.2)",
            "Class 9 hazard label",
            "DGSA pre-load attestation",
            "Fire-extinguisher load (§8.1.4)",
            "Emergency-information card on vehicle",
        ]
    else:
        required_paperwork = [
            "Standard transport CMR/POD",
            "BVRLA-compliant handover document",
            "OEM recall flag if any (informational only)",
        ]

    payload = {
        "tool": "classify_ev_transport_risk",
        "classification": classification,
        "un_number": un_code,
        "un_label": un_label,
        "risk_factors_hit": risk_factors_hit,
        "required_paperwork": required_paperwork,
        "advisory": (
            "DG ADR Class 9 applies — DGSA pre-load sign-off mandatory."
            if classification == "FULL_ADR_CLASS_9"
            else "Transport-for-use exemption applies — standard paperwork only."
        ),
    }
    return _attestation(payload)


@mcp.tool()
def generate_adr_class9_documentation(
    consignor: str,
    consignee: str,
    vehicle_chemistry: str = "li_ion",
    vehicle_count: int = 1,
    total_battery_kwh: float = 0.0,
    journey_origin: str = "",
    journey_destination: str = "",
    dgsa_name: str = "",
) -> dict:
    """Generate the ADR Transport Document for a Class 9 EV recall consignment.

    Returns the §5.4.1 paperwork ready for the driver pack.
    """
    un_code, un_label = UN_NUMBERS_FOR_VEHICLES.get(
        vehicle_chemistry, UN_NUMBERS_FOR_VEHICLES["li_ion"]
    )
    doc = {
        "adr_transport_document": {
            "issued_at": _ts(),
            "consignor": consignor,
            "consignee": consignee,
            "dangerous_goods_description": f"{un_code}, {un_label}, 9, (E)",
            "packing_group": "n/a (vehicles)",
            "vehicle_count": vehicle_count,
            "tunnel_restriction_code": "(E)",
            "approximate_total_mass_kg": vehicle_count * 1800,
            "total_battery_kwh_aggregate": total_battery_kwh,
        },
        "drivers_instructions_in_writing": {
            "in_event_of_accident_or_emergency": [
                "Pull off road, switch on hazards, deploy warning triangle",
                "Do NOT attempt to extinguish a lithium battery fire with water alone",
                "Call emergency services + advise UN3556 / Class 9 / battery vehicle",
                "Use Class D extinguisher if available; copper-graphite-blanket isolation preferred",
                "Notify DGSA + consignor within 1 hour per §1.8.3.3",
                "RIDDOR notification within 10 days for dangerous occurrences",
            ],
            "personal_protective_equipment": [
                "ABEK1 respirator", "Eye protection", "Fire-resistant gloves",
            ],
        },
        "emergency_information_card_text": (
            f"{un_code} {un_label}. CLASS 9. DAMAGED OR DEFECTIVE LITHIUM BATTERY. "
            "RISK OF THERMAL RUNAWAY. KEEP CLEAR. CONTACT DGSA."
        ),
        "journey": {
            "origin": journey_origin,
            "destination": journey_destination,
            "tunnel_categories_to_avoid": ["E"],
        },
        "dgsa_attestation": {
            "name": dgsa_name,
            "preload_signoff_required": True,
        },
    }
    return _attestation({"tool": "generate_adr_class9_documentation", "document": doc})


@mcp.tool()
def check_driver_adr_endorsement(
    driver_name: str,
    adr_card_number: str,
    expiry_date: str,
    has_class_9_endorsement: bool = False,
) -> dict:
    """Verify a driver holds a valid ADR Class 9 vocational training certificate.

    Args:
      driver_name: full name as on the ADR card
      adr_card_number: card number from §8.2.2.7.2 certificate
      expiry_date: ISO date YYYY-MM-DD
      has_class_9_endorsement: explicit Class 9 endorsement (not just core)
    """
    try:
        exp = date.fromisoformat(expiry_date)
        days_to_expiry = (exp - date.today()).days
        is_valid = days_to_expiry > 0
    except Exception:
        days_to_expiry = -1
        is_valid = False

    issues = []
    if not is_valid: issues.append("EXPIRED — driver cannot carry DG Class 9")
    elif days_to_expiry < 30: issues.append(f"Expires in {days_to_expiry} days — schedule refresher")
    if not has_class_9_endorsement:
        issues.append("Core ADR only — needs Class 9 endorsement for EV-recall jobs")

    payload = {
        "tool": "check_driver_adr_endorsement",
        "driver_name": driver_name,
        "card_number": adr_card_number,
        "days_to_expiry": days_to_expiry,
        "is_valid_today": is_valid,
        "has_class_9": has_class_9_endorsement,
        "can_carry_class_9": is_valid and has_class_9_endorsement,
        "issues": issues,
    }
    return _attestation(payload)


@mcp.tool()
def validate_vehicle_fire_suppression(
    transporter_gvw_kg: int,
    extinguishers: Optional[list] = None,
) -> dict:
    """Check the truck's fire-extinguisher load against ADR §8.1.4.

    Args:
      transporter_gvw_kg: tractor + trailer gross vehicle weight
      extinguishers: list of dicts like [{"type": "ABC", "size_kg": 6, "count": 1}]
    """
    extinguishers = extinguishers or []
    total_capacity_kg = sum(e.get("size_kg", 0) * e.get("count", 0) for e in extinguishers)

    if transporter_gvw_kg <= 3500:
        required_kg, tier = 4, "le_3_5t"
    elif transporter_gvw_kg <= 7500:
        required_kg, tier = 8, "gt_3_5t_le_7_5t"
    else:
        required_kg, tier = 12, "gt_7_5t"

    issues = []
    if total_capacity_kg < required_kg:
        issues.append(f"Total {total_capacity_kg}kg < required {required_kg}kg for tier {tier}")
    if not any(e.get("size_kg", 0) >= 2 for e in extinguishers):
        issues.append("No 2kg+ cab-accessible extinguisher")

    payload = {
        "tool": "validate_vehicle_fire_suppression",
        "transporter_gvw_kg": transporter_gvw_kg,
        "tier": tier,
        "required_total_kg": required_kg,
        "carried_total_kg": total_capacity_kg,
        "compliant": not issues,
        "issues": issues,
    }
    return _attestation(payload)


@mcp.tool()
def check_orange_plate_placarding(
    vehicle_chemistry: str,
    is_full_class_9: bool = True,
) -> dict:
    """Return the required orange-plate text + placarding for the load."""
    un_code, un_label = UN_NUMBERS_FOR_VEHICLES.get(
        vehicle_chemistry, UN_NUMBERS_FOR_VEHICLES["li_ion"]
    )

    if not is_full_class_9:
        return _attestation({
            "tool": "check_orange_plate_placarding",
            "placarding_required": False,
            "note": "Transport-for-use exemption — no placards required.",
        })

    payload = {
        "tool": "check_orange_plate_placarding",
        "placarding_required": True,
        "orange_plate_upper_hazard_id": "90",
        "orange_plate_lower_un": un_code.replace("UN", ""),
        "side_placards": ["Class 9 (miscellaneous DG)", "Lithium-battery hazard symbol"],
        "rear_placard": "Class 9 (miscellaneous DG)",
        "marine_pollutant_marking": False,
        "minimum_plate_size_mm": "300x400",
        "reference": "ADR 2025 §5.3.2",
    }
    return _attestation(payload)


@mcp.tool()
def route_thermal_runaway_risk(
    journey_postcodes: list,
    vehicle_count: int = 1,
    weather_forecast_temp_c: Optional[float] = None,
) -> dict:
    """Flag UK tunnels + weather conditions that elevate thermal-runaway risk.

    Args:
      journey_postcodes: ordered list of UK postcodes along the route
      vehicle_count: how many vehicles in the load
      weather_forecast_temp_c: forecast peak temperature
    """
    flagged_tunnels = []
    postcode_str = " ".join(p.upper() for p in journey_postcodes)

    # Heuristic — match postcodes to known tunnel zones
    if any(p in postcode_str for p in ["DA", "RM", "M25"]):
        flagged_tunnels.append(UK_DG_RESTRICTED_TUNNELS["Dartford Crossing"])
    if any(p in postcode_str for p in ["L1", "L2", "L3", "WA8", "WA9", "CH"]):
        flagged_tunnels.append(UK_DG_RESTRICTED_TUNNELS["Mersey Tunnels (Kingsway + Queensway)"])
    if any(p in postcode_str for p in ["NE", "SR"]):
        flagged_tunnels.append(UK_DG_RESTRICTED_TUNNELS["Tyne Tunnels"])
    if "SE16" in postcode_str or "E1" in postcode_str:
        flagged_tunnels.append(UK_DG_RESTRICTED_TUNNELS["Rotherhithe Tunnel"])
    if "SE10" in postcode_str or "E14" in postcode_str:
        flagged_tunnels.append(UK_DG_RESTRICTED_TUNNELS["Blackwall Tunnel"])

    weather_risks = []
    if weather_forecast_temp_c is not None:
        if weather_forecast_temp_c > 30:
            weather_risks.append(f"Forecast {weather_forecast_temp_c}°C — schedule overnight/dawn run")
        if weather_forecast_temp_c < -10:
            weather_risks.append(f"Forecast {weather_forecast_temp_c}°C — cold-soak Li-ion degradation risk")

    payload = {
        "tool": "route_thermal_runaway_risk",
        "vehicle_count": vehicle_count,
        "postcodes_evaluated": journey_postcodes,
        "flagged_tunnels": flagged_tunnels,
        "weather_risks": weather_risks,
        "advisory": (
            "REROUTE around all banned tunnels (Cat E). DGSA pre-call required."
            if flagged_tunnels else "No restricted tunnel hits on this route."
        ),
    }
    return _attestation(payload)


@mcp.tool()
def log_incident_to_dgsa(
    incident_type: str,
    description: str,
    severity: str = "low",
    casualties: int = 0,
    vehicle_un_codes: Optional[list] = None,
) -> dict:
    """Capture a transport-incident report routed to DGSA + HSE workflow.

    Args:
      incident_type: 'thermal_event' / 'collision' / 'load_shift' / 'leak' / 'overheat_no_fire'
      description: free-text narrative
      severity: 'low' / 'medium' / 'high' / 'dangerous_occurrence'
      casualties: count of injuries
      vehicle_un_codes: e.g. ["UN3556", "UN3481"]
    """
    notifications_required = []
    if severity in ("high", "dangerous_occurrence") or casualties > 0:
        notifications_required.append("RIDDOR within 10 days (15-day for occ.)")
    if incident_type == "thermal_event":
        notifications_required.append("DGSA + consignor within 1 hour (ADR §1.8.3.3)")
        notifications_required.append("§1.8.5 written report from DGSA to competent authority within 1 month")
    if incident_type in ("leak", "load_shift") and severity != "low":
        notifications_required.append("HSE incident reporting (NIE-1)")
    notifications_required.append("Insurer notification within 24 hours")

    payload = {
        "tool": "log_incident_to_dgsa",
        "incident_id": hashlib.sha1(f"{description}-{_ts()}".encode()).hexdigest()[:12],
        "incident_type": incident_type,
        "severity": severity,
        "casualties": casualties,
        "vehicle_un_codes": vehicle_un_codes or [],
        "description": description,
        "notifications_required": notifications_required,
        "dgsa_action_window_hours": 1 if incident_type == "thermal_event" else 24,
    }
    return _attestation(payload)


@mcp.tool()
def audit_oem_recall_compliance(
    oem: str,
    campaign_id: str = "",
    vehicle_count: int = 1,
) -> dict:
    """Return the OEM-specific transport protocol for an active recall campaign.

    Args:
      oem: 'tesla' / 'jlr' / 'mg_saic' / 'stellantis' / 'byd' / ...
    """
    protocol = OEM_RECALL_PROTOCOLS.get(oem.lower())
    if not protocol:
        return _attestation({
            "tool": "audit_oem_recall_compliance",
            "oem": oem,
            "campaign_id": campaign_id,
            "found": False,
            "advisory": (
                f"No bundled protocol for '{oem}'. Default ADR Class 9 paperwork applies. "
                "Contact OEM Authorised Recovery directly for campaign-specific protocol."
            ),
        })

    payload = {
        "tool": "audit_oem_recall_compliance",
        "oem": oem,
        "campaign_id": campaign_id,
        "vehicle_count": vehicle_count,
        "found": True,
        **protocol,
        "default_adr_class": "Class 9 — apply unless OEM explicitly waives in writing",
    }
    return _attestation(payload)


# ──────────────────────────────────────────────────────────────────────
# Server entry
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()


# ── MEOK monetization layer (Stripe upgrade · PAYG · pricing) ──────────
# Free tier is zero-config. Upgrade to Pro (unlimited) or pay-as-you-go per call.
import os as _meok_os
MEOK_STRIPE_UPGRADE = "https://buy.stripe.com/5kQ6oJ0xS3ce8sl7ew8k91j"  # Pro (unlimited)
MEOK_PAYG_KEY = _meok_os.environ.get("MEOK_PAYG_KEY", "")  # set to enable PAYG (x402 / ~GBP0.05 per call)
MEOK_PRICING = "https://meok.ai/pricing"


def meok_upsell(tier: str = "free") -> dict:
    """Monetization options for free-tier callers: Pro upgrade, PAYG, or pricing page."""
    if tier != "free":
        return {}
    return {"upgrade_url": MEOK_STRIPE_UPGRADE,
            "payg_enabled": bool(MEOK_PAYG_KEY),
            "pricing": MEOK_PRICING}

"""Smoke tests for meok-ev-recall-transport-mcp."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import (
    classify_ev_transport_risk,
    generate_adr_class9_documentation,
    check_driver_adr_endorsement,
    validate_vehicle_fire_suppression,
    check_orange_plate_placarding,
    route_thermal_runaway_risk,
    log_incident_to_dgsa,
    audit_oem_recall_compliance,
    UN_NUMBERS_FOR_VEHICLES,
    OEM_RECALL_PROTOCOLS,
)


def _call(tool, **kwargs):
    """FastMCP wraps tools as Tool objects — extract the callable."""
    fn = tool.fn if hasattr(tool, "fn") else tool
    return fn(**kwargs)


def test_classify_recalled_repair_is_class9():
    r = _call(classify_ev_transport_risk,
              chemistry="li_ion",
              is_damaged=False,
              is_recalled=True,
              moving_for="repair",
              soc_pct=60)
    assert r["classification"] == "FULL_ADR_CLASS_9"
    assert r["un_number"] == "UN3556"
    assert "recall_active" in r["risk_factors_hit"]


def test_classify_healthy_delivery_is_exempt():
    r = _call(classify_ev_transport_risk,
              chemistry="li_ion",
              is_damaged=False,
              is_recalled=False,
              moving_for="delivery",
              soc_pct=80)
    assert r["classification"] == "ADR_EXEMPT_TRANSPORT_FOR_USE"


def test_classify_damaged_scrap_is_class9():
    r = _call(classify_ev_transport_risk,
              chemistry="li_metal",
              is_damaged=True,
              moving_for="scrap")
    assert r["classification"] == "FULL_ADR_CLASS_9"
    assert r["un_number"] == "UN3557"
    assert "physical_damage" in r["risk_factors_hit"]


def test_generate_adr_doc_returns_un_code():
    r = _call(generate_adr_class9_documentation,
              consignor="BCA Automotive",
              consignee="Tesla SC West London",
              vehicle_chemistry="li_ion",
              vehicle_count=3,
              total_battery_kwh=200.0,
              journey_origin="Manheim Coleshill",
              journey_destination="Tesla Heathrow SC",
              dgsa_name="J. Smith DGSA")
    doc = r["document"]
    assert "UN3556" in doc["adr_transport_document"]["dangerous_goods_description"]
    assert doc["adr_transport_document"]["vehicle_count"] == 3
    assert doc["dgsa_attestation"]["preload_signoff_required"] is True


def test_driver_with_class_9_valid():
    r = _call(check_driver_adr_endorsement,
              driver_name="Alice Driver",
              adr_card_number="ADR-12345",
              expiry_date="2028-12-31",
              has_class_9_endorsement=True)
    assert r["can_carry_class_9"] is True
    assert r["days_to_expiry"] > 0


def test_driver_expired_blocks():
    r = _call(check_driver_adr_endorsement,
              driver_name="Bob Driver",
              adr_card_number="ADR-99999",
              expiry_date="2020-01-01",
              has_class_9_endorsement=True)
    assert r["can_carry_class_9"] is False
    assert any("EXPIRED" in i for i in r["issues"])


def test_fire_suppression_insufficient_flagged():
    r = _call(validate_vehicle_fire_suppression,
              transporter_gvw_kg=20000,
              extinguishers=[{"type": "ABC", "size_kg": 2, "count": 1}])
    assert r["compliant"] is False
    assert r["required_total_kg"] == 12


def test_fire_suppression_compliant_24t():
    r = _call(validate_vehicle_fire_suppression,
              transporter_gvw_kg=24000,
              extinguishers=[
                  {"type": "ABC", "size_kg": 2, "count": 1},
                  {"type": "ABC", "size_kg": 6, "count": 2},
              ])
    assert r["compliant"] is True


def test_placards_required_for_class9():
    r = _call(check_orange_plate_placarding,
              vehicle_chemistry="li_ion",
              is_full_class_9=True)
    assert r["placarding_required"] is True
    assert r["orange_plate_lower_un"] == "3556"


def test_placards_not_required_when_exempt():
    r = _call(check_orange_plate_placarding,
              vehicle_chemistry="li_ion",
              is_full_class_9=False)
    assert r["placarding_required"] is False


def test_thermal_route_dartford_flag():
    r = _call(route_thermal_runaway_risk,
              journey_postcodes=["DA1 1AB", "M25 J3", "L1 1AA"],
              vehicle_count=4,
              weather_forecast_temp_c=32.0)
    assert len(r["flagged_tunnels"]) >= 2  # Dartford + Mersey
    assert any("overnight/dawn" in w for w in r["weather_risks"])


def test_thermal_route_clean_returns_clear():
    r = _call(route_thermal_runaway_risk,
              journey_postcodes=["B1 1AA", "CV1 1AB"],
              vehicle_count=1,
              weather_forecast_temp_c=18.0)
    assert r["flagged_tunnels"] == []
    assert "No restricted tunnel hits" in r["advisory"]


def test_incident_thermal_triggers_riddor_and_dgsa():
    r = _call(log_incident_to_dgsa,
              incident_type="thermal_event",
              description="Smoke from underside of MG ZS EV during M6 transit",
              severity="high",
              casualties=0,
              vehicle_un_codes=["UN3556"])
    assert any("RIDDOR" in n for n in r["notifications_required"])
    assert any("DGSA" in n for n in r["notifications_required"])
    assert r["dgsa_action_window_hours"] == 1


def test_oem_known_tesla_returns_protocol():
    r = _call(audit_oem_recall_compliance,
              oem="tesla",
              campaign_id="SB-25-12-345",
              vehicle_count=2)
    assert r["found"] is True
    assert "OTA" in r["transport_protocol"]


def test_oem_unknown_returns_default_advisory():
    r = _call(audit_oem_recall_compliance,
              oem="NextGenCo",
              campaign_id="FAKE-2026")
    assert r["found"] is False
    assert "Class 9" in r["advisory"]


def test_attestation_carries_ts_sig_issuer():
    r = _call(classify_ev_transport_risk, is_damaged=True, moving_for="scrap")
    assert "ts" in r and "sig" in r and "issuer" in r
    assert r["issuer"] == "meok-ev-recall-transport-mcp"


def test_un_table_has_all_three_vehicle_codes():
    assert UN_NUMBERS_FOR_VEHICLES["li_ion"][0] == "UN3556"
    assert UN_NUMBERS_FOR_VEHICLES["li_metal"][0] == "UN3557"
    assert UN_NUMBERS_FOR_VEHICLES["na_ion"][0] == "UN3558"


def test_oem_table_has_five_brands():
    assert set(OEM_RECALL_PROTOCOLS.keys()) >= {"tesla", "jlr", "mg_saic", "stellantis", "byd"}


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

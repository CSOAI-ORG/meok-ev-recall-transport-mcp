<!-- mcp-name: io.github.CSOAI-ORG/meok-ev-recall-transport-mcp -->
[![MCP Scorecard: 84/100](https://img.shields.io/badge/proofof.ai-84%2F100-5b21b6)](https://proofof.ai/scorecard/meok-ev-recall-transport-mcp.html)

# meok-ev-recall-transport-mcp

[![PyPI](https://img.shields.io/badge/PyPI-1.0.0-blue)](https://pypi.org/project/meok-ev-recall-transport-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-1.3.0+-green)](https://modelcontextprotocol.io)

> ADR Class 9 compliance toolkit for UK car transporters moving damaged or recalled EVs. By **MEOK AI Labs**.

## Why this exists

UK car transporters move millions of vehicles per year. EVs being carried **for use** are exempt from full ADR rules under §1.1.3.7. But a **damaged or RECALLED** EV being carried for repair, return, or scrap **loses that exemption** and becomes full **Class 9 dangerous goods** — UN3556 (Li-ion), UN3557 (Li-metal), UN3558 (Na-ion).

The ZEV Mandate 2026 forces 33% of new UK car sales to be EV. Recall campaigns are ballooning (LG Chem, Hyundai Kona, Chevy Bolt, Stellantis). A single damaged-EV thermal runaway during transport = corporate manslaughter risk, £1m+ truck loss, £100k+ HSE fine, reputation kill.

This MCP gives car transport operators and **DGSAs (Dangerous Goods Safety Advisers)** the callable compliance toolkit they have been doing on paper.

## Install

```bash
pip install meok-ev-recall-transport-mcp
```

## Claude Desktop config

```json
{
  "mcpServers": {
    "ev-recall-transport": {
      "command": "meok-ev-recall-transport-mcp"
    }
  }
}
```

## Tools (8)

| Tool | Use case |
|------|----------|
| `classify_ev_transport_risk` | Is this job ADR-exempt or full Class 9? Decide in seconds. |
| `generate_adr_class9_documentation` | §5.4.1 Transport Document + driver instructions + emergency card. |
| `check_driver_adr_endorsement` | Is the driver Class 9 valid? Expiry warnings. |
| `validate_vehicle_fire_suppression` | ADR §8.1.4 fire-extinguisher load check. |
| `check_orange_plate_placarding` | What goes on the truck — placards + plates per §5.3.2. |
| `route_thermal_runaway_risk` | Flag UK tunnels (Dartford, Rotherhithe, Mersey etc.) banned/restricted for Class 9. |
| `log_incident_to_dgsa` | RIDDOR + DGSA + HSE notification routing. |
| `audit_oem_recall_compliance` | OEM-specific protocols: Tesla, JLR, MG SAIC, Stellantis, BYD. |

## Pricing

- **Free** — MIT self-host
- **Starter** — £79/mo (signed attestations + email support)
- **Pro** — £249/mo (DGSA dashboard + multi-user)
- **Fleet** — £999/mo (50+ trucks, audit-export, SLA)

[Subscribe Pro → £79/mo](https://buy.stripe.com/aFa7sNcgAdQS0ZT1Uc8k91t) · [Talk to Nick](mailto:nicholas@meok.ai)

## Regulatory basis

- ADR 2025 §1.1.3.7 (transport-for-use exemption + scope)
- ADR 2025 §2.2.9 (Class 9 miscellaneous DG)
- ADR 2025 §3.2 (Dangerous Goods List)
- ADR 2025 §5.3.2 (Marking + placarding)
- ADR 2025 §5.4 (Documentation)
- ADR 2025 §8.1.4 (Fire-extinguisher requirements)
- ADR 2025 §8.2 (Driver training)
- ADR 2025 §1.8.3 (DGSA appointment + duties)
- HSE NIE-1 — Notification of Incident
- RIDDOR 2013 — Reporting of dangerous occurrences

## Sign your responses (production)

```bash
export MEOK_HMAC_SECRET="your-secret"
meok-ev-recall-transport-mcp
```

Every tool response returns an HMAC-SHA256 signature for audit-trail evidence.

## Companion MCPs

Part of the **MEOK Car Transport** stack on haulage.app:

- `meok-car-transport-uk-mcp` — DVSA + tacho + C&U
- `meok-vehicle-handover-mcp` — NAMA + BVRLA + POD
- `meok-ev-recall-transport-mcp` — this one

## License

MIT © 2026 Nicholas Templeman / MEOK AI Labs · [haulage.app](https://haulage.app)

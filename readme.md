# GTFS Bogotá

Automated pipeline for generating, improving and validating the Bogotá GTFS feed.

This project downloads the latest official Bogotá GTFS feed, rebuilds route geometries using OpenStreetMap and Pfaedle, cleans problematic shape metadata, and validates the resulting feed using MobilityData GTFS Validator.

The entire process runs automatically through GitHub Actions.

---

# Objectives

This project aims to:

- Download the newest official Bogotá GTFS feed automatically
- Keep OpenStreetMap data up-to-date
- Improve route geometries through map matching
- Reduce GTFS validation warnings and errors
- Provide a reproducible GTFS processing pipeline
- Maintain a fully automated workflow

---

# Data Sources

## GTFS Feed

Official GTFS feed:

```text
https://storage.googleapis.com/gtfs-estaticos/
```

## Fares

The official feed ships an empty `fare_attributes.txt`. `scripts/add_fares.py` adds fares after map matching, using the values in `config/fares.json`:

| Network | Agencies (`agency_id`) | Fare |
|---|---|---|
| TransMilenio Troncal (incl. Dual) | 1, 6 | $3.550 COP |
| TransMiZonal (Urbano, Complementario, Especial) | 3, 4, 5 | $3.550 COP |
| TransMiCable | 7 | $3.550 COP |
| Alimentadores | 2 | free |

Transfers between troncal, zonal and cable are free within 125 minutes (max. 2 transfers), only with a personalised TuLlave card. Source: [Bogotá tariffs 2026](https://bogota.gov.co/mi-ciudad/movilidad/tarifa-transmilenio-transmicable-y-transmizonal-2026-bogota), valid from 14 January 2026.

Both fare models are written:

- **Fares v1**: `fare_attributes.txt`, `fare_rules.txt`. One shared fare for all paid routes with `transfers=2` and `transfer_duration=7500`. It cannot distinguish card types, so it describes the personalised-card case.
- **Fares v2**: `networks.txt`, `route_networks.txt`, `fare_media.txt`, `fare_products.txt`, `fare_leg_rules.txt`, `fare_transfer_rules.txt`. The free transfer product only exists for `tullave_personalizada`, so riders with a basic TuLlave or a bank card pay per boarding.

When tariffs change, edit `config/fares.json` only. If a new `agency_id` appears in the official feed, the script stops with an error until it is mapped to a network.

Run locally on an extracted feed:

```bash
python scripts/add_fares.py gtfs-out config/fares.json
```

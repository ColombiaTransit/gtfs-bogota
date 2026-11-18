#!/usr/bin/env python3
"""
Add fare information to an extracted Bogotá GTFS feed.

Writes both:
  * GTFS Fares v1: fare_attributes.txt, fare_rules.txt
  * GTFS Fares v2: networks.txt, route_networks.txt, fare_media.txt,
                   fare_products.txt, fare_leg_rules.txt, fare_transfer_rules.txt

Everything is derived from config/fares.json and the feed's routes.txt
(routes are assigned to a network by their agency_id).

Usage:
    python scripts/add_fares.py gtfs-out [config/fares.json]
"""

import csv
import json
import sys
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "fares.json"

PAID_GROUP = "lg_pagado"
FREE_GROUP = "lg_alimentador"
FARE_PRODUCT = "pasaje"
FREE_PRODUCT = "alimentador_gratis"
TRANSFER_PRODUCT = "transbordo"


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  wrote {path.name} ({len(rows)} rows)")


def load_routes(gtfs_dir):
    with open(gtfs_dir / "routes.txt", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if "network_id" in (reader.fieldnames or []):
            # route_networks.txt and routes.network_id are mutually exclusive.
            sys.exit("ERROR: routes.txt already has a network_id column")
        return [(r["route_id"], r.get("agency_id", "")) for r in reader]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    gtfs_dir = Path(sys.argv[1])
    config_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CONFIG
    cfg = json.loads(config_path.read_text(encoding="utf-8"))

    networks = {k: v for k, v in cfg["networks"].items() if not k.startswith("_")}
    media = {k: v for k, v in cfg["fare_media"].items() if not k.startswith("_")}
    currency = cfg["currency"]
    price = cfg["fare_price"]
    transfer = cfg["transfer"]
    transfer_seconds = int(transfer["duration_minutes"]) * 60

    agency_to_network = {}
    for network_id, net in networks.items():
        for agency_id in net["agency_ids"]:
            agency_to_network[str(agency_id)] = network_id

    # ---- Assign routes to networks -------------------------------------
    routes = load_routes(gtfs_dir)
    route_network = []
    unmapped = {}
    for route_id, agency_id in routes:
        network_id = agency_to_network.get(agency_id)
        if network_id is None:
            unmapped[agency_id] = unmapped.get(agency_id, 0) + 1
            continue
        route_network.append((route_id, network_id))

    if unmapped:
        details = ", ".join(f"agency_id={a!r} ({n} routes)" for a, n in unmapped.items())
        sys.exit(
            f"ERROR: routes with unmapped agency_id: {details}. "
            f"Add them to 'networks' in {config_path}."
        )

    counts = {}
    for _, network_id in route_network:
        counts[network_id] = counts.get(network_id, 0) + 1
    print("Routes per network: " + ", ".join(f"{k}={v}" for k, v in counts.items()))

    # Agency used for fare_attributes.agency_id (required when a feed has
    # several agencies). TransMilenio S.A. manages all networks, so the first
    # agency of each network group is used.
    paid_agency = next(
        str(net["agency_ids"][0]) for net in networks.values() if net["paid"]
    )
    free_agency = next(
        (str(net["agency_ids"][0]) for net in networks.values() if not net["paid"]),
        paid_agency,
    )

    print(f"Writing fares to {gtfs_dir}")

    # ---- Fares v1 ------------------------------------------------------
    # One shared fare for all paid networks, so trip planners treat
    # troncal <-> zonal <-> cable transfers as included.
    write_csv(
        gtfs_dir / "fare_attributes.txt",
        ["fare_id", "price", "currency_type", "payment_method",
         "transfers", "agency_id", "transfer_duration"],
        [
            [FARE_PRODUCT, f"{price:.2f}", currency, 0,
             transfer["max_transfers"], paid_agency, transfer_seconds],
            [FREE_PRODUCT, "0.00", currency, 0, "", free_agency, ""],
        ],
    )
    write_csv(
        gtfs_dir / "fare_rules.txt",
        ["fare_id", "route_id"],
        [
            [FARE_PRODUCT if networks[n]["paid"] else FREE_PRODUCT, route_id]
            for route_id, n in route_network
        ],
    )

    # ---- Fares v2 ------------------------------------------------------
    write_csv(
        gtfs_dir / "networks.txt",
        ["network_id", "network_name"],
        [[n, net["name"]] for n, net in networks.items()],
    )
    write_csv(
        gtfs_dir / "route_networks.txt",
        ["network_id", "route_id"],
        [[n, route_id] for route_id, n in route_network],
    )
    write_csv(
        gtfs_dir / "fare_media.txt",
        ["fare_media_id", "fare_media_name", "fare_media_type"],
        [[m, med["name"], med["type"]] for m, med in media.items()],
    )

    products = [
        [FARE_PRODUCT, "Pasaje SITP", m, f"{price:.2f}", currency] for m in media
    ]
    products.append([FREE_PRODUCT, "Alimentador (gratis)", "", "0.00", currency])
    products += [
        [TRANSFER_PRODUCT, "Transbordo", m, f"{transfer['price']:.2f}", currency]
        for m, med in media.items()
        if med["transfers"]
    ]
    write_csv(
        gtfs_dir / "fare_products.txt",
        ["fare_product_id", "fare_product_name", "fare_media_id", "amount", "currency"],
        products,
    )

    write_csv(
        gtfs_dir / "fare_leg_rules.txt",
        ["leg_group_id", "network_id", "fare_product_id"],
        [
            [PAID_GROUP, n, FARE_PRODUCT] if net["paid"] else [FREE_GROUP, n, FREE_PRODUCT]
            for n, net in networks.items()
        ],
    )

    # Transfers between paid legs: first leg's fare + transfer product.
    # The transfer product only exists for media with transfers=true, so other
    # media fall back to paying a full fare per leg.
    write_csv(
        gtfs_dir / "fare_transfer_rules.txt",
        ["from_leg_group_id", "to_leg_group_id", "transfer_count",
         "duration_limit", "duration_limit_type", "fare_transfer_type",
         "fare_product_id"],
        [[PAID_GROUP, PAID_GROUP, transfer["max_transfers"], transfer_seconds,
          1, 0, TRANSFER_PRODUCT]],
    )

    print("Fares added")


if __name__ == "__main__":
    main()

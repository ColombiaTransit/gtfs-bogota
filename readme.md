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

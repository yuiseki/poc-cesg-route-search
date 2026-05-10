"""Helpers for converting Valhalla route responses to GeoJSON."""

import json


def decode_polyline6(encoded: str) -> list[list[float]]:
    """Decode a Valhalla polyline6-encoded string into [[lon, lat], ...] pairs."""
    result = []
    index = 0
    lat = 0
    lng = 0
    n = len(encoded)

    while index < n:
        b = 0
        shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            lat += (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        if lat & 1:
            lat = ~lat
        lat >>= 1

        b = 0
        shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            lng += (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        if lng & 1:
            lng = ~lng
        lng >>= 1

        result.append([lng / 1e6, lat / 1e6])

    return result


def route_to_geojson(response: dict) -> dict:
    """
    Convert a Valhalla route response to a GeoJSON FeatureCollection.

    Each leg becomes a LineString Feature.
    """
    features = []
    try:
        legs = response["trip"]["legs"]
        for i, leg in enumerate(legs):
            shape_encoded = leg.get("shape", "")
            if shape_encoded:
                coords = decode_polyline6(shape_encoded)
            else:
                coords = []

            summary = leg.get("summary", {})
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords,
                },
                "properties": {
                    "leg_index": i,
                    "length_km": summary.get("length"),
                    "time_s": summary.get("time"),
                },
            }
            features.append(feature)
    except (KeyError, TypeError):
        pass

    return {
        "type": "FeatureCollection",
        "features": features,
    }

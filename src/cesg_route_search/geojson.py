"""Helpers for converting Valhalla route responses to GeoJSON."""

import json


def decode_polyline6(encoded: str, precision: int = 6) -> list[list[float]]:
    """Decode Valhalla encoded polyline (precision 6) to [[lon, lat], ...].

    Valhalla uses precision=6 (1e-6 degrees). Returns coordinates in GeoJSON
    order: [[lon, lat], ...] (note: Valhalla encodes as lat, lon pairs).
    """
    result = []
    index = 0
    lat = 0
    lng = 0
    n = len(encoded)
    scale = 10 ** precision

    while index < n:
        # Decode latitude delta
        b = 0
        shift = 0
        result_val = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result_val |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result_val >> 1) if (result_val & 1) else (result_val >> 1)
        lat += dlat

        # Decode longitude delta
        b = 0
        shift = 0
        result_val = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result_val |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result_val >> 1) if (result_val & 1) else (result_val >> 1)
        lng += dlng

        # Valhalla encodes [lat, lon] — return as GeoJSON [lon, lat]
        result.append([lng / scale, lat / scale])

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

"""
data_sources.py
----------------
Simulated real-time feeds for a disaster area.
  - satellite imagery  -> a provider API (Planet, Maxar, Sentinel Hub)
    run through a damage-detection model
  - social media       -> Twitter/X API, Facebook Crisis Response API,
    filtered + geotagged by an NLP classifier
  - sensor feeds        -> USGS seismic feeds, river gauge APIs, IoT
    flood/structural sensors

Here, we generate realistic-looking synthetic reports around a given
center point so the rest of the system (clustering, prioritization,
the agent loop) can be demonstrated and tested end-to-end without
needing live credentials.
"""

import random
import uuid
from datetime import datetime, timedelta

random.seed()


def _random_point_near(lat, lon, radius_km=5.0):
    """Return a random (lat, lon) within roughly `radius_km` of a center point."""
    # ~1 degree latitude ≈ 111 km; a rough local approximation is fine for a demo.
    d_lat = random.uniform(-radius_km, radius_km) / 111.0
    d_lon = random.uniform(-radius_km, radius_km) / (111.0 * 0.7)
    return round(lat + d_lat, 5), round(lon + d_lon, 5)


def _recent_timestamp(max_minutes_ago=180):
    delta = timedelta(minutes=random.randint(0, max_minutes_ago))
    return (datetime.now() - delta).isoformat(timespec="seconds")


SATELLITE_DESCRIPTIONS = [
    "Collapsed multi-story structure detected",
    "Roof damage consistent with structural failure",
    "Standing floodwater covering residential block",
    "Possible debris field, thermal anomaly detected",
    "Road/bridge segment washed out",
    "Building footprint mismatch vs. pre-event imagery",
]

SOCIAL_MEDIA_TEXTS = [
    "trapped in basement, water rising fast, need help #flood",
    "building collapsed near the market, people are still inside",
    "we're on the roof, please send a boat",
    "heard people calling for help from the rubble on 5th street",
    "elderly neighbor can't evacuate, no signal for hours",
    "bridge is out, several cars stuck, unclear if anyone injured",
]


def fetch_satellite_reports(center_lat: float, center_lon: float, count: int = 5) -> list:
    """Simulate structural/flood damage detections from satellite imagery analysis."""
    reports = []
    for _ in range(count):
        lat, lon = _random_point_near(center_lat, center_lon)
        reports.append(
            {
                "id": f"sat-{uuid.uuid4().hex[:8]}",
                "source": "satellite_imagery",
                "lat": lat,
                "lon": lon,
                "description": random.choice(SATELLITE_DESCRIPTIONS),
                "confidence": round(random.uniform(0.55, 0.97), 2),
                "timestamp": _recent_timestamp(max_minutes_ago=360),
            }
        )
    return reports


def fetch_social_media_reports(center_lat: float, center_lon: float, count: int = 8) -> list:
    """Simulate geotagged, NLP-filtered social media posts mentioning distress/entrapment."""
    reports = []
    for _ in range(count):
        lat, lon = _random_point_near(center_lat, center_lon)
        reports.append(
            {
                "id": f"soc-{uuid.uuid4().hex[:8]}",
                "source": "social_media",
                "lat": lat,
                "lon": lon,
                "description": random.choice(SOCIAL_MEDIA_TEXTS),
                # Social posts are noisier/less verified than sensors or imagery.
                "confidence": round(random.uniform(0.3, 0.75), 2),
                "timestamp": _recent_timestamp(max_minutes_ago=60),
            }
        )
    return reports


def fetch_sensor_feeds(center_lat: float, center_lon: float, count: int = 4) -> list:
    """Simulate IoT/seismic/water-level sensor readings above alert thresholds."""
    sensor_types = ["seismic", "water_level", "structural_strain"]
    reports = []
    for _ in range(count):
        lat, lon = _random_point_near(center_lat, center_lon, radius_km=6.0)
        sensor_type = random.choice(sensor_types)
        reports.append(
            {
                "id": f"sen-{uuid.uuid4().hex[:8]}",
                "source": "sensor_feed",
                "sensor_type": sensor_type,
                "lat": lat,
                "lon": lon,
                "description": f"{sensor_type} reading above alert threshold",
                "confidence": round(random.uniform(0.7, 0.99), 2),
                "timestamp": _recent_timestamp(max_minutes_ago=30),
            }
        )
    return reports

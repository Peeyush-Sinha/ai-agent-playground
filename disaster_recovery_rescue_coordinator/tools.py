"""
tools.py
--------
The tools the RescueCoordinator agent can call. These wrap the raw
data sources with the actual "coordinator" logic:

  fetch_satellite_reports / fetch_social_media_reports / fetch_sensor_feeds
      -> pull raw reports from each simulated feed (see data_sources.py)

  cluster_reports
      -> merge nearby reports (regardless of source) into "incident
         clusters", since 10 reports about the same collapsed building
         should become 1 incident, not 10

  score_incident
      -> compute a 0-100 priority score for a cluster, from signal
         count, source diversity, confidence, and recency

  save_incident / list_incidents
      -> persist prioritized incidents so responders (or the next
         agent run) can see what's already been logged
"""

import json
import math
import os
import uuid
from datetime import datetime

from data_sources import fetch_satellite_reports, fetch_social_media_reports, fetch_sensor_feeds

INCIDENTS_FILE = os.path.join(os.path.dirname(__file__), "incidents.json")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_satellite_reports(center_lat: float, center_lon: float, count: int = 5) -> str:
    return json.dumps(fetch_satellite_reports(center_lat, center_lon, count))


def get_social_media_reports(center_lat: float, center_lon: float, count: int = 8) -> str:
    return json.dumps(fetch_social_media_reports(center_lat, center_lon, count))


def get_sensor_feeds(center_lat: float, center_lon: float, count: int = 4) -> str:
    return json.dumps(fetch_sensor_feeds(center_lat, center_lon, count))


def cluster_reports(reports_json: str, radius_km: float = 0.5) -> str:
    """
    Merge reports that are within `radius_km` of each other into clusters.
    `reports_json` should be a JSON array combining reports from any/all
    of the three feeds (the agent is expected to gather them first, then
    concatenate before calling this).
    """
    try:
        reports = json.loads(reports_json)
    except Exception as e:
        return json.dumps({"error": f"Could not parse reports_json: {e}"})

    clusters = []  # each: {"reports": [...], "center_lat":, "center_lon":}

    for report in reports:
        placed = False
        for cluster in clusters:
            dist = _haversine_km(
                report["lat"], report["lon"], cluster["center_lat"], cluster["center_lon"]
            )
            if dist <= radius_km:
                cluster["reports"].append(report)
                # Recompute the cluster's centroid as reports are added.
                cluster["center_lat"] = sum(r["lat"] for r in cluster["reports"]) / len(cluster["reports"])
                cluster["center_lon"] = sum(r["lon"] for r in cluster["reports"]) / len(cluster["reports"])
                placed = True
                break
        if not placed:
            clusters.append(
                {
                    "cluster_id": f"cluster-{uuid.uuid4().hex[:8]}",
                    "center_lat": report["lat"],
                    "center_lon": report["lon"],
                    "reports": [report],
                }
            )

    return json.dumps(clusters)


def score_incident(cluster_json: str) -> str:
    """
    Compute a 0-100 priority score for a single cluster (one incident),
    from:
      - number of independent reports (more reports = more likely real)
      - number of distinct sources (satellite + social + sensor agreeing
        is a much stronger signal than 5 social posts alone)
      - average confidence of the reports
      - recency (a report from 5 minutes ago matters more than one from
        3 hours ago)
    """
    try:
        cluster = json.loads(cluster_json)
        reports = cluster["reports"]
    except Exception as e:
        return json.dumps({"error": f"Could not parse cluster_json: {e}"})

    num_reports = len(reports)
    sources = {r["source"] for r in reports}
    avg_confidence = sum(r["confidence"] for r in reports) / num_reports

    now = datetime.now()
    recency_scores = []
    for r in reports:
        age_minutes = (now - datetime.fromisoformat(r["timestamp"])).total_seconds() / 60
        # Full recency score if <15 min old, decaying to ~0 by 6 hours old.
        recency_scores.append(max(0.0, 1 - age_minutes / 360))
    avg_recency = sum(recency_scores) / len(recency_scores)

    volume_score = min(1.0, num_reports / 6)          # saturates at 6+ reports
    diversity_score = min(1.0, len(sources) / 3)        # saturates at all 3 sources agreeing

    priority = (
        0.30 * volume_score
        + 0.30 * diversity_score
        + 0.25 * avg_confidence
        + 0.15 * avg_recency
    ) * 100

    return json.dumps(
        {
            "cluster_id": cluster.get("cluster_id"),
            "center_lat": round(cluster["center_lat"], 5),
            "center_lon": round(cluster["center_lon"], 5),
            "num_reports": num_reports,
            "sources": sorted(sources),
            "avg_confidence": round(avg_confidence, 2),
            "avg_recency_score": round(avg_recency, 2),
            "priority_score": round(priority, 1),
        }
    )


def save_incident(cluster_id: str, center_lat: float, center_lon: float,
                   priority_score: float, summary: str) -> str:
    """Persist a prioritized incident to disk for responders to review."""
    incidents = _load_incidents()
    incidents[cluster_id] = {
        "center_lat": center_lat,
        "center_lon": center_lon,
        "priority_score": priority_score,
        "summary": summary,
        "logged_at": datetime.now().isoformat(timespec="seconds"),
        "status": "open",
    }
    with open(INCIDENTS_FILE, "w") as f:
        json.dump(incidents, f, indent=2)
    return json.dumps({"status": "saved", "cluster_id": cluster_id})


def list_incidents() -> str:
    """List all logged incidents, most urgent first."""
    incidents = _load_incidents()
    ranked = sorted(incidents.items(), key=lambda kv: kv[1]["priority_score"], reverse=True)
    return json.dumps([{**v, "cluster_id": k} for k, v in ranked])


def _load_incidents() -> dict:
    if not os.path.exists(INCIDENTS_FILE):
        return {}
    with open(INCIDENTS_FILE, "r") as f:
        return json.load(f)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Schemas (sent to the Claude API) and the name -> function map
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "get_satellite_reports",
        "description": "Fetch simulated satellite-imagery damage detections near a center point.",
        "input_schema": {
            "type": "object",
            "properties": {
                "center_lat": {"type": "number"},
                "center_lon": {"type": "number"},
                "count": {"type": "integer", "description": "How many reports to fetch (default 5)."},
            },
            "required": ["center_lat", "center_lon"],
        },
    },
    {
        "name": "get_social_media_reports",
        "description": "Fetch simulated geotagged social media distress posts near a center point.",
        "input_schema": {
            "type": "object",
            "properties": {
                "center_lat": {"type": "number"},
                "center_lon": {"type": "number"},
                "count": {"type": "integer", "description": "How many reports to fetch (default 8)."},
            },
            "required": ["center_lat", "center_lon"],
        },
    },
    {
        "name": "get_sensor_feeds",
        "description": "Fetch simulated seismic/water-level/structural sensor alerts near a center point.",
        "input_schema": {
            "type": "object",
            "properties": {
                "center_lat": {"type": "number"},
                "center_lon": {"type": "number"},
                "count": {"type": "integer", "description": "How many reports to fetch (default 4)."},
            },
            "required": ["center_lat", "center_lon"],
        },
    },
    {
        "name": "cluster_reports",
        "description": (
            "Merge a combined JSON array of reports (from any/all feeds) into incident "
            "clusters based on geographic proximity. Call this after gathering reports "
            "from the feeds you need, having combined them into a single JSON array string."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reports_json": {"type": "string", "description": "JSON array of report objects."},
                "radius_km": {"type": "number", "description": "Merge radius in km (default 0.5)."},
            },
            "required": ["reports_json"],
        },
    },
    {
        "name": "score_incident",
        "description": "Compute a 0-100 priority score for a single incident cluster (from cluster_reports output).",
        "input_schema": {
            "type": "object",
            "properties": {
                "cluster_json": {"type": "string", "description": "One cluster object as a JSON string."}
            },
            "required": ["cluster_json"],
        },
    },
    {
        "name": "save_incident",
        "description": "Log a scored incident so responders can see it, with a short human-readable summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "center_lat": {"type": "number"},
                "center_lon": {"type": "number"},
                "priority_score": {"type": "number"},
                "summary": {"type": "string", "description": "1-2 sentence plain-language summary for a responder."},
            },
            "required": ["cluster_id", "center_lat", "center_lon", "priority_score", "summary"],
        },
    },
    {
        "name": "list_incidents",
        "description": "List all logged incidents, ranked from highest to lowest priority.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

TOOL_REGISTRY = {
    "get_satellite_reports": get_satellite_reports,
    "get_social_media_reports": get_social_media_reports,
    "get_sensor_feeds": get_sensor_feeds,
    "cluster_reports": cluster_reports,
    "score_incident": score_incident,
    "save_incident": save_incident,
    "list_incidents": list_incidents,
}

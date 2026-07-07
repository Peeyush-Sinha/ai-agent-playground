# RescueCoordinator

A decision-support AI agent that aggregates multi-source disaster
signals — satellite imagery, social media, and sensor feeds — clusters
them into incidents and prioritizes where human responders should
look first after an earthquake or flood.

## The problem it addresses

After a disaster, information arrives from many uncoordinated
channels at once: satellite damage-detection passes, thousands of
social media posts, and sensor networks (seismic, water level,
structural). No single human can read all of it fast enough. Two
things responders need help with:

1. **De-duplication** — 50 tweets and 3 satellite detections about the
   same collapsed building are one incident, not 53.
2. **Triage** — with limited rescue teams, which incidents are most
   likely real, most urgent, and most severe?

This agent automates the *aggregation and first-pass triage* so a
human coordinator can spend their attention on the highest-value
decisions, not on manually scanning feeds.

## How it works

1. **Ingest** — `get_satellite_reports`, `get_social_media_reports`,
   and `get_sensor_feeds` each return a list of geotagged reports near
   a location.

2. **Cluster** — `cluster_reports` merges reports within a configurable
   radius (default 500m) into incident clusters using simple
   haversine-distance grouping, recomputing each cluster's centroid as
   reports are added. This is an algorithm — swap in DBSCAN or a proper
   geospatial index for a real system with much higher report volumes.

4. **Score** — `score_incident` turns each cluster into a 0-100
   priority score from four signals:
   - **Volume** — more independent reports about the same spot
   - **Source diversity** — satellite + social + sensor all agreeing
     is much stronger evidence than 5 social posts alone
   - **Confidence** — the average confidence of the underlying reports
   - **Recency** — a reading from 5 minutes ago outweighs one from 3
     hours ago

   These weights (`0.30 / 0.30 / 0.25 / 0.15` in `tools.py`) are a
   reasonable starting point, not a validated model — see below.

5. **Log & brief** — `save_incident` records the incidents worth a
   responder's attention with a short plain-language summary;
   `list_incidents` returns the current board ranked by priority. The
   agent then writes a concise text briefing.

The agent (`agent.py`) is the same tool-use loop pattern as a general
ReAct agent: send the conversation + tool schemas to agent, execute
whichever tools it calls, feed results back, repeat until it produces
a final text briefing (capped at `MAX_STEPS` for safety).

## Running it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python main.py
```

Try:
```
Coordinator request: Earthquake reported near lat 34.05, lon -118.25
(downtown LA). Pull all feeds, cluster them, score the incidents, log
the top ones, and brief me.
```

The agent will call the feed tools, cluster and score the results, log
the highest-priority incidents, and return something like:

```
--- Agent briefing ---
Based on aggregated signals near 34.05, -118.25 (decision support only —
please verify before dispatch):

1. [Priority 87.3] 34.0512, -118.2478 — 3 sources agree (satellite,
   social, sensor): likely building collapse with people trapped.
   Highest confidence and most recent signals in this batch.
2. [Priority 61.0] 34.0489, -118.2531 — Multiple social reports of
   rising floodwater; not yet corroborated by sensor or imagery data.
...
```

## Ideas to extend this

- Add a `get_infrastructure_status` tool (power/water/road closures)
  as a fourth signal source.
- Replace the simple distance-based clustering with a proper
  geospatial clustering library for large-scale deployments.
- Add a `dispatch_recommendation` step that also factors in known
  responder team locations and estimated travel time.
- Persist and diff incident state between runs, so the agent can
  report "this incident's priority increased" rather than only a
  point-in-time snapshot.

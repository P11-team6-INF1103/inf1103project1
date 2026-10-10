import json
import os
from datetime import datetime

_SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "tests", "sample_input.json")

with open(_SAMPLE_PATH, "r", encoding="utf-8") as f:
    _SAMPLES = json.load(f)


# ============================================================
# Owner: whole team  |  Day 1 shared reference (fakes.py)
# Stands in for Daniel's get_time_of_day() + Darrel's classify_lighting_condition(). Don't edit without telling that person.
# ============================================================
def _fallback_time_and_lighting(timestamp: str | None) -> tuple[str, str]:
    try:
        hour = datetime.fromisoformat(timestamp).hour
    except (TypeError, ValueError):
        return "day", "daylight"
    if 7 <= hour < 18:
        return "day", "daylight"
    if 18 <= hour < 20 or 5 <= hour < 7:
        return "dusk_dawn", "low_light"
    return "night", "dark"


# ---- stands in for ai_manager.py (hazard-context + weather enrichment) -----

# ============================================================
# Owner: whole team  |  Day 1 shared reference (fakes.py)
# Stands in for Lennart's enrich_record(). Don't edit without telling that person.
# ============================================================
def fake_enrich_record(record: dict) -> dict:
    for candidate in _SAMPLES["enriched_records"]:
        if candidate["description"] == record.get("description"):
            return dict(candidate)
    # fallback: no weather enrichment, contract-shaped, hazard-context fields
    # still populated (they don't depend on relevance/an API call, see contracts.md)
    time_of_day, lighting_condition = _fallback_time_and_lighting(record.get("timestamp"))
    out = dict(record)
    out.update({
        "weather_available": False,
        "condition": None,
        "temperature_c": None,
        "humidity_pct": None,
        "enrichment_error": None,
        "time_of_day": time_of_day,
        "lighting_condition": lighting_condition,
        "working_at_height": False,
        "height_estimate_m": None,
        "heavy_machinery_present": False,
        "ppe_status": "unspecified",
        "context_flags_error": None,
        "similar_incidents_checked": True,
        "similar_incidents": None,
        "similar_incidents_error": None,
    })
    return out


# ---- stands in for logic_manager.py, judgment half (assess_severity) -------

# ============================================================
# Owner: whole team  |  Day 1 shared reference (fakes.py)
# Stands in for Daniel's assess_severity(). Don't edit without telling that person.
# ============================================================
def fake_assess_severity(record: dict, weather_data: dict | None = None) -> dict:
    for candidate in _SAMPLES["assessed_records"]:
        if candidate["description"] == record.get("description"):
            return dict(candidate)
    out = dict(record)
    out.update({
        "hazard_type": "other",
        "severity_estimate": 1,
        "likelihood_recurrence": "low",
        "assessment_error": None,
    })
    return out


# ---- stands in for data_manager.py -----------------------------------------

# ============================================================
# Owner: whole team  |  Day 1 shared reference (fakes.py)
# Stands in for Lennart's load_records(). Don't edit without telling that person.
# ============================================================
def fake_load_records() -> list:
    return [dict(r) for r in _SAMPLES["assessed_records"]]


# ============================================================
# Owner: whole team  |  Day 1 shared reference (fakes.py)
# Stands in for Ren Xiang's query_by_location(). Don't edit without telling that person.
# ============================================================
def fake_query_by_location(location: str, days: int) -> list:
    if location == "Site A - Block 3":
        return [dict(r) for r in _SAMPLES["history_examples"]["site_a_block_3_recent"]]
    return []


# ============================================================
# Owner: whole team  |  Day 1 shared reference (fakes.py)
# Stands in for Sufi's save_record(). Don't edit without telling that person.
# ============================================================
def fake_save_record(record: dict) -> None:
    # no-op: fakes never touch the filesystem
    return None


# ---- stands in for logic_manager.py, rules half (decide_outcome) -----------

# ============================================================
# Owner: whole team  |  Day 1 shared reference (fakes.py)
# Stands in for Sufi's decide_outcome(). Don't edit without telling that person.
# ============================================================
def fake_decide_outcome(record: dict, history: list) -> str:
    severity = record.get("severity_estimate", 0)
    injury = record.get("injury", False)
    recurrence = record.get("likelihood_recurrence", "unknown")
    if severity >= 4 or (injury and recurrence == "high"):
        return "stop_work_review"
    if len(history) >= 3:
        return "systemic_escalation"
    if record.get("assessment_error"):
        return "pending_review"
    return "log_only"

from datetime import datetime

# classifications
_TYPE_A_HAZARDS = ("fall_from_height", "vehicular", "struck_by_machinery")

_INJURY_POINTS = {"none": 0, "unspecified": 0, "minor": 1, "serious": 2}

_ESCALATED_OUTCOMES = ("stop_work_review", "systemic_escalation")

SEVERITY_LEVELS = {
    1: ("Minimal", (
        "Near miss or no injury, low-risk hazard, controls in place "
        "(e.g. PPE worn). Record it and carry on.")),
    2: ("Minor", (
        "One aggravating factor, e.g. a minor injury or a ground-level "
        "slip/trip. Record it; supervisor fixes the cause on the spot.")),
    3: ("Moderate", (
        "Several aggravating factors, e.g. injury in poor lighting, or "
        "a high-risk hazard type with no injury. Logged, but the site "
        "team should review the cause this week.")),
    4: ("High", (
        "Serious injury, or a MOM Type A hazard (fall from height, vehicle, "
        "machinery) combined with injury, height or missing PPE. Work "
        "stops for a safety review.")),
    5: ("Critical", (
        "Fatal, or several serious factors at once (e.g. fall from "
        "height, no harness, injured, at night). Work stops "
        "immediately; report to management and MOM as required.")),
}

OUTCOME_ACTIONS = {
    "stop_work_review": "Stop the affected work and hold a safety review before it restarts.",
    "systemic_escalation": "Escalate to management: this location keeps having incidents.",
    "log_only": "Record the incident; no escalation needed.",
    "pending_review": "The AI could not assess it; a person must review it manually.",
}

#daniel
def get_time_of_day(timestamp: str | None) -> str:
    try:
        hour = datetime.fromisoformat(timestamp).hour
    except (TypeError, ValueError):
        return "day"
    if 7 <= hour < 18:
        return "day"
    if 18 <= hour < 20 or 5 <= hour < 7:
        return "dusk_dawn"
    return "night"

def assess_severity(record: dict, weather_data: dict | None = None, history: list | None = None) -> dict:
    # Bad inputs are treated as empty rather than crashing the pipeline.
    if not isinstance(record, dict):
        record = {}
    if not isinstance(weather_data, dict):
        weather_data = {}
    if not isinstance(history, list):
        history = []

    result = dict(record)

    if record.get("context_flags_error") or record.get("hazard_category") is None:
        result["hazard_type"] = "unassessed"
        result["severity_estimate"] = 0
        result["likelihood_recurrence"] = "unknown"
        result["severity_reasons"] = []
        result["assessment_error"] = (
            "Cannot judge severity without AI hazard extraction: "
            f"{record.get('context_flags_error') or 'hazard_category missing'}"
        )
        return result
    
    hazard_type = record["hazard_category"]
    # Unknown or oddly-cased values count as "unspecified", so an injured
    # person still gets the "hurt but not described" point below.
    injury_severity = str(record.get("injury_severity") or "unspecified").lower()
    if injury_severity != "fatal" and injury_severity not in _INJURY_POINTS:
        injury_severity = "unspecified"
    # Only a real True counts; the text "false" would otherwise be truthy.
    at_height = record.get("working_at_height") is True
    machinery = record.get("heavy_machinery_present") is True
    ppe_not_worn = record.get("ppe_status") == "not_worn"
    poor_light = record.get("lighting_condition") in ("dark", "low_light")
    similar = record.get("similar_incidents")
    if not isinstance(similar, list):
        similar = []
    similar_escalated = any(
        isinstance(item, dict) and item.get("outcome") in _ESCALATED_OUTCOMES for item in similar
    )

    severity = 1
    reasons = []
    if injury_severity == "fatal":
        severity = 5
        reasons.append("Someone died (set to 5)")
    else:
        injury_points = _INJURY_POINTS.get(injury_severity, 0)
        if injury_points:
            severity += injury_points
            reasons.append(f"{injury_severity.capitalize()} injury (+{injury_points})")
        # Reporter said someone was hurt but the description didn't say how badly.
        if record.get("injury") and injury_severity in ("none", "unspecified"):
            severity += 1
            reasons.append("Someone was hurt, but how badly wasn't described (+1)")
    
    if hazard_type in _TYPE_A_HAZARDS:
        severity += 1
        reasons.append("One of MOM's highest-risk hazard types (+1)")
    if at_height:
        severity += 1
        reasons.append("Working at height (+1)")
    if machinery and ppe_not_worn:
        severity += 1
        reasons.append("Heavy machinery around, without safety gear (+1)")
    if ppe_not_worn:
        severity += 1
        reasons.append("Safety gear (PPE) not worn (+1)")
    elif record.get("ppe_status") == "worn":
        severity -= 1
        reasons.append("Safety gear (PPE) was worn (-1)")
    if poor_light:
        severity += 1
        reasons.append("Poor lighting or dark (+1)")
    if weather_data.get("condition") == "rain" and (at_height or machinery):
        severity += 1
        reasons.append("Raining during work at height or with machinery (+1)")
    if similar_escalated:
        severity += 1
        reasons.append("A similar past incident on our sites was escalated (+1)")
    severity = max(1, min(severity, 5))
    
        # --- likelihood_recurrence: simple tiered logic ---
    recurrence = "low"
    if poor_light or len(history) >= 1:
        recurrence = "medium"
    if severity >= 4 or len(history) >= 3 or similar_escalated:
        recurrence = "high"
    
    result["hazard_type"] = hazard_type
    result["severity_estimate"] = severity
    result["likelihood_recurrence"] = recurrence
    result["severity_reasons"] = reasons
    result["assessment_error"] = None
    return result

def is_high_severity(record: dict) -> bool:
    severity = record.get("severity_estimate", 0)
    injury = record.get("injury", False)
    recurrence = record.get("likelihood_recurrence", "unknown")
    return severity >= 4 or (injury and recurrence == "high")

def is_systemic_risk(record: dict, history: list) -> bool:
    return len(history) >= 3

def decide_outcome(record: dict, history: list) -> str:
    if record.get("assessment_error"):
        return "pending_review"
    if is_high_severity(record):
        return "stop_work_review"
    if is_systemic_risk(record, history):
        return "systemic_escalation"
    return "log_only"
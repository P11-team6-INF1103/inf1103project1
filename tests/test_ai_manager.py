import json
from unittest import mock

import ai_manager

_GOOD_FLAGS = {
    "hazard_category": "fall_from_height", "injury_severity": "serious",
    "working_at_height": True, "height_estimate_m": 10,
    "heavy_machinery_present": False, "ppe_status": "not_worn",
}


def _incident(description="Worker fell from scaffolding", weather_relevant=False):
    return {"description": description, "location": "Site A", "reporter_role": "site_supervisor",
            "injury": True, "timestamp": "2026-09-27T20:44:10",
            "weather_relevant": weather_relevant, "time_of_day": "night",
            "monsoon_season": "southwest_monsoon"}


def _flags_for(reply):
    ai_manager.load_response_cache({})
    return mock.patch.object(ai_manager, "_call_gemini", return_value=json.dumps(reply))


def test_flags_ai_can_reject_text_that_is_not_a_safety_incident():
    reply = dict(_GOOD_FLAGS, hazard_category="other", is_valid_incident=False,
                 invalid_reason="It is random text, not an incident.")
    with mock.patch.object(ai_manager, "_get_gemini_client", return_value=object()), _flags_for(reply):
        result = ai_manager.extract_hazard_context_flags("asdf qwerty banana")
    assert result["is_valid_incident"] is False
    assert "random text" in result["invalid_reason"]


def test_flags_treat_a_reply_without_the_new_field_or_an_ai_outage_as_valid():
    with mock.patch.object(ai_manager, "_get_gemini_client", return_value=object()), _flags_for(_GOOD_FLAGS):
        result = ai_manager.extract_hazard_context_flags("Worker fell")
    assert result["is_valid_incident"] is True and result["invalid_reason"] is None
    with mock.patch.object(ai_manager, "_get_gemini_client", return_value=None):
        assert ai_manager.extract_hazard_context_flags("Worker fell")["is_valid_incident"] is True


def test_enrich_record_stops_early_when_incident_is_invalid():
    flags = {"hazard_category": "other", "injury_severity": "none", "working_at_height": False,
             "height_estimate_m": None, "heavy_machinery_present": False, "ppe_status": "unspecified",
             "is_valid_incident": False, "invalid_reason": "not an incident", "context_flags_error": None}
    boom = mock.Mock(side_effect=AssertionError("should not be called for an invalid incident"))
    with mock.patch.object(ai_manager, "extract_hazard_context_flags", return_value=flags), \
            mock.patch.object(ai_manager, "call_weather_api", boom), \
            mock.patch.object(ai_manager, "find_similar_incidents", boom), \
            mock.patch.object(ai_manager, "search_web_for_similar_incidents", boom), \
            mock.patch.object(ai_manager, "generate_incident_review", boom):
        result = ai_manager.enrich_record(_incident("asdf qwerty banana", weather_relevant=True), [])
    assert result["is_valid_incident"] is False and result["invalid_reason"] == "not an incident"


def test_gemini_json_asks_once_more_when_the_reply_is_malformed():
    ai_manager.load_response_cache({})
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
    replies = ["not json at all", json.dumps({"ok": True})]
    with mock.patch.object(ai_manager, "_call_gemini", side_effect=replies) as call:
        assert ai_manager._gemini_json(object(), "prompt", schema) == {"ok": True}
    assert call.call_count == 2


def test_gemini_json_gives_up_after_one_retry():
    ai_manager.load_response_cache({})
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
    with mock.patch.object(ai_manager, "_call_gemini", return_value=json.dumps({"ok": "yes"})) as call:
        try:
            ai_manager._gemini_json(object(), "prompt", schema)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")
    assert call.call_count == 2

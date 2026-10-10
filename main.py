import argparse
import logging

import ai_manager
import data_manager
import io_manager
import logic_manager

decide_outcome = logic_manager.decide_outcome
save_record = data_manager.save_record
generate_incident_review = ai_manager.generate_incident_review
SEVERITY_LEVELS = logic_manager.SEVERITY_LEVELS
OUTCOME_ACTIONS = logic_manager.OUTCOME_ACTIONS

# Not written yet (Darrel). Until they land, each step passes the record through unchanged.
derive_context = getattr(logic_manager, "derive_context", dict)
apply_lighting = getattr(logic_manager, "apply_lighting", dict)


# Lennart
def start_up() -> list:
    log_path = data_manager.get_log_path()
    if log_path:
        logging.basicConfig(
            filename=log_path, level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    problem = data_manager.check_records_file()
    if problem:
        io_manager.display_message(f"Warning: {problem}. Starting with no saved incidents.")
    records = data_manager.load_records()
    ai_manager.load_response_cache(data_manager.load_ai_cache())
    io_manager.display_message(f"Loaded {len(records)} saved incident(s).")
    return records


# Lennart
# Returns None, and saves nothing, when the AI says the text is not a real safety incident.
# interactive=False (batch, scripts, Docker) never waits on input() after a failed save.
def process_incident(incident: dict, records: list, interactive: bool = True) -> dict | None:
    with_context = derive_context(incident)
    with io_manager.show_loading("AI is analysing the incident"):
        enriched = ai_manager.enrich_record(with_context, records)
        is_valid = enriched.get("is_valid_incident", True)
        if is_valid:
            enriched = apply_lighting(enriched)
            enriched.update(generate_incident_review(enriched))
    if not is_valid:
        io_manager.display_message(
            "Incident rejected: " + str(enriched.get("invalid_reason") or "not a workplace safety incident")
        )
        return None

    history = data_manager.query_by_location(
        enriched.get("location", ""), 30, as_of=enriched.get("timestamp"), records=records
    )
    weather_data = {
        "weather_available": enriched.get("weather_available"),
        "condition": enriched.get("condition"),
        "temperature_c": enriched.get("temperature_c"),
        "humidity_pct": enriched.get("humidity_pct"),
    }
    assessed = logic_manager.assess_severity(enriched, weather_data, history)

    final_record = dict(assessed)
    final_record["outcome"] = decide_outcome(assessed, history)

    saved = save_record(final_record)
    while saved is False and interactive and io_manager.ask_retry_save():
        saved = save_record(final_record)
    if saved is False:
        io_manager.display_message("Warning: could not save this incident to disk.")
    records.append(final_record)
    if not data_manager.save_ai_cache(ai_manager.export_response_cache()):
        io_manager.display_message("Warning: could not save the AI reply cache.")
    return final_record


# Lennart
# If the AI rejects the incident, asks whether to enter it again instead of showing a report.
def log_incident_flow(records: list) -> dict | None:
    while True:
        incident = io_manager.get_incident_input()
        final_record = process_incident(incident, records)
        if final_record is not None:
            break
        if not io_manager.ask_try_again():
            return None
    io_manager.display_outcome(final_record, SEVERITY_LEVELS, OUTCOME_ACTIONS)
    return final_record


# Lennart
def run_batch(path: str) -> int:
    incidents, problems = io_manager.read_incident_file(path)
    for problem in problems:
        io_manager.display_message(f"Skipped: {problem}")
    if not incidents:
        io_manager.display_message("No valid incidents to process.")
        return 1

    records = start_up()
    for incident in incidents:
        final_record = process_incident(incident, records, interactive=False)
        if final_record is None:
            continue
        io_manager.display_outcome(final_record, SEVERITY_LEVELS, OUTCOME_ACTIONS)
    io_manager.display_summary(records, SEVERITY_LEVELS, OUTCOME_ACTIONS, interactive=False)
    return 0


# Lennart
def main() -> None:
    records = start_up()
    while True:
        choice = io_manager.get_menu_choice()
        if choice == "1":
            log_incident_flow(records)
        elif choice == "2":
            records = data_manager.load_records()
            io_manager.display_summary(records, SEVERITY_LEVELS, OUTCOME_ACTIONS)
        elif choice == "3":
            query = io_manager.get_location_query()
            if query is None:
                continue
            location, days = query
            io_manager.display_query_results(data_manager.query_by_location(location, days))
        elif choice == "4":
            io_manager.display_message("Goodbye.")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workplace Safety Incident Triage System")
    parser.add_argument("--batch", metavar="FILE", help="process the incidents in FILE (JSON) and exit")
    arguments = parser.parse_args()
    if arguments.batch:
        raise SystemExit(run_batch(arguments.batch))
    main()

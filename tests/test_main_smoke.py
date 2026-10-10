import json

import fakes
import main


def _incident(**overrides):
    incident = {
        "description": "Worker slipped on a wet floor near the loading bay.",
        "location": "Site A - Block 3",
        "reporter_role": "site_supervisor",
        "injury": False,
        "timestamp": "2026-10-05T09:00:00",
    }
    incident.update(overrides)
    return incident


def _use_fakes(monkeypatch):
    monkeypatch.setattr(main.ai_manager, "enrich_record", lambda record, history=None: fakes.fake_enrich_record(record))
    monkeypatch.setattr(main.logic_manager, "assess_severity", lambda record, weather=None, history=None: fakes.fake_assess_severity(record))
    monkeypatch.setattr(main, "decide_outcome", fakes.fake_decide_outcome)


def test_start_up_returns_a_list_of_records():
    assert main.start_up() == []


def test_process_incident_saves_and_returns_a_record_with_an_outcome(monkeypatch):
    _use_fakes(monkeypatch)
    records = []
    final_record = main.process_incident(_incident(), records)
    assert final_record["outcome"] in ("log_only", "pending_review", "systemic_escalation", "stop_work_review")
    assert records == [final_record]
    assert main.data_manager.load_records() == [final_record]


def _ai_rejects(monkeypatch, reason="It is random text."):
    monkeypatch.setattr(
        main.ai_manager, "enrich_record",
        lambda record, history=None: dict(record, is_valid_incident=False, invalid_reason=reason),
    )


def test_process_incident_returns_none_and_saves_nothing_when_the_ai_rejects_it(monkeypatch, capsys):
    _use_fakes(monkeypatch)
    _ai_rejects(monkeypatch)
    records = []
    assert main.process_incident(_incident(description="asdf qwerty banana"), records) is None
    assert "Incident rejected: It is random text." in capsys.readouterr().out
    assert records == [] and main.data_manager.load_records() == []


def test_failed_save_offers_retry_and_keeps_record_in_memory(monkeypatch, capsys):
    _use_fakes(monkeypatch)
    attempts = []
    monkeypatch.setattr(main, "save_record", lambda record: attempts.append(record) or len(attempts) >= 3)
    answers = iter(["y", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    records = []
    assert main.process_incident(_incident(), records) is not None
    out = capsys.readouterr().out
    assert len(attempts) == 3 and len(records) == 1
    assert out.count("INCIDENT NOT SAVED") == 2 and "Warning: could not save" not in out

    attempts.clear()
    records = []
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert main.process_incident(_incident(), records) is not None
    assert len(attempts) == 1 and len(records) == 1
    assert "Warning: could not save this incident" in capsys.readouterr().out


def test_failed_save_never_prompts_when_not_interactive(monkeypatch, capsys):
    _use_fakes(monkeypatch)
    monkeypatch.setattr(main, "save_record", lambda record: False)

    def no_typing(prompt=""):
        raise AssertionError("input() called")

    monkeypatch.setattr("builtins.input", no_typing)
    assert main.process_incident(_incident(), [], interactive=False) is not None
    assert "Warning: could not save this incident" in capsys.readouterr().out


def test_log_incident_flow_runs_one_incident(monkeypatch, capsys):
    _use_fakes(monkeypatch)
    monkeypatch.setattr(main.io_manager, "get_incident_input", lambda: _incident())
    final_record = main.log_incident_flow([])
    assert "outcome" in final_record
    assert capsys.readouterr().out != ""


def test_log_incident_flow_asks_again_after_a_rejection_and_can_be_declined(monkeypatch, capsys):
    _use_fakes(monkeypatch)
    _ai_rejects(monkeypatch)
    monkeypatch.setattr(main.io_manager, "get_incident_input", lambda: _incident())
    answers = iter(["y", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert main.log_incident_flow([]) is None
    out = capsys.readouterr().out
    assert out.count("Incident rejected") == 2 and main.data_manager.load_records() == []


def test_run_batch_processes_every_incident_in_the_file(monkeypatch, tmp_path):
    _use_fakes(monkeypatch)
    path = tmp_path / "batch.json"
    path.write_text(json.dumps([_incident(), _incident(location="Site B")]))
    assert main.run_batch(str(path)) == 0
    assert len(main.data_manager.load_records()) == 2


def test_run_batch_skips_an_incident_the_ai_rejects(monkeypatch, tmp_path, capsys):
    _use_fakes(monkeypatch)
    _ai_rejects(monkeypatch)
    path = tmp_path / "batch.json"
    path.write_text(json.dumps([_incident(description="asdf qwerty banana")]))
    main.run_batch(str(path))
    assert "Incident rejected" in capsys.readouterr().out
    assert main.data_manager.load_records() == []


def test_run_batch_never_prompts_after_a_failed_save(monkeypatch, tmp_path, capsys):
    _use_fakes(monkeypatch)
    monkeypatch.setattr(main, "save_record", lambda record: False)

    def no_typing(prompt=""):
        raise AssertionError("input() called")

    monkeypatch.setattr("builtins.input", no_typing)
    path = tmp_path / "batch.json"
    path.write_text(json.dumps([_incident()]))
    assert main.run_batch(str(path)) == 0
    assert "Warning: could not save this incident" in capsys.readouterr().out


def test_run_batch_returns_1_for_an_unreadable_file(tmp_path):
    assert main.run_batch(str(tmp_path / "missing.json")) == 1


def test_main_menu_logs_an_incident_then_exits(monkeypatch):
    _use_fakes(monkeypatch)
    choices = iter(["1", "2", "4"])
    monkeypatch.setattr(main.io_manager, "get_menu_choice", lambda: next(choices))
    monkeypatch.setattr(main.io_manager, "get_incident_input", lambda: _incident())
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    main.main()
    assert len(main.data_manager.load_records()) == 1


def test_main_location_query_can_go_back_to_the_menu(monkeypatch):
    _use_fakes(monkeypatch)
    choices = iter(["3", "4"])
    monkeypatch.setattr(main.io_manager, "get_menu_choice", lambda: next(choices))
    monkeypatch.setattr(main.io_manager, "get_location_query", lambda: None)
    searched = []
    monkeypatch.setattr(main.data_manager, "query_by_location", lambda *a: searched.append(a) or [])
    main.main()
    assert searched == []

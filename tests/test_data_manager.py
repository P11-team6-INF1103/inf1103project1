import json
import os
import tempfile
from unittest import mock

import data_manager as dm
from tests._suite import suite_from, temp_data_dir


def _write(folder, name, text):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        f.write(text)


def _files(folder):
    return sorted(os.listdir(folder))


def test_missing_file_means_empty_and_no_problem():
    with temp_data_dir():
        assert dm.load_records() == [] and dm.check_records_file() is None


def test_corrupt_file_is_set_aside_not_overwritten():
    with temp_data_dir() as folder:
        _write(folder, "incidents.json", "{not json")
        assert "corrupt" in dm.check_records_file()
        assert dm.load_records() == []
        assert dm.save_record({"location": "A"}) is True
        names = _files(folder)
        backups = [n for n in names if ".corrupt-" in n]
        assert len(backups) == 1, names
        with open(os.path.join(folder, backups[0]), encoding="utf-8") as f:
            assert f.read() == "{not json"
        assert dm.load_records() == [{"location": "A"}]


def test_load_corrupt_without_prior_check_also_keeps_backup():
    with temp_data_dir() as folder:
        _write(folder, "incidents.json", "\x00\x01 garbage")
        assert dm.load_records() == []
        assert any(".corrupt-" in n for n in _files(folder))


def test_wrong_shape_file_is_set_aside():
    with temp_data_dir() as folder:
        _write(folder, "incidents.json", '{"a": 1}')
        assert dm.load_records() == []
        assert any(".corrupt-" in n for n in _files(folder))


def test_non_object_entries_are_dropped_and_queries_do_not_crash():
    with temp_data_dir() as folder:
        _write(folder, "incidents.json", json.dumps([1, "x", None, {"location": "A", "timestamp": "2026-09-27T10:00:00", "outcome": "log_only"}]))
        assert len(dm.load_records()) == 1
        assert len(dm.query_by_location("A", 30, as_of="2026-09-28T00:00:00")) == 1
        assert dm.query_by_location("A", 30, records=[1, None, "x"]) == []


def test_unreadable_file_is_not_overwritten_by_save():
    with temp_data_dir() as folder:
        _write(folder, "incidents.json", json.dumps([{"location": "old"}]))
        real_open = open

        def locked(path, mode="r", *args, **kwargs):
            if "r" in mode and str(path).endswith("incidents.json"):
                raise PermissionError("locked by another program")
            return real_open(path, mode, *args, **kwargs)

        with mock.patch("builtins.open", locked):
            assert dm.save_record({"location": "new"}) is False
        assert dm.load_records() == [{"location": "old"}]


def test_unsaveable_record_returns_false_and_keeps_file():
    circular = {}
    circular["self"] = circular
    with temp_data_dir() as folder:
        assert dm.save_record({"location": "old"}) is True
        for bad in ({1: "a", "b": 2}, {(1, 2): "x"}, circular):
            assert dm.save_record(bad) is False
        assert dm.load_records() == [{"location": "old"}]
        assert _files(folder) == ["incidents.json"]


def test_unwritable_location_returns_false_instead_of_crashing():
    with tempfile.NamedTemporaryFile() as blocker, \
            mock.patch.dict(os.environ, {"INCIDENT_DATA_DIR": os.path.join(blocker.name, "sub")}):
        assert dm.save_record({"a": 1}) is False
        assert dm.save_ai_cache({"k": "v"}) is False
        assert dm.load_records() == []


def test_roundtrip_filter_and_order():
    with temp_data_dir():
        for stamp, place in (("2026-09-01T10:00:00", "A"), ("2026-09-20T10:00:00", "A"),
                             ("2026-09-25T10:00:00", "B"), ("2026-09-26T10:00:00", "A")):
            assert dm.save_record({"location": place, "timestamp": stamp, "outcome": "log_only"})
        assert len(dm.load_records()) == 4
        hits = dm.query_by_location("A", 30, as_of="2026-09-27T00:00:00")
        assert [h["timestamp"] for h in hits] == ["2026-09-26T10:00:00", "2026-09-20T10:00:00", "2026-09-01T10:00:00"]
        assert len(dm.query_by_location("A", 10, as_of="2026-09-27T00:00:00")) == 2
        assert set(hits[0]) == {"location", "timestamp", "outcome"}


def test_ai_cache_roundtrip_and_corruption():
    with temp_data_dir() as folder:
        assert dm.load_ai_cache() == {}
        assert dm.save_ai_cache({"k": "v"}) is True and dm.load_ai_cache() == {"k": "v"}
        _write(folder, "ai_cache.json", "[1]")
        assert dm.load_ai_cache() == {}


def load_tests(loader, tests, pattern):
    return suite_from(globals())
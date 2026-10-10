import json
import os
from datetime import datetime, timedelta

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_DATA_PATH = os.path.join(_DATA_DIR, "incidents.json")


# Lennart
def _data_dir():
    return os.environ.get("INCIDENT_DATA_DIR") or _DATA_DIR


# Lennart
def _incidents_path():
    return os.path.join(_data_dir(), "incidents.json")


# Lennart
def _cache_path():
    return os.path.join(_data_dir(), "ai_cache.json")


def _set_aside_corrupt(path):
    backup = f"{path}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    try:
        os.replace(path, backup)
        return backup
    except OSError:
        return None


def _read_json(path, expected_type):
    if not os.path.exists(path):
        return expected_type(), None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        backup = _set_aside_corrupt(path)
        return expected_type(), f"{os.path.basename(path)} was corrupt (kept as {os.path.basename(backup) if backup else 'unmovable file'})"
    except OSError as error:
        return expected_type(), f"could not read {os.path.basename(path)}: {error}"
    if not isinstance(data, expected_type):
        backup = _set_aside_corrupt(path)
        return expected_type(), f"{os.path.basename(path)} had the wrong format (kept as {os.path.basename(backup) if backup else 'unmovable file'})"
    return data, None

def _write_json(path, data):
    temp_path = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, sort_keys=True)
        os.replace(temp_path, path)
        return True
    except (OSError, TypeError, ValueError):
        try:
            os.remove(temp_path)
        except OSError:
            pass
        return False

# Lennart
def get_log_path():
    try:
        os.makedirs(_data_dir(), exist_ok=True)
    except OSError:
        return None
    return os.path.join(_data_dir(), "app.log")


# Lennart
def load_records():
    data, _problem = _read_json(_incidents_path(), list)
    return [item for item in data if isinstance(item, dict)]


# Lennart
def check_records_file():
    _data, problem = _read_json(_incidents_path(), list)
    return problem


# Lennart
def load_ai_cache():
    data, _problem = _read_json(_cache_path(), dict)
    return data

def save_ai_cache(cache):
    return _write_json(_cache_path(), cache)

#Daniel
def save_record(record):
    path = _incidents_path()
    records, problem = _read_json(path, list)
    if problem and os.path.exists(path):
        return False
    records = [item for item in records if isinstance(item, dict)]
    records.append(record)
    return _write_json(path, records)

#Ren Xiang
def query_by_location(location, days, as_of=None, records=None):
    try:
        reference = datetime.fromisoformat(as_of) if as_of else datetime.now()
    except (TypeError, ValueError):
        reference = datetime.now()
    cutoff = reference - timedelta(days=days)
    matches = []
    for record in (load_records() if records is None else records):
        if not isinstance(record, dict) or record.get("location") != location:
            continue
        try:
            record_time = datetime.fromisoformat(record.get("timestamp", ""))
        except (TypeError, ValueError):
            continue
        if record_time >= cutoff:
            matches.append({
                "location": record.get("location"),
                "timestamp": record.get("timestamp"),
                "outcome": record.get("outcome"),
            })
    matches.sort(key=lambda r: r["timestamp"], reverse=True)
    return matches

def list_locations(records=None):
    counts = {}
    for record in (load_records() if records is None else records):
        if not isinstance(record, dict):
            continue
        location = record.get("location")
        if isinstance(location, str) and location.strip():
            counts[location] = counts.get(location, 0) + 1
    return sorted(counts.items(), key=lambda item: (item[0].lower(), item[0]))
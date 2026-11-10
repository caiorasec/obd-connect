"""Durable receipt ledger and history. Called exclusively in an executor."""

import hashlib
import json
import math
from pathlib import Path
import sqlite3
from uuid import UUID

from .const import MAX_RECORDS, METRICS


def uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("invalid_uuid")
    return value


def timestamp(value, now):
    if type(value) is not int or not 946684800000 <= value <= now + 300000:
        raise ValueError("invalid_timestamp")
    return value


def validate(record, now):
    if not isinstance(record, dict):
        raise ValueError("invalid_record")
    kind = record.get("type")
    uid = uuid(record.get("id"))
    if record.get("source") != "REAL":
        raise ValueError("real_only")
    if kind == "telemetry":
        if set(record) != {"key", "type", "id", "source", "pid", "value", "unit", "capturedAtMs", "recordedAtMs", "sessionId", "tripId"}:
            raise ValueError("invalid_fields")
        metric = METRICS.get(record["pid"])
        value = record["value"]
        if not metric or record["unit"] != metric[1] or type(value) not in (int, float) or not math.isfinite(value) or not metric[2] <= value <= metric[3]:
            raise ValueError("invalid_metric")
        timestamp(record["capturedAtMs"], now)
        timestamp(record["recordedAtMs"], now)
        uuid(record["sessionId"])
        if record["tripId"] is not None:
            uuid(record["tripId"])
        expected = f"telemetry:{uid}"
    elif kind == "trip":
        if set(record) != {"key", "type", "id", "source", "revision", "startedAtMs", "lastObservedAtMs", "endedAtMs", "status", "telemetryCount"}:
            raise ValueError("invalid_fields")
        rev = record["revision"]
        if not isinstance(rev, str) or len(rev) != 64 or any(c not in "0123456789abcdef" for c in rev):
            raise ValueError("invalid_revision")
        start = timestamp(record["startedAtMs"], now)
        last = timestamp(record["lastObservedAtMs"], now)
        end = record["endedAtMs"]
        if last < start or (end is not None and timestamp(end, now) < last):
            raise ValueError("invalid_interval")
        if record["status"] not in ("ACTIVE", "ENDED", "INTERRUPTED") or (record["status"] == "ENDED" and end is None):
            raise ValueError("invalid_status")
        if type(record["telemetryCount"]) is not int or record["telemetryCount"] < 0:
            raise ValueError("invalid_count")
        expected = f"trip:{uid}:{rev}"
    else:
        raise ValueError("unsupported_type")
    if record.get("key") != expected:
        raise ValueError("invalid_key")


class Ledger:
    """No acknowledgements before the SQLite commit; receipts survive restart."""

    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, kind TEXT NOT NULL, record_id TEXT NOT NULL, captured INTEGER NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL, received INTEGER NOT NULL)")
        db.execute("CREATE INDEX IF NOT EXISTS metric_latest ON records(kind,json_extract(payload,'$.pid'),captured DESC)")
        db.commit()
        return db

    def ingest(self, payload, vehicle_id, now):
        if not isinstance(payload, dict) or set(payload) != {"schemaVersion", "batchId", "vehicleId", "records"} or type(payload["schemaVersion"]) is not int or payload["schemaVersion"] != 1:
            raise ValueError("invalid_envelope")
        uuid(payload["batchId"])
        if payload["vehicleId"] != vehicle_id:
            raise ValueError("wrong_vehicle")
        records = payload["records"]
        if not isinstance(records, list) or not 1 <= len(records) <= MAX_RECORDS:
            raise ValueError("invalid_batch_size")
        accepted, rejected, seen = [], [], set()
        db = self.connect()
        try:
            with db:
                for record in records:
                    key = record.get("key") if isinstance(record, dict) else None
                    try:
                        validate(record, now)
                        if key in seen:
                            raise ValueError("duplicate_key_in_batch")
                        seen.add(key)
                        body = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
                        digest = hashlib.sha256(body.encode()).hexdigest()
                        old = db.execute("SELECT digest FROM records WHERE key=?", (key,)).fetchone()
                        if old and old[0] != digest:
                            raise ValueError("id_content_conflict")
                        captured = record.get("capturedAtMs", record.get("lastObservedAtMs"))
                        db.execute("INSERT OR IGNORE INTO records VALUES (?,?,?,?,?,?,?)", (key, record["type"], record["id"], captured, body, digest, now))
                        accepted.append(key)
                    except (ValueError, TypeError, KeyError, AttributeError):
                        rejected.append({"key": key if isinstance(key, str) and len(key) <= 150 else None, "reason": "invalid_or_conflicting_record"})
            # Exiting the transaction committed all accepted records.
            return {"schemaVersion": 1, "batchId": payload["batchId"], "accepted": accepted, "rejected": rejected, "serverReceivedAtMs": now}
        finally:
            db.close()

    def snapshot(self):
        db = self.connect()
        try:
            latest = {}
            for pid in METRICS:
                row = db.execute("SELECT payload FROM records WHERE kind='telemetry' AND json_extract(payload,'$.pid')=? ORDER BY captured DESC,key DESC LIMIT 1", (pid,)).fetchone()
                if row:
                    latest[pid] = json.loads(row[0])
            return {"latest": latest, "received": db.execute("SELECT MAX(received) FROM records").fetchone()[0], "records": db.execute("SELECT COUNT(*) FROM records").fetchone()[0]}
        finally:
            db.close()

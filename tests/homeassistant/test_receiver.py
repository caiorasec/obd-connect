"""Real Home Assistant runtime and durable protocol regression tests."""

import asyncio
import copy
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import socket
import tempfile
import time
import unittest
from uuid import uuid4

from aiohttp import ClientSession
from homeassistant import loader
from homeassistant.helpers import frame
from homeassistant.core import HomeAssistant
from homeassistant.bootstrap import async_from_config_dict
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er

from custom_components.obd_connect.storage import Ledger
from custom_components.obd_connect import BatchView

VEHICLE = str(uuid4())
NOW = int(time.time() * 1000)


def sample(at=NOW, value=750):
    uid = str(uuid4())
    return {"key": f"telemetry:{uid}", "id": uid, "type": "telemetry", "source": "REAL", "pid": "010C", "unit": "rpm", "value": value, "capturedAtMs": at, "recordedAtMs": at, "sessionId": str(uuid4()), "tripId": None}


def batch(*records):
    return {"schemaVersion": 1, "batchId": str(uuid4()), "vehicleId": VEHICLE, "records": list(records)}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "history.sqlite3"
        self.ledger = Ledger(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_restart_and_retry_after_lost_ack_deduplicate(self):
        row = sample()
        first = self.ledger.ingest(batch(row), VEHICLE, NOW)
        restarted = Ledger(self.path)
        second = restarted.ingest(batch(row), VEHICLE, NOW + 1000)
        self.assertEqual(first["accepted"], second["accepted"])
        self.assertEqual(1, restarted.snapshot()["records"])

    def test_partial_ack_and_conflicting_id(self):
        row = sample()
        self.ledger.ingest(batch(row), VEHICLE, NOW)
        conflict = {**row, "value": 900}
        new = sample()
        response = self.ledger.ingest(batch(conflict, new), VEHICLE, NOW)
        self.assertEqual([new["key"]], response["accepted"])
        self.assertEqual(row["key"], response["rejected"][0]["key"])
        self.assertEqual(2, self.ledger.snapshot()["records"])

    def test_old_backfill_does_not_regress_latest(self):
        new, old = sample(NOW, 900), sample(NOW - 86400000, 700)
        self.ledger.ingest(batch(new), VEHICLE, NOW)
        self.ledger.ingest(batch(old), VEHICLE, NOW)
        self.assertEqual(900, self.ledger.snapshot()["latest"]["010C"]["value"])

    def test_simulation_gps_future_and_invalid_values_rejected(self):
        bad = [dict(sample(), source="SYNTHETIC"), dict(sample(), type="gps"), sample(NOW + 600000), sample(value=float("nan")), dict(sample(), unit="V"), dict(sample(), latitude=0)]
        response = self.ledger.ingest(batch(*bad), VEHICLE, NOW)
        self.assertEqual([], response["accepted"])
        self.assertEqual(6, len(response["rejected"]))
        self.assertEqual(0, self.ledger.snapshot()["records"])

    def test_wrong_vehicle_and_oversized_envelope(self):
        for payload in [batch(*[sample() for _ in range(257)]), dict(batch(sample()), vehicleId=str(uuid4()))]:
            with self.assertRaises(ValueError):
                self.ledger.ingest(payload, VEHICLE, NOW)

    def test_trip_revisions_are_durable_and_conflicts_are_not_overwritten(self):
        uid = str(uuid4())
        row = {"key": f"trip:{uid}:" + "a" * 64, "id": uid, "type": "trip", "source": "REAL", "revision": "a" * 64, "startedAtMs": NOW - 10000, "lastObservedAtMs": NOW, "endedAtMs": None, "status": "ACTIVE", "telemetryCount": 2}
        ended = {**row, "key": f"trip:{uid}:" + "b" * 64, "revision": "b" * 64, "endedAtMs": NOW, "status": "ENDED"}
        result = self.ledger.ingest(batch(row, ended), VEHICLE, NOW)
        self.assertEqual(2, len(result["accepted"]))
        self.assertEqual(2, Ledger(self.path).snapshot()["records"])


class HomeAssistantTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        shutil.copytree("custom_components", Path(self.temp.name) / "custom_components", ignore=shutil.ignore_patterns("__pycache__"))
        self.hass = HomeAssistant(self.temp.name)
        loader.async_setup(self.hass)
        frame.async_setup(self.hass)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        configured = await async_from_config_dict({"http": {"server_port": port}, "api": {}}, hass=self.hass)
        self.assertIsNotNone(configured)
        await self.hass.async_start()
        self.entry = ConfigEntry(domain="obd_connect", title="Test HR-V", data={"vehicle_id": VEHICLE, "receiver_key": "a" * 43, "name": "Test HR-V"}, options={}, source="user", unique_id=VEHICLE, version=1, minor_version=1, discovery_keys={}, subentries_data=[])
        await self.hass.config_entries.async_add(self.entry)
        await self.hass.async_block_till_done()
        self.assertEqual("loaded", self.entry.state.value, str(self.hass.config.components))
        self.client = ClientSession(base_url=f"http://127.0.0.1:{port}")

    async def asyncTearDown(self):
        if hasattr(self, "client"):
            await self.client.close()
        await self.hass.async_stop()
        self.temp.cleanup()

    async def send(self, payload, key="a" * 43):
        return await self.client.post(f"/api/obd_connect/{VEHICLE}/batches", json=payload, headers={"Authorization": f"Bearer {key}"})

    async def test_http_auth_ingestion_entities_and_expiry(self):
        row = sample(int(time.time() * 1000))
        unauthorized = await self.send(batch(row), "wrong")
        self.assertEqual(401, unauthorized.status)
        response = await self.send(batch(row))
        self.assertEqual(200, response.status)
        self.assertEqual([row["key"]], (await response.json())["accepted"])
        await self.hass.async_block_till_done()
        ids = {e.entity_id for e in er.async_get(self.hass).entities.values() if e.config_entry_id == self.entry.entry_id}
        sensors = [s for s in self.hass.states.async_all("sensor") if s.entity_id in ids]
        rpm = next(s for s in sensors if s.attributes.get("unit_of_measurement") == "rpm")
        self.assertEqual("750", rpm.state)
        old = sample(int(time.time() * 1000) - 86400000, 900)
        await self.send(batch(old))
        await self.hass.async_block_till_done()
        self.assertEqual("750", self.hass.states.get(rpm.entity_id).state)
        self.assertEqual(9, len(sensors))

    async def test_http_payload_limit_and_invalid_json(self):
        response = await self.client.post(f"/api/obd_connect/{VEHICLE}/batches", data=b"x" * 262145, headers={"Authorization": "Bearer " + "a" * 43})
        self.assertEqual(413, response.status)
        response = await self.client.post(f"/api/obd_connect/{VEHICLE}/batches", data=b"not-json", headers={"Authorization": "Bearer " + "a" * 43})
        self.assertEqual(400, response.status)

    async def test_stale_history_creates_no_current_value_and_unload_stops_receiver(self):
        await self.send(batch(sample(int(time.time() * 1000) - 86400000)))
        await self.hass.async_block_till_done()
        rpm = next(s for s in self.hass.states.async_all("sensor") if s.attributes.get("unit_of_measurement") == "rpm")
        self.assertEqual("unavailable", rpm.state)
        await self.hass.config_entries.async_unload(self.entry.entry_id)
        response = await self.send(batch(sample()))
        self.assertEqual(401, response.status)

    async def test_configuration_flow_rejects_invalid_pairing(self):
        result = await self.hass.config_entries.flow.async_init("obd_connect", context={"source": "user"}, data={"name": "Other", "vehicle_id": "bad", "receiver_key": "short"})
        self.assertEqual("invalid_pairing", result["errors"]["base"])

    async def test_reload_preserves_durable_receipts(self):
        row = sample(int(time.time() * 1000))
        await self.send(batch(row))
        await self.hass.config_entries.async_unload(self.entry.entry_id)
        await self.hass.config_entries.async_setup(self.entry.entry_id)
        response = await self.send(batch(row))
        self.assertEqual([row["key"]], (await response.json())["accepted"])
        self.assertEqual(1, self.entry.runtime_data["coordinator"].data["records"])

    async def test_sensor_expires_without_any_new_batch(self):
        await self.send(batch(sample(int(time.time() * 1000) - 175000)))
        await self.hass.async_block_till_done()
        rpm = next(s for s in self.hass.states.async_all("sensor") if s.attributes.get("unit_of_measurement") == "rpm")
        self.assertEqual("750", rpm.state)
        await asyncio.sleep(31.5)
        await self.hass.async_block_till_done()
        self.assertEqual("unavailable", self.hass.states.get(rpm.entity_id).state)

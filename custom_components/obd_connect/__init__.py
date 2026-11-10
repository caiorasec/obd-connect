"""Authenticated direct-push OBD telemetry receiver."""

import asyncio
import hmac
import json
import logging
import time
from aiohttp import web
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.helpers.http import HomeAssistantView
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, MAX_BODY
from .storage import Ledger


async def async_setup(hass, config):
    hass.http.register_view(BatchView())
    return True


async def async_setup_entry(hass, entry):
    ledger = Ledger(hass.config.path(".storage", DOMAIN, f"{entry.entry_id}.sqlite3"))
    coordinator = DataUpdateCoordinator(hass, logging.getLogger(__name__), name=DOMAIN, config_entry=entry)
    coordinator.async_set_updated_data(await hass.async_add_executor_job(ledger.snapshot))
    entry.runtime_data = {"ledger": ledger, "coordinator": coordinator, "lock": asyncio.Lock()}
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])


class BatchView(HomeAssistantView):
    url = "/api/obd_connect/{vehicle_id}/batches"
    name = "api:obd_connect:batches"
    requires_auth = False  # Authentication below is restricted to this receiver/vehicle.

    async def post(self, request, vehicle_id):
        hass = request.app["hass"]
        entry = next((e for e in hass.config_entries.async_entries(DOMAIN) if e.data["vehicle_id"] == vehicle_id and e.state is ConfigEntryState.LOADED and hasattr(e, "runtime_data") and e.runtime_data), None)
        authorization = request.headers.get("Authorization", "")
        expected = f"Bearer {entry.data['receiver_key']}" if entry else ""
        if not entry or not hmac.compare_digest(authorization.encode(), expected.encode()):
            return web.json_response({"error": "unauthorized"}, status=401)
        body = bytearray()
        async for chunk in request.content.iter_chunked(8192):
            body.extend(chunk)
            if len(body) > MAX_BODY:
                return web.json_response({"error": "batch_too_large"}, status=413)
        try:
            payload = json.loads(body)
            runtime = entry.runtime_data
            async with runtime["lock"]:
                result = await hass.async_add_executor_job(runtime["ledger"].ingest, payload, vehicle_id, int(time.time() * 1000))
                runtime["coordinator"].async_set_updated_data(await hass.async_add_executor_job(runtime["ledger"].snapshot))
        except (ValueError, TypeError, KeyError):
            return web.json_response({"error": "invalid_batch"}, status=400)
        return web.json_response(result)

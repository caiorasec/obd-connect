"""Summary only: no receiver key, identifiers or raw vehicle history."""


async def async_get_config_entry_diagnostics(hass, entry):
    data = entry.runtime_data["coordinator"].data
    return {"stored_records": data["records"], "last_received_ms": data["received"], "metric_types": sorted(data["latest"]), "gps_supported": False}

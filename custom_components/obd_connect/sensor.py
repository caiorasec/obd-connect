"""Latest fresh values; backfill never becomes a current measurement."""

from datetime import UTC, datetime, timedelta
import time
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FRESH_MS, METRICS


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([*(ObdSensor(entry, pid) for pid in METRICS), ObdReceiptSensor(entry, "stored_records"), ObdReceiptSensor(entry, "last_received")])


class ObdSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry, pid):
        super().__init__(entry.runtime_data["coordinator"])
        self.pid = pid
        self._attr_unique_id = f"{entry.data['vehicle_id']}_{pid}"
        self._attr_name = METRICS[pid][0]
        self._attr_native_unit_of_measurement = METRICS[pid][1]
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.data["vehicle_id"])}, name=entry.title, manufacturer="OBD Connect", model="Android + ELM327")

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_track_time_interval(self.hass, self._expire, timedelta(seconds=30)))

    @callback
    def _expire(self, now):
        self.async_write_ha_state()

    @property
    def available(self):
        sample = self.coordinator.data["latest"].get(self.pid)
        return sample is not None and 0 <= time.time() * 1000 - sample["capturedAtMs"] <= FRESH_MS

    @property
    def native_value(self):
        sample = self.coordinator.data["latest"].get(self.pid)
        return sample["value"] if sample else None

    @property
    def extra_state_attributes(self):
        sample = self.coordinator.data["latest"].get(self.pid)
        return {"captured_at_ms": sample["capturedAtMs"], "source": "REAL"} if sample else {}


class ObdReceiptSensor(CoordinatorEntity, SensorEntity):
    """Durable receipt diagnostics, independent of measurement freshness."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, key):
        super().__init__(entry.runtime_data["coordinator"])
        self.key = key
        self._attr_unique_id = f"{entry.data['vehicle_id']}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.data["vehicle_id"])}, name=entry.title, manufacturer="OBD Connect", model="Android + ELM327")
        if key == "last_received":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        else:
            self._attr_icon = "mdi:database-check-outline"

    @property
    def native_value(self):
        if self.key == "stored_records":
            return self.coordinator.data["records"]
        received = self.coordinator.data["received"]
        return datetime.fromtimestamp(received / 1000, UTC) if received is not None else None

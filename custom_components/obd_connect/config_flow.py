"""Pair one vehicle using a scoped receiver key."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import DOMAIN
from .storage import uuid


class ObdConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                vehicle = uuid(user_input["vehicle_id"])
                key = user_input["receiver_key"]
                if not isinstance(key, str) or not 32 <= len(key) <= 128 or not key.isascii() or any(c.isspace() for c in key):
                    raise ValueError("invalid_key")
                await self.async_set_unique_id(vehicle)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input["name"], data=user_input)
            except (ValueError, TypeError, AttributeError):
                errors["base"] = "invalid_pairing"
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("name", default="Honda HR-V"): str,
            vol.Required("vehicle_id"): str,
            vol.Required("receiver_key"): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        }), errors=errors)

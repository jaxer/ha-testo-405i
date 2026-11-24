"""Config flow: pick a Testo 405i seen by any Bluetooth adapter or proxy."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, MANUFACTURER, MODEL
from .protocol import LOCAL_NAME_PREFIX, is_probe


def _is_probe(info: BluetoothServiceInfoBleak) -> bool:
    return info.connectable and is_probe(info.name, info.manufacturer_data, info.service_uuids)


def _title(info: BluetoothServiceInfoBleak) -> str:
    """Use the name the probe advertises if a scanner heard it, else model and address."""
    if info.name.startswith(LOCAL_NAME_PREFIX):
        return info.name
    return f"{MANUFACTURER} {MODEL} ({info.address})"


class Testo405iConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle discovery and manual selection."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}
        self._picked: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Offer to add a probe that just advertised."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._picked = discovery_info
        self.context["title_placeholders"] = {"name": _title(discovery_info)}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered probe."""
        assert self._picked is not None
        if user_input is not None:
            return self.async_create_entry(
                title=_title(self._picked), data={CONF_ADDRESS: self._picked.address}
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": _title(self._picked)},
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user choose among probes currently in range."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=_title(self._discovered[address]), data={CONF_ADDRESS: address}
            )

        configured = self._async_current_ids(include_ignore=False)
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address not in configured and _is_probe(info):
                self._discovered[info.address] = info
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {address: _title(info) for address, info in self._discovered.items()}
                    )
                }
            ),
        )

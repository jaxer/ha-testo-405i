"""Entities follow the notification stream and the duct diameter."""

from unittest.mock import patch

import pytest
from homeassistant.const import CONF_ADDRESS, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.testo_405i.const import DOMAIN

from .frames import BATTERY_CYCLE, TEMPERATURE_CYCLE, VELOCITY_CYCLE

ADDRESS = "FF:03:00:5F:EB:3A"
VELOCITY_1_MS = bytes.fromhex("0800000056656c6f636974790000803f0200")


async def setup_probe(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.testo_405i.coordinator.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
        patch(
            "custom_components.testo_405i.coordinator.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def push(entry: MockConfigEntry, chunks: list[bytes]) -> None:
    for chunk in chunks:
        entry.runtime_data.handle_chunk(chunk)


async def test_readings_are_unavailable_while_the_probe_is_off(hass: HomeAssistant) -> None:
    await setup_probe(hass)
    for key in ("velocity", "temperature", "flow"):
        assert hass.states.get(f"sensor.testo_405i_{key}").state == STATE_UNAVAILABLE
    assert hass.states.get("number.testo_405i_duct_diameter").state == "100.0"


async def test_the_stream_drives_the_sensors(hass: HomeAssistant) -> None:
    entry = await setup_probe(hass)
    push(entry, VELOCITY_CYCLE + TEMPERATURE_CYCLE + BATTERY_CYCLE)
    await hass.async_block_till_done()

    assert float(hass.states.get("sensor.testo_405i_velocity").state) == pytest.approx(
        0.06028, abs=1e-5
    )
    assert float(hass.states.get("sensor.testo_405i_temperature").state) == pytest.approx(
        25.30, abs=0.01
    )
    assert float(hass.states.get("sensor.testo_405i_battery").state) == pytest.approx(
        95.27, abs=0.01
    )


async def test_flow_follows_the_duct_diameter(hass: HomeAssistant) -> None:
    entry = await setup_probe(hass)
    push(entry, [VELOCITY_1_MS])
    await hass.async_block_till_done()
    assert float(hass.states.get("sensor.testo_405i_flow").state) == pytest.approx(7.854, abs=1e-3)

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.testo_405i_duct_diameter", "value": 125},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert float(hass.states.get("sensor.testo_405i_flow").state) == pytest.approx(12.272, abs=1e-3)


async def test_switching_the_probe_off_clears_live_readings_but_keeps_the_battery(
    hass: HomeAssistant,
) -> None:
    entry = await setup_probe(hass)
    push(entry, VELOCITY_CYCLE + BATTERY_CYCLE)
    entry.runtime_data._on_disconnected(None)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.testo_405i_velocity").state == STATE_UNAVAILABLE
    assert float(hass.states.get("sensor.testo_405i_battery").state) == pytest.approx(
        95.27, abs=0.01
    )

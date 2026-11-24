"""Config flow: discovery and manual pick."""

from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.testo_405i.const import DOMAIN

ADDRESS = "FF:03:00:5F:EB:3A"
NAME = "T405i SN:12345678"

PROBE_INFO = BluetoothServiceInfoBleak(
    name=NAME,
    address=ADDRESS,
    rssi=-58,
    manufacturer_data={},
    service_data={},
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    source="AA:BB:CC:DD:EE:01",
    device=BLEDevice(ADDRESS, NAME, {}),
    advertisement=AdvertisementData(
        local_name=NAME,
        manufacturer_data={},
        service_data={},
        service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
        tx_power=-127,
        rssi=-58,
        platform_data=(),
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)


async def test_bluetooth_discovery_creates_an_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=PROBE_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch("custom_components.testo_405i.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS


async def test_same_probe_is_not_added_twice(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}).add_to_hass(
        hass
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=PROBE_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_lists_probes_in_range(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.testo_405i.config_flow.async_discovered_service_info",
        return_value=[PROBE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("custom_components.testo_405i.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}


async def test_user_flow_aborts_when_nothing_is_in_range(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.testo_405i.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


def nameless_probe() -> BluetoothServiceInfoBleak:
    """The probe as a passive proxy reports it: no name, only company id and service."""
    return BluetoothServiceInfoBleak(
        name=ADDRESS,
        address=ADDRESS,
        rssi=-76,
        manufacturer_data={766: b"%\x03\x05\x06"},
        service_data={},
        service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
        source="AA:BB:CC:DD:EE:02",
        device=BLEDevice(ADDRESS, ADDRESS, {}),
        advertisement=AdvertisementData(
            local_name=None,
            manufacturer_data={766: b"%\x03\x05\x06"},
            service_data={},
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
            tx_power=-127,
            rssi=-76,
            platform_data=(),
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )


async def test_a_probe_heard_without_its_name_is_still_offered(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.testo_405i.config_flow.async_discovered_service_info",
        return_value=[nameless_probe()],
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    with patch("custom_components.testo_405i.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Testo 405i ({ADDRESS})"

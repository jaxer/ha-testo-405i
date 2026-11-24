"""Keep a Testo 405i connected while it is switched on and publish its readings."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    MONOTONIC_TIME,
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_DUCT_DIAMETER_MM, DOMAIN
from .protocol import (
    BATTERY,
    NOTIFY_CHARACTERISTIC_UUID,
    START_COMMANDS,
    TEMPERATURE,
    VELOCITY,
    WRITE_CHARACTERISTIC_UUID,
    StreamParser,
    flow_l_s,
)

_LOGGER = logging.getLogger(__name__)

_STATE_FIELDS = {
    VELOCITY: "velocity_m_s",
    TEMPERATURE: "temperature_c",
    BATTERY: "battery_percent",
}

_CONNECT_ATTEMPTS = 3
_COMMAND_GAP_S = 0.5
# Home Assistant does not pass on an advertisement identical to the last one it saw, so a probe
# switched on again can go unnoticed; check every few seconds as well.
_RETRY_INTERVAL = timedelta(seconds=5)
# Only retry while the probe was heard this recently: an older advertisement means it is off.
_AWAKE_WITHIN_S = 15.0

type Testo405iConfigEntry = ConfigEntry[Testo405iCoordinator]


@dataclass(frozen=True, slots=True)
class ProbeState:
    """Everything the entities show."""

    connected: bool = False
    velocity_m_s: float | None = None
    temperature_c: float | None = None
    battery_percent: float | None = None


class Testo405iCoordinator(DataUpdateCoordinator[ProbeState]):
    """Connect on advertisement, send the start commands, stream FFF2."""

    config_entry: Testo405iConfigEntry

    def __init__(self, hass: HomeAssistant, entry: Testo405iConfigEntry, address: str) -> None:
        """Set up the coordinator for one probe."""
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN}:{address}", update_interval=None
        )
        self.address = address
        self.duct_diameter_mm = DEFAULT_DUCT_DIAMETER_MM
        self._parser = StreamParser()
        self._client: BleakClient | None = None
        self._connect_lock = asyncio.Lock()
        self._unregister_advertisements: CALLBACK_TYPE | None = None
        self._cancel_retry: CALLBACK_TYPE | None = None
        self.data = ProbeState()

    @property
    def flow_l_s(self) -> float | None:
        """Volume flow for the configured duct, from the current velocity."""
        velocity = self.data.velocity_m_s
        return None if velocity is None else flow_l_s(velocity, self.duct_diameter_mm)

    @callback
    def set_duct_diameter(self, diameter_mm: float) -> None:
        """Change the duct the flow is computed for."""
        self.duct_diameter_mm = diameter_mm
        self.async_update_listeners()

    async def async_start(self) -> None:
        """Start listening for the probe."""
        self._unregister_advertisements = bluetooth.async_register_callback(
            self.hass,
            self._on_advertisement,
            BluetoothCallbackMatcher(address=self.address, connectable=True),
            BluetoothScanningMode.ACTIVE,
        )
        self._cancel_retry = async_track_time_interval(
            self.hass, self._retry_if_awake, _RETRY_INTERVAL
        )
        if bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True):
            self.hass.async_create_task(self._async_connect())

    async def async_stop(self) -> None:
        """Stop listening and drop the connection."""
        if self._unregister_advertisements:
            self._unregister_advertisements()
            self._unregister_advertisements = None
        if self._cancel_retry:
            self._cancel_retry()
            self._cancel_retry = None
        client = self._client
        self._client = None
        if client and client.is_connected:
            try:
                await client.disconnect()
            except BleakError:
                _LOGGER.debug("Disconnect on stop failed", exc_info=True)

    @callback
    def _on_advertisement(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        if self._client is None:
            self.hass.async_create_task(self._async_connect())

    @callback
    def _retry_if_awake(self, _: datetime) -> None:
        if self._client is not None or self._connect_lock.locked():
            return
        info = bluetooth.async_last_service_info(self.hass, self.address, connectable=True)
        if info is not None and MONOTONIC_TIME() - info.time < _AWAKE_WITHIN_S:
            self.hass.async_create_task(self._async_connect())

    async def _async_connect(self) -> None:
        async with self._connect_lock:
            if self._client is not None:
                return
            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if device is None:
                return
            try:
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    device,
                    self.address,
                    disconnected_callback=self._on_disconnected,
                    max_attempts=_CONNECT_ATTEMPTS,
                    ble_device_callback=lambda: bluetooth.async_ble_device_from_address(
                        self.hass, self.address, connectable=True
                    ),
                )
            except (BleakError, TimeoutError) as err:
                _LOGGER.debug("Connection to %s failed: %s", self.address, err)
                return
            self._client = client
            self._parser = StreamParser()
            try:
                await client.start_notify(NOTIFY_CHARACTERISTIC_UUID, self._on_notification)
                for command in START_COMMANDS:
                    await client.write_gatt_char(WRITE_CHARACTERISTIC_UUID, command, response=False)
                    await asyncio.sleep(_COMMAND_GAP_S)
            except (BleakError, TimeoutError) as err:
                _LOGGER.warning("Starting the stream of %s failed: %s", self.address, err)
                self._client = None
                try:
                    await client.disconnect()
                except BleakError:
                    _LOGGER.debug("Disconnect after a failed start failed", exc_info=True)
                return
            if self._client is not client:
                # The probe went away while the stream was starting.
                return
            _LOGGER.debug("Connected to %s, MTU %s", self.address, client.mtu_size)
            self.async_set_updated_data(replace(self.data, connected=True))

    @callback
    def _on_notification(self, _: BleakGATTCharacteristic, data: bytearray) -> None:
        self.handle_chunk(bytes(data))

    @callback
    def handle_chunk(self, chunk: bytes) -> None:
        """Feed one notification and publish what it completed."""
        _LOGGER.debug("Notification %s", chunk.hex())
        readings = self._parser.feed(chunk)
        if not readings:
            return
        changes = {_STATE_FIELDS[name]: value for name, value in readings}
        self.async_set_updated_data(replace(self.data, connected=True, **changes))

    @callback
    def _on_disconnected(self, _: BleakClient) -> None:
        _LOGGER.debug("Disconnected from %s", self.address)
        self._client = None
        self.async_set_updated_data(ProbeState(battery_percent=self.data.battery_percent))

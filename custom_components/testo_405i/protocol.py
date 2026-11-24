"""Testo 405i wire format: start commands and the measurement stream.

The probe is silent after connecting. Writing the three start commands to FFF1 makes it stream
on FFF2, about once a second, frames whose payload is
``<u32 LE name length><ASCII name><float32 LE value>`` with the names ``Velocity`` (m/s),
``Temperature`` (°C) and ``BatteryLevel`` (%). One frame arrives split over several
notifications, so the parser works on the byte stream and looks for the names.
"""

from __future__ import annotations

import math
import struct
from collections.abc import Container

LOCAL_NAME_PREFIX = "T405i"
# Passive scanners (most Bluetooth proxies) never see the name, which is in the scan response,
# so the probe is also recognised by Testo's company id together with its service.
MANUFACTURER_ID = 766
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_CHARACTERISTIC_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
NOTIFY_CHARACTERISTIC_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"

START_COMMANDS: tuple[bytes, ...] = (
    bytes.fromhex("5600030000000c69023e81"),
    bytes.fromhex("200000000000077b"),
    bytes.fromhex("110000000000035a"),
)

VELOCITY = "Velocity"
TEMPERATURE = "Temperature"
BATTERY = "BatteryLevel"
_NAMES = tuple(name.encode() for name in (VELOCITY, TEMPERATURE, BATTERY))
_KEEP = max(len(name) for name in _NAMES) - 1


class StreamParser:
    """Turn notification chunks into ``(name, value)`` readings."""

    def __init__(self) -> None:
        """Start with an empty buffer."""
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[tuple[str, float]]:
        """Add one notification and return the readings it completed."""
        self._buffer += chunk
        readings: list[tuple[str, float]] = []
        while True:
            hits = [(pos, name) for name in _NAMES if (pos := self._buffer.find(name)) >= 0]
            if not hits:
                # Keep a tail that may be the start of a name split across notifications.
                del self._buffer[:-_KEEP]
                return readings
            pos, name = min(hits)
            end = pos + len(name) + 4
            if len(self._buffer) < end:
                del self._buffer[:pos]
                return readings
            (value,) = struct.unpack_from("<f", self._buffer, pos + len(name))
            del self._buffer[:end]
            if math.isfinite(value):
                readings.append((name.decode(), value))


def is_probe(name: str, manufacturer_ids: Container[int], service_uuids: Container[str]) -> bool:
    """Whether an advertisement comes from a Testo 405i."""
    if name.startswith(LOCAL_NAME_PREFIX):
        return True
    return MANUFACTURER_ID in manufacturer_ids and SERVICE_UUID in service_uuids


def flow_l_s(velocity_m_s: float, duct_diameter_mm: float) -> float:
    """Volume flow in a round duct: mean velocity times the cross-section."""
    area_m2 = math.pi * (duct_diameter_mm / 2000) ** 2
    return velocity_m_s * area_m2 * 1000

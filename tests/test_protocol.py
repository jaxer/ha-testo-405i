import struct

import pytest

from custom_components.testo_405i.protocol import (
    BATTERY,
    TEMPERATURE,
    VELOCITY,
    StreamParser,
    flow_l_s,
)

from .frames import BATTERY_CYCLE, HANDSHAKE_REPLIES, TEMPERATURE_CYCLE, VELOCITY_CYCLE


def feed_all(parser: StreamParser, chunks: list[bytes]) -> list[tuple[str, float]]:
    return [reading for chunk in chunks for reading in parser.feed(chunk)]


def test_real_capture_gives_velocity_temperature_and_battery() -> None:
    readings = feed_all(
        StreamParser(), HANDSHAKE_REPLIES + VELOCITY_CYCLE + TEMPERATURE_CYCLE + BATTERY_CYCLE
    )
    assert [name for name, _ in readings] == [VELOCITY, TEMPERATURE, BATTERY]
    assert readings[0][1] == pytest.approx(0.06028, abs=1e-5)
    assert readings[1][1] == pytest.approx(25.30, abs=0.01)
    assert readings[2][1] == pytest.approx(95.27, abs=0.01)


@pytest.mark.parametrize("cut", range(1, 16))
def test_a_frame_split_anywhere_is_still_read(cut: int) -> None:
    frame = VELOCITY_CYCLE[1]
    parser = StreamParser()
    assert parser.feed(frame[:cut]) == []
    assert parser.feed(frame[cut:]) == [(VELOCITY, pytest.approx(0.06028, abs=1e-5))]


def test_handshake_replies_and_noise_give_nothing() -> None:
    parser = StreamParser()
    assert feed_all(parser, HANDSHAKE_REPLIES + [b"\x00" * 40]) == []


def test_a_value_that_is_not_a_number_is_dropped() -> None:
    frame = b"\x08\x00\x00\x00Velocity" + struct.pack("<f", float("nan"))
    assert StreamParser().feed(frame) == []


def test_flow_in_a_100_mm_duct() -> None:
    assert flow_l_s(1.0, 100) == pytest.approx(7.854, abs=1e-3)
    assert flow_l_s(2.5, 125) == pytest.approx(30.68, abs=1e-2)

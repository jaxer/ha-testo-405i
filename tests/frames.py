"""Notifications captured from a real Testo 405i."""

# One cycle as it arrived on FFF2, chunk by chunk.
VELOCITY_CYCLE = [
    bytes.fromhex("10801400000006a5"),
    bytes.fromhex("0800000056656c6f63697479dbe7763d0200"),
    bytes.fromhex("051a"),
]
TEMPERATURE_CYCLE = [
    bytes.fromhex("10801700000006e1"),
    bytes.fromhex("0b00000054656d7065726174757265746eca410100"),
    bytes.fromhex("0000"),
]
BATTERY_CYCLE = [
    bytes.fromhex("108016000000071d"),
    bytes.fromhex("0c000000426174746572794c6576656cde89be42"),
    bytes.fromhex("29e2"),
]
# Replies to the start commands; they carry no reading.
HANDSHAKE_REPLIES = [bytes.fromhex("0020"), bytes.fromhex("07000000000001ac")]

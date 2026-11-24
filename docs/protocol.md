# Testo 405i Bluetooth protocol

Worked out by experiment on one probe. Nothing here comes from Testo documentation.

## Advertisement

| Field | Value |
|---|---|
| Local name | `T405i SN:<serial number>`, in the scan response |
| Manufacturer id | 766 (Testo), data `25 03 05 06` |
| Service | `0000fff0-0000-1000-8000-00805f9b34fb` |

A passive scanner never receives the scan response, so it sees no name. The integration therefore
also recognises the probe by the manufacturer id together with the service.

## Characteristics

| Characteristic | Use |
|---|---|
| `fff1` | commands, written without response |
| `fff2` | notifications: replies and the measurement stream |

## Starting the stream

After connecting the probe sends nothing. Writing these three commands to `fff1`, half a second
apart, starts the stream:

```
5600030000000c69023e81
200000000000077b
110000000000035a
```

The probe replies `0020`, then `07000000000001ac`.

## The measurement stream

The stream repeats about once a second. Each reading arrives as three notifications:

1. an 8-byte header: `10 80 14 …` before a velocity, `10 80 17 …` before a temperature,
   `10 80 16 …` before a battery level;
2. the payload;
3. two trailing bytes that look like a checksum.

The payload is

```
<u32 LE name length> <ASCII name> <float32 LE value> [2 bytes]
```

| Name | Unit | Payload length |
|---|---|---|
| `Velocity` | m/s | 18 bytes |
| `Temperature` | °C | 21 bytes |
| `BatteryLevel` | % | 20 bytes |

Velocity and temperature come every cycle, the battery level less often.

The integration does not check the header or the trailing bytes: it searches the byte stream for
the three names and reads the four bytes after each. Captured notifications are in
[`tests/frames.py`](../tests/frames.py).

## The temperature payload is fragmented on the air

A 21-byte notification is 28 bytes of L2CAP, one more than fits a single 27-byte link-layer
packet, so the temperature payload arrives in two fragments, even on a connection with a large
MTU. A receiver that mishandles the short second fragment loses the temperature while velocity
and battery level pass on the same connection.

This was seen on an ESPHome Bluetooth proxy running 2026.6.2 (reported MTU 203). Its log showed,
once per lost notification:

```
BT_HCI: ACL packet too short (len=5)
BT_HCI: reassemble_and_dispatch found unfinished packet for handle with start packet. Dropping old.
```

The same proxy on ESPHome 2026.11.0 delivers every reading, as do a proxy on 2025.6.0 and a Mac.

## Not known

- What the three start commands mean individually.
- Whether the probe needs a keep-alive on long sessions.
- The meaning of the other characteristics (`fe63`, `fe64`, service `5a90`).

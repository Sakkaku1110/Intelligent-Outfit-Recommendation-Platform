# WS63 -> SS928 NearLink AS7341 bridge

This directory contains a transport-agnostic NearLink bridge for sending
GY-AS7341 spectral readings from WS63 to SS928.

The code is split intentionally:

- `spectral_nearlink_packet.h` defines the stable binary frame shared by WS63
  and SS928.
- `nearlink_as7341_sender.c` owns the WS63 send loop and calls external port
  functions that you map to the real WS63 AS7341 driver and NearLink SDK.
- `../../board/app/nearlink_frame.py` decodes the same frame on SS928 and feeds
  the existing `spectral_material.py` classifier.

## Frame format

All integer fields are little-endian. One frame is 48 bytes:

```text
magic[4]      = "SWSP"
version       = 1
msg_type      = 1   AS7341 reading
payload_len   = 32
device_id     uint32
seq           uint32
timestamp_ms  uint32
f1..f8        8 x uint16
clear         uint16
nir           uint16
gain          uint8
atime         uint16
astep         uint16
flags         uint8
crc16_ccitt   uint16 over all previous bytes
```

## WS63 integration points

Provide these functions from your WS63 project:

```c
int ws63_as7341_read_sample(ws63_as7341_sample_t *sample);
int ws63_nearlink_send(const uint8_t *data, uint16_t len);
uint32_t ws63_time_ms(void);
void ws63_delay_ms(uint32_t ms);
void ws63_log(const char *fmt, ...);
```

`ws63_nearlink_send()` is the only function that depends on the actual 星闪 /
NearLink SDK. It should send exactly the `len` bytes it receives.

## SS928 smoke test

When the SS928 NearLink SDK exposes received bytes, pass the bytes to:

```python
from board.app.nearlink_frame import iter_spectral_frames

for frame in iter_spectral_frames(byte_chunks):
    payload = frame.to_payload()
```

For a serial/file replay:

```bash
python smart-wardrobe-system/board/tools/receive_nearlink_frame.py --input frames.bin
```

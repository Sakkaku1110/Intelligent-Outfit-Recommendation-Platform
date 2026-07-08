/*
 * WS63 NearLink sender for GY-AS7341 spectral samples.
 *
 * This file is intentionally SDK-neutral. Wire the port functions below to the
 * WS63 I2C/AS7341 code and the WS63 NearLink SDK used by your board package.
 */

#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>

#include "spectral_nearlink_packet.h"

#ifndef WS63_SPECTRAL_DEVICE_ID
#define WS63_SPECTRAL_DEVICE_ID 0x00006301U
#endif

#ifndef WS63_AS7341_GAIN_CODE
#define WS63_AS7341_GAIN_CODE 0x08U
#endif

#ifndef WS63_AS7341_ATIME
#define WS63_AS7341_ATIME 99U
#endif

#ifndef WS63_AS7341_ASTEP
#define WS63_AS7341_ASTEP 999U
#endif

#ifndef WS63_NEARLINK_SEND_INTERVAL_MS
#define WS63_NEARLINK_SEND_INTERVAL_MS 1000U
#endif

#ifdef WS63_NEARLINK_EXTERNAL_PORT
int ws63_as7341_read_sample(ws63_as7341_sample_t *sample);
int ws63_nearlink_send(const uint8_t *data, uint16_t len);
uint32_t ws63_time_ms(void);
void ws63_delay_ms(uint32_t ms);
void ws63_log(const char *fmt, ...);
#else
/*
 * Defaults let this file compile on a desktop, but they do not talk to hardware.
 * Define WS63_NEARLINK_EXTERNAL_PORT in the real WS63 project.
 */
int ws63_as7341_read_sample(ws63_as7341_sample_t *sample)
{
    (void)sample;
    return -1;
}

int ws63_nearlink_send(const uint8_t *data, uint16_t len)
{
    (void)data;
    (void)len;
    return -1;
}

uint32_t ws63_time_ms(void)
{
    return 0;
}

void ws63_delay_ms(uint32_t ms)
{
    (void)ms;
}

void ws63_log(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    vprintf(fmt, args);
    va_end(args);
}
#endif

static uint32_t g_spectral_seq = 0;

int ws63_send_as7341_nearlink_once(void)
{
    ws63_as7341_sample_t sample = {0};
    spectral_nl_reading_t reading = {0};
    uint8_t frame[SPECTRAL_NL_FRAME_SIZE] = {0};
    uint16_t frame_len = 0;

    if (ws63_as7341_read_sample(&sample) != 0) {
        ws63_log("AS7341 read failed\r\n");
        return -1;
    }

    reading.device_id = WS63_SPECTRAL_DEVICE_ID;
    reading.seq = g_spectral_seq++;
    reading.timestamp_ms = ws63_time_ms();
    reading.sample = sample;
    reading.gain = WS63_AS7341_GAIN_CODE;
    reading.atime = WS63_AS7341_ATIME;
    reading.astep = WS63_AS7341_ASTEP;
    reading.flags = 0;

    frame_len = spectral_nl_encode_reading(&reading, frame);
    if (frame_len != SPECTRAL_NL_FRAME_SIZE) {
        ws63_log("NearLink frame encode failed: %u\r\n", (unsigned)frame_len);
        return -1;
    }

    if (ws63_nearlink_send(frame, frame_len) != 0) {
        ws63_log("NearLink send failed, seq=%lu\r\n", (unsigned long)reading.seq);
        return -1;
    }

    ws63_log("NearLink AS7341 sent, seq=%lu\r\n", (unsigned long)reading.seq);
    return 0;
}

void ws63_as7341_nearlink_loop(void)
{
    while (1) {
        (void)ws63_send_as7341_nearlink_once();
        ws63_delay_ms(WS63_NEARLINK_SEND_INTERVAL_MS);
    }
}

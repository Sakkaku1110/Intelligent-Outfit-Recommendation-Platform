#ifndef SPECTRAL_NEARLINK_PACKET_H
#define SPECTRAL_NEARLINK_PACKET_H

#include <stdint.h>
#include <string.h>

#define SPECTRAL_NL_MAGIC_0 'S'
#define SPECTRAL_NL_MAGIC_1 'W'
#define SPECTRAL_NL_MAGIC_2 'S'
#define SPECTRAL_NL_MAGIC_3 'P'
#define SPECTRAL_NL_VERSION 1U
#define SPECTRAL_NL_MSG_AS7341_READING 1U
#define SPECTRAL_NL_CHANNEL_COUNT 10U
#define SPECTRAL_NL_PAYLOAD_SIZE 32U
#define SPECTRAL_NL_FRAME_SIZE 48U

typedef struct {
    uint16_t f1;
    uint16_t f2;
    uint16_t f3;
    uint16_t f4;
    uint16_t f5;
    uint16_t f6;
    uint16_t f7;
    uint16_t f8;
    uint16_t clear;
    uint16_t nir;
} ws63_as7341_sample_t;

typedef struct {
    uint32_t device_id;
    uint32_t seq;
    uint32_t timestamp_ms;
    ws63_as7341_sample_t sample;
    uint8_t gain;
    uint16_t atime;
    uint16_t astep;
    uint8_t flags;
} spectral_nl_reading_t;

static inline void spectral_nl_put_u16(uint8_t *buffer, uint16_t value)
{
    buffer[0] = (uint8_t)(value & 0xFFU);
    buffer[1] = (uint8_t)((value >> 8U) & 0xFFU);
}

static inline void spectral_nl_put_u32(uint8_t *buffer, uint32_t value)
{
    buffer[0] = (uint8_t)(value & 0xFFU);
    buffer[1] = (uint8_t)((value >> 8U) & 0xFFU);
    buffer[2] = (uint8_t)((value >> 16U) & 0xFFU);
    buffer[3] = (uint8_t)((value >> 24U) & 0xFFU);
}

static inline uint16_t spectral_nl_crc16_ccitt(const uint8_t *data, uint16_t len)
{
    uint16_t crc = 0xFFFFU;

    for (uint16_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8U;
        for (uint8_t bit = 0; bit < 8U; bit++) {
            if ((crc & 0x8000U) != 0U) {
                crc = (uint16_t)((crc << 1U) ^ 0x1021U);
            } else {
                crc = (uint16_t)(crc << 1U);
            }
        }
    }

    return crc;
}

static inline uint16_t spectral_nl_encode_reading(
    const spectral_nl_reading_t *reading,
    uint8_t out_frame[SPECTRAL_NL_FRAME_SIZE])
{
    uint16_t offset = 0;
    uint16_t crc = 0;
    const uint16_t channels[SPECTRAL_NL_CHANNEL_COUNT] = {
        reading->sample.f1,
        reading->sample.f2,
        reading->sample.f3,
        reading->sample.f4,
        reading->sample.f5,
        reading->sample.f6,
        reading->sample.f7,
        reading->sample.f8,
        reading->sample.clear,
        reading->sample.nir,
    };

    memset(out_frame, 0, SPECTRAL_NL_FRAME_SIZE);
    out_frame[offset++] = SPECTRAL_NL_MAGIC_0;
    out_frame[offset++] = SPECTRAL_NL_MAGIC_1;
    out_frame[offset++] = SPECTRAL_NL_MAGIC_2;
    out_frame[offset++] = SPECTRAL_NL_MAGIC_3;
    out_frame[offset++] = SPECTRAL_NL_VERSION;
    out_frame[offset++] = SPECTRAL_NL_MSG_AS7341_READING;
    spectral_nl_put_u16(&out_frame[offset], SPECTRAL_NL_PAYLOAD_SIZE);
    offset = (uint16_t)(offset + 2U);
    spectral_nl_put_u32(&out_frame[offset], reading->device_id);
    offset = (uint16_t)(offset + 4U);
    spectral_nl_put_u32(&out_frame[offset], reading->seq);
    offset = (uint16_t)(offset + 4U);
    spectral_nl_put_u32(&out_frame[offset], reading->timestamp_ms);
    offset = (uint16_t)(offset + 4U);

    for (uint8_t i = 0; i < SPECTRAL_NL_CHANNEL_COUNT; i++) {
        spectral_nl_put_u16(&out_frame[offset], channels[i]);
        offset = (uint16_t)(offset + 2U);
    }

    out_frame[offset++] = reading->gain;
    spectral_nl_put_u16(&out_frame[offset], reading->atime);
    offset = (uint16_t)(offset + 2U);
    spectral_nl_put_u16(&out_frame[offset], reading->astep);
    offset = (uint16_t)(offset + 2U);
    out_frame[offset++] = reading->flags;

    crc = spectral_nl_crc16_ccitt(out_frame, offset);
    spectral_nl_put_u16(&out_frame[offset], crc);
    offset = (uint16_t)(offset + 2U);

    return offset;
}

#endif

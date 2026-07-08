/*
 * WS63 + GY-AS7341 spectral sensor smoke test.
 *
 * Porting notes:
 * 1. Replace ws63_i2c_write_reg/ws63_i2c_read_reg with your WS63 SDK I2C APIs.
 * 2. Replace ws63_delay_ms and ws63_log with the SDK delay/printf APIs.
 * 3. Call as7341_test_loop() from your WS63 app task after I2C init.
 *
 * Serial output is newline-delimited JSON, so the Mac-side script can forward it
 * to /api/ws63/sensor.
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>

#if defined(__unix__) || defined(__APPLE__)
#include <unistd.h>
#endif

#define AS7341_I2C_ADDR 0x39

#define AS7341_REG_ENABLE 0x80
#define AS7341_REG_ATIME 0x81
#define AS7341_REG_ID 0x92
#define AS7341_REG_STATUS2 0xA3
#define AS7341_REG_CFG0 0xA9
#define AS7341_REG_CFG1 0xAA
#define AS7341_REG_CFG6 0xAF
#define AS7341_REG_CH0_DATA_L 0x95
#define AS7341_REG_ASTEP_L 0xCA
#define AS7341_REG_ASTEP_H 0xCB

#define AS7341_ENABLE_PON 0x01
#define AS7341_ENABLE_SP_EN 0x02
#define AS7341_ENABLE_SMUXEN 0x10

#define AS7341_STATUS2_AVALID 0x40
#define AS7341_CFG0_REG_BANK 0x10
#define AS7341_SMUX_CMD_WRITE 0x10

/* Gain code used by AS7341 CFG1. 0x08 is 128x on common AS7341 drivers. */
#define AS7341_GAIN_128X 0x08

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
} as7341_sample_t;

/*
 * Port layer.
 *
 * Option A: directly replace the default functions below with WS63 SDK calls.
 * Option B: compile this file with AS7341_EXTERNAL_PORT and provide these four
 * functions from another source file in your WS63 project.
 */
#ifdef AS7341_EXTERNAL_PORT
int ws63_i2c_write_reg(uint8_t device_addr, uint8_t reg_addr, uint8_t value);
int ws63_i2c_read_reg(uint8_t device_addr, uint8_t reg_addr, uint8_t *value);
void ws63_delay_ms(uint32_t ms);
void ws63_log(const char *fmt, ...);
#else
static int ws63_i2c_write_reg(uint8_t device_addr, uint8_t reg_addr, uint8_t value)
{
    (void)device_addr;
    (void)reg_addr;
    (void)value;
    return -1;
}

static int ws63_i2c_read_reg(uint8_t device_addr, uint8_t reg_addr, uint8_t *value)
{
    (void)device_addr;
    (void)reg_addr;
    if (value != NULL) {
        *value = 0;
    }
    return -1;
}

static void ws63_delay_ms(uint32_t ms)
{
#if defined(__unix__) || defined(__APPLE__)
    usleep(ms * 1000U);
#else
    (void)ms;
#endif
}

static void ws63_log(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    vprintf(fmt, args);
    va_end(args);
}
#endif

static int as7341_write8(uint8_t reg_addr, uint8_t value)
{
    return ws63_i2c_write_reg(AS7341_I2C_ADDR, reg_addr, value);
}

static int as7341_read8(uint8_t reg_addr, uint8_t *value)
{
    return ws63_i2c_read_reg(AS7341_I2C_ADDR, reg_addr, value);
}

static int as7341_read16(uint8_t reg_addr, uint16_t *value)
{
    uint8_t low = 0;
    uint8_t high = 0;

    if (as7341_read8(reg_addr, &low) != 0) {
        return -1;
    }
    if (as7341_read8((uint8_t)(reg_addr + 1U), &high) != 0) {
        return -1;
    }

    *value = (uint16_t)(((uint16_t)high << 8U) | low);
    return 0;
}

static int as7341_set_register_bank(bool high_bank)
{
    uint8_t cfg0 = 0;

    if (as7341_read8(AS7341_REG_CFG0, &cfg0) != 0) {
        return -1;
    }

    if (high_bank) {
        cfg0 |= AS7341_CFG0_REG_BANK;
    } else {
        cfg0 &= (uint8_t)~AS7341_CFG0_REG_BANK;
    }

    return as7341_write8(AS7341_REG_CFG0, cfg0);
}

static int as7341_set_power(bool enabled)
{
    return as7341_write8(AS7341_REG_ENABLE, enabled ? AS7341_ENABLE_PON : 0x00);
}

static int as7341_wait_smux_done(void)
{
    uint8_t enable = 0;

    for (uint16_t i = 0; i < 100; i++) {
        if (as7341_read8(AS7341_REG_ENABLE, &enable) != 0) {
            return -1;
        }
        if ((enable & AS7341_ENABLE_SMUXEN) == 0) {
            return 0;
        }
        ws63_delay_ms(10);
    }

    return -1;
}

static int as7341_write_smux(const uint8_t smux[20])
{
    if (as7341_set_power(true) != 0) {
        return -1;
    }
    if (as7341_set_register_bank(false) != 0) {
        return -1;
    }
    if (as7341_write8(AS7341_REG_CFG6, AS7341_SMUX_CMD_WRITE) != 0) {
        return -1;
    }

    for (uint8_t i = 0; i < 20U; i++) {
        if (as7341_write8(i, smux[i]) != 0) {
            return -1;
        }
    }

    if (as7341_write8(AS7341_REG_ENABLE, AS7341_ENABLE_PON | AS7341_ENABLE_SMUXEN) != 0) {
        return -1;
    }

    return as7341_wait_smux_done();
}

static int as7341_wait_data_ready(void)
{
    uint8_t status2 = 0;

    for (uint16_t i = 0; i < 100; i++) {
        if (as7341_read8(AS7341_REG_STATUS2, &status2) != 0) {
            return -1;
        }
        if ((status2 & AS7341_STATUS2_AVALID) != 0) {
            return 0;
        }
        ws63_delay_ms(10);
    }

    return -1;
}

static int as7341_read_adc6(uint16_t adc[6])
{
    if (as7341_write8(AS7341_REG_ENABLE, AS7341_ENABLE_PON | AS7341_ENABLE_SP_EN) != 0) {
        return -1;
    }
    if (as7341_wait_data_ready() != 0) {
        return -1;
    }

    for (uint8_t i = 0; i < 6U; i++) {
        if (as7341_read16((uint8_t)(AS7341_REG_CH0_DATA_L + (2U * i)), &adc[i]) != 0) {
            return -1;
        }
    }

    return as7341_write8(AS7341_REG_ENABLE, AS7341_ENABLE_PON);
}

static int as7341_setup_f1_f4_clear_nir(void)
{
    static const uint8_t smux[20] = {
        0x30, 0x01, 0x00, 0x00, 0x00,
        0x42, 0x00, 0x00, 0x50, 0x00,
        0x00, 0x00, 0x20, 0x04, 0x00,
        0x30, 0x01, 0x50, 0x00, 0x06,
    };

    return as7341_write_smux(smux);
}

static int as7341_setup_f5_f8_clear_nir(void)
{
    static const uint8_t smux[20] = {
        0x00, 0x00, 0x00, 0x40, 0x02,
        0x00, 0x10, 0x03, 0x50, 0x10,
        0x03, 0x00, 0x00, 0x00, 0x24,
        0x00, 0x00, 0x50, 0x00, 0x06,
    };

    return as7341_write_smux(smux);
}

static int as7341_begin(void)
{
    uint8_t id = 0;

    if (as7341_set_power(true) != 0) {
        return -1;
    }
    ws63_delay_ms(20);

    if (as7341_read8(AS7341_REG_ID, &id) != 0) {
        return -1;
    }

    if ((id & 0xFCU) != 0x24U) {
        ws63_log("AS7341 not found, ID=0x%02X\r\n", id);
        return -1;
    }

    /*
     * Integration time = (ATIME + 1) * (ASTEP + 1) * 2.78us.
     * These values are conservative for desk-light testing.
     */
    if (as7341_write8(AS7341_REG_ATIME, 99) != 0) {
        return -1;
    }
    if (as7341_write8(AS7341_REG_ASTEP_L, 999 & 0xFF) != 0) {
        return -1;
    }
    if (as7341_write8(AS7341_REG_ASTEP_H, (999 >> 8) & 0xFF) != 0) {
        return -1;
    }
    if (as7341_write8(AS7341_REG_CFG1, AS7341_GAIN_128X) != 0) {
        return -1;
    }

    return 0;
}

static int as7341_read_sample(as7341_sample_t *sample)
{
    uint16_t adc[6] = {0};

    if (sample == NULL) {
        return -1;
    }

    if (as7341_setup_f1_f4_clear_nir() != 0) {
        return -1;
    }
    if (as7341_read_adc6(adc) != 0) {
        return -1;
    }

    sample->f1 = adc[0];
    sample->f2 = adc[1];
    sample->f3 = adc[2];
    sample->f4 = adc[3];
    sample->clear = adc[4];
    sample->nir = adc[5];

    if (as7341_setup_f5_f8_clear_nir() != 0) {
        return -1;
    }
    if (as7341_read_adc6(adc) != 0) {
        return -1;
    }

    sample->f5 = adc[0];
    sample->f6 = adc[1];
    sample->f7 = adc[2];
    sample->f8 = adc[3];
    sample->clear = (uint16_t)(((uint32_t)sample->clear + adc[4]) / 2U);
    sample->nir = (uint16_t)(((uint32_t)sample->nir + adc[5]) / 2U);

    return 0;
}

static void as7341_print_json(const as7341_sample_t *sample)
{
    ws63_log(
        "{\"device\":\"WS63\",\"sensor\":\"GY-AS7341\","
        "\"f1\":%u,\"f2\":%u,\"f3\":%u,\"f4\":%u,"
        "\"f5\":%u,\"f6\":%u,\"f7\":%u,\"f8\":%u,"
        "\"clear\":%u,\"nir\":%u}\r\n",
        (unsigned)sample->f1,
        (unsigned)sample->f2,
        (unsigned)sample->f3,
        (unsigned)sample->f4,
        (unsigned)sample->f5,
        (unsigned)sample->f6,
        (unsigned)sample->f7,
        (unsigned)sample->f8,
        (unsigned)sample->clear,
        (unsigned)sample->nir);
}

void as7341_test_loop(void)
{
    as7341_sample_t sample = {0};

    if (as7341_begin() != 0) {
        ws63_log("AS7341 init failed\r\n");
        return;
    }

    ws63_log("AS7341 init ok\r\n");

    while (1) {
        if (as7341_read_sample(&sample) == 0) {
            as7341_print_json(&sample);
        } else {
            ws63_log("AS7341 read failed\r\n");
        }
        ws63_delay_ms(1000);
    }
}

#ifdef AS7341_STANDALONE_MAIN
int main(void)
{
    as7341_test_loop();
    return 0;
}
#endif

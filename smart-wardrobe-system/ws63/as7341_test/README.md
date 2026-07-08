# WS63 GY-AS7341 光谱传感器测试

这个目录放 WS63 端的 GY-AS7341 测试代码。目标是让 WS63 通过 I2C 读取光谱传感器，并通过串口输出一行一个 JSON，方便电脑端脚本读取。

## 接线

```text
GY-AS7341 VCC/VIN -> WS63 3.3V
GY-AS7341 GND     -> WS63 GND
GY-AS7341 SCL     -> WS63 SCL
GY-AS7341 SDA     -> WS63 SDA
```

GY-AS7341 默认 I2C 地址是 `0x39`。

## 输出格式

烧录成功后，串口应该周期性输出类似：

```json
{"device":"WS63","sensor":"GY-AS7341","f1":123,"f2":118,"f3":97,"f4":90,"f5":76,"f6":61,"f7":54,"f8":49,"clear":320,"nir":42}
```

然后在 Mac 上运行：

```bash
python smart-wardrobe-system/board/tools/test_ws63_serial.py \
  --port /dev/cu.wchusbserial130 \
  --baud 115200 \
  --post-to http://127.0.0.1:8000/api/ws63/sensor
```

## 移植到 WS63 工程

把 `as7341_spectral_test.c` 复制到 WS63 SDK 示例工程里，然后根据你们工程实际 API 替换文件顶部这 4 个函数：

```c
ws63_i2c_write_reg(...)
ws63_i2c_read_reg(...)
ws63_delay_ms(...)
ws63_log(...)
```

如果你们的 SDK 已经有 I2C 示例，直接把示例里的 I2C 读写函数封装成上面两个函数即可。

## 判断是否成功

- 如果串口还在打印 `APP|[SYS INFO] mem...`，说明当前烧录的仍然是默认程序或系统日志，不是光谱测试程序。
- 如果打印 `AS7341 not found`，先检查 VCC/GND/SCL/SDA 和 I2C 地址。
- 如果能打印 JSON，但数值一直为 0 或 65535，通常是积分时间、增益、光照或 I2C 读取顺序需要再调。

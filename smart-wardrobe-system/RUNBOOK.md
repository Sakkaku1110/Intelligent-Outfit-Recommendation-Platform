# 智能衣柜运行与调试手册

## 1. 当前部署位置

电脑端项目备份：

```text
C:\Users\t1507\Documents\嵌入式竞赛\smart-wardrobe-system
```

板子端运行目录：

```text
/root/workspace/smart-wardrobe
```

板子地址：

```text
192.168.137.2
```

手机端/电脑端浏览器访问：

```text
http://192.168.137.2
http://192.168.137.2:8000
```

## 2. 启动服务

在电脑 PowerShell 里：

```powershell
ssh hieulerpi
```

进入板子后：

```bash
cd /root/workspace/smart-wardrobe
bash scripts/run_server.sh
```

如果要后台运行：

```bash
cd /root/workspace/smart-wardrobe
bash scripts/stop_server.sh
setsid bash scripts/run_server.sh > data/server.log 2>&1 < /dev/null &
```

## 3. 停止服务

```bash
cd /root/workspace/smart-wardrobe
bash scripts/stop_server.sh
```

## 4. 快速检查

在电脑 PowerShell 里：

```powershell
ping 192.168.137.2
curl.exe http://192.168.137.2:8000/api/health
curl.exe http://192.168.137.2:8000/api/clothes
curl.exe "http://192.168.137.2:8000/api/recommendations?city=Hangzhou&occasion=school"
```

## 5. 摄像头调试

在板子上：

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
fswebcam -d /dev/video0 -r 640x480 -S 10 --no-banner /root/camera-test/check.jpg
```

正常情况：

- `/dev/video0` 是视频采集口
- `/dev/video1` 多数情况下是 UVC metadata
- `fswebcam` 能生成 jpg 图片

## 6. 入库流程

打开：

```text
http://192.168.137.2:8000
```

进入“入库”页：

- AI识别入库：板子调用 `/dev/video0` 拍照，保存图片，自动推测衣物类别、主体颜色和材质初值，并写入 SQLite
- 手动入库：不拍照，只记录衣物属性

当前识别能力：

- 颜色识别：根据衣物主体区域的 RGB/HSV 特征推测主体颜色，可靠性相对较高
- 类别识别：根据主体外接框比例推测上衣、下装、鞋子、外套，受摆放方式影响较大
- 材质识别：根据纹理、高光、饱和度粗略推测棉、牛仔、皮革、涤纶、毛织等，只作为初值，建议允许人工修正

## 7. 推荐流程

打开首页“试衣镜”页：

1. 输入城市，例如 `Hangzhou`
2. 选择场景，例如 `上课`
3. 点击刷新

后端会：

- 从互联网获取当前温度
- 读取 SQLite 里的已入库衣物
- 按温度、场景、季节、保暖值、颜色、偏好分生成推荐组合
- 返回推荐理由
- 在平板页面中展示推荐衣服组合；如果衣物有入库图片，会显示组合预览

### 7.1 可选云端大模型增强

板端 `/api/recommendations` 已支持可选的大模型增强推荐。默认不开启时继续使用本地规则推荐；开启后会把衣柜、天气、场景和本地规则结果发给云端 `/api/llm/recommend`，云端不可用时自动回退本地结果。

板端 `.env` 示例：

```bash
SMART_WARDROBE_LLM_ENABLED=true
SMART_WARDROBE_LLM_URL=http://YOUR_SERVER_IP/api/llm/recommend
SMART_WARDROBE_LLM_API_KEY=your-long-random-write-key
SMART_WARDROBE_LLM_TIMEOUT=6
```

状态检查：

```bash
curl http://192.168.137.2:8000/api/llm/status
curl "http://192.168.137.2:8000/api/recommendations?city=Hangzhou&occasion=school"
```

## 8. 平板触控屏方案

当前建议使用“平板浏览器 + 板端 Web 服务”的方式：

```text
SS928 板子运行后端和数据库
平板连接同一网络
平板浏览器打开 http://192.168.137.2
```

这种方案优点：

- 不需要给平板单独开发原生 App
- 平板触控天然可用
- 摄像头、数据库、推荐算法仍然在 SS928 上运行，符合边缘端项目逻辑
- 后续可以把平板固定在衣柜门上，浏览器全屏显示作为触控屏

如果以后要做真正内置屏：

- HDMI 触控屏：板子负责显示，触控通常通过 USB HID 回传
- Android 平板内嵌：板子只提供网页服务，平板作为独立触控终端
- 推荐优先使用 Android 平板方案，稳定、成本低、调试简单

## 9. WS63 串口测试

Mac 已经识别到 CH340 串口时，会看到类似：

```bash
ls /dev/cu.*
```

```text
/dev/cu.wchusbserial130
```

先只监听 WS63 输出：

```bash
python smart-wardrobe-system/board/tools/test_ws63_serial.py \
  --port /dev/cu.wchusbserial130 \
  --baud 115200 \
  --raw
```

如果 WS63 程序已经按“一行一个 JSON”输出光谱数据，可以直接转发到后端：

```bash
python smart-wardrobe-system/board/tools/test_ws63_serial.py \
  --port /dev/cu.wchusbserial130 \
  --baud 115200 \
  --post-to http://127.0.0.1:8000/api/ws63/sensor
```

建议 WS63 输出格式：

```json
{"device":"WS63","sensor":"GY-AS7341","channels":{"f1":123,"f2":118,"f3":97,"f4":90,"f5":76,"f6":61,"f7":54,"f8":49},"clear":320,"nir":42}
```

如果一直没有输出，优先检查：

- WS63 是否已经烧录了串口打印程序
- 波特率是否是 `115200`
- GY-AS7341 接线是否为 `VCC -> 3.3V`、`GND -> GND`、`SCL -> SCL`、`SDA -> SDA`
- 重新插拔 USB 后串口号是否变化

WS63 端读取 GY-AS7341 的测试代码在：

```text
smart-wardrobe-system/ws63/as7341_test/as7341_spectral_test.c
```

把它复制进 WS63 SDK 工程后，需要先用 SDK 的 I2C 函数替换文件顶部的：

```c
ws63_i2c_write_reg(...)
ws63_i2c_read_reg(...)
ws63_delay_ms(...)
ws63_log(...)
```

然后在 WS63 应用任务里调用：

```c
as7341_test_loop();
```

## 10. 常见问题

### 网页打不开

先检查：

```powershell
ping 192.168.137.2
curl.exe http://192.168.137.2/api/health
curl.exe http://192.168.137.2:8000/api/health
```

如果 ping 不通，先处理电脑和板子的网络；如果 ping 通但 8000 不通，重启后端服务。

现在服务同时监听两个端口：

- `http://192.168.137.2`：推荐给平板使用
- `http://192.168.137.2:8000`：调试端口

如果 ping 通但 curl 不通，优先在板子上检查：

```bash
systemctl status smart-wardrobe.service
ss -ltnp | grep ':80'
ss -ltnp | grep ':8000'
```

正常情况应该能看到 `python3` 同时监听 `0.0.0.0:80` 和 `0.0.0.0:8000`。

### 天气显示离线估计

说明板子暂时访问不了 Open-Meteo。先检查：

```bash
ping 223.5.5.5
ping api.open-meteo.com
```

网络恢复后刷新页面即可。

### 摄像头拍照失败

检查：

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
```

如果没有 `/dev/video0`，重新插拔摄像头或换 USB 口。

### 页面里衣物不够推荐

推荐至少需要：

- 1 件上衣
- 1 件下装
- 1 双鞋

低温时最好再加入 1 件外套。

# 云端 AI 预处理 + 边缘 AI 识别方案

## 推荐 API

推荐优先使用 **Google Gemini API**，原因是它的视觉能力支持直接做图像理解和 object detection，适合返回衣物主体的 bounding box。我们的需求不是让云端判断最终是哪件衣服，而是让云端从杂乱画面中找出“真正要入库的衣物主体”。

你需要申请：

```text
GEMINI_API_KEY
```

板子或电脑环境变量：

```bash
export GEMINI_API_KEY="你的 key"
export GEMINI_MODEL="gemini-2.5-flash"
```

Windows PowerShell：

```powershell
$env:GEMINI_API_KEY="你的 key"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

验证 key 是否能用：

```powershell
python smart-wardrobe-system\vision_lab\test_gemini_key.py
```

如果返回 `HTTP 401`，说明这枚 key 不能调用 Gemini。通常需要重新从 Google AI Studio 生成 Gemini API key，或在 Google Cloud 项目中启用 Generative Language API，并检查 key 的 API 限制和来源限制。

## 主链路

```text
板子摄像头原图
  -> 取景框裁剪
  -> 云端 Gemini 找衣物主体 bbox
  -> 生成主体裁剪图
  -> 板端边缘模型识别固定 7 件衣物
  -> 人工审核确认
  -> 入库/推荐/训练
```

如果没有网络或没有配置 API key，系统会自动回退：

```text
板子摄像头原图 -> 取景框裁剪 -> 板端边缘模型识别 -> 人工审核
```

## 电脑代理模式

如果板子能 ping 外网，但无法直接 HTTPS 访问 Google，可以让电脑作为云端代理。电脑访问 Gemini，板子只访问电脑。

电脑启动网关：

```powershell
$env:GEMINI_API_KEY="你的 key"
$env:GEMINI_MODEL="gemini-2.5-flash"
python smart-wardrobe-system\pc_gateway.py --host 0.0.0.0 --port 8088 --board http://192.168.137.2
```

板子 `/root/workspace/smart-wardrobe/.env` 增加：

```bash
SMART_WARDROBE_CLOUD_PROXY_URL=http://192.168.137.1:8088/__cloud/preprocess
```

然后重启板端服务：

```bash
systemctl restart smart-wardrobe.service
```

检查：

```powershell
curl.exe http://127.0.0.1:8088/__gateway
curl.exe http://192.168.137.2/api/vision/cloud/status
```

## 为什么不让云端直接做最终分类

云端更擅长处理复杂背景、手、衣架、床铺、桌面、窗帘和其他杂物干扰，适合做主体定位。

边缘模型更适合比赛演示中的固定衣柜分类。我们的目标是稳定识别 7 件固定衣物，而不是识别全世界所有服装。这样可以保留离线演示能力，也能降低网络、延迟、费用和隐私风险。

## 已实现功能

板端：

- `/api/health` 返回云端预处理配置状态。
- `/api/vision/cloud/status` 返回云端 provider、model、是否已配置。
- `/api/clothes/capture/analyze` 默认执行“取景框裁剪 -> 云端主体裁剪 -> 边缘识别”。
- 云端失败时自动回退，不影响拍照入库。

触控端：

- AI 入库页展示实时摄像头。
- 点击“拍照识别”后自动执行云边协同链路。
- 审核页显示云端主体提取状态和边缘模型识别结果。
- 人工确认后才真正入库。

数据集：

- 可以对已经采集的 `demo_dataset` 批量执行云端主体裁剪。
- 裁剪后的数据集可以再训练模型，提升边缘模型稳定性。

## 批量处理已采集数据集

先设置 key：

```powershell
$env:GEMINI_API_KEY="你的 key"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

生成云端裁剪后的数据集：

```powershell
python smart-wardrobe-system\vision_lab\cloud_preprocess_dataset.py --dataset smart-wardrobe-system\vision_lab\demo_dataset --out smart-wardrobe-system\vision_lab\demo_dataset_cloud --fallback-copy
```

训练云端裁剪后的数据集：

```powershell
python smart-wardrobe-system\vision_lab\train_demo_model.py --dataset smart-wardrobe-system\vision_lab\demo_dataset_cloud
```

推送模型到板子：

```powershell
python smart-wardrobe-system\vision_lab\deploy_demo_model.py --model smart-wardrobe-system\vision_lab\demo_dataset_cloud\vision_model.json --restart
```

## 比赛答辩表述

本项目采用“云边协同”的视觉链路。云端模型负责复杂场景下的衣物主体定位和背景干扰剔除，边缘端模型负责固定衣柜物品的低延迟分类和推荐决策。这样既提高了入库图片质量，也保留了嵌入式系统的本地运行能力。

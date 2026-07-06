# 视觉识别与数据集采集流程

这个目录用于给比赛演示衣物建立一个稳定的小数据集，并训练板端优先使用的演示识别模型。

## 0. 启动板子摄像头数据集采集台

先确认板子智能衣柜服务已经运行，并且电脑能访问：

```powershell
curl.exe http://192.168.137.2/api/health
```

在电脑上启动采集台：

```powershell
cd C:\Users\t1507\Documents\嵌入式竞赛
python smart-wardrobe-system\vision_lab\dataset_studio.py --host 0.0.0.0 --port 8090 --board-url http://192.168.137.2
```

电脑浏览器打开：

```text
http://127.0.0.1:8090
```

手机或平板连接同一个网络后打开：

```text
http://电脑WLAN地址:8090
```

## 1. 采集流程

1. 选择本次采集的衣物标签。
2. 左侧实时画面来自板子摄像头，把衣物放进取景框。
3. 点击“确认拍照”。
4. 右侧进入“人工审核”，检查裁剪图是不是可用。
5. 如果标签不对，在审核区改标签。
6. 点击“确认录入”，照片才会进入训练数据集。
7. 如果画面糊、太暗、衣服没放好，点击“丢弃重拍”。

样本库支持：

- 查询：页面下方直接显示所有已录入样本。
- 新增：确认拍照并审核录入。
- 修改：点样本卡片里的“修改”，可以重新选择标签。
- 删除：点样本卡片里的“删除”，会同时删除图片和 `labels.csv` 记录。

每件固定演示衣物建议先拍 12-20 张，包含：

- 正面完整图
- 稍微左转、右转
- 近一点、远一点
- 正常光、偏暗光
- 轻微模糊但还能看清主体

训练数据会保存在：

```text
smart-wardrobe-system\vision_lab\demo_dataset
```

训练结果会生成：

```text
smart-wardrobe-system\vision_lab\demo_dataset\vision_model.json
```

## 2. 训练并推送到板子

在网页中点击：

1. “训练模型”
2. “推送到板子”

也可以用命令行：

```powershell
python smart-wardrobe-system\vision_lab\train_demo_model.py --dataset smart-wardrobe-system\vision_lab\demo_dataset
python smart-wardrobe-system\vision_lab\deploy_demo_model.py --model smart-wardrobe-system\vision_lab\demo_dataset\vision_model.json --restart
```

推送后，板子会优先使用这个固定衣柜模型识别比赛演示衣物。

比赛现场更推荐直接在板子上训练，因为板子有 OpenCV，训练特征和推理特征完全一致：

```powershell
python smart-wardrobe-system\vision_lab\train_on_board.py --dataset smart-wardrobe-system\vision_lab\demo_dataset
```

## 2.1 云边协同主体提取

推荐申请 Google Gemini API key，并在板子服务环境中设置：

```bash
export GEMINI_API_KEY="你的 key"
export GEMINI_MODEL="gemini-2.5-flash"
```

如果要先处理已经采集好的数据集：

```powershell
$env:GEMINI_API_KEY="你的 key"
python smart-wardrobe-system\vision_lab\cloud_preprocess_dataset.py --dataset smart-wardrobe-system\vision_lab\demo_dataset --out smart-wardrobe-system\vision_lab\demo_dataset_cloud --fallback-copy
python smart-wardrobe-system\vision_lab\train_on_board.py --dataset smart-wardrobe-system\vision_lab\demo_dataset_cloud
```

如果没有配置 key，板端会自动回退到取景框裁剪，不影响入库演示。

## 3. 从板子同步已入库样本

如果已经在智能衣柜 App 里入库过衣服，可以同步出来做评测：

```powershell
python smart-wardrobe-system\vision_lab\sync_board_samples.py
```

如果电脑不能直连板子，可以改用电脑网关：

```powershell
python smart-wardrobe-system\vision_lab\sync_board_samples.py --base http://127.0.0.1:8088
```

输出目录：

```text
smart-wardrobe-system\vision_lab\samples
```

## 4. 批量评测当前算法

评测真实样本：

```powershell
python smart-wardrobe-system\vision_lab\evaluate_vision.py --labels smart-wardrobe-system\vision_lab\samples\labels.csv
```

生成模糊、暗光增强样本：

```powershell
python smart-wardrobe-system\vision_lab\augment_samples.py --labels smart-wardrobe-system\vision_lab\samples\labels.csv
```

评测增强样本：

```powershell
python smart-wardrobe-system\vision_lab\evaluate_vision.py --labels smart-wardrobe-system\vision_lab\samples_augmented\labels.csv
```

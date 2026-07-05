# 视觉识别调试流程

这个目录用于把“感觉识别不准”变成可量化的测试集。

## 0. 演示数据集采集 App

在电脑上启动：

```powershell
cd C:\Users\t1507\Documents\嵌入式竞赛
python smart-wardrobe-system\vision_lab\dataset_studio.py --host 0.0.0.0 --port 8090
```

电脑浏览器打开：

```text
http://127.0.0.1:8090
```

手机和平板连接同一个 Wi-Fi 后打开：

```text
http://电脑WLAN地址:8090
```

采集流程：

1. 选择一个固定衣物标签。
2. 把衣物放进取景框。
3. 点击“拍摄并上传”。
4. 每件衣物拍 8-12 张。
5. 点击“训练模型”。
6. 点击“推送到板子”。

训练结果会生成：

```text
smart-wardrobe-system\vision_lab\demo_dataset\vision_model.json
```

推送后板子会优先用这个样本模型识别固定演示衣物。

## 1. 从板子同步已入库样本

先确认电脑中转服务可用：

```powershell
curl.exe http://127.0.0.1:8088/api/health
```

同步图片和标签：

```powershell
cd C:\Users\t1507\Documents\嵌入式竞赛
python smart-wardrobe-system\vision_lab\sync_board_samples.py
```

输出目录：

```text
smart-wardrobe-system\vision_lab\samples
```

如果电脑不能直连板子，再改用 `--base http://127.0.0.1:8088`。

## 2. 生成模糊/暗光增强样本

```powershell
python smart-wardrobe-system\vision_lab\augment_samples.py --labels smart-wardrobe-system\vision_lab\samples\labels.csv
```

输出：

```text
smart-wardrobe-system\vision_lab\samples_augmented
```

## 3. 批量评测当前算法

评测真实样本：

```powershell
python smart-wardrobe-system\vision_lab\evaluate_vision.py --labels smart-wardrobe-system\vision_lab\samples\labels.csv
```

评测增强样本：

```powershell
python smart-wardrobe-system\vision_lab\evaluate_vision.py --labels smart-wardrobe-system\vision_lab\samples_augmented\labels.csv
```

每次调整算法后都跑一遍，观察：

- 类别准确率
- 颜色族准确率
- 类别混淆矩阵
- 每张图片的预测结果

## 4. 推荐采样方式

每类至少先拍 15 张：

- 上衣：挂着、手拿、折叠、局部遮挡
- 裤子：竖着拿、横着拿、只露半截
- 鞋子：单只、双只、手拿、鞋底朝外
- 外套：展开、半折叠、深色和浅色各一批

拍完在 App 的 AI识别结果页人工改准，再入库。同步出来的标签才可以当作评测真值。

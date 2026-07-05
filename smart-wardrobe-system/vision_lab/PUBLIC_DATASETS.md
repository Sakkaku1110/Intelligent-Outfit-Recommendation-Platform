# 可参考的公开衣物数据集

公开数据集适合做离线验证和后续训练，但比赛现场最终仍应优先使用开发板摄像头拍到的真实样本做校准。

## DeepFashion2

- 地址：https://github.com/switchablenorms/DeepFashion2
- 适合：衣物检测、类别、遮挡、视角变化、用户实拍和商拍对比。
- 注意：需要按官方说明申请/下载数据，体量较大。

## Fashionpedia

- 地址：https://fashionpedia.github.io/home/
- 适合：细粒度衣物类别、属性、分割标注。
- 注意：适合训练更复杂模型；对 SS928 端直接跑大模型不一定划算，可以先在电脑训练或导出轻量模型。

## Open Images

- 地址：https://storage.googleapis.com/openimages/web/index.html
- 适合：筛选 Shoe、Shirt、Dress、Pants 等大类做泛化测试。
- 注意：数据非常大，标签广，筛选和清洗成本高。

## 当前建议

1. 先用 `sync_board_samples.py` 同步自己的入库图片。
2. 用 `augment_samples.py` 生成暗光、模糊、噪声版本。
3. 用 `evaluate_vision.py` 看当前规则算法的真实准确率。
4. 当每类真实样本超过 50 张后，再考虑引入公开数据集训练一个轻量分类器。

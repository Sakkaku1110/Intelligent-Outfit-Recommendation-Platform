# 手机/平板访问方案

## 推荐地址

如果手机、平板或另一台电脑不能直接打开开发板地址，就让这台电脑做中转。

当前电脑中转地址：

```text
http://192.168.43.9:8088
```

开发板本机地址仍然是：

```text
http://192.168.137.2
http://192.168.137.2:8000
```

## 为什么要这样做

开发板现在在 `192.168.137.x` 网段，手机/平板通常在 Wi-Fi 网段。两边能不能互相访问，取决于 Windows 共享网络、路由和防火墙。电脑中转服务会让手机/平板访问电脑，再由电脑转发到开发板，稳定性更高。

当前 `pc_gateway.py` 会直接从电脑提供最新版触控端页面，`/api/*`、`/uploads/*`、摄像头流和入库请求再转发到开发板。这样即使开发板上的静态页面还没有同步，手机/平板打开 `http://192.168.43.9:8088` 也能看到最新 UI。

## 启动电脑中转服务

在这台电脑的 PowerShell 里执行：

```powershell
cd C:\Users\t1507\Documents\嵌入式竞赛
python smart-wardrobe-system\pc_gateway.py --host 0.0.0.0 --port 8088 --board http://192.168.137.2:8000
```

如果想隐藏到后台运行：

```powershell
cd C:\Users\t1507\Documents\嵌入式竞赛
Start-Process -WindowStyle Hidden -FilePath python -ArgumentList 'smart-wardrobe-system\pc_gateway.py --host 0.0.0.0 --port 8088 --board http://192.168.137.2:8000'
```

## 检查是否成功

在电脑上执行：

```powershell
curl.exe http://127.0.0.1:8088/__gateway
curl.exe http://127.0.0.1:8088/api/health
curl.exe http://192.168.43.9:8088/api/health
```

三个命令能返回内容，说明电脑中转已经通了。

## 手机/平板打不开时

1. 确认手机/平板和电脑在同一个 Wi-Fi 或热点网络下。
2. 在手机浏览器打开 `http://192.168.43.9:8088`。
3. 如果仍打不开，Windows 弹出防火墙提示时允许 Python 访问专用网络。
4. 如果电脑 Wi-Fi 地址变了，重新查地址：

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' } | Select-Object InterfaceAlias,IPAddress
```

优先使用 `WLAN` 对应的地址，把端口 `:8088` 加在后面。

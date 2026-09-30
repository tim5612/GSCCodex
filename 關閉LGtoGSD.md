# 關閉 LGDevB，切換到 GSD

## 快速方式（建議）

先開啟「系統管理員 PowerShell」，切換到專案資料夾，再執行：

```powershell
.\關閉LGtoGSD.bat
```

接著依畫面提示貼入 GSD Token。

Token 只會保存在該次執行視窗的暫存變數中，不會寫入 BAT 檔案。

BAT 會先檢查 `http://127.0.0.1:5000`；如果 OCR 尚未啟動，會自動在另一個視窗執行純英文輔助檔 `start_GSD_OCR.bat`。OCR 模型可能需要約 20 秒載入，Tunnel 會在服務可用後自動恢復連線。

以下內容是需要手動操作時使用的完整步驟。

> 請使用「以系統管理員身分執行」的 PowerShell，依順序逐項操作。
>
> 此操作只會暫停 LGDevB，不會刪除 LGDevB 的服務或設定。

## 1. 先啟動 GSD OCR 程式

在專案資料夾中雙擊：

```text
啟動OCR服務.bat
```

等待 OCR 模型載入完成，並確認電腦瀏覽器可以開啟：

```text
http://127.0.0.1:5000
```

## 2. 停止 LGDevB 的 Cloudflared 服務

在系統管理員 PowerShell 執行：

```powershell
Stop-Service Cloudflared
```

檢查服務狀態：

```powershell
Get-Service Cloudflared
```

確認 `Status` 顯示為 `Stopped`。

## 3. 填入 GSD Token

從 Cloudflare 的 `Networking → Tunnels → GSD → Overview` 複製 GSD Token。

把下方 `請貼上GSD的Token` 換成真正的 Token，保留左右單引號：

```powershell
$GSD_TOKEN = '請貼上GSD的Token'
```

Token 是機密資料，不要傳給其他人，也不要貼到聊天或截圖中。

## 4. 啟動 GSD Tunnel

```powershell
cloudflared.exe tunnel run --token $GSD_TOKEN
```

這項命令會持續運行，因此 PowerShell 不會回到提示字元，這是正常現象。請保持這個視窗開啟。

稍等約 10～30 秒後，確認 Cloudflare 上的 GSD 狀態變成 `Healthy`，再用手機開啟：

```text
https://gsd.superb-supplies.com.tw
```

## 注意事項

- GSD 使用期間，請勿關閉執行 Tunnel 的 PowerShell 視窗。
- GSD 使用期間，請勿重新執行 `Start-Service Cloudflared`，否則 LGDevB 也會重新連線。
- 不要執行 `cloudflared service uninstall`。
- 電腦重新開機後，GSD 前景命令不會自動執行；原本安裝的 LGDevB 服務會自動啟動。

# 關閉 GSD，切換回 LGDevB

## 快速方式（建議）

先開啟「系統管理員 PowerShell」，切換到專案資料夾，再執行：

```powershell
.\關閉GSDtoLG.bat
```

批次檔會停止 GSD，並恢復 LGDevB 的 Windows 服務。

以下內容是需要手動操作時使用的完整步驟。

> 請在目前執行 GSD Tunnel 的 PowerShell 視窗停止 GSD，再使用「以系統管理員身分執行」的 PowerShell 恢復 LGDevB。

## 1. 停止 GSD Tunnel

切換到正在顯示 GSD Tunnel 訊息的 PowerShell 視窗，按下：

```text
Ctrl+C
```

等待命令停止並重新出現 PowerShell 提示字元。

## 2. 清除目前視窗中的 GSD Token 變數

```powershell
Remove-Variable GSD_TOKEN -ErrorAction SilentlyContinue
```

關閉該 PowerShell 視窗也能清除這個暫存變數。

## 3. 啟動 LGDevB 的 Cloudflared 服務

在系統管理員 PowerShell 執行：

```powershell
Start-Service Cloudflared
```

## 4. 確認服務已恢復

```powershell
Get-Service Cloudflared
```

確認 `Status` 顯示為 `Running`。

稍等約 10～30 秒，再到 Cloudflare 的 Tunnels 頁面確認 `LGDevB` 顯示為 `Healthy`。

## 5. 如果不再使用 GSD OCR

可以關閉 `啟動OCR服務.bat` 的執行視窗，或在該視窗按下：

```text
Ctrl+C
```

## 注意事項

- 不需要重新輸入 LGDevB Token。
- 不需要重新安裝 Cloudflared。
- 不要執行 `cloudflared service uninstall`。
- LGDevB 已安裝為 Windows 自動啟動服務；電腦重新開機後會預設啟動 LGDevB。

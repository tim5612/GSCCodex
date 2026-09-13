# 外箱型號 OCR 測試

本機 Python + HTML 原型，處理步驟為：白色標籤定位、沿輪廓取得四個真實角點、梯形透視校正、上方區域裁切、EasyOCR 辨識、型號候選抽取。

## 啟動

```powershell
python app.py
```

再開啟 <http://127.0.0.1:5000>，上傳專案根目錄的 `LGSample.png`。

本專案使用 Python 3.12 虛擬環境與 CPU 版 PyTorch 2.5.1。要啟用本機 OCR，執行：

```powershell
$env:ENABLE_EASYOCR="1"
python app.py
```

EasyOCR 第一次使用時可能需要下載英文辨識模型。正式部署時應預先準備模型，避免現場臨時下載。

## 判讀原則

- 系統只會統一大小寫、空白及破折號。
- 系統不會自動互換 `8/B`、`0/O`、`1/I`、`5/S` 等易混淆字元。
- OCR 結果仍須由人員對照裁切後的原始照片確認。

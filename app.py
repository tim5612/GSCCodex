from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
import uuid
from datetime import date
from pathlib import Path

import cv2
import numpy as np
import qrcode
from flask import Flask, abort, jsonify, render_template, request, send_from_directory


APP_DIR = Path(__file__).resolve().parent
CAPTURE_DIR = APP_DIR / "data" / "captures"
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)

_reader = None
_reader_lock = threading.Lock()


def encode_png(image: np.ndarray) -> str:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("無法編碼處理後的圖片")
    return "data:image/png;base64," + base64.b64encode(encoded).decode("ascii")


def order_points(points: np.ndarray) -> np.ndarray:
    points = points.astype("float32")
    result = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    result[0] = points[np.argmin(sums)]       # top-left
    result[2] = points[np.argmax(sums)]       # bottom-right
    result[1] = points[np.argmin(differences)]  # top-right
    result[3] = points[np.argmax(differences)]  # bottom-left
    return result


def warp_from_points(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = order_points(points)
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if width < 80 or height < 40:
        raise ValueError("偵測到的標籤太小")

    target = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl]), target)
    warped = cv2.warpPerspective(image, matrix, (width, height))
    if warped.shape[0] > warped.shape[1]:
        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
    return warped


def contour_to_quadrilateral(contour: np.ndarray) -> np.ndarray | None:
    """Return four real contour corners instead of a rotated bounding box."""
    hull = cv2.convexHull(contour)
    perimeter = cv2.arcLength(hull, True)
    for epsilon_ratio in np.linspace(0.008, 0.08, 30):
        approximate = cv2.approxPolyDP(hull, epsilon_ratio * perimeter, True)
        if len(approximate) == 4 and cv2.isContourConvex(approximate):
            return approximate.reshape(4, 2).astype("float32")
    return None


def find_white_label(image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width = image.shape[:2]
    scale = min(1.0, 1400.0 / max(height, width))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    # Printed white stock stays bright with relatively low saturation.
    # Keep the threshold deliberately strict so pale cardboard or a concrete wall
    # does not merge into one enormous "white" candidate.
    mask = cv2.inRange(hsv, np.array([0, 0, 160]), np.array([179, 65, 255]))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = small.shape[0] * small.shape[1]
    best = None
    best_contour = None
    best_score = -1.0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * 0.015 or area > image_area * 0.35:
            continue
        rect = cv2.minAreaRect(contour)
        rw, rh = rect[1]
        if min(rw, rh) < 30:
            continue
        aspect = max(rw, rh) / min(rw, rh)
        if not 1.25 <= aspect <= 4.5:
            continue
        rectangularity = area / max(rw * rh, 1)
        if rectangularity < 0.55:
            continue
        # Favor a clean rectangle with useful size; do not require fixed position.
        score = area * rectangularity * (1.0 if 1.5 <= aspect <= 3.5 else 0.75)
        if score > best_score:
            best_score = score
            best_contour = contour
            best = contour_to_quadrilateral(contour)

    if best_contour is None:
        raise ValueError("找不到白色矩形標籤，請靠近並讓標籤完整入鏡")

    # A rectangular fallback keeps unusual/damaged labels usable, but ordinary
    # trapezoidal labels use the four actual contour corners above.
    if best is None:
        best = cv2.boxPoints(cv2.minAreaRect(best_contour))

    points = best / scale
    preview = image.copy()
    cv2.polylines(preview, [points.astype(np.int32)], True, (40, 220, 40), 8)
    return warp_from_points(image, points), preview, mask


def prepare_model_region(label: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # The model occupies the top band in this label family.
    crop_height = max(1, int(label.shape[0] * 0.24))
    region = label[:crop_height, :]
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    enhanced = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return region, enhanced


def get_reader():
    global _reader
    with _reader_lock:
        if _reader is None:
            import easyocr

            # The fixed label layout has already isolated the single model line,
            # so the heavier free-form text detector is unnecessary here.
            _reader = easyocr.Reader(["en"], gpu=False, detector=False)
    return _reader


def run_ocr(enhanced: np.ndarray) -> tuple[list[tuple], str | None]:
    # Torch currently does not support every newly released Python version. Keep
    # geometry testing available even when the local OCR runtime is unavailable.
    if os.environ.get("ENABLE_EASYOCR") != "1":
        return [], "本機 OCR 尚未啟用；請用 Python 3.12 安裝套件後設定 ENABLE_EASYOCR=1"
    try:
        return get_reader().recognize(
            enhanced,
            detail=1,
            paragraph=False,
            allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
        ), None
    except Exception as exc:
        return [], f"EasyOCR 無法執行：{exc}"


def normalize_model(value: str) -> str:
    value = value.upper().translate(str.maketrans({"–": "-", "—": "-", "－": "-", "_": "-"}))
    value = re.sub(r"\s*-\s*", "-", value)
    return re.sub(r"\s+", "", value).strip("-:;,.|_")


def choose_model(ocr_items: list[tuple]) -> tuple[str, str, float]:
    candidates = []
    for _, text, confidence in ocr_items:
        normalized = normalize_model(text)
        # A model must contain letters and digits and normally contains a separator.
        if (
            5 <= len(normalized) <= 28
            and re.fullmatch(r"[A-Z0-9-]+", normalized)
            and re.search(r"[A-Z]", normalized)
            and re.search(r"\d", normalized)
        ):
            score = float(confidence) + (0.25 if "-" in normalized else 0)
            candidates.append((score, text, normalized, float(confidence)))

    # OCR sometimes splits the two sides of the dash into separate boxes.
    joined_raw = "-".join(str(item[1]) for item in ocr_items)
    joined = normalize_model(joined_raw)
    if 5 <= len(joined) <= 28 and re.fullmatch(r"[A-Z0-9-]+", joined):
        joined_confidence = min((float(item[2]) for item in ocr_items), default=0.0)
        candidates.append((joined_confidence + 0.20, joined_raw, joined, joined_confidence))

    if not candidates:
        return "", "", 0.0
    _, raw, normalized, confidence = max(candidates, key=lambda item: item[0])
    return raw, normalized, confidence


def analyze(image: np.ndarray) -> dict:
    label, detected_preview, _ = find_white_label(image)
    model_region, enhanced = prepare_model_region(label)
    results, ocr_error = run_ocr(enhanced)
    raw, model, confidence = choose_model(results)
    return {
        "model": model,
        "modelOriginal": raw,
        "confidence": round(confidence, 4),
        "needsReview": confidence < 0.80 or not model,
        "ocrError": ocr_error,
        "ocrItems": [
            {"text": str(item[1]), "confidence": round(float(item[2]), 4)} for item in results
        ],
        "_artifacts": {
            "detected": detected_preview,
            "rectified": label,
            "modelRegion": model_region,
            "enhanced": enhanced,
        },
    }


def write_image(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise ValueError(f"無法儲存圖片：{path.name}")
    encoded.tofile(str(path))


def find_capture_dir(capture_id: str) -> Path | None:
    try:
        normalized = str(uuid.UUID(capture_id))
    except ValueError:
        return None
    matches = list(CAPTURE_DIR.glob(f"*/{normalized}"))
    return matches[0] if matches else None


def clean_qr_value(value: object, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"請輸入{label}")
    if "|" in text:
        raise ValueError(f"{label}不可包含 | 符號")
    if len(text) > 80:
        raise ValueError(f"{label}內容過長")
    return text


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/analyze")
def api_analyze():
    started_at = time.perf_counter()
    uploaded = request.files.get("image")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "請選擇照片"}), 400
    data = np.frombuffer(uploaded.read(), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        return jsonify({"error": "無法讀取這張圖片"}), 400
    try:
        result = analyze(image)
        artifacts = result.pop("_artifacts")
        capture_id = str(uuid.uuid4())
        folder = CAPTURE_DIR / date.today().isoformat() / capture_id
        folder.mkdir(parents=True)

        write_image(folder / "original.jpg", image)
        write_image(folder / "rectified.png", artifacts["rectified"])
        write_image(folder / "model-region.png", artifacts["modelRegion"])
        write_image(folder / "enhanced.png", artifacts["enhanced"])
        metadata = {
            "captureId": capture_id,
            "capturedDate": date.today().isoformat(),
            "ocrModel": result["model"],
            "ocrOriginal": result["modelOriginal"],
            "ocrConfidence": result["confidence"],
        }
        (folder / "capture.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        result["captureId"] = capture_id
        result["imageUrls"] = {
            "original": f"/api/captures/{capture_id}/original.jpg",
            "rectified": f"/api/captures/{capture_id}/rectified.png",
            "modelRegion": f"/api/captures/{capture_id}/model-region.png",
        }
        result["processingMs"] = round((time.perf_counter() - started_at) * 1000)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:
        app.logger.exception("Image analysis failed")
        return jsonify({"error": f"辨識失敗：{exc}"}), 500


@app.get("/api/captures/<capture_id>/<filename>")
def capture_file(capture_id: str, filename: str):
    allowed = {"original.jpg", "rectified.png", "model-region.png", "enhanced.png", "qr.png"}
    folder = find_capture_dir(capture_id)
    if folder is None or filename not in allowed or not (folder / filename).is_file():
        abort(404)
    return send_from_directory(folder, filename)


@app.post("/api/create-qr")
def create_qr():
    data = request.get_json(silent=True) or {}
    folder = find_capture_dir(str(data.get("captureId", "")))
    if folder is None or not (folder / "rectified.png").is_file():
        return jsonify({"error": "請先拍攝並保存標籤照片"}), 400
    try:
        model = clean_qr_value(data.get("model"), "商品型號")
        serial = clean_qr_value(data.get("serialNumber"), "S/NO")
        qr_date = date.fromisoformat(clean_qr_value(data.get("date"), "日期")).isoformat()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    input_method = str(data.get("inputMethod") or "manual")
    if input_method not in {"ocr", "barcode", "manual"}:
        input_method = "manual"
    payload = f"{model}|{serial}|{qr_date}"
    qr_image = qrcode.make(payload)
    qr_image.save(folder / "qr.png")
    record = {
        "captureId": folder.name,
        "model": model,
        "serialNumber": serial,
        "date": qr_date,
        "payload": payload,
        "modelInputMethod": input_method,
        "photoConfirmed": True,
    }
    (folder / "result.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return jsonify({
        "payload": payload,
        "qrUrl": f"/api/captures/{folder.name}/qr.png?v={uuid.uuid4().hex[:8]}",
        "record": record,
    })


if __name__ == "__main__":
    if os.environ.get("ENABLE_EASYOCR") == "1":
        print("正在預載 EasyOCR 模型…", flush=True)
        started_at = time.perf_counter()
        get_reader()
        print(f"EasyOCR 已就緒（{time.perf_counter() - started_at:.1f} 秒）", flush=True)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

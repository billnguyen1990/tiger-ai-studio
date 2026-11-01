import os
import time
import base64
import requests
import cv2
from concurrent.futures import ThreadPoolExecutor

DIR_NAME = os.path.dirname(os.path.abspath(__file__))
from camera_service import capture_camera_snapshot

_GEMINI_KEY_B64 = "QVEuQWI4Uk42Si1IcTFRUi1pcURTeV9CRGxDMXFmbE84bG5haExCbUNGRzFSamdKeXhuSkE="
HARDCODED_DEFAULT_GEMINI_KEY = base64.b64decode(_GEMINI_KEY_B64).decode("utf-8")

def get_gemini_api_key():
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    config_file = os.path.join(DIR_NAME, "gemini_config.json")
    if not os.path.exists(config_file):
        config_file = os.path.join(os.path.dirname(DIR_NAME), "gemini_config.json")
    if os.path.exists(config_file):
        try:
            import json
            with open(config_file, "r", encoding="utf-8") as f:
                k = json.load(f).get("gemini_api_key", "").strip()
                if k:
                    return k
        except Exception:
            pass
    return HARDCODED_DEFAULT_GEMINI_KEY

def analyze_warehouse_camera_image(image_path, hub_name):
    """Sử dụng Gemini 3.5 Flash Vision phân tích hiện trường kho bãi thời gian thực"""
    api_key = get_gemini_api_key()
    if not api_key or not os.path.exists(image_path):
        return None

    try:
        # Resize nhẹ để API phản hồi tức thì trong 1.5 - 2 giây
        img = cv2.imread(image_path)
        if img is None:
            return None
        img_resized = cv2.resize(img, (800, 450))
        _, buf = cv2.imencode('.jpg', img_resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
        img_b64 = base64.b64encode(buf).decode('utf-8')

        prompt = f"""Bạn là 'Tiger AI - Trợ Lý Giám Sát Vận Hành Kho Bãi GHN Logistics'.
Hãy quan sát bức ảnh camera an ninh tại {hub_name} và đưa ra báo cáo giám sát thông minh:
1. 🚚 Bãi xe & Dock: Số lượng xe tải/phương tiện (nêu biển số nếu thấy rõ), tình trạng dock bốc dỡ có bị kẹt hay thông thoáng?
2. 📦 5S & An Toàn: Lối đi, hàng hóa có chướng ngại vật hay nguy cơ đổ ngã không?
3. ☀️ Thời tiết & Ánh sáng: Nắng, mưa hay tối?
4. 🤖 ĐÁNH GIÁ VẬN HÀNH: Tóm tắt 1 câu [BÌNH THƯỜNG / CẦN LƯU Ý / CẢNH BÁO] và đề xuất hành động.

Viết ngắn gọn, chuyên nghiệp, có icon, trình bày gạch đầu dòng rõ ràng để gửi Telegram."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                    {"text": prompt}
                ]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 600
            }
        }
        res = requests.post(url, json=payload, timeout=20)
        if res.status_code == 200:
            ans = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return ans
        else:
            print(f"[Vision Guard Error] Status {res.status_code}: {res.text[:200]}")
    except Exception as e:
        print(f"Error analyzing image with Gemini: {e}")
    return None

def run_vision_guard_audit(hub_key="cairang", cam_id=None):
    """Chụp ảnh và phân tích tức thì 1 kho"""
    ok, msg, snap_path = capture_camera_snapshot(hub_key, cam_id)
    if not ok or not snap_path:
        return False, f"Không thể lấy luồng camera: {msg}", None, None

    analysis = analyze_warehouse_camera_image(snap_path, msg)
    return True, msg, snap_path, analysis

if __name__ == "__main__":
    print("Testing Vision Guard on Cái Răng...")
    ok, msg, snap, analysis = run_vision_guard_audit("cairang", 8)
    print("Result:", ok, msg)
    print("Analysis:\n", analysis)

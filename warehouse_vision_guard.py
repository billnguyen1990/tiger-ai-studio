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

def analyze_warehouse_camera_image(image_path, hub_name, is_indoor=True):
    """Sử dụng Gemini 3.5 Flash Vision phân tích thanh tra hiện trường kho bãi khắt khe 100%"""
    api_key = get_gemini_api_key()
    if not api_key or not os.path.exists(image_path):
        return None

    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        img_resized = cv2.resize(img, (800, 450))
        _, buf = cv2.imencode('.jpg', img_resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_b64 = base64.b64encode(buf).decode('utf-8')

        if is_indoor:
            prompt = f"""Bạn là 'Tiger AI - Trưởng Ban Giám Sát Thanh Tra Vận Hành & 5S Kho Bãi GHN Logistics'.
Hãy soi thật kỹ bức ảnh camera an ninh BÊN TRONG SÀN KHO tại {hub_name} và đưa ra kết luận thanh tra cực kỳ chuẩn xác, khắt khe, tuyệt đối không bao biện hay nhận định hời hợt:

1. 🚨 SOI LỖI HÀNG HÓA ĐẶT DƯỚI NỀN ĐẤT / SÀN BÊ TÔNG (QUAN TRỌNG NHẤT):
   - Có bất kỳ thùng carton, kiện hàng, bọc bao nào bị ĐỂ TRỰC TIẾP DƯỚI SÀN BÊ TÔNG MÀ KHÔNG KÊ LÊN PALLET không? (Chỉ rõ vị trí: góc trái, góc phải, chân tường, giữa sàn...).
   - Nếu có hàng dưới đất: BẮT BUỘC KẾT LUẬN LÀ VI PHẠM 5S NGHIÊM TRỌNG, nguy cơ ngấm ẩm hư hỏng bao bì hàng hóa!

2. 📦 HIỆN TRẠNG PALLET & THIẾT BỊ SÀN KHO:
   - Các pallet xếp gọn gàng hay ngổn ngang lộn xộn?
   - Xe nâng tay (pallet jack), xe đẩy có để đúng nơi quy định không (có bị để trên mặt pallet hoặc chặn lối đi không)?

3. 🧹 TIÊU CHUẨN 5S & RỦI RO:
   - Lối đi có bị cản trở không? Hàng hóa có nguy cơ đổ ngã hay va quẹt không?

4. 🎯 KẾT LUẬN THANH TRA:
   - 🔴 [CẢNH BÁO VI PHẠM 5S]: Nếu có hàng để dưới đất hoặc pallet/xe nâng ngổn ngang.
   - 🟢 [ĐẠT CHUẨN 5S]: CHỈ KHI 100% hàng hóa được kê trên pallet và sàn kho gọn gàng hoàn hảo.
   - Đề xuất hành động chấn chỉnh dứt khoát cho Thủ kho / NVXL."""
        else:
            prompt = f"""Bạn là 'Tiger AI - Trưởng Ban Giám Sát Thanh Tra Vận Hành Bãi Xe & Dock GHN Logistics'.
Hãy quan sát bức ảnh camera an ninh NGOÀI TRỜI BÃI XE tại {hub_name}:
1. 🚚 Bãi xe & Dock: Số lượng xe tải/phương tiện (nêu biển số nếu thấy rõ), tình trạng dock bốc dỡ có bị kẹt hay thông thoáng?
2. 📦 An Toàn 5S bãi: Lối đi xe tải, cổng có chướng ngại vật hay hàng hóa để ngoài trời không?
3. ☀️ Thời tiết & Ánh sáng: Nắng, mưa hay tối?
4. 🤖 ĐÁNH GIÁ VẬN HÀNH: Tóm tắt 1 câu [BÌNH THƯỜNG / CẦN LƯU Ý / CẢNH BÁO]."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                    {"text": prompt}
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
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

def run_vision_guard_audit(hub_key="cairang", cam_id=None, is_indoor=True):
    """Chụp ảnh và phân tích tức thì 1 kho"""
    ok, msg, snap_path = capture_camera_snapshot(hub_key, cam_id)
    if not ok or not snap_path:
        return False, f"Không thể lấy luồng camera: {msg}", None, None

    analysis = analyze_warehouse_camera_image(snap_path, msg, is_indoor=is_indoor)
    return True, msg, snap_path, analysis

if __name__ == "__main__":
    print("Testing Vision Guard strict inspection...")
    ok, msg, snap, analysis = run_vision_guard_audit("vithanh", 6, is_indoor=True)
    print("Result:", ok, msg)
    print("Analysis:\n", analysis)

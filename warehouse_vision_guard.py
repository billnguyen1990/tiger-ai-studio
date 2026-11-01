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

def analyze_warehouse_camera_image(image_path, hub_name, cam_label="Sàn kho", is_indoor=True):
    """Sử dụng Gemini Vision phân tích thanh tra hiện trường kho bãi khắt khe 100% theo tiêu chuẩn 5S GHN"""
    api_key = get_gemini_api_key()
    if not api_key or not os.path.exists(image_path):
        return None

    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        img_resized = cv2.resize(img, (960, 540))
        _, buf = cv2.imencode('.jpg', img_resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_b64 = base64.b64encode(buf).decode('utf-8')

        if is_indoor:
            prompt = f"""Bạn là 'Tiger AI - Trưởng Ban Giám Sát Thanh Tra Vận Hành & Tiêu Chuẩn 5S Kho Bãi GHN Logistics'.
Hãy soi thật kỹ bức ảnh camera an ninh BÊN TRONG SÀN KHO chứa hàng tại {hub_name} ({cam_label}) và đưa ra kết luận thanh tra cực kỳ chuẩn xác, khắt khe, trung thực 100% với thực tế:

1. 🚨 SOI LỖI HÀNG HÓA TIẾP XÚC TRỰC TIẾP DƯỚI NỀN ĐẤT / SÀN BÊ TÔNG (TIÊU CHUẨN SỐ 1 GHN):
   - Quan sát kỹ nền bê tông, chân tường, góc kho và khoảng trống giữa các pallet: Có bất kỳ kiện hàng/thùng carton nào ĐANG BỊ ĐẶT TRỰC TIẾP DƯỚI NỀN SÀN BÊ TÔNG MÀ KHÔNG KÊ LÊN PALLET KHÔNG?
   - Chỉ rõ vị trí cụ thể (ví dụ: góc phải sàn, cạnh tường, giữa sàn...).
   - Nếu có hàng đặt dưới sàn: BẮT BUỘC ĐÁNH DẤU ❌ [VI PHẠM 5S NGHIÊM TRỌNG] vì vi phạm quy định chống ẩm mốc và bảo quản hàng hóa GHN!

2. 🚜 SOI HIỆN TRẠNG PALLET RỖNG & XE NÂNG TAY (PALLET JACK):
   - Pallet rỗng có được xếp chồng vuông vắn gọn gàng vào khu vực quy định không, hay để rải rác ngổn ngang chiếm dụng sàn?
   - Xe nâng tay (pallet jack) có để lung tung giữa sàn kho hay trên mặt pallet gây cản trở lối đi và mất an toàn lao động không?

3. 📦 MẬT ĐỘ HÀNG HÓA & LỐI THOÁT HIỂM / LỐI VẬN HÀNH:
   - Sàn kho tồn nhiều hay ít hàng, lối đi chính cho luồng di chuyển có thông thoáng không?

4. 🎯 KẾT LUẬN THANH TRA:
   - 🔴 [CẢNH BÁO VI PHẠM 5S]: Nếu có hàng để dưới sàn đất HOẶC pallet/xe nâng ngổn ngang. Nêu rõ việc cần làm chấn chỉnh ngay lập tức (kê hàng lên pallet, xếp xe nâng gọn gàng).
   - 🟢 [ĐẠT CHUẨN 5S]: CHỈ KHI 100% kiện hàng nằm trên pallet và mặt sàn kho hoàn toàn sạch sẽ, gọn gàng."""
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

    from camera_service import VR_MAP, CAM_DESC_MAP
    hub_info = VR_MAP.get(hub_key.lower().strip(), VR_MAP["cairang"])
    hub_name = hub_info["name"]
    cid = cam_id or hub_info.get("default_cam", 2)
    label = CAM_DESC_MAP.get((hub_info["vr_id"], int(cid)), "Khu vực kho")

    analysis = analyze_warehouse_camera_image(snap_path, hub_name, cam_label=label, is_indoor=is_indoor)
    return True, analysis or "Không có phản hồi phân tích", snap_path, label

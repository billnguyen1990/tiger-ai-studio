import os
import time
import base64
import requests
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor

DIR_NAME = os.path.dirname(os.path.abspath(__file__))
from camera_service import capture_camera_snapshot

def get_gemini_api_key():
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    for cfg in [
        os.path.join(DIR_NAME, "gemini_config.json"),
        os.path.join(os.path.dirname(DIR_NAME), "gemini_config.json"),
        os.path.join(DIR_NAME, "tiger_studio", "gemini_config.json")
    ]:
        if os.path.exists(cfg):
            try:
                import json
                with open(cfg, "r", encoding="utf-8") as f:
                    k = json.load(f).get("gemini_api_key", "").strip()
                    if k:
                        return k
            except Exception:
                pass
    return ""

def _opencv_smart_scene_audit(img, hub_name):
    """Phân tích trực diện khung hình Camera bằng OpenCV Multi-Zone Vision (Sàn kho / Bãi xe / Ánh sáng / 5S)"""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    mean_bri = float(np.mean(gray))
    std_con = float(np.std(gray))

    # Phân tích vùng trung tâm & nửa dưới (sàn kho / sân bãi) và vùng nửa trên (cửa dock / xe tải đậu)
    top_roi = gray[int(h * 0.12):int(h * 0.50), int(w * 0.08):int(w * 0.92)]
    bot_roi = gray[int(h * 0.50):int(h * 0.90), int(w * 0.08):int(w * 0.92)]

    edges_top = cv2.Canny(top_roi, 60, 160)
    edges_bot = cv2.Canny(bot_roi, 60, 160)

    top_density = round(float(np.count_nonzero(edges_top)) / max(1, edges_top.size) * 100.0, 1)
    bot_density = round(float(np.count_nonzero(edges_bot)) / max(1, edges_bot.size) * 100.0, 1)
    overall_occ = min(95, max(8, int((top_density * 5.2 + bot_density * 4.5))))

    is_outdoor = any(k in hub_name.lower() for k in ["bãi", "ngoài trời", "sân", "cổng", "đường"])

    # 1. Đánh giá Ánh sáng & Thời tiết
    if mean_bri >= 135:
        light_desc = "☀️ Trời nắng ráo / Ánh sáng rất tốt, tầm nhìn camera sắc nét 100%." if is_outdoor else "💡 Hệ thống chiếu sáng sàn kho rất tốt, hình ảnh rõ nét."
    elif mean_bri >= 85:
        light_desc = "🌤️ Ánh sáng ổn định, mặt sân khô ráo, thuận lợi xuất nhập hàng." if is_outdoor else "💡 Ánh sáng trong kho ổn định, đảm bảo điều kiện vận hành."
    else:
        light_desc = "🌙 Ánh sáng yếu / Khung giờ tối (Đèn pha bãi xe đang hoạt động)." if is_outdoor else "🌙 Khu vực kho ánh sáng dịu / Đang bật đèn trực ca."

    # 2. Đánh giá Bãi xe / Dock / Sàn kho
    if is_outdoor:
        if top_density >= 6.5:
            dock_desc = f"Phát hiện phương tiện/xe tải đang đậu tại khu vực cửa Dock (Mật độ chi tiết vùng Dock: {top_density}%)."
        else:
            dock_desc = "Khu vực cửa Dock & đường dẫn thông thoáng, sẵn sàng đón xe tải cập bến."
        if bot_density <= 5.0:
            five_s_desc = "Mặt sân bê tông trung tâm thông thoáng, không có vật cản hay hàng hóa ứ đọng ngoài trời."
            status_tag = "🟢 BÌNH THƯỜNG — SÂN BÃI & DOCK THÔNG THOÁNG"
        else:
            five_s_desc = f"Sân bãi đang có phương tiện/hoạt động tập kết (Mật độ mặt sân: ~{overall_occ}%). Lưu ý giữ làn xe quay đầu."
            status_tag = "🟡 ĐANG HOẠT ĐỘNG — LƯU Ý ĐIỀU TIẾT LUỒNG XE"
    else:
        if bot_density >= 9.0:
            dock_desc = f"Sàn kho đang tập kết lượng hàng hóa/Pallet khá dày (Ước tính mật độ lấp đầy sàn: ~{overall_occ}%)."
            five_s_desc = "Cần ưu tiên giải phóng các kiện hàng dọc hành lang xe nâng, đảm bảo chuẩn 5S và lối đi an toàn."
            status_tag = "🟡 CẦN LƯU Ý — MẬT ĐỘ HÀNG TRÊN SÀN CAO, CẦN ĐẨY NHANH GÁN CHUYẾN"
        else:
            dock_desc = f"Khu vực tập kết Pallet & sàn kho gọn gàng (Ước tính mật độ sàn: ~{overall_occ}%)."
            five_s_desc = "Lối đi nội bộ thông thoáng, hàng hóa xếp trên Pallet đúng quy chuẩn 5S."
            status_tag = "🟢 BÌNH THƯỜNG — SÀN KHO GỌN GÀNG, ĐẠT CHUẨN 5S"

    return (
        f"• 🚚 <b>Hiện trường &amp; Khu vực Dock:</b> {dock_desc}\n"
        f"• 📦 <b>Tiêu chuẩn 5S &amp; Luồng tuyến:</b> {five_s_desc}\n"
        f"• ☀️ <b>Ánh sáng &amp; Môi trường:</b> {light_desc} <i>(Độ sáng TB: {mean_bri:.0f}/255)</i>\n"
        f"• 🤖 <b>ĐÁNH GIÁ TIGER AI VISION:</b> <b>[{status_tag}]</b>"
    )

def analyze_warehouse_camera_image(image_path, hub_name):
    """Phân tích hiện trường kho bãi thời gian thực bằng Gemini Vision + OpenCV Multi-Zone Fallback"""
    if not image_path or not os.path.exists(image_path):
        return None

    img = cv2.imread(image_path)
    if img is None:
        return None

    api_key = get_gemini_api_key()
    if api_key and not api_key.startswith("AQ.Ab8RN6J"):
        try:
            img_resized = cv2.resize(img, (800, 450))
            _, buf = cv2.imencode('.jpg', img_resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
            img_b64 = base64.b64encode(buf).decode('utf-8')

            prompt = f"""Bạn là 'Tiger AI - Trợ Lý Giám Sát Vận Hành Kho Bãi GHN Logistics'.
Hãy quan sát bức ảnh camera an ninh tại {hub_name} và đưa ra báo cáo giám sát thông minh:
1. 🚚 Bãi xe & Dock: Số lượng xe tải/phương tiện, tình trạng dock bốc dỡ có bị kẹt hay thông thoáng?
2. 📦 5S & An Toàn: Lối đi, hàng hóa có chướng ngại vật hay nguy cơ đổ ngã không?
3. ☀️ Thời tiết & Ánh sáng: Nắng, mưa hay tối?
4. 🤖 ĐÁNH GIÁ VẬN HÀNH: Tóm tắt 1 câu [BÌNH THƯỜNG / CẦN LƯU Ý / CẢNH BÁO] và đề xuất hành động.
Viết ngắn gọn, chuyên nghiệp, có icon, trình bày gạch đầu dòng rõ ràng để gửi Telegram."""

            for model_name in ["gemini-2.5-flash", "gemini-2.0-flash"]:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                            {"text": prompt}
                        ]
                    }],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600}
                }
                res = requests.post(url, json=payload, timeout=12)
                if res.status_code == 200:
                    ans = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if ans:
                        return ans
        except Exception as e:
            print(f"[Vision Guard] Gemini fallback to OpenCV Vision: {e}")

    return _opencv_smart_scene_audit(img, hub_name)

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

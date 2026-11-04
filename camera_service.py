import requests
import cv2
import os
import time
import tempfile
import json
import logging

logger = logging.getLogger("CameraGuardian")

BASE_API = "https://camera-api.ghn.vn/public-api"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(SCRIPT_DIR, "camera_headers.json")

# Fallback headers if file not found
DEFAULT_HEADERS = {
    "sec-ch-ua-platform": '"Windows"',
    "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3NUb2tlbiI6IjZkYTNlMWZmLTllY2ItNGM2NS1hMWFkLWVmNDQ4YzZhY2ExZCIsImV4cCI6MTgyNTMxMzc3MiwibmFtZSI6Ik5ndXnhu4VuIFBoxrDhu5tjIELhuqNvIEzhu5ljIiwicm9sZXMiOiIiLCJ1c2VySWQiOjMwMzY5NDF9.nYEpJ9BWZDiExwIaS5aIWEKpaf3MbFbQcY0l68W0AaY",
    "referer": "https://nhanh.ghn.vn/",
    "sec-ch-ua": '"Not:A-Brand";v="8", "Chromium";v="156", "Google Chrome";v="156"',
    "sec-ch-ua-mobile": "?0",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/156.0.0.0 Safari/537.36",
    "accept": "application/json, text/plain, */*"
}

VR_MAP = {
    "cairang": {"name": "Kho Giao Hàng Nặng Cái Răng", "vr_id": "6577e3250ad53fcbaab02947", "default_cam": 2, "outdoor_cam": 8, "indoor_cam": 2, "weather_cam": 8},
    "cr": {"name": "Kho Giao Hàng Nặng Cái Răng", "vr_id": "6577e3250ad53fcbaab02947", "default_cam": 2, "outdoor_cam": 8, "indoor_cam": 2, "weather_cam": 8},
    "binhthuy": {"name": "Kho Giao Hàng Nặng Bình Thủy", "vr_id": "6577e3250ad53fcbaab02947", "default_cam": 6, "outdoor_cam": 7, "indoor_cam": 6, "weather_cam": 7, "allowed_cams": [1, 6, 7, 14, 16]},
    "bt": {"name": "Kho Giao Hàng Nặng Bình Thủy", "vr_id": "6577e3250ad53fcbaab02947", "default_cam": 6, "outdoor_cam": 7, "indoor_cam": 6, "weather_cam": 7, "allowed_cams": [1, 6, 7, 14, 16]},
    "omon": {"name": "Kho Giao Hàng Nặng Ô Môn", "vr_id": "69dcba16a22d4e6ace3eadf6", "default_cam": 4, "outdoor_cam": 3, "indoor_cam": 4, "weather_cam": 3},
    "om": {"name": "Kho Giao Hàng Nặng Ô Môn", "vr_id": "69dcba16a22d4e6ace3eadf6", "default_cam": 4, "outdoor_cam": 3, "indoor_cam": 4, "weather_cam": 3},
    "vithanh": {"name": "Kho Giao Hàng Nặng Vị Thanh", "vr_id": "69c4fb54a9cd53f0d672a24d", "default_cam": 6, "outdoor_cam": 8, "indoor_cam": 6, "weather_cam": 8},
    "vt": {"name": "Kho Giao Hàng Nặng Vị Thanh", "vr_id": "69c4fb54a9cd53f0d672a24d", "default_cam": 6, "outdoor_cam": 8, "indoor_cam": 6, "weather_cam": 8},
}

CAM_DESC_MAP = {
    ("6577e3250ad53fcbaab02947", 1): "Cửa dock xuất/nhập xe tải",
    ("6577e3250ad53fcbaab02947", 2): "Sàn kho & Khu vực tập kết Pallet hàng hóa (Cái Răng)",
    ("6577e3250ad53fcbaab02947", 6): "Khu vực tập kết Pallet & Kiện hàng sàn kho (Bình Thủy)",
    ("6577e3250ad53fcbaab02947", 7): "Bãi đỗ xe tải & Sân ngoài trời (Bình Thủy)",
    ("6577e3250ad53fcbaab02947", 8): "Bãi đỗ xe tải & Quang cảnh ngoài trời (Cái Răng)",
    ("6577e3250ad53fcbaab02947", 14): "Toàn cảnh luồng hàng & kho bãi",
    ("6577e3250ad53fcbaab02947", 16): "Hành lang vận hành bốc dỡ xe nâng",
    ("69dcba16a22d4e6ace3eadf6", 3): "Sân bãi bê tông ngoài trời (Ô Môn)",
    ("69dcba16a22d4e6ace3eadf6", 4): "Sàn kho trung tâm & Pallet chứa hàng (Ô Môn)",
    ("69dcba16a22d4e6ace3eadf6", 2): "Sàn kho bốc dỡ & Pallet nhựa (Ô Môn)",
    ("69c4fb54a9cd53f0d672a24d", 8): "Cổng ngoài trời & đường lộ (Vị Thanh)",
    ("69c4fb54a9cd53f0d672a24d", 6): "Khu vực lưu trữ hàng hóa & Pallet kiện hàng (Vị Thanh)",
    ("69c4fb54a9cd53f0d672a24d", 3): "Sàn kho hàng hóa & Pallet nhựa (Vị Thanh)",
}

def load_camera_headers():
    """Tải headers camera từ file JSON lưu trữ hoặc fallback mặc định"""
    for path in [HEADERS_FILE, os.path.join(os.path.dirname(SCRIPT_DIR), "camera_headers.json"), "camera_headers.json"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return DEFAULT_HEADERS.copy()

def save_camera_headers(headers):
    """Lưu headers camera mới vào file"""
    try:
        with open(HEADERS_FILE, "w", encoding="utf-8") as f:
            json.dump(headers, f, indent=2)
    except Exception as e:
        logger.warning(f"Không thể lưu camera_headers.json: {e}")

def check_token_health(headers):
    """Bác sĩ kiểm tra Token: gọi thử permission để xem token còn sống không"""
    try:
        r = requests.post(
            f"{BASE_API}/permission/getPermission",
            headers=headers,
            json={},
            timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("code") == 200 and data.get("data", {}).get("permission_check_list", {}).get("view_camera"):
                return True, "Token khỏe mạnh"
        return False, f"Token không hợp lệ (HTTP {r.status_code})"
    except Exception as e:
        return False, f"Lỗi kết nối kiểm tra: {e}"

def self_heal_camera_token():
    """Bot tự động chữa lỗi Token: Mở Playwright ngầm lấy token mới nhất từ Nhanh GHN"""
    logger.info("🛡️ [Auto-Healer] Phát hiện Token Camera cần làm mới, tiến hành tự phục hồi...")
    try:
        from playwright.sync_api import sync_playwright
        profile_path = os.path.join(os.path.dirname(SCRIPT_DIR), "ghn_chrome_profile")
        if not os.path.exists(profile_path):
            profile_path = r"c:\Users\nguye\.gemini\antigravity\scratch\ghn_chrome_profile"

        if not os.path.exists(profile_path):
            return False, "Không tìm thấy Chrome Profile để tự động lấy token"

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                headless=True
            )
            page = browser.pages[0] if browser.pages else browser.new_page()

            captured_headers = {}
            def on_req(req):
                if "permission/getPermission" in req.url:
                    captured_headers.update(req.headers)

            page.on("request", on_req)
            page.goto("https://nhanh.ghn.vn/camera/", wait_until="networkidle", timeout=20000)
            time.sleep(2)
            browser.close()

            if captured_headers and "authorization" in captured_headers:
                save_camera_headers(captured_headers)
                logger.info("🛡️ [Auto-Healer] Tự khắc phục thành công! Đã cập nhật Token Camera mới.")
                return True, captured_headers
    except Exception as e:
        logger.error(f"🛡️ [Auto-Healer] Lỗi tự phục hồi token: {e}")
    return False, None

def capture_camera_snapshot(hub_key="cairang", cam_id=None, output_file=None, max_retries=2):
    """
    Hàm chụp camera được bảo vệ bởi Quality Guard Bot:
    - Tự động kiểm tra token trước khi gọi API
    - Tự động chữa lành token nếu hết hạn (Auto-healing)
    - Tự động retry stream nếu playlist chưa sẵn sàng
    - Xác minh chất lượng ảnh trước khi trả kết quả 100% đúng
    """
    clean_key = hub_key.lower().strip()
    hub_info = VR_MAP.get(clean_key, VR_MAP["cairang"])
    vr_id = hub_info["vr_id"]
    hub_name = hub_info["name"]

    if cam_id is None:
        cam_id = hub_info.get("default_cam", 2)
    else:
        try:
            cam_id = int(cam_id)
        except Exception:
            cam_id = hub_info.get("default_cam", 2)

    temp_dir = tempfile.gettempdir()
    if not output_file:
        output_file = os.path.join(temp_dir, f"snap_{clean_key}_{cam_id}_{int(time.time())}.jpg")

    headers = load_camera_headers()

    # Pre-flight check token
    is_healthy, _ = check_token_health(headers)
    if not is_healthy:
        logger.info("🛡️ [Pre-flight] Token hết hạn, kích hoạt tự sửa lỗi...")
        ok_heal, new_headers = self_heal_camera_token()
        if ok_heal and new_headers:
            headers = new_headers

    # Vòng lặp chụp với cơ chế tự phục hồi
    for attempt in range(max_retries + 1):
        params = {"vrId": vr_id, "cameraId": cam_id, "subStream": "true"}
        try:
            r = requests.get(f"{BASE_API}/stream/liveview", headers=headers, params=params, timeout=10)
        except Exception as e:
            if attempt == max_retries:
                return False, f"Lỗi kết nối tới Server Camera: {e}", None
            time.sleep(1.5)
            continue

        # Nếu bị 401 Unauthorized -> Tự chữa lành ngay lập tức
        if r.status_code == 401:
            logger.warning("🛡️ [Auto-Healer] Gặp lỗi 401, tự động cấp lại Token...")
            ok_heal, new_headers = self_heal_camera_token()
            if ok_heal and new_headers:
                headers = new_headers
                continue
            else:
                return False, "Hết phiên đăng nhập Camera GHN (Cần cấp lại Token)", None

        if r.status_code != 200:
            if attempt == max_retries:
                return False, f"Server Camera trả về lỗi (HTTP {r.status_code})", None
            time.sleep(1.5)
            continue

        data = r.json()
        hls_url = data.get("data", {}).get("hlsUrl")
        if not hls_url:
            if attempt == max_retries:
                return False, "Không trích xuất được luồng HLS từ Camera", None
            time.sleep(1.5)
            continue

        base_stream_url = hls_url.rsplit('/', 1)[0] + '/'

        # Chờ HLS playlist sinh chunk video (thử tối đa 8 lần)
        playlist_text = None
        for p_attempt in range(8):
            time.sleep(1)
            try:
                r_pl = requests.get(hls_url, headers=headers, timeout=5)
                if r_pl.status_code == 200 and "#EXTM3U" in r_pl.text and ".m4s" in r_pl.text:
                    playlist_text = r_pl.text
                    break
            except Exception:
                pass

        if not playlist_text:
            if attempt < max_retries:
                logger.info(f"🛡️ [Auto-Retry] Thử lại lần {attempt+1} cho {hub_name} Cam {cam_id}...")
                time.sleep(2)
                continue
            return False, "Mất tín hiệu kết nối stream từ đầu ghi kho (Vui lòng kiểm tra mạng kho)", None

        # Trích xuất file init và media chunk
        init_file = None
        media_files = []
        for line in playlist_text.splitlines():
            line = line.strip()
            if line.startswith("#EXT-X-MAP:URI="):
                init_file = line.split('"')[1]
            elif line.endswith(".m4s"):
                media_files.append(line)

        if not init_file or not media_files:
            if attempt < max_retries:
                time.sleep(2)
                continue
            return False, "Luồng video không có phân đoạn hình ảnh (Segment rỗng)", None

        try:
            r_init = requests.get(base_stream_url + init_file, headers=headers, timeout=8)
            r_media = requests.get(base_stream_url + media_files[-1], headers=headers, timeout=8)
        except Exception:
            if attempt < max_retries:
                time.sleep(2)
                continue
            return False, "Không tải được dữ liệu frame hình ảnh từ CDN", None

        if r_init.status_code != 200 or r_media.status_code != 200:
            if attempt < max_retries:
                time.sleep(2)
                continue
            return False, "CDN không phản hồi frame hình ảnh", None

        temp_video = os.path.join(temp_dir, f"temp_cam_{clean_key}_{cam_id}_{int(time.time())}.mp4")
        with open(temp_video, "wb") as f:
            f.write(r_init.content)
            f.write(r_media.content)

        cap = cv2.VideoCapture(temp_video)
        success, frame = cap.read()
        cap.release()

        try:
            os.remove(temp_video)
        except Exception:
            pass

        # Bác sĩ xác minh chất lượng ảnh trước khi xuất xưởng
        if not success or frame is None or frame.shape[0] < 100:
            if attempt < max_retries:
                time.sleep(2)
                continue
            return False, "Giải mã frame hình ảnh thất bại (Ảnh không hợp lệ)", None

        cv2.imwrite(output_file, frame)
        if not os.path.exists(output_file) or os.path.getsize(output_file) < 1000:
            return False, "File ảnh chụp rỗng hoặc lỗi ghi đĩa", None

        desc = CAM_DESC_MAP.get((vr_id, cam_id), f"Mắt Cam số {cam_id:02d}")
        logger.info(f"✅ [Quality Guard Verified] {hub_name} Cam {cam_id} đã chụp chuẩn 100%!")
        return True, f"{hub_name} - {desc}", output_file

    return False, "Không thể lấy hình ảnh sau khi đã tự động thử lại nhiều lần", None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Quality Guard Camera Service...")
    ok, msg, snap = capture_camera_snapshot("cr", 2)
    print("Result:", ok, msg, snap)

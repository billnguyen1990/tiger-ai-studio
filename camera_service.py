import requests
import cv2
import os
import time
import tempfile

HEADERS = {
    "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3NUb2tlbiI6IjZkYTNlMWZmLTllY2ItNGM2NS1hMWFkLWVmNDQ4YzZhY2ExZCIsImV4cCI6MTgyNDk0NTk4OCwibmFtZSI6Ik5ndXnhu4VuIFBoxrDhu5tjIELhuqNvIEzhu5ljIiwicm9sZXMiOiIiLCJ1c2VySWQiOjMwMzY5NDF9.PhaL8Tim94OW9uphTx9bKFBE4lwJu34uEzFXbNFTb14",
    "referer": "https://nhanh.ghn.vn/",
    "origin": "https://nhanh.ghn.vn",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/156.0.0.0 Safari/537.36",
    "accept": "*/*"
}

BASE_API = "https://camera-api.ghn.vn/public-api"

VR_MAP = {
    "cairang": {"name": "Kho Giao Hàng Nặng Cái Răng", "vr_id": "6577e3250ad53fcbaab02947", "default_cam": 1},
    "cr": {"name": "Kho Giao Hàng Nặng Cái Răng", "vr_id": "6577e3250ad53fcbaab02947", "default_cam": 1},
    "binhthuy": {"name": "Kho Bình Thủy (Khu vực tại Kho Cái Răng)", "vr_id": "6577e3250ad53fcbaab02947", "default_cam": 6, "allowed_cams": [1, 6, 14, 16]},
    "bt": {"name": "Kho Bình Thủy (Khu vực tại Kho Cái Răng)", "vr_id": "6577e3250ad53fcbaab02947", "default_cam": 6, "allowed_cams": [1, 6, 14, 16]},
    "omon": {"name": "Kho Giao Hàng Nặng Ô Môn", "vr_id": "69dcba16a22d4e6ace3eadf6", "default_cam": 1},
    "om": {"name": "Kho Giao Hàng Nặng Ô Môn", "vr_id": "69dcba16a22d4e6ace3eadf6", "default_cam": 1},
    "vithanh": {"name": "Kho Giao Hàng Nặng Vị Thanh", "vr_id": "69c4fb54a9cd53f0d672a24d", "default_cam": 1},
    "vt": {"name": "Kho Giao Hàng Nặng Vị Thanh", "vr_id": "69c4fb54a9cd53f0d672a24d", "default_cam": 1},
}

CAM_DESC_MAP = {
    ("6577e3250ad53fcbaab02947", 1): "Cửa dock xuất/nhập xe tải",
    ("6577e3250ad53fcbaab02947", 2): "Toàn cảnh sàn kho & xe nâng",
    ("6577e3250ad53fcbaab02947", 6): "Khu vực tập kết Pallet & Xe nâng tay (Bình Thủy)",
    ("6577e3250ad53fcbaab02947", 14): "Toàn cảnh luồng hàng & kho bãi (Bình Thủy)",
    ("6577e3250ad53fcbaab02947", 16): "Hành lang vận hành bốc dỡ xe nâng (Bình Thủy)",
}

def capture_camera_snapshot(hub_key="cairang", cam_id=None, output_file=None):
    clean_key = hub_key.lower().strip()
    hub_info = VR_MAP.get(clean_key, VR_MAP["cairang"])
    vr_id = hub_info["vr_id"]
    hub_name = hub_info["name"]

    # Handle default cam or allowed cams
    if cam_id is None:
        cam_id = hub_info.get("default_cam", 1)
    else:
        try:
            cam_id = int(cam_id)
        except Exception:
            cam_id = hub_info.get("default_cam", 1)

    temp_dir = tempfile.gettempdir()
    if not output_file:
        output_file = os.path.join(temp_dir, f"snap_{clean_key}_{cam_id}_{int(time.time())}.jpg")

    # 1. Request liveview session
    params = {"vrId": vr_id, "cameraId": cam_id, "subStream": "true"}
    r = requests.get(f"{BASE_API}/stream/liveview", headers=HEADERS, params=params, timeout=8)
    if r.status_code != 200:
        return False, f"Lỗi gọi API Camera (HTTP {r.status_code})", None

    data = r.json()
    hls_url = data.get("data", {}).get("hlsUrl")
    if not hls_url:
        return False, f"Không lấy được HLS URL: {data}", None

    base_stream_url = hls_url.rsplit('/', 1)[0] + '/'

    # 2. Wait for HLS playlist to be ready (up to 6 retries)
    playlist_text = None
    for attempt in range(6):
        time.sleep(1)
        r_pl = requests.get(hls_url, headers=HEADERS, timeout=5)
        if r_pl.status_code == 200 and "#EXTM3U" in r_pl.text and ".m4s" in r_pl.text:
            playlist_text = r_pl.text
            break

    if not playlist_text:
        return False, "Camera chưa sẵn sàng truyền luồng video (stream warming up)", None

    # 3. Parse init and latest m4s segment
    lines = [l.strip() for l in playlist_text.split("\n") if l.strip()]
    init_file = None
    m4s_file = None
    for l in lines:
        if "EXT-X-MAP" in l and 'URI="' in l:
            init_file = l.split('URI="')[1].split('"')[0]
        elif l.endswith(".m4s"):
            m4s_file = l

    if not init_file or not m4s_file:
        return False, "Không tìm thấy đoạn video m4s trong playlist", None

    # 4. Download init and chunk
    r_init = requests.get(base_stream_url + init_file, headers=HEADERS, timeout=8)
    r_chunk = requests.get(base_stream_url + m4s_file, headers=HEADERS, timeout=8)

    temp_mp4 = os.path.join(temp_dir, f"temp_{vr_id}_{cam_id}.mp4")
    with open(temp_mp4, "wb") as f:
        f.write(r_init.content + r_chunk.content)

    cap = cv2.VideoCapture(temp_mp4)
    ret, frame = cap.read()
    cap.release()
    try:
        os.remove(temp_mp4)
    except Exception:
        pass

    if ret and frame is not None:
        cv2.imwrite(output_file, frame)
        desc = CAM_DESC_MAP.get((vr_id, cam_id), f"Mắt Cam số {cam_id:02d}")
        return True, f"{hub_name} - {desc}", output_file

    return False, "Không giải mã được khung hình từ video", None

if __name__ == '__main__':
    ok, msg, path = capture_camera_snapshot("bt", 6)
    print("Capture result:", ok, msg, path)

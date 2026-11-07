# -*- coding: utf-8 -*-
"""
🐯 TIGER AI • HỆ THỐNG TUẦN TRA & KIỂM ĐỊNH CAMERA BÊN TRONG 4 KHO ĐỊNH KỲ (06:00 SÁNG & 20:00 TỐI)
Cấu hình mắt Camera chuẩn theo chỉ đạo của Sếp Lộc:
- Kho Cái Răng  : Cam 10 (Sàn kho bên trong & Khu vực Pallet hàng hóa)
- Kho Bình Thủy : Cam 16 (Sàn kho bên trong & Hành lang bốc dỡ xe nâng)
- Kho Vị Thanh  : Cam 3  (Sàn kho bên trong & Khu vực Pallet hàng hóa)
- Kho Ô Môn     : Cam 7  (Sàn kho bên trong & Khu vực Pallet hàng hóa)
"""

import os
import sys
import json
import time
import datetime
import requests
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from warehouse_vision_guard import run_vision_guard_audit

TELEGRAM_BOT_TOKEN = "8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk"
TELEGRAM_CHAT_ID = "-1003940889949"
CAM_TOPIC_ID = 3365  # Phòng 📸 Camera Giám Sát Kho
LOCK_FILE = os.path.join(BASE_DIR, "indoor_cam_last_run.json")

INDOOR_CAM_TARGETS = [
    {
        "hub_key": "cairang",
        "hub_name": "Kho Cái Răng",
        "cam_id": 10,
        "cam_label": "Cam 10 (Sàn kho trung tâm & Khu vực Pallet)",
        "nvxl_tag": "@CONGBANGCAIRANGCANTHO"
    },
    {
        "hub_key": "binhthuy",
        "hub_name": "Kho Bình Thủy",
        "cam_id": 16,
        "cam_label": "Cam 16 (Sàn kho bên trong & Hành lang bốc dỡ)",
        "nvxl_tag": "@Nguyen_Toan"
    },
    {
        "hub_key": "vithanh",
        "hub_name": "Kho Vị Thanh",
        "cam_id": 3,
        "cam_label": "Cam 03 (Sàn kho bên trong & Khu vực Pallet)",
        "nvxl_tag": "@DUCTRUNG17TUOI"
    },
    {
        "hub_key": "omon",
        "hub_name": "Kho Ô Môn",
        "cam_id": 7,
        "cam_label": "Cam 07 (Sàn kho bên trong & Khu vực Pallet)",
        "nvxl_tag": "@pinca0602"
    },
]

def get_vietnam_now():
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    return utc_now.astimezone(datetime.timezone(datetime.timedelta(hours=7)))

def send_telegram_text(text, topic_id=CAM_TOPIC_ID):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_thread_id": topic_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.json()
    except Exception as e:
        print(f"[Indoor Cam Scheduler] Lỗi gửi text: {e}")
        return {"ok": False}

def send_telegram_photo(photo_path, caption, topic_id=CAM_TOPIC_ID):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "message_thread_id": topic_id,
                "caption": caption[:1024],
                "parse_mode": "HTML"
            }
            r = requests.post(url, data=data, files=files, timeout=25)
            return r.json()
    except Exception as e:
        print(f"[Indoor Cam Scheduler] Lỗi gửi ảnh: {e}")
        return {"ok": False}

def run_indoor_cam_inspection(send_telegram=True, force=False):
    now_vn = get_vietnam_now()
    now_ts = time.time()
    now_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")
    date_str = now_vn.strftime("%d/%m/%Y")
    hr = now_vn.hour

    if hr < 12:
        shift_key = now_vn.strftime("%Y-%m-%d_06h")
        shift_title = "CA SÁNG ĐẦU NGÀY (06:00)"
        shift_note = "Kiểm tra hiện trường sàn kho đầu ca, lượng hàng lưu sàn qua đêm, tiêu chuẩn 5S & sẵn sàng đón tải phân hàng."
    elif hr >= 18:
        shift_key = now_vn.strftime("%Y-%m-%d_20h")
        shift_title = "CA TỐI CUỐI NGÀY (20:00)"
        shift_note = "Kiểm tra giải phóng sàn kho cuối ngày, rà soát hàng tồn đọng trên sàn & chuẩn 5S an toàn trước khi đóng kho."
    else:
        shift_key = now_vn.strftime("%Y-%m-%d_%Hh")
        shift_title = f"KIỂM TRA ĐỘT XUẤT ({now_vn.strftime('%H:%M')})"
        shift_note = "Soi trực tiếp 4 mắt Camera bên trong sàn kho theo vị trí chuẩn chỉ định."

    caller_id = "Render_Cloud" if (os.environ.get("RENDER") == "true" or sys.platform != "win32") else "Windows_PC"

    # 1. KHÓA TẬP TRUNG CLOUD TRÁNH CHẠY SONG SONG GIỮA CLOUD VÀ PC
    if send_telegram and not force:
        lock_endpoints = [
            "https://tiger-ai-studio.onrender.com/api/indoor-cam-lock",
            "http://127.0.0.1:5050/api/indoor-cam-lock"
        ]
        for ep in lock_endpoints:
            try:
                r = requests.post(
                    ep,
                    json={"action": "acquire", "shift": shift_key, "caller": caller_id},
                    timeout=2.5
                )
                if r.status_code == 200:
                    data = r.json()
                    if not data.get("acquired", True):
                        print(f"[Indoor Cam Scheduler] ⛔ {data.get('reason')}. BỎ QUA ĐỂ TRÁNH GỬI TRÙNG!")
                        return {"ok": True, "skipped": True, "reason": data.get("reason")}
                    else:
                        print(f"[Indoor Cam Scheduler] 🔒 Đã nhận khóa tập trung từ {ep} cho ca {shift_key}")
                        break
            except Exception:
                continue

    # 2. KHÓA DỰ PHÒNG FILE CỤC BỘ (LOCAL FILE LOCK)
    if send_telegram and not force and os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_ts = float(data.get("last_ts", 0))
            last_shift = data.get("shift", "")
            if (now_ts - last_ts < 1200) or (last_shift and last_shift == shift_key):
                print(f"[Indoor Cam Scheduler] Đã chạy cách đây {int(now_ts - last_ts)}s (Ca {last_shift}). Bỏ qua để tránh trùng lặp.")
                return {"ok": True, "skipped": True}
        except Exception:
            pass

    # Ghi nhận khóa cục bộ
    if send_telegram:
        try:
            with open(LOCK_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "last_ts": now_ts,
                    "last_str": now_vn.strftime("%Y-%m-%d %H:%M:%S"),
                    "shift": shift_key,
                    "caller": caller_id
                }, f)
        except Exception:
            pass

    print(f"🐯 [Tiger AI] Đang trích xuất & phân tích 4 mắt Camera bên trong kho ({shift_title})...")

    def _worker(item):
        ok, cam_desc, snap_path, analysis = run_vision_guard_audit(item["hub_key"], item["cam_id"])
        return {
            "item": item,
            "ok": ok,
            "cam_desc": cam_desc,
            "snap_path": snap_path,
            "analysis": analysis
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_worker, INDOOR_CAM_TARGETS))

    header_msg = (
        f"👁️ <b>TIGER AI • TUẦN TRA CAMERA BÊN TRONG 4 KHO MT01</b>\n"
        f"⏰ <b>Khung giờ:</b> <b>{shift_title}</b> — <code>{date_str}</code>\n"
        f"🎯 <b>Mục tiêu:</b> <i>{shift_note}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>Danh sách vị trí Camera chuẩn bên trong 4 kho:</b>\n"
        f"  1️⃣ <b>Kho Cái Răng:</b> <code>Cam 10</code> ({INDOOR_CAM_TARGETS[0]['nvxl_tag']})\n"
        f"  2️⃣ <b>Kho Bình Thủy:</b> <code>Cam 16</code> ({INDOOR_CAM_TARGETS[1]['nvxl_tag']})\n"
        f"  3️⃣ <b>Kho Vị Thanh:</b> <code>Cam 03</code> ({INDOOR_CAM_TARGETS[2]['nvxl_tag']})\n"
        f"  4️⃣ <b>Kho Ô Môn:</b> <code>Cam 07</code> ({INDOOR_CAM_TARGETS[3]['nvxl_tag']})"
    )

    print("\n" + "=" * 60)
    print(header_msg)
    print("=" * 60)

    if send_telegram:
        send_telegram_text(header_msg, topic_id=CAM_TOPIC_ID)
        time.sleep(0.5)

    ok_count = 0
    for idx, res in enumerate(results, 1):
        it = res["item"]
        ok = res["ok"]
        snap_path = res["snap_path"]
        analysis = res["analysis"] or ""

        caption = (
            f"📸 <b>[{idx}/4] {it['hub_name'].upper()} — {it['cam_label']}</b>\n"
            f"👤 <b>Phụ trách:</b> {it['nvxl_tag']} | ⏰ <code>{now_str}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{analysis}"
        )
        print(f"\n--- [{idx}/4] {it['hub_name']} (Cam {it['cam_id']}): ok={ok} ---")
        print(caption)

        if send_telegram:
            if ok and snap_path and os.path.exists(snap_path):
                ok_count += 1
                send_telegram_photo(snap_path, caption=caption, topic_id=CAM_TOPIC_ID)
                try:
                    os.remove(snap_path)
                except Exception:
                    pass
                time.sleep(0.6)
            else:
                send_telegram_text(
                    f"⚠️ <b>[{idx}/4] {it['hub_name']} ({it['cam_label']}):</b> Chưa trích xuất được hình ảnh ({res['cam_desc']}). Đề nghị {it['nvxl_tag']} kiểm tra mạng đầu ghi!",
                    topic_id=CAM_TOPIC_ID
                )
        else:
            if snap_path and os.path.exists(snap_path):
                ok_count += 1
                try:
                    os.remove(snap_path)
                except Exception:
                    pass

    print(f"\n✅ Hoàn tất kiểm tra {ok_count}/4 mắt camera bên trong kho!")
    return {"ok": True, "captured": ok_count, "total": 4}

if __name__ == "__main__":
    is_send = "--send" in sys.argv
    is_force = "--force" in sys.argv
    run_indoor_cam_inspection(send_telegram=is_send, force=is_force)

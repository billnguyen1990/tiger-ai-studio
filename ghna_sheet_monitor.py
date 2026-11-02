# -*- coding: utf-8 -*-
"""
🐯 TIGER AI • GOOGLE SHEET GHNa AUTO MONITOR & ALERT SYSTEM
Giám sát tự động tab GHNa trên Google Sheet:
Link: https://docs.google.com/spreadsheets/d/17ntSJzL8IS180hiJ0jBLWctnKF6iZVZ64sOE5JB1mwg/edit?usp=sharing
Quét 4 lần/ngày: 08:00, 12:00, 16:00, 20:00 (hoặc trigger qua API/Telegram).
Phát hiện bất kỳ ai điền dữ liệu hoặc note giải trình -> Bắn Telegram ngay cho anh Lộc & Topic Báo Cáo MT01!
"""

import os
import sys
import json
import csv
import io
import hashlib
import datetime
import urllib.request
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Cấu hình Google Sheet
SPREADSHEET_ID = "17ntSJzL8IS180hiJ0jBLWctnKF6iZVZ64sOE5JB1mwg"
SHEET_NAME = "GHNa"
SHEET_GID = "1819305983"
SHEET_VIEW_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid={SHEET_GID}"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

# Cấu hình Telegram (Chỉ gửi DUY NHẤT về room 'The 5 Guardians' theo chỉ đạo của anh Lộc)
TELEGRAM_BOT_TOKEN = "8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk"
GUARDIANS_CHAT_ID = "-5295214199"        # Room The 5 Guardians (8 thành viên cốt cán)

SNAPSHOT_FILE = os.path.join(BASE_DIR, "ghna_state_snapshot.json")

def get_now_str():
    vn_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)
    return vn_now.strftime("%H:%M:%S %d/%m/%Y")

def fetch_ghna_sheet_rows():
    """Tải dữ liệu mới nhất từ tab GHNa qua endpoint CSV Google Sheet"""
    req = urllib.request.Request(
        SHEET_CSV_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TigerAI/2.9"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        content = resp.read().decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        raw_rows = list(reader)
    return raw_rows

def parse_ghna_data(raw_rows):
    """
    Phân tích cấu trúc tab GHNa:
    Row 1: Whitespace/Title
    Row 2: Headers (Vùng, ID AM, Tên AM, ID TBC, Tên TBC, Cửa hàng, ID phiếu...)
    Row 3+: Dữ liệu thực tế
    """
    if len(raw_rows) < 2:
        return [], []

    # Tìm hàng header
    header_idx = -1
    for idx, r in enumerate(raw_rows[:5]):
        text_row = " ".join(r).lower()
        if "cửa hàng" in text_row or "id phiếu" in text_row or "tiêu chí" in text_row:
            header_idx = idx
            break

    if header_idx == -1:
        header_idx = 1 if len(raw_rows) > 1 else 0

    headers = [c.strip() for c in raw_rows[header_idx]]

    data_rows = []
    for r_idx in range(header_idx + 1, len(raw_rows)):
        row = raw_rows[r_idx]
        # Bỏ qua dòng trống hoàn toàn
        non_empty = [c.strip() for c in row if c and c.strip()]
        if not non_empty:
            continue

        # Map theo header
        row_dict = {}
        for c_idx, val in enumerate(row):
            h_name = headers[c_idx] if c_idx < len(headers) and headers[c_idx] else f"col_{c_idx}"
            # Chuẩn hóa tên cột
            clean_h = h_name.replace("\n", " ").strip()
            row_dict[clean_h] = val.strip()

        row_dict["_row_number"] = r_idx + 1
        data_rows.append(row_dict)

    return headers, data_rows

def load_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[GHNa Monitor] Error reading snapshot: {e}")
    return {"last_scanned_at": None, "total_rows": 0, "records": {}}

def save_snapshot(state):
    try:
        with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[GHNa Monitor] Error saving snapshot: {e}")

def get_row_identity(row_dict):
    """Tạo khóa định danh duy nhất cho từng dòng"""
    id_phieu = row_dict.get("ID phiếu (wo_link)") or row_dict.get("ID phiếu") or ""
    cua_hang = row_dict.get("Cửa hàng") or ""
    ngay_tao = row_dict.get("Ngày tạo") or ""
    tieu_chi = row_dict.get("Tiêu Chí") or ""
    if id_phieu:
        return f"phieu_{id_phieu}"
    if cua_hang and tieu_chi:
        return f"{cua_hang}_{tieu_chi}_{ngay_tao}"
    return f"row_{row_dict.get('_row_number')}"

def get_row_hash(row_dict):
    """Tạo hash băm nội dung để phát hiện cập nhật giải trình hoặc sửa đổi"""
    serialized = json.dumps({k: v for k, v in row_dict.items() if not k.startswith("_")}, sort_keys=True)
    return hashlib.md5(serialized.encode("utf-8")).hexdigest()

def send_telegram_alert(message_html):
    """Gửi cảnh báo DUY NHẤT đến room The 5 Guardians theo chỉ đạo anh Lộc (bỏ 2 room kia)"""
    targets = [
        {"name": "The 5 Guardians", "chat_id": GUARDIANS_CHAT_ID, "thread_id": None}
    ]
    results = {}
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    for t in targets:
        payload = {
            "chat_id": t["chat_id"],
            "text": message_html,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        if t["thread_id"]:
            payload["message_thread_id"] = t["thread_id"]
        try:
            r = requests.post(url, json=payload, timeout=12)
            data = r.json()
            results[t["name"]] = data.get("ok", False)
            if not data.get("ok"):
                print(f"[GHNa Telegram] Lỗi gửi {t['name']}: {data}")
        except Exception as e:
            results[t["name"]] = False
            print(f"[GHNa Telegram] Ngoại lệ gửi {t['name']}: {e}")

    return results

def format_alert_message(new_rows, updated_rows):
    """Định dạng bản tin Telegram đẹp mắt, chỉn chu"""
    now_str = get_now_str()
    lines = [
        "🐯 <b>[TIGER AI • BÁO CÁO CẬP NHẬT TAB GHNa]</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ <b>Thời điểm quét:</b> <code>{now_str}</code>",
        f"📊 <b>Biến động:</b> <b>{len(new_rows)} dữ liệu mới</b> • <b>{len(updated_rows)} giải trình cập nhật</b>",
        ""
    ]

    if new_rows:
        lines.append("🆕 <b>DỮ LIỆU ĐƯỢC ĐIỀN MỚI:</b>")
        for idx, item in enumerate(new_rows[:10], start=1):
            cua_hang = item.get("Cửa hàng") or "Chưa rõ"
            vung = item.get("Vùng") or "MT"
            id_phieu = item.get("ID phiếu (wo_link)") or item.get("ID phiếu") or "N/A"
            bai_cham = item.get("Bài Chấm") or "N/A"
            tieu_chi = item.get("Tiêu Chí") or "N/A"
            nv_vi_pham = item.get("Tên NV Vi phạm (CHỐT CUỐI)") or item.get("Tên NV Vi phạm") or "Chưa gán"
            id_nv = item.get("ID NV Vi phạm (CHỐT CUỐI)") or item.get("ID NV Vi phạm") or ""
            muc_phat = item.get("MỨC PHẠT") or "0"
            note = item.get("[BƯU CỤC KHẮC PHỤC] BC note giải trình") or item.get("GHI CHÚ") or "Chưa có note"
            trang_thai = item.get("TRẠNG THÁI") or "Mới"

            lines.append(
                f"<b>{idx}. Bưu cục:</b> <b>{cua_hang}</b> ({vung})\n"
                f"   ├ 🎫 Phiếu: <code>{id_phieu}</code> | Trạng thái: <b>{trang_thai}</b>\n"
                f"   ├ ⚠️ Tiêu chí: {tieu_chi} ({bai_cham})\n"
                f"   ├ 👤 NV vi phạm: <b>{nv_vi_pham}</b>" + (f" (<code>{id_nv}</code>)" if id_nv else "") + "\n"
                f"   ├ 💰 Mức phạt: <code>{muc_phat}</code>\n"
                f"   └ 📝 Giải trình BC: <i>\"{note}\"</i>"
            )

    if updated_rows:
        lines.append("")
        lines.append("📝 <b>GIẢI TRÌNH / GHI CHÚ VỪA CẬP NHẬT:</b>")
        for idx, item in enumerate(updated_rows[:10], start=1):
            cua_hang = item.get("Cửa hàng") or "Chưa rõ"
            id_phieu = item.get("ID phiếu (wo_link)") or item.get("ID phiếu") or "N/A"
            note = item.get("[BƯU CỤC KHẮC PHỤC] BC note giải trình") or item.get("GHI CHÚ") or ""
            trang_thai = item.get("TRẠNG THÁI") or "Đang xử lý"

            lines.append(
                f"<b>{idx}. Bưu cục:</b> <b>{cua_hang}</b> (Phiếu <code>{id_phieu}</code>)\n"
                f"   ├ 📝 Note mới: <i>\"{note}\"</i>\n"
                f"   └ 📌 Trạng thái: <b>{trang_thai}</b>"
            )

    lines.append("")
    lines.append("📊 <b>Link vào ngay tab GHNa:</b>")
    lines.append(f"👉 <a href='{SHEET_VIEW_URL}'>{SHEET_VIEW_URL}</a>")
    lines.append("<i>Tiger AI tự động rà soát 4 lần/ngày: 08:00 • 12:00 • 16:00 • 20:00</i>")

    return "\n".join(lines)

def run_check(force_send=False, silent_if_empty=True):
    """
    Hàm kiểm tra dữ liệu tab GHNa chính:
    - force_send: ép gửi báo cáo ngay cả khi không có dòng mới (dùng khi test)
    - silent_if_empty: nếu không có gì mới thì không làm phiền Telegram
    """
    print(f"[{get_now_str()}] [GHNa Monitor] Đang nạp dữ liệu từ Google Sheet tab GHNa...")
    try:
        raw_rows = fetch_ghna_sheet_rows()
    except Exception as e:
        print(f"[GHNa Monitor] Lỗi nạp Google Sheet: {e}")
        return {"status": "error", "error": str(e)}

    headers, current_data_rows = parse_ghna_data(raw_rows)
    print(f"[GHNa Monitor] Đã đọc {len(current_data_rows)} dòng dữ liệu trong tab GHNa.")

    snapshot = load_snapshot()
    known_records = snapshot.get("records", {})
    is_initial_run = (len(known_records) == 0 and snapshot.get("last_scanned_at") is None)

    new_rows = []
    updated_rows = []
    new_records_map = {}

    for row in current_data_rows:
        ident = get_row_identity(row)
        r_hash = get_row_hash(row)
        new_records_map[ident] = {
            "hash": r_hash,
            "data": row
        }

        if ident not in known_records:
            if not is_initial_run:
                new_rows.append(row)
        else:
            old_hash = known_records[ident].get("hash")
            if old_hash and old_hash != r_hash:
                updated_rows.append(row)

    # Cập nhật snapshot mới
    snapshot["last_scanned_at"] = get_now_str()
    snapshot["total_rows"] = len(current_data_rows)
    snapshot["records"] = new_records_map
    save_snapshot(snapshot)

    has_changes = (len(new_rows) > 0 or len(updated_rows) > 0)
    telegram_res = None

    if has_changes or force_send:
        if has_changes:
            msg = format_alert_message(new_rows, updated_rows)
        else:
            # Thông điệp kiểm tra định kỳ không có biến động
            now_str = get_now_str()
            msg = (
                "🐯 <b>[TIGER AI • KIỂM TRA ĐỊNH KỲ TAB GHNa]</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏰ <b>Thời điểm kiểm tra:</b> <code>{now_str}</code>\n"
                f"📋 <b>Hiện trạng:</b> Tab <b>GHNa</b> hiện có <b>{len(current_data_rows)} dòng dữ liệu</b>.\n"
                "✅ <i>Chưa phát sinh dữ liệu mới hoặc ghi chú vi phạm mới từ bưu cục. Tiger AI sẽ tiếp tục rà soát ca kế tiếp!</i> 🍻\n\n"
                "📊 <b>Link vào ngay tab GHNa:</b>\n"
                f"👉 <a href='{SHEET_VIEW_URL}'>{SHEET_VIEW_URL}</a>"
            )
        print("[GHNa Monitor] Gửi thông báo đến Telegram...")
        telegram_res = send_telegram_alert(msg)
    else:
        print(f"[{get_now_str()}] [GHNa Monitor] Không có dữ liệu mới. Im lặng theo dõi.")

    return {
        "status": "success",
        "scanned_at": snapshot["last_scanned_at"],
        "total_rows": len(current_data_rows),
        "new_count": len(new_rows),
        "updated_count": len(updated_rows),
        "telegram_sent": bool(telegram_res),
        "telegram_details": telegram_res
    }

if __name__ == "__main__":
    force = "--send" in sys.argv or "--force" in sys.argv
    res = run_check(force_send=force, silent_if_empty=not force)
    print(json.dumps(res, indent=2, ensure_ascii=False))


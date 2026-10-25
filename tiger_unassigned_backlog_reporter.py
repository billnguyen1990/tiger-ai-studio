import requests
import json
import datetime
import os
import sys
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(BASE_DIR, "headers_found.json")
MAP_FILE = os.path.join(BASE_DIR, "nvxl_telegram_map.json")

# Telegram Config (Group: Miền Tây 01 - Topic: Báo Cáo)
TELEGRAM_BOT_TOKEN = "8777045986:AAEX1uau8GFdxPAj0aAVUwDNQnpQb1IZOIA"
TELEGRAM_CHAT_ID = "-1003940889949"
TELEGRAM_MESSAGE_THREAD_ID = 2690

URL_GENERAL = "https://nhanh-api.ghn.vn/api/core/oss/v1/report/get-general-info"
URL_DETAIL = "https://nhanh-api.ghn.vn/api/core/oss/v1/report/get-detail-by-code"
URL_HIST = "https://nhanh-api.ghn.vn/api/lastmile/history/get-order-history"

DURATION_LABELS = [
    ("0_6", "00 - 06h"),
    ("6_12", "06 - 12h"),
    ("12_24", "12 - 24h"),
    ("24_36", "24 - 36h"),
    ("36_48", "36 - 48h"),
    ("48_72", "48 - 72h"),
    ("72_96", "72 - 96h"),
    ("96_120", "96 - 120h"),
    ("120_192", "120 - 192h"),
    ("192_", "192h+")
]

def get_headers():
    if not os.path.exists(HEADERS_FILE):
        raise FileNotFoundError(f"Không tìm thấy file {HEADERS_FILE}")
    with open(HEADERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_nvxl_map():
    if not os.path.exists(MAP_FILE):
        raise FileNotFoundError(f"Không tìm thấy file {MAP_FILE}")
    with open(MAP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_order_reason_and_appointment(headers, order_code):
    """
    Bóc tách lý do lưu kho và trích xuất NGÀY KHÁCH HẸN RÕ RÀNG (DD/MM/YYYY)
    từ lịch sử SMS và cập nhật của NV.
    """
    url = URL_HIST
    payload = {"orderCode": order_code, "paging": {"offset": 0, "limit": 25}}
    sms_date = ""
    next_redo_date = ""
    last_reason = ""

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=5).json()
        items = r.get("data", {}).get("data", []) or []

        for it in items:
            ht = it.get("historyType")
            d_str = it.get("data", "")

            # 1. Quét tin nhắn SMS gửi khách để tìm ngày hẹn chuẩn (DD/MM/YYYY)
            if ht == "SMS" and not sms_date:
                try:
                    dj = json.loads(d_str)
                    content = dj.get("content", "")
                    m = re.search(r'ngay\s*([0-9]{1,2}[\-\/][0-9]{1,2}[\-\/][0-9]{4})', content)
                    if m:
                        sms_date = m.group(1).replace("-", "/")
                except:
                    pass

            # 2. Quét UPDATE_ITEM lấy nextRedoTime
            if ht == "UPDATE_ITEM" and not next_redo_date:
                try:
                    dj = json.loads(d_str)
                    if dj.get("nextRedoTime"):
                        dt = datetime.datetime.strptime(dj["nextRedoTime"][:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=7)
                        next_redo_date = dt.strftime("%d/%m/%Y")
                    if not last_reason:
                        last_reason = dj.get("note") or dj.get("failReasonName") or ""
                except:
                    pass

            # 3. Lấy failReason/Note gần nhất nếu có
            if not last_reason:
                try:
                    dj = json.loads(d_str)
                    if isinstance(dj, dict):
                        last_reason = dj.get("note") or dj.get("failReasonName") or dj.get("failNote") or ""
                except:
                    pass

        # Ngày hẹn ưu tiên lấy từ SMS rồi đến nextRedoTime
        exact_date = sms_date or next_redo_date

        if exact_date:
            final_reason = f"Khách hẹn giao lại ngày: {exact_date}"
        elif last_reason:
            final_reason = last_reason
        elif items:
            last_item = items[0]
            final_reason = f"{last_item.get('historyType')} ({last_item.get('createdByName', 'Hệ thống')})"
        else:
            final_reason = "Đơn mới nhập kho / Chờ xử lý"

        return final_reason
    except Exception as e:
        return f"Lỗi tra cứu: {e}"

def run_unassigned_audit():
    headers = get_headers()
    nvxl_map = get_nvxl_map()
    now = datetime.datetime.now()

    payload = {
        "hub_ids": list(nvxl_map.keys()),
        "view_mode": "CLIENT",
        "order_type": "DAILY_TRIP_NONE"
    }

    r = requests.post(URL_GENERAL, json=payload, headers=headers, timeout=10).json()
    items = r.get("data", []) or []

    results = {
        "date_str": now.strftime("%d/%m/%Y"),
        "time_str": now.strftime("%H:%M"),
        "hubs": {}
    }

    # Gom theo hub_id
    for hub_item in items:
        hid = hub_item.get("hub_id")
        if hid not in nvxl_map:
            continue

        info = nvxl_map[hid]
        hname = info["short_name"]
        nvxl_tag = info["telegram_tag"]

        bucket_counts = {k: 0 for k, _ in DURATION_LABELS}
        bucket_codes = {}
        total_unassigned = 0

        for gi in hub_item.get("general_infos", []):
            if gi.get("order_type") == "DELIVER":
                for inv in gi.get("order_inventories", []):
                    dur = inv.get("duration")
                    cnt = inv.get("total_order", 0)
                    code_grp = inv.get("code")
                    if dur in bucket_counts:
                        bucket_counts[dur] = cnt
                        total_unassigned += cnt
                    if cnt > 0 and code_grp:
                        bucket_codes[dur] = code_grp

        # Lấy chi tiết đơn hàng
        detailed_orders = []
        headers["x-warehouseid"] = hid
        for dur, grp_code in bucket_codes.items():
            dur_display = next((d_lbl for k, d_lbl in DURATION_LABELS if k == dur), dur)
            try:
                r_c = requests.post(URL_DETAIL, json={
                    "code": grp_code,
                    "view_mode": "CLIENT",
                    "order_type": "DAILY_TRIP_NONE"
                }, headers=headers, timeout=10).json()
                ocodes = r_c.get("data", {}).get("order_codes", []) or []
                for oc in ocodes[:15]: # Giới hạn 15 đơn tiêu biểu mỗi khung để tin nhắn không quá dài
                    reason = extract_order_reason_and_appointment(headers, oc)
                    detailed_orders.append({
                        "order_code": oc,
                        "duration_bucket": dur_display,
                        "reason": reason
                    })
            except Exception as e:
                print(f"Lỗi lấy detail {grp_code}: {e}")

        results["hubs"][hid] = {
            "hub_name": hname,
            "nvxl_name": info["nvxl_name"],
            "nvxl_tag": nvxl_tag,
            "total_unassigned": total_unassigned,
            "buckets": bucket_counts,
            "detailed_orders": detailed_orders
        }

    return results

def format_unassigned_message(results):
    d = results["date_str"]
    lines = []
    lines.append("📦 <b>TIGER AI - BÁO CÁO ĐƠN CHƯA GÁN & LƯU KHO MIỀN TÂY 01 (10:00)</b>")
    lines.append(f"📅 <i>Ngày: {d} | Thời điểm kiểm tra: 10:00 sáng (Sau khi gán chuyến)</i>")
    lines.append("━" * 30)

    total_all = sum(h["total_unassigned"] for h in results["hubs"].values())
    lines.append(f"⚠️ <b>TỔNG ĐƠN TỒN CHƯA GÁN TOÀN CỤM MT01:</b> <b>{total_all} đơn hàng</b> đang lưu tại kho!")
    lines.append("━" * 30)

    for hid, h in results["hubs"].items():
        nvxl_name = h.get("nvxl_name", "")
        lines.append(f"🏢 <b>Kho {h['hub_name']}</b> (NVXL: {nvxl_name}): Còn <b>{h['total_unassigned']} đơn chưa gán</b>")

        # Bảng tóm tắt các khung giờ có đơn
        active_buckets = []
        for k, lbl in DURATION_LABELS:
            cnt = h["buckets"].get(k, 0)
            if cnt > 0:
                active_buckets.append(f"<code>{lbl}</code>: <b>{cnt} đơn</b>")

        if active_buckets:
            lines.append(f"  └ 🕒 <i>Phân bổ lưu kho:</i> " + " | ".join(active_buckets))
        else:
            lines.append("  └ 🎉 <i>Kho sạch đơn tồn, 100% đơn đã được gán đi giao!</i>")

        # Chi tiết lý do và ngày khách hẹn
        if h["detailed_orders"]:
            lines.append("  └ 📋 <i>Chi tiết đơn & Ngày khách hẹn rõ ràng:</i>")
            diff_lines = ["<pre><code class=\"language-diff\">"]
            for o in h["detailed_orders"][:5]:
                safe_reason = o['reason']
                icon = "⚠️" if "hẹn" in safe_reason.lower() else "❌"
                diff_lines.append(f"- {icon} {o['order_code']}: {safe_reason} [{o['duration_bucket']}]")
            diff_lines.append("</code></pre>")
            lines.append("\n".join(diff_lines))
        lines.append("")

    lines.append("━" * 30)
    lines.append("👉 <b>YÊU CẦU NVXL CÁC KHO:</b> Rà soát các đơn lưu kho quá 24h và các đơn khách hẹn ngày hôm nay để gán chuyến ca chiều cho NV giao dứt điểm!")

    return "\n".join(lines)

def send_telegram_alert(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_thread_id": TELEGRAM_MESSAGE_THREAD_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        res = r.json()
        if res.get("ok"):
            print("✅ Đã gửi báo cáo đơn chưa gán 10:00 lên Telegram thành công!")
            return True
        else:
            print(f"❌ Lỗi gửi Telegram: {res}")
            return False
    except Exception as e:
        print(f"❌ Lỗi kết nối Telegram: {e}")
        return False

def main():
    args = sys.argv[1:]
    is_send = "--send" in args

    print("⏳ Tiger AI đang quét đơn chưa gán & 10 khung giờ lưu kho 10:00 cho 4 kho MT01...")
    data = run_unassigned_audit()
    msg = format_unassigned_message(data)

    print("\n" + "=" * 55)
    print("NỘI DUNG BÁO CÁO ĐƠN CHƯA GÁN 10:00:")
    print("=" * 55)
    print(msg)
    print("=" * 55 + "\n")

    if is_send:
        print("🚀 Đang tiến hành gửi lên nhóm Telegram Miền Tây 01 (Chủ đề Báo Cáo)...")
        send_telegram_alert(msg)
    else:
        print("💡 Chế độ Dry-Run (chưa gửi). Dùng cờ: --send để gửi thực tế.")

if __name__ == "__main__":
    main()

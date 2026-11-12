import requests
import json
import datetime
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(BASE_DIR, "headers_found.json")
MAP_FILE = os.path.join(BASE_DIR, "nvxl_telegram_map.json")
HISTORY_DIR = os.path.join(BASE_DIR, "assigned_history")

# Telegram Config (Group: Miền Tây 01 - Topic: Báo Cáo)
TELEGRAM_BOT_TOKEN = "8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk"
TELEGRAM_CHAT_ID = "-1003940889949"
TELEGRAM_MESSAGE_THREAD_ID = 2690

URL_TRIPS = "https://nhanh-api.ghn.vn/api/lastmile/trip/get-trip-list-by-hub"

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

def get_vietnam_now():
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    vn_tz = datetime.timezone(datetime.timedelta(hours=7))
    return utc_now.astimezone(vn_tz)

def get_vietnam_today():
    return get_vietnam_now().date()

def run_assigned_audit(target_date=None):
    headers = get_headers()
    nvxl_map = get_nvxl_map()

    if target_date is None:
        target_dt = get_vietnam_today()
    elif isinstance(target_date, str):
        target_date = target_date.strip()
        if "-" in target_date:
            target_dt = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
        else:
            target_dt = datetime.datetime.strptime(target_date, "%Y%m%d").date()
    else:
        target_dt = target_date

    date_int = int(target_dt.strftime("%Y%m%d"))
    date_iso = target_dt.strftime("%Y-%m-%d")
    date_display = target_dt.strftime("%d/%m/%Y")

    results = {
        "date_str": date_display,
        "date_iso": date_iso,
        "hubs": {}
    }

    for hid, info in nvxl_map.items():
        hname = info["short_name"]
        nvxl_tag = info["telegram_tag"]
        h_headers = headers.copy()
        h_headers["x-warehouseid"] = str(hid)

        hub_trips = []
        for st in ["ON_TRIP", "NEW", "FINISHED"]:
            p = {
                "hub_id": str(hid),
                "status": st,
                "is_ready": 0,
                "offset": 0,
                "limit": 50,
                "reverse": 1
            }
            trips = []
            for attempt in range(2):
                try:
                    r = requests.post(URL_TRIPS, headers=h_headers, json=p, timeout=12).json()
                    trips = r.get("data", []) or []
                    break
                except Exception as e:
                    if attempt == 0:
                        time.sleep(1)
                    else:
                        print(f"⚠️ Lỗi lấy chuyến status {st} kho {hname}: {e}")

            for t in trips:
                c_date = t.get("createDateIndex")
                s_date = t.get("startDateIndex")
                c_time = str(t.get("createdTime") or "")
                s_time = str(t.get("startTime") or "")
                if c_date == date_int or s_date == date_int or c_time.startswith(date_iso) or s_time.startswith(date_iso):
                    hub_trips.append(t)

        # Tổng hợp chuyến và đơn
        total_orders = sum(t.get("deliverCount", 0) for t in hub_trips)
        
        trip_details = []
        for t in hub_trips:
            tc = t.get("tripCode")
            driver = t.get("driverName") or "Chưa gán"
            phone = t.get("driverPhone") or ""
            d_cnt = t.get("deliverCount", 0)
            st = t.get("status")
            st_text = "Đang giao" if st == "ON_TRIP" else ("Mới tạo" if st == "NEW" else "Kết thúc")
            
            st_raw = t.get("startTime") or t.get("createdTime") or ""
            st_vn = ""
            if st_raw:
                try:
                    dt = datetime.datetime.strptime(st_raw[:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=7)
                    st_vn = dt.strftime("%H:%M")
                except:
                    st_vn = st_raw
                    
            trip_details.append({
                "trip_code": tc,
                "driver_name": driver,
                "driver_phone": phone,
                "order_count": d_cnt,
                "status_text": st_text,
                "start_time": st_vn
            })

        # Sắp xếp số đơn nhiều nhất lên đầu
        trip_details.sort(key=lambda x: x["order_count"], reverse=True)

        results["hubs"][hid] = {
            "hub_name": hname,
            "nvxl_name": info["nvxl_name"],
            "nvxl_tag": nvxl_tag,
            "trips_count": len(hub_trips),
            "total_orders": total_orders,
            "trip_details": trip_details
        }

    # Tự động lưu lịch sử JSON
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        hist_file = os.path.join(HISTORY_DIR, f"assigned_{date_int}.json")
        with open(hist_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Không thể lưu lịch sử assigned: {e}")

    return results

def format_assigned_message(results):
    d = results["date_str"]
    lines = []
    lines.append("🚚 <b>TIGER AI - BÁO CÁO GIÁM SÁT GÁN CHUYẾN SÁNG MIỀN TÂY 01 (09:00)</b>")
    lines.append(f"📅 <i>Ngày: {d} | Thời điểm kiểm tra: 09:00 sáng</i>")
    lines.append("━" * 30)

    total_all_trips = sum(h["trips_count"] for h in results["hubs"].values())
    total_all_orders = sum(h["total_orders"] for h in results["hubs"].values())
    lines.append(f"📦 <b>TỔNG TOÀN CỤM MT01:</b> <b>{total_all_trips} chuyến xe</b> | <b>{total_all_orders:,} đơn hàng</b> đã xuất bến!")
    lines.append("━" * 30)

    for hid, h in results["hubs"].items():
        nvxl_name = h.get("nvxl_name", "")
        lines.append(f"🏢 <b>Kho {h['hub_name']}</b> (NVXL: {nvxl_name}):")
        lines.append(f"  └ 📊 Tổng: <b>{h['trips_count']} chuyến</b> | <b>{h['total_orders']} đơn hàng</b>")
        if h["trip_details"]:
            for t in h["trip_details"]:
                lines.append(f"     🚗 <code>{t['trip_code']}</code> - <b>NV {t['driver_name']}</b>: <b>{t['order_count']} đơn</b> ({t['status_text']}, xuất bến: {t['start_time']})")
        else:
            lines.append("     ⚠ <i>Chưa phát sinh chuyến xe nào được gán trong sáng nay!</i>")
        lines.append("")

    lines.append("━" * 30)
    lines.append("💡 <i>Nhắc nhở NVXL: Kiểm tra kỹ kho, chuyển sang bước rà soát đơn chưa gán/tồn đọng để xử lý dứt điểm trước 10:00!</i>")

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
            print("✅ Đã gửi báo cáo gán chuyến sáng 09:00 lên Telegram thành công!")
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
    is_force = "--force" in args

    target_date = None
    for idx, arg in enumerate(args):
        if arg == "--date" and idx + 1 < len(args):
            target_date = args[idx + 1]

    print("⏳ Tiger AI đang quét dữ liệu Gán Chuyến Sáng 09:00 cho 4 kho MT01...")
    data = run_assigned_audit(target_date=target_date)

    total_all_trips = sum(h["trips_count"] for h in data["hubs"].values())
    total_all_orders = sum(h["total_orders"] for h in data["hubs"].values())

    # Chốt chặn an toàn chống rỗng (Anti-Zero Safeguard)
    if total_all_trips == 0 and not is_force:
        print("❌ CẢNH BÁO: Toàn bộ 4 kho MT01 ghi nhận 0 chuyến gán (nghi vấn mạng GHN gián đoạn hoặc API lỗi). Hủy gửi báo cáo để tránh thông tin 0 chuyến sai lệch!")
        if is_send:
            sys.exit(1)
        return

    msg = format_assigned_message(data)

    print("\n" + "=" * 55)
    print("NỘI DUNG BÁO CÁO GÁN CHUYẾN SÁNG 09:00:")
    print("=" * 55)
    print(msg)
    print("=" * 55 + "\n")

    if is_send:
        print("🚀 Đang tiến hành gửi lên nhóm Telegram Miền Tây 01 (Chủ đề Báo Cáo)...")
        success = send_telegram_alert(msg)
        if not success:
            sys.exit(1)
    else:
        print("💡 Chế độ Dry-Run (chưa gửi). Dùng cờ: --send để gửi thực tế.")

if __name__ == "__main__":
    main()

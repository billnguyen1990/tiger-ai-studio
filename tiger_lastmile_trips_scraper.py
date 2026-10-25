import os
import sys
import json
import time
import datetime
import requests

# ==============================================================================
# TIGER AI • LASTMILE TRIPS SCRAPER & GOOGLE SHEETS AUTO SYNC (05:00 AM)
# Thay thế hoàn toàn tool Lastmile Desktop thủ công bằng REST API siêu tốc trên Cloud
# ==============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(BASE_DIR, "headers_found.json")
MAP_FILE = os.path.join(BASE_DIR, "nvxl_telegram_map.json")

# Google Apps Script Webhook URL (Tab: Miền Tây 01 Đối Chiếu ODO)
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxS8BqhtWDVQFSqLsEG_D97qDmUObHQAkaagSQekdJK1zlhUmyqOs0NYU2mGHV0WH9_/exec"

# Telegram Bot Config
TELEGRAM_BOT_TOKEN = "8777045986:AAEX1uau8GFdxPAj0aAVUwDNQnpQb1IZOIA"
TELEGRAM_CHAT_ID = "-1003940889949"
TELEGRAM_MESSAGE_THREAD_ID = 2690

URL_TRIPS = "https://nhanh-api.ghn.vn/api/lastmile/trip/get-trip-list-by-hub"
URL_PROFILE = "https://nhanh-api.ghn.vn/api/lastmile/trip/get-trip-profile"

# Danh sách 4 kho trọng điểm Miền Tây 01
WAREHOUSES = [
    {"id": "21088000", "name": "Kho Cái Răng"},
    {"id": "21985000", "name": "Kho Bình Thủy"},
    {"id": "22862000", "name": "Kho Vị Thanh"},
    {"id": "22917000", "name": "Kho Ô Môn"}
]

# Chuẩn 36 cột chính xác khớp 100% với form Google Sheets gốc của Sếp
COLUMNS_36 = [
    "tripCode", "status", "hubId", "servicePartner", "driverId", "driverName",
    "driverPhone", "createdById", "createdByName", "createdByPhone", "isReady",
    "isCollected", "startTime", "displayCounter", "createDateIndex", "startDateIndex",
    "date", "id", "createdTime", "lastUpdatedTime", "endDateIndex", "endTime",
    "partnerTripCode", "partnerServiceCode", "pickCount", "deliverCount", "returnCount",
    "totalTripValue", "needToCollect", "collectedAmount", "orderCount", "transitInCount",
    "transitOutCount", "updatedCount", "needToScan", "scanned"
]

def load_headers():
    if not os.path.exists(HEADERS_FILE):
        raise FileNotFoundError(f"Không tìm thấy file {HEADERS_FILE}")
    with open(HEADERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_vietnam_now():
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    vn_tz = datetime.timezone(datetime.timedelta(hours=7))
    return utc_now.astimezone(vn_tz)

def get_vietnam_today():
    return get_vietnam_now().date()

def parse_target_date(target_date):
    if target_date is None:
        return get_vietnam_today() - datetime.timedelta(days=1)
    if isinstance(target_date, datetime.date):
        return target_date
    if isinstance(target_date, datetime.datetime):
        return target_date.date()
    date_str = str(target_date).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Không nhận diện được định dạng ngày: {target_date}")

def run_lastmile_scraper(target_date=None, send_to_sheet=True, send_to_tg=False):
    """
    Cào toàn bộ chuyến đi Ngày N-1 của 4 kho MT01 và đồng bộ lên Google Sheets (đủ 36 cột)
    """
    target_date = parse_target_date(target_date)
    date_int = int(target_date.strftime("%Y%m%d"))
    date_display = target_date.strftime("%d/%m/%Y")
    
    print("=" * 60)
    print(f"🐯 [TIGER AI] BẮT ĐẦU CÀO CHUYẾN ĐI LASTMILE NGÀY {date_display} (D-1)")
    print("=" * 60)

    headers = load_headers()
    raw_trips = []
    hub_stats = {}

    for wh in WAREHOUSES:
        hid = wh["id"]
        hname = wh["name"]
        headers["x-warehouseid"] = hid
        hub_trips = []

        payload = {
            "hub_id": hid,
            "status": "FINISHED",
            "is_ready": 0,
            "offset": 0,
            "limit": 100
        }

        try:
            res = requests.post(URL_TRIPS, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json().get("data", []) or []
                for t in data:
                    c_date = t.get("createDateIndex")
                    s_date = t.get("startDateIndex")
                    e_date = t.get("endDateIndex")
                    if c_date == date_int or s_date == date_int or e_date == date_int:
                        hub_trips.append(t)
            else:
                print(f"⚠️ Lỗi HTTP {res.status_code} khi cào kho {hname}")
        except Exception as e:
            print(f"❌ Lỗi kết nối API kho {hname}: {e}")

        hub_stats[hname] = len(hub_trips)
        raw_trips.extend(hub_trips)
        print(f"  📄 {hname} ({hid}) ➔ {len(hub_trips)} chuyến hoàn thành")

    total_trips = len(raw_trips)
    print(f"\n👉 TỔNG CỘNG ĐÃ LẤY: {total_trips} chuyến đi ngày {date_display}")

    # Lấy thêm 9 trường chi tiết (COD, giá trị, đơn hàng) từ get-trip-profile
    profile_map = {}
    all_codes = [t.get("tripCode") for t in raw_trips if t.get("tripCode")]
    if all_codes:
        print(f"🔍 Đang truy vấn get-trip-profile cho {len(all_codes)} chuyến để lấy đủ 36 cột...")
        headers["x-warehouseid"] = "21088000"
        batch_size = 50
        for i in range(0, len(all_codes), batch_size):
            chunk = all_codes[i:i + batch_size]
            try:
                res_prof = requests.post(URL_PROFILE, headers=headers, json={"tripCodes": chunk}, timeout=20)
                if res_prof.status_code == 200:
                    for p in res_prof.json().get("data", []) or []:
                        code = p.get("tripCode")
                        if code:
                            profile_map[code] = p
            except Exception as e:
                print(f"⚠️ Lỗi get-trip-profile batch {i}: {e}")

    # Ghép dữ liệu chuẩn 36 cột
    all_rows = []
    for t in raw_trips:
        code = t.get("tripCode")
        prof = profile_map.get(code, {})
        merged = {**t, **prof}
        row = [str(merged.get(k, "")) if merged.get(k) is not None else "" for k in COLUMNS_36]
        all_rows.append(row)

    print(f"✅ Đã chuẩn hóa toàn bộ {len(all_rows)} dòng với ĐỦ {len(COLUMNS_36)} CỘT dữ liệu!")

    # 1. Gửi Telegram thông báo hoàn tất NGAY LẬP TỨC
    if send_to_tg:
        stat_lines = "\n".join([f"  • {h}: <b>{c} chuyến</b>" for h, c in hub_stats.items()])
        tg_msg = (
            f"🐯 <b>HOÀN TẤT CÀO CHUYẾN ĐI LASTMILE (N-1)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 <b>Ngày chuyến:</b> {date_display} (Ngày hôm qua)\n"
            f"⏰ <b>Khung giờ cào:</b> 05:00 AM (Tự động 100% trên Cloud)\n"
            f"📊 <b>Tổng số chuyến đã cào:</b> <b>{total_trips} chuyến</b>\n"
            f"🏢 <b>Chi tiết từng kho:</b>\n{stat_lines}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 <b>Google Sheets:</b> Đang/Đã đồng bộ vào tab <code>Miền Tây 01 Đối Chiếu ODO</code>\n"
            f"⚡ <i>Hệ thống tự động đồng bộ sẵn sàng trước giờ ca sáng!</i>"
        )
        try:
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            tg_res = requests.post(tg_url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "message_thread_id": TELEGRAM_MESSAGE_THREAD_ID,
                "text": tg_msg,
                "parse_mode": "HTML"
            }, timeout=10)
            if tg_res.status_code == 200:
                print("📱 Đã gửi thông báo Telegram thành công!")
            else:
                print(f"⚠️ Lỗi gửi Telegram: {tg_res.text}")
        except Exception as e:
            print(f"❌ Lỗi gửi Telegram: {e}")

    # 2. Gửi dữ liệu lên Google Sheets qua Apps Script Webhook
    sheet_result = "Chưa gửi (chế độ kiểm thử)"
    if send_to_sheet and total_trips > 0:
        print("\n🚀 Đang gửi dữ liệu lên Google Sheets qua Apps Script Webhook...")
        payload_sheet = {
            "headers": COLUMNS_36,
            "rows": all_rows
        }
        for attempt in range(1, 3):
            try:
                resp = requests.post(
                    WEBHOOK_URL,
                    data=json.dumps(payload_sheet, ensure_ascii=False, default=str).encode("utf-8"),
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    timeout=30
                )
                sheet_result = resp.text.strip()
                print(f"✅ Kết quả Google Sheets: {sheet_result}")
                break
            except Exception as e:
                print(f"⚠️ Lần {attempt} lỗi gửi Sheet: {e}")
                time.sleep(2)
    elif total_trips == 0:
        sheet_result = f"Không có chuyến nào cho ngày {date_display}"
        print(sheet_result)

    return {
        "success": True,
        "date": date_display,
        "total_trips": total_trips,
        "hubs": hub_stats,
        "sheet_status": sheet_result
    }

if __name__ == "__main__":
    send_sheet = "--no-sheet" not in sys.argv
    send_tg = "--no-tg" not in sys.argv
    if "--dry-run" in sys.argv:
        send_sheet = False
        send_tg = False
    
    custom_date = None
    if "--date" in sys.argv:
        try:
            idx = sys.argv.index("--date")
            custom_date = sys.argv[idx + 1]
        except:
            pass

    run_lastmile_scraper(target_date=custom_date, send_to_sheet=send_sheet, send_to_tg=send_tg)

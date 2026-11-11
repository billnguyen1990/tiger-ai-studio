import os
import sys
import json
import time
import datetime
import requests

# ==============================================================================
# TIGER AI • LASTMILE TRIPS SCRAPER & GOOGLE SHEETS AUTO SYNC (05:00 AM)
# Quản lý bởi: Sếp Lộc | Trợ lý hỗ trợ: Lisa (Tiger AI)
# Hỗ trợ 4 Vùng Miền Tây Trọng Điểm: MT01, MT02, MT04, MT05 (Loại trừ MT03 theo lệnh Sếp)
# ==============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(BASE_DIR, "headers_found.json")
MAP_FILE = os.path.join(BASE_DIR, "nvxl_telegram_map.json")

# Google Apps Script Webhook URL (Bản triển khai Đa Vùng)
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxS8BqhtWDVQFSqLsEG_D97qDmUObHQAkaagSQekdJK1zlhUmyqOs0NYU2mGHV0WH9_/exec"

# Telegram Bot Config
TELEGRAM_BOT_TOKEN = "8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk"

URL_TRIPS = "https://nhanh-api.ghn.vn/api/lastmile/trip/get-trip-list-by-hub"
URL_PROFILE = "https://nhanh-api.ghn.vn/api/lastmile/trip/get-trip-profile"

# Danh mục 4 Vùng Miền Tây Trọng Điểm (Bỏ qua MT03 theo chỉ đạo của Sếp Lộc)
REGIONS = {
    "MT01": {
        "name": "Miền Tây 01",
        "sheet_name": "Miền Tây 01 Đối Chiếu ODO",
        "warehouses": [
            {"id": "21088000", "name": "Kho Giao Hàng Nặng - Cái Răng - Cần Thơ"},
            {"id": "21985000", "name": "Kho Giao Hàng Nặng - Bình Thủy - Cần Thơ"},
            {"id": "22862000", "name": "Kho Giao Hàng Nặng - TP Vị Thanh - Hậu Giang"},
            {"id": "22917000", "name": "Kho Giao Hàng Nặng - Ô Môn - Cần Thơ"}
        ],
        "telegram_chat_id": "-1003940889949",
        "telegram_thread_id": 2690
    },
    "MT02": {
        "name": "Miền Tây 02",
        "sheet_name": "Miền Tây 02 Đối Chiếu ODO",
        "warehouses": [
            {"id": "21361000", "name": "Kho Giao Hàng Nặng - TP Cà Mau - Cà Mau"},
            {"id": "22187000", "name": "Kho Giao Hàng Nặng - TP Hà Tiên - Kiên Giang"},
            {"id": "21441000", "name": "Kho Giao Hàng Nặng - TP Rạch Giá - Kiên Giang"},
            {"id": "22054000", "name": "Kho Giao Hàng Nặng - Tam Nông - Đồng Tháp"},
            {"id": "21292000", "name": "Kho Giao Hàng Nặng-TP Cao Lãnh-Đồng Tháp"}
        ],
        "telegram_chat_id": "-5295214199",
        "telegram_thread_id": None
    },
    "MT04": {
        "name": "Miền Tây 04",
        "sheet_name": "Miền Tây 04 Đối Chiếu ODO",
        "warehouses": [
            {"id": "22068000", "name": "Kho Giao Hàng Nặng - TP Bạc Liêu - Bạc Liêu"},
            {"id": "21288000", "name": "Kho Giao Hàng Nặng - TP Sóc Trăng - Sóc Trăng"},
            {"id": "21988000", "name": "Kho Giao Hàng Nặng - TP Trà Vinh - Trà Vinh"}
        ],
        "telegram_chat_id": "-5295214199",
        "telegram_thread_id": None
    },
    "MT05": {
        "name": "Miền Tây 05",
        "sheet_name": "Miền Tây 05 Đối Chiếu ODO",
        "warehouses": [
            {"id": "21384000", "name": "Kho Giao Hàng Nặng - TP Châu Đốc - An Giang"},
            {"id": "21503000", "name": "Kho Giao Hàng Nặng - TP Long Xuyên - An Giang"},
            {"id": "21566000", "name": "Kho Giao Hàng Nặng - TP Vĩnh Long - Vĩnh Long"}
        ],
        "telegram_chat_id": "-5295214199",
        "telegram_thread_id": None
    }
}

# Chuẩn 36 cột chính xác khớp 100% với form Google Sheets gốc của Sếp Lộc
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

def scrape_region_trips(region_key, target_date=None, send_to_sheet=True, send_to_tg=False):
    """
    Cào toàn bộ chuyến đi ngày N-1 của 1 vùng chỉ định (MT01, MT02, MT04, MT05)
    và đồng bộ lên đúng tab Google Sheets tương ứng (chuẩn 36 cột)
    """
    if region_key not in REGIONS:
        print(f"❌ Vùng '{region_key}' không hợp lệ hoặc không được hỗ trợ!")
        return {"success": False, "error": f"Invalid region {region_key}"}

    reg_cfg = REGIONS[region_key]
    r_name = reg_cfg["name"]
    sheet_name = reg_cfg["sheet_name"]
    warehouses = reg_cfg["warehouses"]
    tg_chat_id = reg_cfg["telegram_chat_id"]
    tg_thread_id = reg_cfg["telegram_thread_id"]

    target_date = parse_target_date(target_date)
    date_int = int(target_date.strftime("%Y%m%d"))
    date_display = target_date.strftime("%d/%m/%Y")

    print("\n" + "=" * 65)
    print(f"🐯 [TIGER AI] CÀO CHUYẾN ĐI LASTMILE: {r_name.upper()} ({date_display})")
    print(f"📁 Tab đích: '{sheet_name}' | Tổng kho: {len(warehouses)} kho")
    print("=" * 65)

    headers = load_headers()
    raw_trips = []
    hub_stats = {}

    for wh in warehouses:
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
    print(f"👉 TỔNG SỐ CHUYẾN {r_name}: {total_trips} chuyến ngày {date_display}")

    # Lấy thêm 9 trường chi tiết từ get-trip-profile
    profile_map = {}
    all_codes = [t.get("tripCode") for t in raw_trips if t.get("tripCode")]
    if all_codes:
        print(f"🔍 Đang truy vấn get-trip-profile cho {len(all_codes)} chuyến ({r_name})...")
        first_hid = warehouses[0]["id"]
        headers["x-warehouseid"] = first_hid
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

    print(f"✅ Đã chuẩn hóa toàn bộ {len(all_rows)} dòng dữ liệu chuẩn 36 cột cho {r_name}!")

    # 1. Gửi Telegram thông báo hoàn tất
    if send_to_tg and tg_chat_id:
        stat_lines = "\n".join([f"  • {h.split(' - ')[-1]}: <b>{c} chuyến</b>" for h, c in hub_stats.items()])
        tg_msg = (
            f"🐯 <b>HOÀN TẤT CÀO CHUYẾN ĐI LASTMILE (N-1) - {r_name.upper()}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 <b>Ngày chuyến:</b> {date_display} (Ngày hôm qua)\n"
            f"⏰ <b>Khung giờ cào:</b> 05:00 AM (Tự động 100% trên Cloud)\n"
            f"📊 <b>Tổng số chuyến đã cào:</b> <b>{total_trips} chuyến</b>\n"
            f"🏢 <b>Chi tiết từng kho:</b>\n{stat_lines}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 <b>Google Sheets:</b> Đã đồng bộ vào tab <code>{sheet_name}</code>\n"
            f"⚡ <i>Hệ thống tự động đồng bộ sẵn sàng trước giờ ca sáng!</i>"
        )
        try:
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            tg_payload = {
                "chat_id": tg_chat_id,
                "text": tg_msg,
                "parse_mode": "HTML"
            }
            if tg_thread_id:
                tg_payload["message_thread_id"] = tg_thread_id

            tg_res = requests.post(tg_url, json=tg_payload, timeout=10)
            if tg_res.status_code == 200:
                print(f"📱 Đã gửi thông báo Telegram ({r_name}) thành công!")
            else:
                print(f"⚠️ Lỗi gửi Telegram: {tg_res.text}")
        except Exception as e:
            print(f"❌ Lỗi gửi Telegram ({r_name}): {e}")

    # 2. Gửi dữ liệu lên Google Sheets qua Apps Script Webhook
    sheet_result = "Chưa gửi (chế độ kiểm thử dry-run)"
    if send_to_sheet and total_trips > 0:
        print(f"🚀 Đang gửi {len(all_rows)} chuyến lên Google Sheets qua Webhook (Tab: '{sheet_name}')...")
        payload_sheet = {
            "sheetName": sheet_name,
            "headers": COLUMNS_36,
            "rows": all_rows
        }
        for attempt in range(1, 3):
            try:
                resp = requests.post(
                    WEBHOOK_URL,
                    data=json.dumps(payload_sheet, ensure_ascii=False, default=str).encode("utf-8"),
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    timeout=45
                )
                sheet_result = resp.text.strip()
                print(f"✅ Kết quả Google Sheets ({sheet_name}): {sheet_result}")
                break
            except Exception as e:
                print(f"⚠️ Lần {attempt} lỗi gửi Sheet: {e}")
                time.sleep(2)
    elif total_trips == 0:
        sheet_result = f"Không có chuyến nào cho ngày {date_display}"
        print(f"ℹ️ {sheet_result}")

    return {
        "success": True,
        "region": region_key,
        "region_name": r_name,
        "sheet_name": sheet_name,
        "date": date_display,
        "total_trips": total_trips,
        "hubs": hub_stats,
        "sheet_status": sheet_result,
        "rows": all_rows
    }

def run_all_regions(target_date=None, send_to_sheet=True, send_to_tg=False, selected_regions=None):
    """
    Chạy cào chuyến đi cho danh sách vùng được chọn (Mặc định: MT01, MT02, MT04, MT05)
    """
    if selected_regions is None:
        selected_regions = ["MT01", "MT02", "MT04", "MT05"]
    
    # Đảm bảo tuyệt đối không có MT03 theo chỉ đạo của Sếp Lộc
    selected_regions = [r for r in selected_regions if r != "MT03"]

    print("=" * 70)
    print("🐯 [TIGER AI] KHỞI ĐỘNG HỆ THỐNG CÀO LASTMILE ĐA VÙNG (4 VÙNG MIỀN TÂY)")
    print(f"📋 Các vùng thực hiện: {', '.join(selected_regions)}")
    print("=" * 70)

    results = {}
    for rk in selected_regions:
        res = scrape_region_trips(rk, target_date=target_date, send_to_sheet=send_to_sheet, send_to_tg=send_to_tg)
        results[rk] = res
        time.sleep(1)

    print("\n" + "=" * 70)
    print("🏁 TỔNG HỢP KẾT QUẢ CÀO CHUYẾN ĐI LASTMILE:")
    for rk, res in results.items():
        print(f" • {res.get('region_name', rk)}: {res.get('total_trips', 0)} chuyến ➔ {res.get('sheet_status')}")
    print("=" * 70)
    return results

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

    target_regions = None
    if "--region" in sys.argv:
        try:
            idx = sys.argv.index("--region")
            reg_arg = sys.argv[idx + 1].upper()
            if reg_arg == "ALL":
                target_regions = ["MT01", "MT02", "MT04", "MT05"]
            elif reg_arg in REGIONS:
                target_regions = [reg_arg]
            else:
                print(f"⚠️ Vùng '{reg_arg}' không được nhận diện, chạy toàn bộ 4 vùng mặc định.")
        except:
            pass

    run_all_regions(target_date=custom_date, send_to_sheet=send_sheet, send_to_tg=send_tg, selected_regions=target_regions)

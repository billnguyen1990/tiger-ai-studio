import os
import sys
import json
import time
import re
import datetime
import requests
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# TIGER AI • QUẢN LÝ & ĐỐI SOÁT ODO XE TẢI GHN 365 - TOÀN MIỀN TÂY (02:00 AM)
# Tự động hóa 100% trên Cloud Render - Cào dữ liệu chuyến đi Ngày N-1
# Thay thế hoàn toàn App Desktop, không cần bật máy tính, bảo toàn tâm huyết vĩnh viễn!
# ==============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(BASE_DIR, "headers_found.json")

# Google Apps Script Webhook URL (Tab: Team_Leader / Trip_List kèm Radar Đối Soát 365)
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzFP1ORM09dQxWzDVICZPUFbRt-aclYwYqioVCwaIFuKm_G0ILnAmjEJq2X5IRhDmTBXg/exec"
SHEET_NAME = "Team_Leader"

# Telegram Bot Config (Topic Báo Cáo Miền Tây 01)
TELEGRAM_BOT_TOKEN = "8777045986:AAEX1uau8GFdxPAj0aAVUwDNQnpQb1IZOIA"
TELEGRAM_CHAT_ID = "-1003940889949"
TELEGRAM_MESSAGE_THREAD_ID = 2690

URL_TRIPS = "https://nhanh-api.ghn.vn/api/lastmile/trip/get-trip-list-by-hub"
URL_TRIP_DETAIL = "https://nhanh-api.ghn.vn/api/lastmile/v2/trip/trip-detail"

# Danh sách chuẩn toàn bộ 21 Kho Giao Hàng Nặng Miền Tây
WAREHOUSES_21 = {
    "21088000": "Kho Giao Hàng Nặng - Cái Răng - Cần Thơ",
    "21985000": "Kho Giao Hàng Nặng - Bình Thủy - Cần Thơ",
    "22862000": "Kho Giao Hàng Nặng - TP Vị Thanh - Hậu Giang",
    "22917000": "Kho Giao Hàng Nặng - Ô Môn - Cần Thơ",
    "21292000": "Kho Giao Hàng Nặng-TP Cao Lãnh-Đồng Tháp",
    "22054000": "Kho Giao Hàng Nặng - Tam Nông - Đồng Tháp",
    "21566000": "Kho Giao Hàng Nặng - TP Vĩnh Long - Vĩnh Long",
    "21441000": "Kho Giao Hàng Nặng - TP Rạch Giá - Kiên Giang",
    "22187000": "Kho Giao Hàng Nặng - TP Hà Tiên - Kiên Giang",
    "21288000": "Kho Giao Hàng Nặng - TP Sóc Trăng - Sóc Trăng",
    "22068000": "Kho Giao Hàng Nặng - TP Bạc Liêu - Bạc Liêu",
    "21988000": "Kho Giao Hàng Nặng - TP Trà Vinh - Trà Vinh",
    "21503000": "Kho Giao Hàng Nặng - TP Long Xuyên - An Giang",
    "21384000": "Kho Giao Hàng Nặng - TP Châu Đốc - An Giang",
    "21361000": "Kho Giao Hàng Nặng - TP Cà Mau - Cà Mau",
    "22159000": "Kho Giao Hàng Nặng - TP Mỹ Tho - Tiền Giang",
    "21291000": "Kho Giao Hàng Nặng - TP Bến Tre - Bến Tre",
    "22496000": "Kho Giao Hàng Nặng - TX Cai Lậy - Tiền Giang",
    "22953000": "Kho Giao Hàng Nặng - Gò Công - Tiền Giang",
    "21092000": "Kho Giao Hàng Nặng - Đức Hòa - Long An",
    "22067000": "Kho Giao Hàng Nặng - TP Tân An - Long An",
}

# --- THUẬT TOÁN NHẬN DẠNG XE TẢI & DANH SÁCH ĐEN CHUẨN XÁC ---
TRUCK_PATTERN = r"^\d{2}([A-Z]|LD|KT|RM|MK|NN|NG)[\s-]*(\d{3}\.\d{2}|\d{4})$"
MOTORBIKE_PATTERN = r"^\d{2}[A-Z]\d[\s-]*(\d{3}\.\d{2}|\d{4,5})$"
FAKE_PLATES_EXACT = ["84B-111.11"]
FAKE_PLATES_PREFIXES = []
MOTORBIKE_DUMMY_PREFIXES = ["99H-999", "99G-999"]

# Danh sách Biển số Ảo / Sai do NCC 365 cung cấp cần LOẠI BỎ
BLACKLIST_PLATES = [
    "50AD-604.89", "50E-676.01", "50H-043.47", "50H-123.45", "50H-872.35",
    "52H-6052", "62D1-126.03", "63B-095.95", "63B1-830.14", "63B9-095.95", "63M2-1077",
    "63P1-348.80", "63P1-428.80", "63S4-4047", "63X8-7239", "64H-061.76", "65B-793.39",
    "65H-024.69", "65H-043.47", "65K1-329.29", "65MA-144.15", "66F3-9237", "67B2-552.72",
    "67E1-040.90", "67E1-247.42", "67G1-718.89", "67H1-040.90", "67H1-863.51", "67K1-718.67",
    "67K5-0733", "68AA-910.83", "68C-103.83", "68C1-662.54", "68E1-408.83", "68E1-438.87",
    "68FA-101.94", "68G1-776.21", "68H-103.83", "68K1-090.26", "69A-2745", "69AA-2413",
    "69AA-5243", "69AA-6438", "69AA-6458", "69B1-4255", "69B1-5559", "69C-064.37",
    "84B-333.33", "84B-843.84", "94K1-123.45", "94K1-274.48", "94K1-274.56", "94K-135.44",
    "94K2-111.11", "95B2-047.22", "95E1-753.78"
]

_TRUCK_RE = re.compile(TRUCK_PATTERN, re.IGNORECASE)
_MOTORBIKE_RE = re.compile(MOTORBIKE_PATTERN, re.IGNORECASE)

def is_valid_vehicle(plate: str, warehouse_id: str = "") -> tuple[bool, str]:
    """Phân loại xe tải vs xe máy vs xe ảo theo đúng tâm huyết của User"""
    p = plate.strip().upper()
    if not p:
        return False, "Không có biển số"
    
    # 1. Kiểm tra danh sách Blacklist (Kho Đức Hòa 21092000 và Tân An 22067000 không chạy 365)
    if warehouse_id not in ["21092000", "22067000"]:
        p_normalized = p.replace(" ", "").replace(".", "").replace("-", "")
        blacklist_normalized = [wp.replace(" ", "").replace(".", "").replace("-", "") for wp in BLACKLIST_PLATES]
        if p_normalized in blacklist_normalized:
            return False, "Biển số ảo (Danh sách đen 365)"
            
    # 2. Biển số ảo gốc
    if p in FAKE_PLATES_EXACT:
        return False, "Biển số ảo"
    for prefix in FAKE_PLATES_PREFIXES:
        if p.startswith(prefix):
            return False, "Biển số ảo"
            
    # 3. Xe máy giả lập
    for prefix in MOTORBIKE_DUMMY_PREFIXES:
        if p.startswith(prefix):
            return False, "Biển số ảo (Xe máy giả)"
            
    # 4. Kiểm tra cấu trúc Xe máy
    if _MOTORBIKE_RE.match(p):
        return False, "Xe máy"
        
    # 5. Kiểm tra cấu trúc Xe tải chuẩn
    if _TRUCK_RE.match(p):
        return True, "Xe tải"
        
    return False, "Không hợp lệ"

def load_headers():
    if not os.path.exists(HEADERS_FILE):
        raise FileNotFoundError(f"Không tìm thấy file {HEADERS_FILE}")
    with open(HEADERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _fetch_single_trip_detail(item_tuple, headers):
    t, wid, wname, date_display = item_tuple
    code = t.get("tripCode")
    if not code:
        return None

    plate = ""
    driver_name = t.get("driverName") or ""
    driver_id = str(t.get("driverId") or "")
    created_time_raw = t.get("createdTime") or t.get("date") or ""
    
    # Format ngày giờ tạo chuẩn (VD: 24/10/2026 - 07:25:33)
    created_fmt = date_display
    if created_time_raw:
        try:
            dt = datetime.datetime.fromisoformat(created_time_raw.replace("Z", "+00:00"))
            dt_vn = dt + datetime.timedelta(hours=7)
            created_fmt = dt_vn.strftime("%d/%m/%Y - %H:%M:%S")
        except:
            created_fmt = created_time_raw

    # Gọi trip-detail lấy truckPlateNumber
    try:
        res_det = requests.post(URL_TRIP_DETAIL, headers=headers, json={"trip_code": code}, timeout=8)
        if res_det.status_code == 200:
            d_data = res_det.json().get("data") or {}
            plate = (d_data.get("truckPlateNumber") or "").strip().upper()
            if not driver_name:
                driver_name = d_data.get("driverName") or ""
            if not driver_id:
                driver_id = str(d_data.get("driverId") or "")
    except Exception:
        pass

    is_valid, v_type = is_valid_vehicle(plate, wid)
    nhan_vien = f"{driver_id} - {driver_name}".strip(" -")
    
    return {
        "code": code,
        "plate": plate.replace(" ", ""),
        "driver_id": driver_id,
        "driver_name": driver_name,
        "nhan_vien": nhan_vien,
        "ngay_tao": created_fmt,
        "ten_kho": wname,
        "ncc": "365",
        "is_truck": is_valid,
        "v_type": v_type,
        "wid": wid
    }

def run_truck_odo_scraper(target_date=None, send_to_sheet=True, send_to_tg=False):
    """
    Cào toàn bộ chuyến xe tải Ngày N-1 của 21 kho Miền Tây, lọc xe thật và đồng bộ lên Google Sheets (tab Team_Leader)
    """
    if target_date is None:
        target_date = datetime.date.today() - datetime.timedelta(days=1)
    elif isinstance(target_date, str):
        target_date = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()

    date_int = int(target_date.strftime("%Y%m%d"))
    date_display = target_date.strftime("%d/%m/%Y")

    print("=" * 65, flush=True)
    print(f"🐯 [TIGER AI] BẮT ĐẦU ĐỐI SOÁT ODO XE TẢI 365 - TOÀN MIỀN TÂY (NGÀY N-1: {date_display})", flush=True)
    print(f"⏰ Thời gian kích hoạt: 02:00 AM (Tự động 100% trên Cloud Render)", flush=True)
    print("=" * 65, flush=True)

    headers = load_headers()
    all_truck_results = []
    warehouse_stats = {}
    missing_wids = []
    all_tasks = []

    # Quét danh sách chuyến từ 21 kho
    for wid, wname in WAREHOUSES_21.items():
        headers["x-warehouseid"] = wid
        short_name = wname.replace("Kho Giao Hàng Nặng - ", "").replace("Kho Giao Hàng Nặng-", "").strip()
        
        hub_trips = []
        payload = {
            "hub_id": wid,
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
                        all_tasks.append((t, wid, wname, date_display))
                        hub_trips.append(t)
            else:
                print(f"  ⚠️ Kho {short_name} ({wid}) HTTP {res.status_code}", flush=True)
        except Exception as e:
            print(f"  ❌ Lỗi kết nối kho {short_name}: {e}", flush=True)

        if len(hub_trips) == 0:
            missing_wids.append(wid)

    print(f"📡 Đang tải chi tiết biển số cho {len(all_tasks)} chuyến (Song song đa luồng siêu tốc)...", flush=True)

    # Đa luồng lấy chi tiết từng chuyến xe
    with ThreadPoolExecutor(max_workers=8) as executor:
        parsed_results = list(executor.map(lambda item: _fetch_single_trip_detail(item, headers), all_tasks))

    # Tổng hợp theo kho
    for wid, wname in WAREHOUSES_21.items():
        warehouse_stats[wid] = {"Xe tải": 0, "Xe máy": 0, "total": 0}

    for res in parsed_results:
        if not res:
            continue
        wid = res["wid"]
        warehouse_stats[wid]["total"] += 1
        if res["is_truck"]:
            warehouse_stats[wid]["Xe tải"] += 1
            all_truck_results.append({
                "ma_chuyen": res["code"],
                "plate": res["plate"],
                "nhan_vien": res["nhan_vien"],
                "ngay_tao": res["ngay_tao"],
                "ten_kho": res["ten_kho"],
                "ncc": res["ncc"]
            })
        elif res["v_type"] == "Xe máy":
            warehouse_stats[wid]["Xe máy"] += 1

    # In báo cáo từng kho
    for wid, wname in WAREHOUSES_21.items():
        short_name = wname.replace("Kho Giao Hàng Nặng - ", "").replace("Kho Giao Hàng Nặng-", "").strip()
        st = warehouse_stats[wid]
        print(f"  🚚 {short_name} ➔ {st['Xe tải']} xe tải | 🛵 {st['Xe máy']} xe máy (Tổng {st['total']} chuyến)", flush=True)

    total_trucks = len(all_truck_results)
    print(f"\n👉 TỔNG CỘNG XE TẢI HỢP LỆ (NGÀY N-1 {date_display}): {total_trucks} chuyến xe tải của 21 kho", flush=True)

    # Sắp xếp theo ngày cũ -> mới, cùng ngày thì theo thứ tự kho chuẩn
    wh_order = list(WAREHOUSES_21.values())
    def sort_key(x):
        tk = x.get("ten_kho", "")
        wh_idx = wh_order.index(tk) if tk in wh_order else 999
        return (wh_idx, x.get("ngay_tao", ""))
    all_truck_results.sort(key=sort_key)

    # 1. Gửi lên Google Sheets (Tab Team_Leader kèm Radar Đối Soát 365)
    sheet_result = "Chưa gửi (chế độ kiểm thử)"
    if send_to_sheet and total_trucks > 0:
        print(f"\n🚀 Đang gửi {total_trucks} chuyến xe tải lên Google Sheets qua Apps Script...", flush=True)
        sheet_rows = []
        for r in all_truck_results:
            p_str = r.get("plate", "")
            if p_str and not p_str.startswith("'"):
                p_str = "'" + p_str
            sheet_rows.append([
                r.get("ma_chuyen", ""),
                p_str,
                r.get("nhan_vien", ""),
                r.get("ngay_tao", ""),
                r.get("ten_kho", "")
            ])

        payload_sheet = {
            "action": "appendRows",
            "sheetName": SHEET_NAME,
            "rows": sheet_rows
        }

        for attempt in range(1, 4):
            try:
                resp = requests.post(
                    APPS_SCRIPT_URL,
                    json=payload_sheet,
                    headers={"Content-Type": "application/json"},
                    timeout=90
                )
                if resp.status_code == 200:
                    sheet_result = f"Success: Đã ghi thành công {len(sheet_rows)} xe tải vào tab '{SHEET_NAME}'"
                    print(f"  ✓ {sheet_result}", flush=True)
                    break
                else:
                    print(f"  ⚠️ Lần {attempt} lỗi HTTP {resp.status_code}: {resp.text[:150]}", flush=True)
            except Exception as e:
                print(f"  ⚠️ Lần {attempt} lỗi kết nối Sheets: {e}", flush=True)
                time.sleep(3)
    elif total_trucks == 0:
        sheet_result = f"Không có chuyến xe tải nào cho ngày N-1 ({date_display})"
        print(f"  ℹ️ {sheet_result}", flush=True)

    # 2. Gửi Telegram Báo Cáo Tổng Hợp
    if send_to_tg:
        lines = []
        lines.append(f"🚛 <b>HOÀN TẤT ĐỐI SOÁT ODO XE TẢI 365 (N-1)</b>")
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📅 <b>Ngày chuyến:</b> {date_display} (Ngày hôm qua)")
        lines.append(f"⏰ <b>Khung giờ cào:</b> 02:00 AM (Tự động 100% trên Cloud)")
        lines.append(f"🚚 <b>Tổng số xe tải hợp lệ:</b> <b>{total_trucks} chuyến</b>")
        lines.append(f"🏢 <b>Chi tiết từng kho (Xe tải / Xe máy):</b>")

        for wid, wname in WAREHOUSES_21.items():
            st = warehouse_stats.get(wid, {"Xe tải": 0, "Xe máy": 0})
            s_name = wname.replace("Kho Giao Hàng Nặng - ", "").replace("Kho Giao Hàng Nặng-", "").strip()
            lines.append(f"  • {s_name}: <b>{st['Xe tải']} xe tải</b> | 🛵 {st['Xe máy']}")

        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📁 <b>Trạng thái Google Sheets:</b>")
        lines.append(f"👉 <i>{sheet_result}</i>")
        lines.append(f"⚡ <i>Hệ thống tự động kích hoạt Radar Đối Soát trước giờ ca sáng!</i>")

        tg_msg = "\n".join(lines)
        try:
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            tg_res = requests.post(tg_url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "message_thread_id": TELEGRAM_MESSAGE_THREAD_ID,
                "text": tg_msg,
                "parse_mode": "HTML"
            }, timeout=15)
            if tg_res.status_code == 200:
                print("📱 Đã gửi thông báo Telegram thành công!", flush=True)
            else:
                print(f"⚠️ Lỗi gửi Telegram: {tg_res.text}", flush=True)
        except Exception as e:
            print(f"❌ Lỗi gửi Telegram: {e}", flush=True)

    return {
        "success": True,
        "date": date_display,
        "total_trucks": total_trucks,
        "warehouse_stats": warehouse_stats,
        "sheet_status": sheet_result
    }

if __name__ == "__main__":
    send_sheet = True
    send_tg = "--send" in sys.argv
    if "--dry-run" in sys.argv:
        send_sheet = False

    custom_date = None
    if "--date" in sys.argv:
        try:
            idx = sys.argv.index("--date")
            custom_date = sys.argv[idx + 1]
        except:
            pass

    run_truck_odo_scraper(target_date=custom_date, send_to_sheet=send_sheet, send_to_tg=send_tg)

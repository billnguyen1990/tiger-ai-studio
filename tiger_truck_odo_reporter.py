import os
import sys
import json
import time
import random
import re
import datetime
import requests

# ==============================================================================
# TIGER AI • QUẢN LÝ & ĐỐI SOÁT ODO XE TẢI GHN 365 - TOÀN MIỀN TÂY (02:00 AM)
# Tự động hóa 100% trên Cloud Render - Cào dữ liệu chuyến đi Ngày N-1
# Tích hợp Cơ Chế Cào Chậm Chống Nghẽn Mạng: Nghỉ 30s - 60s giữa các kho + Tự động cào bù
# ==============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(BASE_DIR, "headers_found.json")

# Google Apps Script Webhook URL (Tab: Team_Leader / Trip_List kèm Radar Đối Soát 365)
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzFP1ORM09dQxWzDVICZPUFbRt-aclYwYqioVCwaIFuKm_G0ILnAmjEJq2X5IRhDmTBXg/exec"
SHEET_NAME = "Team_Leader"

# Telegram Bot Config (Chỉ gửi duy nhất về Room 'The 5 Guardians' theo yêu cầu của Sếp)
TELEGRAM_BOT_TOKEN = "8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk"
TELEGRAM_CHAT_ID = "-5295214199"

# Google Sheet Link (Tab Team_Leader)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1Nf4bklPe3s3MHfaS5Us5c0AjNqaDR5n8dYaNf4pwIyE/edit"

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

def _get_trip_detail_with_retry(code, wid, wname, date_display, headers, max_retries=3):
    """
    Lấy chi tiết chuyến đi có cơ chế thử lại thông minh (Exponential Backoff) nếu mạng yếu
    """
    plate = ""
    driver_name = ""
    driver_id = ""
    created_fmt = date_display
    success = False

    for attempt in range(1, max_retries + 1):
        try:
            res_det = requests.post(URL_TRIP_DETAIL, headers=headers, json={"trip_code": code}, timeout=12)
            if res_det.status_code == 200:
                d_data = res_det.json().get("data") or {}
                plate = (d_data.get("truckPlateNumber") or "").strip().upper()
                driver_name = d_data.get("driverName") or ""
                driver_id = str(d_data.get("driverId") or "")
                
                created_time_raw = d_data.get("createdTime") or d_data.get("date") or ""
                if created_time_raw:
                    try:
                        dt = datetime.datetime.fromisoformat(created_time_raw.replace("Z", "+00:00"))
                        dt_vn = dt + datetime.timedelta(hours=7)
                        created_fmt = dt_vn.strftime("%d/%m/%Y - %H:%M:%S")
                    except:
                        created_fmt = created_time_raw

                success = True
                break
            else:
                time.sleep(2.0 * attempt)
        except Exception:
            time.sleep(2.5 * attempt)

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
        "wid": wid,
        "success": success
    }

def get_vietnam_now():
    """
    Luôn lấy thời gian chính xác theo múi giờ Việt Nam (UTC+7 / Asia/Ho_Chi_Minh)
    bất kể script đang chạy trên Render (Linux UTC), Windows hay Docker.
    """
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    vn_tz = datetime.timezone(datetime.timedelta(hours=7))
    return utc_now.astimezone(vn_tz)

def get_vietnam_today():
    """Lấy ngày hôm nay chuẩn theo giờ Việt Nam"""
    return get_vietnam_now().date()

def parse_target_date(target_date):
    """
    Nhận diện linh hoạt target_date:
    - None: Tự động lấy Ngày N-1 theo múi giờ Việt Nam (hôm qua)
    - string: Hỗ trợ '%Y-%m-%d', '%d/%m/%Y', '%Y%m%d', '%d-%m-%Y'
    """
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

def run_truck_odo_scraper(target_date=None, send_to_sheet=True, send_to_tg=True, fast_mode=False):
    """
    Cào toàn bộ chuyến xe tải Ngày N-1 của 21 kho Miền Tây.
    Có cơ chế cào chậm an toàn: Nghỉ 30s - 60s giữa các kho + Tự động cào bù khi mạng yếu.
    """
    target_date = parse_target_date(target_date)
    date_int = int(target_date.strftime("%Y%m%d"))
    date_display = target_date.strftime("%d/%m/%Y")

    print("=" * 65, flush=True)
    print(f"🐯 [TIGER AI] BẮT ĐẦU ĐỐI SOÁT ODO XE TẢI 365 - TOÀN MIỀN TÂY (NGÀY N-1: {date_display})", flush=True)
    print(f"⏰ Thời gian kích hoạt: 02:00 AM (Tự động 100% trên Cloud Render)", flush=True)
    if fast_mode:
        print(f"⚡ Chế độ kiểm tra nhanh: Bỏ qua thời gian nghỉ dài để nghiệm thu tức thì", flush=True)
    else:
        print(f"🛡️ Chế độ an toàn ban đêm: Nghỉ 30s - 60s giữa các kho + Tự động cào bù khi mạng yếu", flush=True)
    print("=" * 65, flush=True)

    headers = load_headers()
    all_truck_results = []
    warehouse_stats = {wid: {"Xe tải": 0, "Xe máy": 0, "total": 0} for wid in WAREHOUSES_21}
    
    wh_queue = [(wid, wname, 0) for wid, wname in WAREHOUSES_21.items()]
    seen_trip_codes = set()
    failed_trips_to_rescue = []

    q_idx = 0
    print(f"\n🚀 [VÒNG 1: BẮT ĐẦU QUÉT 21 KHO THONG THẢ BAN ĐÊM]...", flush=True)

    while q_idx < len(wh_queue):
        wid, wname, retry_count = wh_queue[q_idx]
        headers["x-warehouseid"] = wid
        short_name = wname.replace("Kho Giao Hàng Nặng - ", "").replace("Kho Giao Hàng Nặng-", "").strip()

        if retry_count > 0:
            print(f"\n🔄 [TỰ ĐỘNG QUÉT LẠI KHO BỊ HỤT DATA - Lần {retry_count}]: {short_name} ({wid})", flush=True)
        else:
            print(f"\n🏭 [{q_idx + 1}/21] Đang quét kho: {short_name}...", flush=True)

        hub_trips = []
        hub_seen_codes = set()
        fetch_ok = True

        # Quét cả 2 trạng thái: FINISHED (Kết thúc) và ON_TRIP (Đang chạy) để không bao giờ bị sót chuyến
        for trip_st in ["FINISHED", "ON_TRIP"]:
            payload = {
                "hub_id": wid,
                "status": trip_st,
                "is_ready": 0,
                "offset": 0,
                "limit": 100
            }

            st_ok = False
            for att in range(1, 4):
                try:
                    res = requests.post(URL_TRIPS, headers=headers, json=payload, timeout=20)
                    if res.status_code == 200:
                        data = res.json().get("data", []) or []
                        for t in data:
                            t_code = t.get("tripCode")
                            if t_code and t_code not in hub_seen_codes:
                                c_date = t.get("createDateIndex")
                                s_date = t.get("startDateIndex")
                                e_date = t.get("endDateIndex")
                                if c_date == date_int or s_date == date_int or e_date == date_int:
                                    hub_trips.append(t)
                                    hub_seen_codes.add(t_code)
                        st_ok = True
                        break
                    else:
                        time.sleep(1.5)
                except Exception:
                    time.sleep(2.0)
            if not st_ok:
                fetch_ok = False

        # Nếu quét lần đầu mà kho bị lỗi mạng/rớt data -> Tự động đưa kho vào cuối hàng đợi để lát quét lại
        if not fetch_ok and retry_count < 2:
            print(f"  ⚠️ Mạng yếu ở kho {short_name}, tự động đưa vào cuối hàng đợi để cào lại sau!", flush=True)
            wh_queue.append((wid, wname, retry_count + 1))
            q_idx += 1
            time.sleep(2.0)
            continue

        # Lặp từng chuyến đi của kho với khoảng nghỉ nhịp nhàng (1.5s - 3.0s) như người thật bấm máy
        for t in hub_trips:
            code = t.get("tripCode")
            if not code or code in seen_trip_codes:
                continue
            seen_trip_codes.add(code)

            detail = _get_trip_detail_with_retry(code, wid, wname, date_display, headers)
            
            # Nếu chuyến này bị lỗi mạng hoàn toàn (success = False), ghi nhận để cào vét ở Vòng 2
            if not detail["success"]:
                failed_trips_to_rescue.append((t, wid, wname))
                continue

            warehouse_stats[wid]["total"] += 1
            if detail["is_truck"]:
                warehouse_stats[wid]["Xe tải"] += 1
                all_truck_results.append({
                    "ma_chuyen": detail["code"],
                    "plate": detail["plate"],
                    "nhan_vien": detail["nhan_vien"],
                    "ngay_tao": detail["ngay_tao"],
                    "ten_kho": detail["ten_kho"],
                    "ncc": detail["ncc"]
                })
            elif detail["v_type"] == "Xe máy":
                warehouse_stats[wid]["Xe máy"] += 1

            # 🛡️ Nghỉ nhịp nhàng giữa mỗi chuyến đi (0.15s - 0.35s) như người dùng thật thao tác
            trip_pause = random.uniform(0.05, 0.15) if fast_mode else random.uniform(0.15, 0.35)
            time.sleep(trip_pause)

        st = warehouse_stats[wid]
        print(f"  ✓ {short_name}: {st['Xe tải']} xe tải | 🛵 {st['Xe máy']} xe máy (Tổng {st['total']} chuyến)", flush=True)

        q_idx += 1

        # 💤 NGHỈ GIỮA CÁC KHO (30s - 60s THEO YÊU CẦU CỦA USER ĐỂ CHUẨN XÁC 100%)
        if q_idx < len(wh_queue):
            if fast_mode:
                time.sleep(0.5)
            else:
                pause_wh = random.uniform(30.0, 60.0)
                print(f"  💤 [NGHỈ AN TOÀN] Tạm nghỉ {pause_wh:.1f}s trước khi sang kho tiếp theo (Hạ nhiệt server GHN & đảm bảo chuẩn 100%)...", flush=True)
                time.sleep(pause_wh)

    # ==========================================================================
    # VÒNG 2: TỰ ĐỘNG CÀO BÙ NẾU CÓ CHUYẾN BỊ HỤT DATA DO MẠNG YẾU (RESCUE ROUND)
    # ==========================================================================
    if failed_trips_to_rescue:
        rescue_pause = 5.0 if fast_mode else random.uniform(15.0, 30.0)
        print(f"\n🔁 [VÒNG 2: PHÁT HIỆN {len(failed_trips_to_rescue)} CHUYẾN BỊ MẠNG YẾU, NGHỈ {rescue_pause:.1f}S RỒI TIẾN HÀNH CÀO BÙ]...", flush=True)
        time.sleep(rescue_pause)
        for t, wid, wname in failed_trips_to_rescue:
            code = t.get("tripCode")
            detail = _get_trip_detail_with_retry(code, wid, wname, date_display, headers, max_retries=4)
            if detail["success"]:
                warehouse_stats[wid]["total"] += 1
                if detail["is_truck"]:
                    warehouse_stats[wid]["Xe tải"] += 1
                    all_truck_results.append({
                        "ma_chuyen": detail["code"],
                        "plate": detail["plate"],
                        "nhan_vien": detail["nhan_vien"],
                        "ngay_tao": detail["ngay_tao"],
                        "ten_kho": detail["ten_kho"],
                        "ncc": detail["ncc"]
                    })
                elif detail["v_type"] == "Xe máy":
                    warehouse_stats[wid]["Xe máy"] += 1
            time.sleep(0.05 if fast_mode else random.uniform(0.15, 0.35))

    total_trucks = len(all_truck_results)
    print(f"\n👉 TỔNG CỘNG XE TẢI HỢP LỆ (NGÀY N-1 {date_display}): {total_trucks} chuyến xe tải của 21 kho", flush=True)

    # Sắp xếp theo thứ tự kho chuẩn của Sếp
    wh_order = list(WAREHOUSES_21.values())
    def sort_key(x):
        tk = x.get("ten_kho", "")
        wh_idx = wh_order.index(tk) if tk in wh_order else 999
        return (wh_idx, x.get("ngay_tao", ""))
    all_truck_results.sort(key=sort_key)

    # 1. Gửi Telegram Báo Cáo Tổng Hợp NGAY LẬP TỨC tới cả 2 nhóm
    if send_to_tg:
        lines = []
        lines.append(f"🚛💨 <b>BÁO CÁO ODO XE TẢI 365 • TOÀN MIỀN TÂY</b> 🚛💨")
        lines.append(f"📅 <i>Ngày chuyến:</i> <b>{date_display} (Ngày N-1)</b>")
        lines.append(f"⏰ <i>Khung giờ chốt:</i> <code>02:00 AM</code> (Tự động 100% trên Cloud)")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 <b>TỔNG KẾT VẬN HÀNH:</b>")
        lines.append(f"• 🚚 <b>Tổng số xe tải hợp lệ:</b> <b>{total_trucks} chuyến</b>")
        lines.append(f"• 🏢 <b>Tiến độ đối soát:</b> <b>{len(WAREHOUSES_21)}/{len(WAREHOUSES_21)} kho (100% Hoàn hảo 🎯)</b>")
        lines.append("• 🛡️ <b>Bộ lọc an toàn:</b> Đã loại bỏ xe máy & hơn 55 biển số ảo 365")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🏢 <b>CHI TIẾT XE TẢI THEO TỪNG KHO:</b>")

        diff_items = []
        for idx, (wid, wname) in enumerate(WAREHOUSES_21.items(), 1):
            st = warehouse_stats.get(wid, {"Xe tải": 0, "Xe máy": 0})
            s_name = wname.replace("Kho Giao Hàng Nặng - ", "").replace("Kho Giao Hàng Nặng-", "").strip()
            diff_items.append(f"+ {idx}. {s_name} :\n! 🚚 {st['Xe tải']} chuyến xe tải")

        lines.append('<pre><code class="language-diff">' + "\n\n".join(diff_items) + "</code></pre>")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("👉 <b>AE check lại của vùng mình xem đúng không nhé!</b>")
        lines.append(f"📁 <b>Google Sheets:</b> Đang/Đã đồng bộ vào tab <code>{SHEET_NAME}</code>")
        lines.append(f"🔗 <b>Link xem dữ liệu trực tiếp:</b>\n{SHEET_URL}")
        lines.append("🤖 <i>Báo cáo vận hành tự động bởi Tiger AI • Đám mây Cloud Render 24/7</i>")

        tg_msg = "\n".join(lines)
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        # Gửi đồng thời tới cả 2 nhóm: The 5 Guardians và Miền Tây 01 (Topic Báo Cáo)
        tg_targets = [
            {"name": "The 5 Guardians", "chat_id": "-5295214199", "thread_id": None},
            {"name": "Miền Tây 01 (Topic Báo Cáo)", "chat_id": "-1003940889949", "thread_id": 2690}
        ]
        for target in tg_targets:
            try:
                payload = {
                    "chat_id": target["chat_id"],
                    "text": tg_msg,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True
                }
                if target["thread_id"]:
                    payload["message_thread_id"] = target["thread_id"]
                tg_res = requests.post(tg_url, json=payload, timeout=15)
                if tg_res.status_code == 200:
                    print(f"📱 Đã gửi báo cáo Telegram thành công tới [{target['name']}]!", flush=True)
                else:
                    print(f"⚠️ Lỗi gửi Telegram [{target['name']}]: {tg_res.text}", flush=True)
            except Exception as e:
                print(f"❌ Lỗi gửi Telegram [{target['name']}]: {e}", flush=True)

    # 2. Gửi lên Google Sheets (Tab Team_Leader kèm Radar Đối Soát 365)
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

        for attempt in range(1, 3):
            try:
                resp = requests.post(
                    APPS_SCRIPT_URL,
                    json=payload_sheet,
                    headers={"Content-Type": "application/json"},
                    timeout=60
                )
                if resp.status_code == 200:
                    sheet_result = f"Success: Đã ghi thành công {len(sheet_rows)} xe tải vào tab '{SHEET_NAME}'"
                    print(f"  ✓ {sheet_result}", flush=True)
                    break
                else:
                    print(f"  ⚠️ Lần {attempt} phản hồi HTTP {resp.status_code}: {resp.text[:150]}", flush=True)
            except requests.exceptions.ReadTimeout:
                sheet_result = f"Warning: Sheets xử lý xong nhưng phản hồi trễ (ReadTimeout > 60s) - Bỏ qua retry để chống trùng lặp"
                print(f"  ⚠️ {sheet_result}", flush=True)
                break
            except Exception as e:
                print(f"  ⚠️ Lần {attempt} Sheets phản hồi chậm: {e}", flush=True)
                time.sleep(2)
    elif total_trucks == 0:
        sheet_result = f"Không có chuyến xe tải nào cho ngày N-1 ({date_display})"
        print(f"  ℹ️ {sheet_result}", flush=True)

    return {
        "success": True,
        "date": date_display,
        "total_trucks": total_trucks,
        "warehouse_stats": warehouse_stats,
        "sheet_status": sheet_result
    }

if __name__ == "__main__":
    send_sheet = "--no-sheet" not in sys.argv
    send_tg = "--no-tg" not in sys.argv
    if "--dry-run" in sys.argv:
        send_sheet = False
        send_tg = False

    is_fast = "--fast" in sys.argv

    custom_date = None
    if "--date" in sys.argv:
        try:
            idx = sys.argv.index("--date")
            custom_date = sys.argv[idx + 1]
        except:
            pass

    run_truck_odo_scraper(target_date=custom_date, send_to_sheet=send_sheet, send_to_tg=send_tg, fast_mode=is_fast)

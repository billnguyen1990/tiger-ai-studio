import requests
import json
import datetime
import os
import sys

# Đường dẫn file cấu hình
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(BASE_DIR, "headers_found.json")
MAP_FILE = os.path.join(BASE_DIR, "nvxl_telegram_map.json")

# Telegram Config (Group: Miền Tây 01 - Topic: Báo Cáo)
TELEGRAM_BOT_TOKEN = "8777045986:AAEX1uau8GFdxPAj0aAVUwDNQnpQb1IZOIA"
TELEGRAM_CHAT_ID = "-1003940889949"
TELEGRAM_MESSAGE_THREAD_ID = 2690

URL_TRIP_LIST = "https://nhanh-api.ghn.vn/api/lastmile/trip/get-trip-list-by-hub"
URL_UNPAID_COD = "https://nhanh-api.ghn.vn/api/lastmile/receipt/get-collectable-amount-by-hub"
URL_PAID_RECEIPTS = "https://nhanh-api.ghn.vn/api/lastmile/receipt/search-receipt-detail"

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

def run_evening_audit(target_date=None):
    """
    Quét dữ liệu chốt ca 21h cuối ngày:
    1. Chuyến đi chưa kết thúc (còn ON_TRIP)
    2. Đối soát tiền COD: Ai chưa nộp (nợ COD) vs Ai đã nộp (trong Tìm kiếm chi tiết)
    """
    headers = get_headers()
    nvxl_map = get_nvxl_map()

    now = get_vietnam_now()
    if target_date is None:
        target_date = now.date()

    date_display = target_date.strftime("%d/%m/%Y")
    
    results = {
        "date": date_display,
        "hubs_data": {}
    }

    for hid, info in nvxl_map.items():
        hname = info["short_name"]
        nvxl_tag = info["telegram_tag"]
        headers["x-warehouseid"] = hid
        
        # 1. Quét chuyến đi đang chạy (ON_TRIP)
        p_trip = {
            "hub_id": hid,
            "status": "ON_TRIP",
            "is_ready": 0,
            "offset": 0,
            "limit": 50
        }
        r_trip = requests.post(URL_TRIP_LIST, json=p_trip, headers=headers, timeout=10).json()
        raw_trips = r_trip.get("data", []) or []
        
        ongoing_trips = []
        for t in raw_trips:
            t_code = t.get("tripCode")
            d_name = t.get("driverName")
            cnt = t.get("deliverCount", 0)
            st_raw = t.get("startTime", "")
            st_vn = ""
            if st_raw:
                try:
                    dt = datetime.datetime.strptime(st_raw[:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=7)
                    st_vn = dt.strftime("%H:%M")
                except:
                    st_vn = st_raw
            ongoing_trips.append({
                "trip_code": t_code,
                "driver_name": d_name,
                "order_count": cnt,
                "start_time": st_vn
            })

        # 2. Quét tiền COD chưa nộp (Thu hộ cần thu)
        r_unpaid = requests.post(URL_UNPAID_COD, json={"hub_id": hid}, headers=headers, timeout=10).json()
        raw_unpaid = r_unpaid.get("data", []) or []
        
        unpaid_cod = []
        total_unpaid_amount = 0
        for up in raw_unpaid:
            amt = up.get("paid_amount", 0)
            total_unpaid_amount += amt
            unpaid_cod.append({
                "driver_name": up.get("paid_user_name"),
                "trip_code": up.get("trip_code"),
                "order_count": up.get("order_number", 0),
                "amount": amt
            })
            
        # Sắp xếp số tiền nợ nhiều nhất lên đầu
        unpaid_cod.sort(key=lambda x: x["amount"], reverse=True)

        # 3. Quét tiền COD đã nộp thành công (Tìm kiếm chi tiết phiếu thu hôm nay)
        p_paid = {
            "hubId": hid,
            "paging": {"offset": 0, "limit": 100}
        }
        r_paid = requests.post(URL_PAID_RECEIPTS, json=p_paid, headers=headers, timeout=10).json()
        raw_paid = r_paid.get("data", []) or []
        
        paid_trips = {}
        total_paid_amount = 0
        for pd in raw_paid:
            t_code = pd.get("tripCode", "")
            d_name = pd.get("paidUserName", "Khác")
            amt = pd.get("paidAmount", 0)
            total_paid_amount += amt
            if t_code not in paid_trips:
                paid_trips[t_code] = {
                    "trip_code": t_code,
                    "driver_name": d_name,
                    "order_count": 0,
                    "amount": 0
                }
            paid_trips[t_code]["order_count"] += 1
            paid_trips[t_code]["amount"] += amt
            
        results["hubs_data"][hid] = {
            "hub_name": hname,
            "nvxl_name": info["nvxl_name"],
            "nvxl_tag": nvxl_tag,
            "ongoing_trips": ongoing_trips,
            "unpaid_cod": unpaid_cod,
            "total_unpaid_amount": total_unpaid_amount,
            "paid_trips_count": len(paid_trips),
            "total_paid_amount": total_paid_amount,
            "is_clean": (len(ongoing_trips) == 0 and len(unpaid_cod) == 0)
        }

    return results

CACHE_FILE = os.path.join(BASE_DIR, "evening_status_cache.json")

def save_cache_status(data):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Không thể lưu cache: {e}")

def load_cache_status():
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def format_evening_message(audit_data, slot="21h", prev_cache=None):
    """
    Tạo nội dung bản tin chốt ca Telegram chuẩn HTML:
    - Slot 21h: Báo cáo đầy đủ đôn đốc
    - Slot 21h30: Báo cáo nghiệm thu rút gọn sau 30 phút
    """
    d = audit_data["date"]
    total_ongoing = sum(len(h["ongoing_trips"]) for h in audit_data["hubs_data"].values())
    total_unpaid_cod = sum(len(h["unpaid_cod"]) for h in audit_data["hubs_data"].values())
    all_clean = (total_ongoing == 0 and total_unpaid_cod == 0)

    lines = []

    if slot == "21h30":
        # Form nghiệm thu rút gọn lúc 21:30
        lines.append("🌙 <b>TIGER AI - NGHIỆM THU CHỐT SỔ TOÀN CỤM MT01 (21:30)</b>")
        lines.append(f"⏱ <i>Ngày: {d} | Thời điểm kiểm tra: 21:30 (Sau 30 phút đôn đốc)</i>")
        lines.append("━" * 30)

        if all_clean:
            lines.append("🎉 <b>HOÀN TẤT CHỐT SỔ 100%!</b>")
            lines.append("<pre><code class=\"language-diff\">")
            lines.append("+ ✅ 100% chuyến xe đã FINISHED an toàn.")
            lines.append("+ ✅ 100% tiền COD đã nộp đủ vào quỹ kho.")
            lines.append("</code></pre>")
            lines.append("🌟 Tuyên dương 4 kho MT01 đã hoàn thành xuất sắc ca làm việc hôm nay!")
            lines.append("Chúc toàn thể đội ngũ MT01 nghỉ ngơi ngon giấc! 💤")
            return "\n".join(lines)

        lines.append("🚨 <b>CÁC MỤC TỒN ĐỌNG QUA ĐÊM CHƯA XỬ LÝ (21:30):</b>")
        
        # Chuyến treo
        if total_ongoing > 0:
            lines.append("\n🚗 <b>Chuyến đi còn treo ON_TRIP:</b>")
            for hid, h in audit_data["hubs_data"].items():
                if h["ongoing_trips"]:
                    lines.append(f"• <b>Kho {h['hub_name']}</b> (Còn {len(h['ongoing_trips'])} chuyến):")
                    diff_ongoing = ["<pre><code class=\"language-diff\">"]
                    for t in h["ongoing_trips"]:
                        diff_ongoing.append(f"- 🚗 {t['trip_code']}: Treo ON_TRIP ({t['order_count']} đơn) (NV: {t['driver_name']})")
                    diff_ongoing.append("</code></pre>")
                    lines.append("\n".join(diff_ongoing))
                    lines.append(f"  👉 NVXL {h['nvxl_tag']}: Giục NV kết thúc chuyến ngay!")

        # Tiền nợ COD
        if total_unpaid_cod > 0:
            lines.append("\n💵 <b>NV còn giữ tiền COD chưa nộp:</b>")
            for hid, h in audit_data["hubs_data"].items():
                if h["unpaid_cod"]:
                    sum_amt = f"{h['total_unpaid_amount']:,}"
                    lines.append(f"• <b>Kho {h['hub_name']}</b>: {len(h['unpaid_cod'])} NV giữ <b>{sum_amt} đ</b>")
                    diff_cod = ["<pre><code class=\"language-diff\">"]
                    for u in h["unpaid_cod"]:
                        amt_str = f"{u['amount']:,}"
                        diff_cod.append(f"- 💵 {u['trip_code']}: Nợ {amt_str} đ (NV: {u['driver_name']})")
                    diff_cod.append("</code></pre>")
                    lines.append("\n".join(diff_cod))
                    lines.append(f"  👉 NVXL {h['nvxl_tag']}: Chốt nộp két hoặc báo cáo giữ nợ qua đêm!")

        lines.append("\n" + "━" * 30)
        lines.append("⚠️ <i>Yêu cầu Quản lý các kho có tên trên xử lý dứt điểm trước khi rời kho!</i>")
        return "\n".join(lines)

    # Slot 21:00 (Form chuẩn)
    lines.append("🌙 <b>TIGER AI - BÁO CÁO CHỐT CA CUỐI NGÀY MIỀN TÂY 01 (21:00)</b>")
    lines.append(f"📅 <i>Ngày: {d} | Thời điểm kiểm tra: 21:00</i>")
    lines.append("━" * 30)

    # 1. CẢNH BÁO CHUYẾN ĐI
    if total_ongoing > 0:
        lines.append("🚨 <b>CẢNH BÁO 1: CHUYẾN ĐI CHƯA KẾT THÚC (TREO ON_TRIP):</b>")
        for hid, h in audit_data["hubs_data"].items():
            if h["ongoing_trips"]:
                lines.append(f"• 🏢 <b>Kho {h['hub_name']}</b> (Còn {len(h['ongoing_trips'])} chuyến chưa chốt):")
                diff_ongoing = ["<pre><code class=\"language-diff\">"]
                for t in h["ongoing_trips"]:
                    diff_ongoing.append(f"- 🚗 {t['trip_code']}: Treo ON_TRIP ({t['order_count']} đơn) (NV: {t['driver_name']})")
                diff_ongoing.append("</code></pre>")
                lines.append("\n".join(diff_ongoing))
                lines.append(f"  👉 NVXL {h['nvxl_tag']}: Giục NV về kho chốt kết thúc chuyến ngay!")
    else:
        lines.append("✅ <b>CHUYẾN ĐI:</b> 100% chuyến xe của 4 kho đã KẾT THÚC (FINISHED) an toàn!")

    lines.append("━" * 30)

    # 2. CẢNH BÁO TIỀN COD
    if total_unpaid_cod > 0:
        lines.append("💵 <b>CẢNH BÁO 2: NV CHƯA NỘP TIỀN COD (NỢ COD):</b>")
        for hid, h in audit_data["hubs_data"].items():
            if h["unpaid_cod"]:
                sum_amt = f"{h['total_unpaid_amount']:,}"
                lines.append(f"• 🏢 <b>Kho {h['hub_name']}</b>: Còn <b>{len(h['unpaid_cod'])} NV</b> giữ tổng <b>{sum_amt} đ</b>")
                diff_cod = ["<pre><code class=\"language-diff\">"]
                for u in h["unpaid_cod"]:
                    amt_str = f"{u['amount']:,}"
                    diff_cod.append(f"- 💵 {u['trip_code']}: Nợ {amt_str} đ (NV: {u['driver_name']})")
                diff_cod.append("</code></pre>")
                lines.append("\n".join(diff_cod))
                lines.append(f"  👉 NVXL {h['nvxl_tag']}: Thu tiền và bắn kiểm phiếu thu vào quỹ ngay!")
    else:
        lines.append("✅ <b>TIỀN COD:</b> 100% NV đã nộp đủ tiền, NVXL đã khóa phiếu thu sạch sẽ!")

    lines.append("━" * 30)

    # 3. KHO HOÀN TẤT XUẤT SẮC
    clean_hubs = [h for h in audit_data["hubs_data"].values() if h["is_clean"]]
    if clean_hubs:
        lines.append("🏆 <b>KHO ĐÃ HOÀN TẤT CHỐT SỔ 100% (Hết chuyến treo & Sạch COD):</b>")
        for ch in clean_hubs:
            lines.append(f"• 🥇 <b>Kho {ch['hub_name']}</b> (NVXL: {ch.get('nvxl_name', '')}) - Xuất sắc hoàn thành chốt ca!")

    return "\n".join(lines)

def send_telegram_alert(text):
    """Gửi tin nhắn Telegram vào nhóm Miền Tây 01"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    if TELEGRAM_MESSAGE_THREAD_ID is not None:
        payload["message_thread_id"] = TELEGRAM_MESSAGE_THREAD_ID

    try:
        r = requests.post(url, json=payload, timeout=10)
        res = r.json()
        if res.get("ok"):
            print("✅ Đã gửi báo cáo chốt ca lên Telegram thành công!")
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
    is_shutdown = "--shutdown" in args
    
    # Xác định mốc giờ: 21h hoặc 21h30
    slot = "21h"
    if "--slot" in args:
        idx = args.index("--slot")
        if idx + 1 < len(args):
            slot = args[idx + 1].strip().lower()

    print(f"⏳ Tiger AI đang quét dữ liệu Chuyến đi & Tiền COD 4 kho MT01 (Mốc {slot})...")
    data = run_evening_audit()
    
    total_ongoing = sum(len(h["ongoing_trips"]) for h in data["hubs_data"].values())
    total_unpaid_cod = sum(len(h["unpaid_cod"]) for h in data["hubs_data"].values())
    all_clean_now = (total_ongoing == 0 and total_unpaid_cod == 0)

    # Đọc cache mốc 21h
    prev_cache = load_cache_status()

    # Kiểm tra điều kiện im lặng thông minh lúc 21h30
    skip_telegram_send = False
    if slot == "21h30":
        was_21h_clean = prev_cache.get("all_clean", False) if prev_cache else False
        if was_21h_clean and all_clean_now:
            skip_telegram_send = True
            print("🤫 [IM LẶNG LÀ VÀNG]: Cả 4 kho đã sạch 100% từ mốc 21:00. Bỏ qua không gửi Telegram lúc 21:30 để tránh làm phiền đội ngũ!")

    # Lưu cache hiện tại
    save_cache_status({
        "date": data["date"],
        "slot": slot,
        "all_clean": all_clean_now,
        "total_ongoing": total_ongoing,
        "total_unpaid_cod": total_unpaid_cod,
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    msg = format_evening_message(data, slot=slot, prev_cache=prev_cache)

    print("\n" + "=" * 55)
    print(f"NỘI DUNG BÁO CÁO CHỐT CA ({slot}):")
    print("=" * 55)
    print(msg)
    print("=" * 55 + "\n")

    if is_send:
        if skip_telegram_send:
            print("ℹ️ Đã kích hoạt chế độ im lặng, không gửi tin Telegram.")
        else:
            print("🚀 Đang tiến hành gửi lên nhóm Telegram Miền Tây 01...")
            send_telegram_alert(msg)
    else:
        print("💡 Chế độ Dry-Run (chưa gửi). Để gửi thực tế lên Telegram, thêm cờ --send")

    # Kích hoạt bảng thông báo tắt máy tự động 5 phút (nếu có cờ --shutdown)
    if is_shutdown:
        print("\n⏳ [TỰ ĐỘNG TẮT NGUỒN] Đang khởi chạy bảng đếm ngược 5 phút tắt máy (Giao diện Card VIP)...")
        ps1_path = os.path.join(BASE_DIR, "tiger_shutdown_ui.ps1")
        if os.path.exists(ps1_path):
            try:
                import win32process
                si = win32process.STARTUPINFO()
                si.lpDesktop = r"WinSta0\Default"
                cmd = f'powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "{ps1_path}" -Seconds 300'
                win32process.CreateProcess(None, cmd, None, None, False, 0, None, BASE_DIR, si)
                print("✅ Đã kích hoạt bảng đếm ngược WPF VIP trên màn hình chính của sếp!")
            except Exception as e:
                # Fallback subprocess nếu win32process lỗi
                import subprocess
                subprocess.Popen(["powershell.exe", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", ps1_path, "-Seconds", "300"])
                print(f"✅ Đã kích hoạt bảng đếm ngược qua subprocess.Popen: {e}")

if __name__ == "__main__":
    main()


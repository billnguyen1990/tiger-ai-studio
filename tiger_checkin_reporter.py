import requests
import json
import datetime
import os
import sys
import time

# Đường dẫn file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(BASE_DIR, "headers_found.json")
MAP_FILE = os.path.join(BASE_DIR, "nvxl_telegram_map.json")

# Telegram Config (Group: Miền Tây 01 - Topic: Báo Cáo)
TELEGRAM_BOT_TOKEN = "8777045986:AAEX1uau8GFdxPAj0aAVUwDNQnpQb1IZOIA"
TELEGRAM_CHAT_ID = "-1003940889949"
TELEGRAM_MESSAGE_THREAD_ID = 2690

URL_SCHEDULE = "https://nhanh-api.ghn.vn/api/sop/user-schedule/get-user-schedules-by-hub"
URL_CHECKIN = "https://nhanh-api.ghn.vn/api/sop/management/get-checkin-history"

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

def run_checkin_audit(target_date=None):
    """Quét dữ liệu lịch làm việc và check-in của 4 kho MT01 cho ngày target_date (mặc định hôm nay)"""
    headers = get_headers()
    nvxl_map = get_nvxl_map()

    now = get_vietnam_now()
    if target_date is None:
        target_date = now.date()

    # Dải thời gian UTC tương ứng với 00:00:00 -> 23:59:59 giờ VN (UTC+7)
    dt_vn_start = datetime.datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
    dt_vn_end = datetime.datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
    
    dt_utc_start = dt_vn_start - datetime.timedelta(hours=7)
    dt_utc_end = dt_vn_end - datetime.timedelta(hours=7)
    
    from_date_iso = dt_utc_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    to_date_iso = dt_utc_end.strftime("%Y-%m-%dT%H:%M:%S.999Z")
    
    date_display = target_date.strftime("%d/%m/%Y")
    
    results = {
        "date": date_display,
        "total_scheduled": 0,
        "total_checked_in": 0,
        "missing_checkin": [],   # Có ca nhưng chưa checkin
        "late_checkin": [],      # Checkin trễ
        "early_checkin": [],     # Checkin đúng giờ / sớm
        "spotless_hubs": []      # Kho 100% đúng giờ / sớm
    }

    for hid, info in nvxl_map.items():
        hname = info["short_name"]
        nvxl_tag = info["telegram_tag"]
        
        # 1. Kéo Lịch làm việc
        p_sched = {
            "hub_id": hid,
            "from_date": from_date_iso,
            "to_date": to_date_iso
        }
        r_sched = requests.post(URL_SCHEDULE, json=p_sched, headers=headers, timeout=10).json()
        users_sched = r_sched.get("data", {}).get("users", [])
        
        # 2. Kéo Lịch sử check-in
        p_checkin = {
            "hub_id": hid,
            "user_id": "",
            "from_date": from_date_iso,
            "to_date": to_date_iso,
            "offset": 0,
            "limit": 100
        }
        r_checkin = requests.post(URL_CHECKIN, json=p_checkin, headers=headers, timeout=10).json()
        records_checkin = r_checkin.get("data", {}).get("data", [])
        
        # Map user check-in
        user_checkin_map = {}
        for rc in records_checkin:
            uid = str(rc.get("user_id"))
            if uid not in user_checkin_map:
                user_checkin_map[uid] = []
            user_checkin_map[uid].append(rc)
            
        hub_has_late = False
        hub_has_missing = False
        hub_scheduled_count = len(users_sched)
        results["total_scheduled"] += hub_scheduled_count
        
        for u in users_sched:
            uid = str(u.get("user_id"))
            uname = u.get("user_name")
            schedules = u.get("schedules", [])
            
            shifts = []
            if schedules:
                shifts = schedules[0].get("shifts", []) or []
                
            is_on_leave = False
            if shifts and shifts[0].get("is_on_leave"):
                is_on_leave = True
                
            # Nếu có ca làm việc và không nghỉ phép
            if shifts and not is_on_leave:
                if uid not in user_checkin_map:
                    # Chưa check-in
                    hub_has_missing = True
                    results["missing_checkin"].append({
                        "hub_id": hid,
                        "hub_name": hname,
                        "nvxl_tag": nvxl_tag,
                        "user_id": uid,
                        "user_name": uname,
                        "shift": f"{shifts[0].get('start_at')} ~ {shifts[0].get('end_at')}"
                    })
                else:
                    results["total_checked_in"] += 1
                    # Kiểm tra giờ check-in
                    recs = user_checkin_map[uid]
                    recs.sort(key=lambda x: x.get("checkin_at", ""))
                    # Lấy bản ghi thành công
                    succ = [x for x in recs if "Check in sớm" in x.get("message", "") or "Check in trễ" in x.get("message", "")]
                    top = succ[-1] if succ else recs[-1]
                    
                    t_raw = top.get("checkin_at", "")
                    dt_checkin = datetime.datetime.strptime(t_raw[:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=7)
                    t_vn_str = dt_checkin.strftime("%H:%M:%S")
                    
                    # Chuẩn ca: 07:30
                    shift_threshold = dt_checkin.replace(hour=7, minute=30, second=0, microsecond=0)
                    diff_sec = (dt_checkin - shift_threshold).total_seconds()
                    
                    if diff_sec > 0:
                        # Muộn
                        hub_has_late = True
                        diff_min = int(diff_sec // 60)
                        results["late_checkin"].append({
                            "hub_id": hid,
                            "hub_name": hname,
                            "nvxl_tag": nvxl_tag,
                            "user_id": uid,
                            "user_name": uname,
                            "checkin_time": t_vn_str,
                            "diff_min": diff_min,
                            "message": top.get("message", "")
                        })
                    else:
                        # Sớm
                        diff_min = int(abs(diff_sec) // 60)
                        results["early_checkin"].append({
                            "hub_id": hid,
                            "hub_name": hname,
                            "nvxl_tag": nvxl_tag,
                            "user_id": uid,
                            "user_name": uname,
                            "checkin_time": t_vn_str,
                            "diff_min": diff_min
                        })
                        
        if not hub_has_late and not hub_has_missing and hub_scheduled_count > 0:
            results["spotless_hubs"].append({
                "hub_name": hname,
                "count": hub_scheduled_count,
                "nvxl_name": info["nvxl_name"],
                "nvxl_tag": nvxl_tag
            })
            
    # Sắp xếp
    results["early_checkin"].sort(key=lambda x: x["checkin_time"])
    results["late_checkin"].sort(key=lambda x: x["diff_min"], reverse=True)
    return results

def format_telegram_message(audit_data):
    """Định dạng bản tin báo cáo gửi Telegram chuẩn HTML"""
    d = audit_data["date"]
    lines = []
    lines.append("⏰ <b>TIGER AI - ĐIỂM DANH ĐẦU CA MIỀN TÂY 01</b>")
    lines.append(f"📅 <i>Ngày: {d} | Mốc chuẩn ca làm việc: 07:30</i>")
    lines.append("━" * 28)
    
    # 1. CẢNH BÁO CHƯA CHECK-IN
    missing = audit_data["missing_checkin"]
    if missing:
        lines.append("🚨 <b>CẢNH BÁO: CÓ CA LÀM NHƯNG CHƯA CHECK-IN!</b>")
        for m in missing:
            lines.append(f"• 🏢 <b>{m['hub_name']}</b>: <b>NV {m['user_name']}</b> (Mã: <code>{m['user_id']}</code>)")
            lines.append(f"  👉 NVXL {m['nvxl_tag']}: Giục NV check-in & phân ca ngay!")
    else:
        lines.append("✅ <b>QUÂN SỐ ĐẦY ĐỦ:</b> 100% NV có ca đều đã check-in!")
        
    lines.append("━" * 28)
    
    # 2. CẢNH BÁO CHECK-IN TRỄ
    late = audit_data["late_checkin"]
    if late:
        lines.append("⚠️ <b>CẢNH BÁO: CHECK-IN TRỄ GIỜ (Sau 07:30)</b>")
        for l in late:
            lines.append(f"• 🏢 <b>{l['hub_name']}</b>: <b>NV {l['user_name']}</b> (<code>{l['user_id']}</code>)")
            lines.append(f"  🕒 Check-in lúc: <b>{l['checkin_time']}</b> (Trễ <b>{l['diff_min']} phút</b>)")
            lines.append(f"  👉 NVXL {l['nvxl_tag']}: Chấn chỉnh kỷ luật giờ giấc của NV!")
    else:
        lines.append("🌟 <b>100% ĐÚNG GIỜ:</b> Không có NV nào check-in trễ!")
        
    lines.append("━" * 28)
    
    # 3. TUYÊN DƯƠNG KHO XUẤT SẮC
    spotless = audit_data["spotless_hubs"]
    if spotless:
        lines.append("🏆 <b>KHO GƯƠNG MẪU (100% Quân số đúng giờ / sớm):</b>")
        for s in spotless:
            lines.append(f"• 🥇 <b>Kho {s['hub_name']}</b>: {s['count']}/{s['count']} NV đúng giờ (NVXL: {s.get('nvxl_name', '')})")
            
    # 4. TOP ĐI SỚM
    early = audit_data["early_checkin"]
    if early:
        top3 = early[:3]
        lines.append("\n🎖️ <b>Top gương mặt đi sớm nhất MT01:</b>")
        medals = ["🥇", "🥈", "🥉"]
        for idx, item in enumerate(top3):
            m = medals[idx] if idx < len(medals) else "•"
            lines.append(f"{m} <b>NV {item['user_name']}</b> ({item['hub_name']}) - <code>{item['checkin_time']}</code> (Sớm {item['diff_min']}p)")
            
    return "\n".join(lines)

def send_telegram_alert(text):
    """Gửi tin nhắn Telegram vào Topic MT01"""
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
            print("✅ Đã gửi báo cáo điểm danh Telegram thành công!")
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
    is_dry = "--dry-run" in args or not is_send
    
    print("⏳ Tiger AI đang quét Lịch Làm Việc & Lịch Sử Check-in MT01...")
    data = run_checkin_audit()
    msg = format_telegram_message(data)
    
    print("\n" + "=" * 50)
    print("NỘI DUNG BÁO CÁO TELEGRAM SẼ GỬI:")
    print("=" * 50)
    print(msg)
    print("=" * 50 + "\n")
    
    if is_send:
        print("🚀 Đang tiến hành gửi lên nhóm Telegram...")
        send_telegram_alert(msg)
    else:
        print("💡 Chế độ Dry-Run (chưa gửi). Để gửi thực tế lên Telegram, chạy lệnh: python tiger_checkin_reporter.py --send")

if __name__ == "__main__":
    main()

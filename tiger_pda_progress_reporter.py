import requests
import json
import datetime
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(BASE_DIR, "headers_found.json")
MAP_FILE = os.path.join(BASE_DIR, "nvxl_telegram_map.json")

# Telegram Config (Group: Miền Tây 01 - Topic: Báo Cáo)
TELEGRAM_BOT_TOKEN = "8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk"
TELEGRAM_CHAT_ID = "-1003940889949"
TELEGRAM_MESSAGE_THREAD_ID = 2690

URL_TRIPS = "https://nhanh-api.ghn.vn/api/lastmile/trip/get-trip-list-by-hub"
URL_ITEMS = "https://nhanh-api.ghn.vn/api/lastmile/v2/trip/get-trip-items"
URL_TRIP_HIST = "https://nhanh-api.ghn.vn/api/lastmile/history/get-trip-history"
URL_ORDER_HIST = "https://nhanh-api.ghn.vn/api/lastmile/history/get-order-history"

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

def fetch_ghn_post(url, headers, payload, max_retries=3, timeout=20):
    """Gửi request POST tới GHN với cơ chế tự động thử lại (Retry) khi gặp nghẽn mạng/timeout"""
    for attempt in range(max_retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                code = data.get("code")
                err = data.get("error")
                err_code = data.get("errorCode")
                # GHN có API trả code 0, có API trả code 200, có API trả error=None/False và data != None
                is_success = (code in [0, 200, "0", "200", None]) and (not err) and (err_code in [0, "0", None])
                if is_success:
                    return data
                else:
                    print(f"  [Lần {attempt+1}/{max_retries}] GHN trả mã lỗi code={code}: {data.get('message')}")
            else:
                print(f"  [Lần {attempt+1}/{max_retries}] HTTP status {r.status_code}")
        except Exception as e:
            print(f"  [Lần {attempt+1}/{max_retries}] Lỗi kết nối: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(1.0 * (attempt + 1))
    return None

def get_order_assign_count(headers, order_code):
    """Đếm số lần đơn hàng này đã từng bị gán giao (số lần đi giao)"""
    try:
        res = fetch_ghn_post(URL_ORDER_HIST, headers, {"orderCode": order_code, "paging": {"offset": 0, "limit": 30}}, max_retries=2, timeout=10)
        items = (res.get("data", {}).get("data", []) or []) if res else []
        assign_cnt = sum(1 for it in items if it.get("historyType") in ["ASSIGN_TRIP", "START_TRIP", "ASSIGN"])
        return max(1, assign_cnt)
    except:
        return 1

def get_vietnam_now():
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    vn_tz = datetime.timezone(datetime.timedelta(hours=7))
    return utc_now.astimezone(vn_tz)

def run_pda_progress_audit():
    headers = get_headers()
    nvxl_map = get_nvxl_map()
    now = get_vietnam_now()
    today_int = int(now.strftime("%Y%m%d"))
    today_str = str(today_int)
    today_iso = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    results = {
        "date_str": now.strftime("%d/%m/%Y"),
        "time_str": time_str,
        "hubs": {}
    }

    for hid, info in nvxl_map.items():
        hname = info["short_name"]
        nvxl_tag = info["telegram_tag"]
        headers["x-warehouseid"] = str(hid)

        # 1. Quét các chuyến đi hôm nay (hỗ trợ limit 100 và retry phòng nghẽn)
        hub_trips = []
        for st in ["ON_TRIP", "FINISHED", "NEW"]:
            p = {
                "hub_id": str(hid),
                "status": st,
                "is_ready": 0,
                "offset": 0,
                "limit": 100,
                "reverse": 1
            }
            res = fetch_ghn_post(URL_TRIPS, headers, p, max_retries=3, timeout=20)
            trips = (res.get("data", []) or []) if res else []
            for t in trips:
                c_date = str(t.get("createDateIndex") or "")
                s_date = str(t.get("startDateIndex") or "")
                c_time = str(t.get("createdTime") or "")
                s_time = str(t.get("startTime") or "")
                
                # Nhận diện chuyến hôm nay chính xác tuyệt đối qua cả index và timestamp
                if c_date == today_str or s_date == today_str or c_time.startswith(today_iso) or s_time.startswith(today_iso):
                    hub_trips.append(t)

        total_orders = 0
        total_gtc = 0
        total_gtb = 0
        total_dang_giao = 0
        gtb_details = []
        driver_pda_timelines = []

        for t in hub_trips:
            tc = t.get("tripCode")
            driver = t.get("driverName") or "Chưa rõ"
            phone = t.get("driverPhone") or ""
            trip_status = t.get("status")

            # Lấy danh sách đơn của chuyến với retry
            p_items = {"typeList": ["DELIVER"], "offset": 0, "limit": 200, "TripCode": tc}
            res_items = fetch_ghn_post(URL_ITEMS, headers, p_items, max_retries=2, timeout=15)
            items = (res_items.get("data", []) or []) if res_items else []

            trip_gtc = 0
            trip_gtb = 0
            trip_dang_giao = 0

            for it in items:
                total_orders += 1
                is_up = it.get("isUpdated", False)
                is_suc = it.get("isSucceeded", False)
                if not is_up:
                    total_dang_giao += 1
                    trip_dang_giao += 1
                elif is_suc:
                    total_gtc += 1
                    trip_gtc += 1
                else:
                    total_gtb += 1
                    trip_gtb += 1
                    fn = it.get("failNote") or "Không rõ lý do"
                    oc = it.get("orderCode")
                    # Tối ưu: Chỉ query lịch sử đơn cho top 5 đơn GTB hiển thị để tốc độ cào đạt mức mili-giây
                    assign_cnt = get_order_assign_count(headers, oc) if len(gtb_details) < 5 else 1
                    gtb_details.append({
                        "order_code": oc,
                        "driver_name": driver,
                        "trip_code": tc,
                        "fail_reason": fn,
                        "assign_count": assign_cnt
                    })

            # Lấy timeline PDA của chuyến đi (Tối ưu: Chỉ gọi API timeline chi tiết cho top 5 chuyến hiển thị trên báo cáo)
            first_act = "-"
            last_act = "-"
            start_vn = "-"
            end_vn = "Đang chạy" if trip_status == "ON_TRIP" else ("Hoàn tất" if trip_status == "FINISHED" else "Mới tạo")

            if len(driver_pda_timelines) < 5:
                try:
                    res_hist = fetch_ghn_post(URL_TRIP_HIST, headers, {"tripCode": tc, "paging": {"offset": 0, "limit": 200}}, max_retries=2, timeout=8)
                    h_items = (res_hist.get("data", {}).get("data", []) or []) if res_hist else []
                    h_sorted = sorted(h_items, key=lambda x: x.get("createdTime", ""))

                    update_events = [x for x in h_sorted if x.get("historyType") == "UPDATE_ITEM"]
                    if update_events:
                        t_first = update_events[0].get("createdTime", "")
                        t_last = update_events[-1].get("createdTime", "")
                        if t_first:
                            dt1 = datetime.datetime.strptime(t_first[:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=7)
                            first_act = dt1.strftime("%H:%M")
                        if t_last:
                            dt2 = datetime.datetime.strptime(t_last[:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=7)
                            last_act = dt2.strftime("%H:%M")

                    start_evt = next((x for x in h_sorted if x.get("historyType") == "START_TRIP"), None)
                    if start_evt and start_evt.get("createdTime"):
                        dt_s = datetime.datetime.strptime(start_evt["createdTime"][:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=7)
                        start_vn = dt_s.strftime("%H:%M")
                    elif t.get("startTime"):
                        try:
                            dt_s = datetime.datetime.strptime(t["startTime"][:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=7)
                            start_vn = dt_s.strftime("%H:%M")
                        except:
                            pass
                except:
                    pass
            elif t.get("startTime"):
                try:
                    dt_s = datetime.datetime.strptime(t["startTime"][:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=7)
                    start_vn = dt_s.strftime("%H:%M")
                except:
                    pass

            driver_pda_timelines.append({
                "driver_name": driver,
                "trip_code": tc,
                "total_orders": len(items),
                "done_count": trip_gtc + trip_gtb,
                "gtc": trip_gtc,
                "gtb": trip_gtb,
                "remaining": trip_dang_giao,
                "start_time": start_vn,
                "first_action": first_act,
                "last_action": last_act,
                "status_text": end_vn
            })

        # Tính % tiến độ
        processed = total_gtc + total_gtb
        progress_pct = round((processed / total_orders * 100), 1) if total_orders > 0 else 0.0
        gtc_rate = round((total_gtc / processed * 100), 1) if processed > 0 else 0.0

        results["hubs"][hid] = {
            "hub_name": hname,
            "nvxl_name": info["nvxl_name"],
            "nvxl_tag": nvxl_tag,
            "total_orders": total_orders,
            "total_dang_giao": total_dang_giao,
            "total_gtc": total_gtc,
            "total_gtb": total_gtb,
            "progress_pct": progress_pct,
            "gtc_rate": gtc_rate,
            "gtb_details": gtb_details,
            "timelines": driver_pda_timelines
        }

    return results

def format_pda_message(results):
    d = results["date_str"]
    tm = results["time_str"]

    lines = []
    lines.append(f"📱 <b>TIGER AI - TIẾN ĐỘ GIAO HÀNG & THAO TÁC PDA ({tm})</b>")
    lines.append(f"📅 <i>Ngày: {d} | Mốc cập nhật tiến độ: {tm}</i>")
    lines.append("━" * 30)

    # Tổng quan toàn cụm
    tot_orders = sum(h["total_orders"] for h in results["hubs"].values())
    tot_gtc = sum(h["total_gtc"] for h in results["hubs"].values())
    tot_gtb = sum(h["total_gtb"] for h in results["hubs"].values())
    tot_dang = sum(h["total_dang_giao"] for h in results["hubs"].values())
    tot_proc = tot_gtc + tot_gtb
    tot_pct = round((tot_proc / tot_orders * 100), 1) if tot_orders > 0 else 0.0

    lines.append(f"🎯 <b>TIẾN ĐỘ CHUNG CỤM MT01:</b> Đã xử lý <b>{tot_proc}/{tot_orders} đơn</b> (<b>{tot_pct}%</b>)")
    lines.append(f"   └ 🟢 GTC: <b>{tot_gtc}</b> | 🔴 GTB: <b>{tot_gtb}</b> | 🛵 Đang giao: <b>{tot_dang} đơn</b>")
    lines.append("━" * 30)

    hubs_need_action = []

    for hid, h in results["hubs"].items():
        nvxl_name = h.get("nvxl_name", "")
        lines.append(f"🏢 <b>Kho {h['hub_name']}</b> (NVXL: {nvxl_name}):")
        lines.append(f"  └ 📊 Tiến độ: <b>{h['progress_pct']}%</b> | Đang giao: <b>{h['total_dang_giao']}</b> | GTC: <b>{h['total_gtc']}</b> | GTB: <b>{h['total_gtb']}</b>")

        # 1. Thao tác PDA của NV
        if h["timelines"]:
            lines.append("  └ 🛵 <i>Tiến độ thao tác PDA của NV:</i>")
            for tl in h["timelines"][:5]:
                done = tl['done_count']
                total = tl['total_orders']
                gtc = tl['gtc']
                gtb = tl['gtb']
                start = tl['start_time']
                first = tl['first_action']
                last = tl['last_action']

                if total > 0 and done >= total:
                    status_lbl = "Xong"
                    time_lbl = "Hoàn tất"
                elif done == 0:
                    status_lbl = "Chưa thao tác"
                    time_lbl = "Hiện tại"
                else:
                    status_lbl = "Đang thao tác"
                    time_lbl = "Hiện tại"

                lines.append(f"     • <b>NV {tl['driver_name']}</b>:")
                lines.append(f"        └ <b>{status_lbl}</b> : <b>{done}/{total}</b> đơn ( GTC : <b>{gtc}</b> ;  GTB : <b>{gtb}</b> ) .")
                lines.append(f"           └  Bắt đầu : {start} | Đơn đầu: {first} ➔ {time_lbl} : {last}")

        # 2. Chi tiết tiến độ & đơn GTB (Diff highlight đỏ/xanh)
        diff_lines = ["<pre><code class=\"language-diff\">"]
        if h["gtb_details"]:
            for gb in h["gtb_details"][:5]:
                safe_fn = gb['fail_reason']
                icon = "⚠️" if "hẹn" in safe_fn.lower() else "❌"
                diff_lines.append(f"- {icon} {gb['order_code']}: {safe_fn} (NV: {gb['driver_name']})")
        diff_lines.append(f"+ ✅ Đã giao thành công: {h['total_gtc']} đơn ({h['gtc_rate']}%)")
        diff_lines.append("</code></pre>")
        lines.append(f"  └ 📋 <i>Đối soát kết quả giao:</i>")
        lines.append("\n".join(diff_lines))

        if h["total_dang_giao"] > 10 or h["total_gtb"] > 5:
            hubs_need_action.append(h['nvxl_tag'])

        lines.append("")

    lines.append("━" * 30)
    if hubs_need_action:
        tags_str = " ".join(set(hubs_need_action))
        lines.append(f"👉 <b>HƯỚNG DẪN ĐIỀU HÀNH:</b> NVXL {tags_str} giục các NV còn nhiều đơn đẩy nhanh tiến độ giao dứt điểm và liên hệ xử lý ngay các đơn GTB!")
    else:
        lines.append("👉 <b>HƯỚNG DẪN ĐIỀU HÀNH:</b> Các kho duy trì tiến độ tốt, NVXL tiếp tục đôn đốc NV hoàn thành chỉ tiêu ca!")

    return "\n".join(lines)

def send_telegram_alert(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Tự động chia nhỏ tin nhắn nếu dài hơn giới hạn Telegram (4096 ký tự)
    chunks = []
    if len(text) > 3800:
        parts = text.split("\n\n")
        curr = ""
        for p in parts:
            if len(curr) + len(p) + 2 < 3800:
                curr = (curr + "\n\n" + p).strip()
            else:
                if curr:
                    chunks.append(curr)
                curr = p
        if curr:
            chunks.append(curr)
    else:
        chunks = [text]

    success = True
    for idx, chunk in enumerate(chunks):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "message_thread_id": TELEGRAM_MESSAGE_THREAD_ID,
            "text": chunk,
            "parse_mode": "HTML"
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            res = r.json()
            if res.get("ok"):
                print(f"✅ Đã gửi phần {idx+1}/{len(chunks)} lên Telegram thành công!")
            else:
                print(f"❌ Lỗi gửi Telegram phần {idx+1}: {res}")
                success = False
        except Exception as e:
            print(f"❌ Lỗi kết nối Telegram: {e}")
            success = False
    return success

def main():
    args = sys.argv[1:]
    is_send = "--send" in args

    print("⏳ Tiger AI đang quét tiến độ đơn hàng & timeline PDA 4 kho MT01...")
    data = run_pda_progress_audit()
    tot_orders = sum(h["total_orders"] for h in data["hubs"].values())

    # Nếu toàn bộ 4 kho ra 0 đơn (bất thường do nghẽn mạng), chờ 10s rồi thử lại toàn bộ 1 lần nữa
    if tot_orders == 0:
        print("⚠️ Phát hiện 0 đơn toàn cụm MT01 (bất thường), tiến hành quét lại toàn bộ sau 10 giây...")
        time.sleep(10)
        data = run_pda_progress_audit()
        tot_orders = sum(h["total_orders"] for h in data["hubs"].values())

    msg = format_pda_message(data)

    print("\n" + "=" * 55)
    print("NỘI DUNG BÁO CÁO TIẾN ĐỘ PDA:")
    print("=" * 55)
    print(msg)
    print("=" * 55 + "\n")

    if is_send:
        # CHỐT CHẶN AN TOÀN TUYỆT ĐỐI: Không bao giờ bắn báo cáo 0/0 gây hoang mang vận hành
        if tot_orders == 0:
            print("⛔ [HUỶ GỬI] Toàn bộ 4 kho MT01 đều ghi nhận 0 đơn. Có thể do nghẽn mạng GHN hoặc API gián đoạn.")
            print("👉 Đã chủ động hủy lệnh gửi tin nhắn 0/0 lên Telegram để bảo vệ tính chuẩn xác của hệ thống!")
            return

        print("🚀 Đang tiến hành gửi lên nhóm Telegram Miền Tây 01 (Chủ đề Báo Cáo)...")
        send_telegram_alert(msg)
    else:
        print("💡 Chế độ Dry-Run (chưa gửi). Dùng cờ: --send để gửi thực tế.")

if __name__ == "__main__":
    main()

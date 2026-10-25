import requests
import json
import datetime
import os
import sys

# Đường dẫn file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(BASE_DIR, "headers_found.json")
MAP_FILE = os.path.join(BASE_DIR, "nvxl_telegram_map.json")

# Telegram Config (Group: Miền Tây 01 - Topic: Báo Cáo)
TELEGRAM_BOT_TOKEN = "8777045986:AAEX1uau8GFdxPAj0aAVUwDNQnpQb1IZOIA"
TELEGRAM_CHAT_ID = "-1003940889949"
TELEGRAM_MESSAGE_THREAD_ID = 2690

URL_TRIPS = "https://nhanh-api.ghn.vn/api/lastmile/trip/get-trip-list-by-hub"
URL_ITEMS = "https://nhanh-api.ghn.vn/api/lastmile/v2/trip/get-trip-items"

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

def run_kpi_audit(target_date=None):
    """
    Quét và tổng hợp KPI Giao thành công (GTC) / Giao thất bại (GTB) của ngày hôm trước
    """
    headers = get_headers()
    nvxl_map = get_nvxl_map()

    if target_date is None:
        target_date = datetime.date.today() - datetime.timedelta(days=1)

    date_int = int(target_date.strftime("%Y%m%d"))
    date_display = target_date.strftime("%d/%m/%Y")

    results = {
        "date_str": date_display,
        "date_int": date_int,
        "hubs": {}
    }

    for hid, info in nvxl_map.items():
        hname = info["short_name"]
        nvxl_tag = info["telegram_tag"]
        headers["x-warehouseid"] = hid

        # 1. Quét tất cả chuyến đi của ngày
        hub_trips = []
        for st in ["FINISHED", "ON_TRIP", "NEW"]:
            payload = {
                "hub_id": hid,
                "status": st,
                "is_ready": 0,
                "offset": 0,
                "limit": 100
            }
            try:
                res = requests.post(URL_TRIPS, headers=headers, json=payload, timeout=10).json()
                trips = res.get("data", []) or []
                for t in trips:
                    c_date = t.get("createDateIndex")
                    s_date = t.get("startDateIndex")
                    if c_date == date_int or s_date == date_int:
                        hub_trips.append(t)
            except Exception as e:
                print(f"Lỗi lấy chuyến status {st} kho {hname}: {e}")

        # 2. Quét chi tiết từng đơn hàng trong các chuyến (GIAO & LẤY)
        total_assigned = 0
        gtc_count = 0
        gtb_count = 0
        pending_count = 0
        fail_reasons = {}

        pick_assigned = 0
        ltc_count = 0
        ltb_count = 0

        drivers_summary = {}

        for t in hub_trips:
            tc = t.get("tripCode")
            driver = t.get("driverName") or "Chưa rõ NV"
            if driver not in drivers_summary:
                drivers_summary[driver] = {"del_assigned": 0, "gtc": 0, "gtb": 0, "pick_assigned": 0, "ltc": 0, "ltb": 0}

            # A. DELIVER (Giao)
            p_items = {
                "typeList": ["DELIVER"],
                "offset": 0,
                "limit": 200,
                "TripCode": tc
            }
            try:
                r_items = requests.post(URL_ITEMS, headers=headers, json=p_items, timeout=10).json()
                items = r_items.get("data", []) or []
                for it in items:
                    total_assigned += 1
                    drivers_summary[driver]["del_assigned"] += 1
                    is_up = it.get("isUpdated", False)
                    is_suc = it.get("isSucceeded", False)
                    if not is_up:
                        pending_count += 1
                    elif is_suc:
                        gtc_count += 1
                        drivers_summary[driver]["gtc"] += 1
                    else:
                        gtb_count += 1
                        drivers_summary[driver]["gtb"] += 1
                        fn = it.get("failNote") or it.get("failReasonName") or "Lý do khác"
                        fail_reasons[fn] = fail_reasons.get(fn, 0) + 1
            except Exception as e:
                print(f"Lỗi lấy đơn giao chuyến {tc}: {e}")

            # B. PICK (Lấy)
            p_pick = {
                "typeList": ["PICK"],
                "offset": 0,
                "limit": 200,
                "TripCode": tc
            }
            try:
                r_pick = requests.post(URL_ITEMS, headers=headers, json=p_pick, timeout=10).json()
                items_pick = r_pick.get("data", []) or []
                for it in items_pick:
                    pick_assigned += 1
                    drivers_summary[driver]["pick_assigned"] += 1
                    is_up = it.get("isUpdated", False)
                    is_suc = it.get("isSucceeded", False)
                    if is_suc:
                        ltc_count += 1
                        drivers_summary[driver]["ltc"] += 1
                    elif is_up:
                        ltb_count += 1
                        drivers_summary[driver]["ltb"] += 1
            except Exception as e:
                print(f"Lỗi lấy đơn lấy chuyến {tc}: {e}")

        # 3. Tính toán cộng gộp đơn lấy vào đơn gán, LTC vào GTC, LTB vào GTB theo yêu cầu nghiệp vụ
        comb_assigned = total_assigned + pick_assigned
        comb_success = gtc_count + ltc_count
        comb_fail = gtb_count + ltb_count
        comb_rate = round((comb_success / comb_assigned) * 100, 1) if comb_assigned > 0 else 0.0

        # Phân loại đánh giá theo chuẩn KPI 85%
        if comb_assigned == 0:
            status_level = "NO_DATA"
            comment = "Không có đơn giao/lấy trong ngày"
        elif comb_rate >= 85.0:
            status_level = "DAT_CHUAN"
            comment = "Đạt chỉ tiêu xuất sắc (>= 85%)"
        elif 80.0 <= comb_rate < 85.0:
            status_level = "CAN_CHUAN"
            comment = "Cận chuẩn (80% - 84%), cần cố gắng hơn nữa"
        else:
            status_level = "DUOI_CHUAN"
            comment = "Dưới chuẩn (< 80%), cần giải trình nguyên nhân"

        # Sắp xếp top lý do thất bại
        sorted_reasons = sorted(fail_reasons.items(), key=lambda x: x[1], reverse=True)[:4]

        results["hubs"][hid] = {
            "hub_name": hname,
            "nvxl_name": info["nvxl_name"],
            "nvxl_tag": nvxl_tag,
            "trips_count": len(hub_trips),
            "total_assigned": comb_assigned,
            "gtc_count": comb_success,
            "gtb_count": comb_fail,
            "pending_count": pending_count,
            "gtc_rate": comb_rate,
            "deliver_assigned": total_assigned,
            "deliver_gtc": gtc_count,
            "deliver_gtb": gtb_count,
            "pick_assigned": pick_assigned,
            "pick_ltc": ltc_count,
            "pick_ltb": ltb_count,
            "status_level": status_level,
            "comment": comment,
            "top_reasons": sorted_reasons
        }

        if "snapshot" not in results:
            results["snapshot"] = {}
        results["snapshot"][hname] = {
            "hub_id": hid,
            "deliver": {
                "assigned": total_assigned,
                "gtc": gtc_count,
                "gtb": gtb_count,
                "rate": round(gtc_count / total_assigned * 100, 1) if total_assigned > 0 else 0.0,
                "reasons": sorted_reasons
            },
            "pick": {
                "assigned": pick_assigned,
                "ltc": ltc_count,
                "ltb": ltb_count,
                "rate": round(ltc_count / pick_assigned * 100, 1) if pick_assigned > 0 else 100.0,
                "reasons": []
            },
            "drivers": drivers_summary
        }

    return results

def format_kpi_message(results):
    """Định dạng bản tin báo cáo KPI gửi Telegram chuẩn HTML (Cộng gộp Giao & Lấy)"""
    d = results["date_str"]
    lines = []
    lines.append("📊 <b>TIGER AI - BÁO CÁO TỔNG HỢP KPI GIAO & LẤY HÀNG • MIỀN TÂY 01</b>")
    lines.append(f"📅 <i>Kết quả ca ngày hôm qua: {d} | Thời gian gửi: 07:00</i>")
    lines.append("🎯 <b>Chỉ tiêu chuẩn KPI: >= 85% (Đã cộng dồn Đơn Giao & Đơn Lấy)</b>")
    lines.append("━" * 30)

    # Thống kê từng kho
    hubs_data = results["hubs"]

    # 1. KHO ĐẠT CHUẨN (>= 85%)
    dat_chuan = [h for h in hubs_data.values() if h["status_level"] == "DAT_CHUAN"]
    if dat_chuan:
        lines.append("🏆 <b>KHO ĐẠT CHỈ TIÊU XUẤT SẮC (>= 85%):</b>")
        for h in dat_chuan:
            lines.append(f"• 🟢 <b>Kho {h['hub_name']}</b>: KPI đạt <b>{h['gtc_rate']}%</b>")
            lines.append(f"  └ 📦 Tổng gán: <b>{h['total_assigned']} đơn</b> (Giao {h['deliver_assigned']} + Lấy {h['pick_assigned']})")
            lines.append(f"  └ ✅ Thành công: <b>{h['gtc_count']} đơn</b> (GTC {h['deliver_gtc']} + LTC {h['pick_ltc']})")
            lines.append(f"  └ ❌ Thất bại: <b>{h['gtb_count']} đơn</b> (GTB {h['deliver_gtb']} + LTB {h['pick_ltb']})")
            lines.append(f"  👉 Tuyên dương tập thể kho và NVXL {h['nvxl_name']} đã hoàn thành rất tốt!")
        lines.append("")

    # 2. KHO CẬN CHUẨN (80% - 84.9%)
    can_chuan = [h for h in hubs_data.values() if h["status_level"] == "CAN_CHUAN"]
    if can_chuan:
        lines.append("⚠️ <b>KHO CẬN CHUẨN (80% - 84.9%):</b>")
        for h in can_chuan:
            lines.append(f"• 🟡 <b>Kho {h['hub_name']}</b>: KPI đạt <b>{h['gtc_rate']}%</b>")
            lines.append(f"  └ 📦 Tổng gán: <b>{h['total_assigned']} đơn</b> (Giao {h['deliver_assigned']} + Lấy {h['pick_assigned']})")
            lines.append(f"  └ ✅ Thành công: <b>{h['gtc_count']} đơn</b> (GTC {h['deliver_gtc']} + LTC {h['pick_ltc']})")
            lines.append(f"  └ ❌ Thất bại: <b>{h['gtb_count']} đơn</b> (GTB {h['deliver_gtb']} + LTB {h['pick_ltb']})")
            lines.append(f"  👉 NVXL {h['nvxl_tag']}: Đôn đốc NV kho cố gắng kéo tỉ lệ vượt mốc 85% trong ca hôm nay!")
        lines.append("")

    # 3. KHO DƯỚI CHUẨN (DƯỚI 80%)
    duoi_chuan = [h for h in hubs_data.values() if h["status_level"] == "DUOI_CHUAN"]
    if duoi_chuan:
        lines.append("🚨 <b>KHO CHƯA ĐẠT CHUẨN (DƯỚI 80%) - YÊU CẦU GIẢI TRÌNH:</b>")
        for h in duoi_chuan:
            lines.append(f"• 🔴 <b>Kho {h['hub_name']}</b>: KPI chỉ đạt <b>{h['gtc_rate']}%</b> (Quá thấp!)")
            lines.append(f"  └ 📦 Tổng gán: <b>{h['total_assigned']} đơn</b> (Giao {h['deliver_assigned']} + Lấy {h['pick_assigned']})")
            lines.append(f"  └ ✅ Thành công: <b>{h['gtc_count']} đơn</b> (GTC {h['deliver_gtc']} + LTC {h['pick_ltc']})")
            lines.append(f"  └ ❌ Thất bại: <b>{h['gtb_count']} đơn</b> (GTB {h['deliver_gtb']} + LTB {h['pick_ltb']})")
            if h["top_reasons"]:
                lines.append(f"  └ <i>Top lý do GTB nhiều nhất:</i>")
                diff_reasons = ["<pre><code class=\"language-diff\">"]
                for r_name, r_cnt in h["top_reasons"]:
                    safe_r_name = str(r_name).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    icon = "⚠️" if "hẹn" in safe_r_name.lower() else "❌"
                    diff_reasons.append(f"- {icon} {safe_r_name}: {r_cnt} đơn")
                diff_reasons.append(f"+ ✅ Đã giao thành công: {h['gtc_count']} đơn ({h['gtc_rate']}%)")
                diff_reasons.append("</code></pre>")
                lines.append("\n".join(diff_reasons))
            lines.append(f"  👉 <b>YÊU CẦU:</b> NVXL {h['nvxl_tag']} kiểm tra lại và giải trình rõ nguyên nhân vì sao kho hôm qua bị thất bại quá nhiều đơn!")
        lines.append("")

    lines.append("━" * 30)
    lines.append("💡 <i>Các kho lưu ý tập trung giao dứt điểm các đơn còn tồn đọng ngay trong ca sáng nay!</i>")

    return "\n".join(lines)

def send_telegram_alert(text):
    """Gửi tin nhắn Telegram vào chủ đề Báo Cáo"""
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
            print("✅ Đã gửi báo cáo KPI GTC 07:00 lên Telegram thành công!")
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
    is_today = "--today" in args

    target_date = datetime.date.today() if is_today else (datetime.date.today() - datetime.timedelta(days=1))

    # Hỗ trợ truyền ngày tùy chọn --date YYYYMMDD
    for i, a in enumerate(args):
        if a == "--date" and i + 1 < len(args):
            try:
                target_date = datetime.datetime.strptime(args[i+1], "%Y%m%d").date()
            except:
                pass

    data = run_kpi_audit(target_date)
    msg = format_kpi_message(data)

    # Tự động lưu trữ lịch sử vĩnh viễn vào thư mục kpi_history/
    try:
        history_dir = os.path.join(BASE_DIR, "kpi_history")
        os.makedirs(history_dir, exist_ok=True)
        date_key = target_date.strftime("%Y%m%d")
        hist_file = os.path.join(history_dir, f"kpi_{date_key}.json")
        with open(hist_file, "w", encoding="utf-8") as f:
            json.dump(data.get("snapshot", data), f, ensure_ascii=False, indent=2)
        print(f"💾 Đã lưu trữ vĩnh viễn báo cáo ngày {target_date.strftime('%d/%m/%Y')} vào: {hist_file}")
    except Exception as e:
        print(f"⚠️ Không thể lưu file lịch sử: {e}")

    print("\n" + "=" * 55)
    print("NỘI DUNG BÁO CÁO KPI GTC 07:00:")
    print("=" * 55)
    print(msg)
    print("=" * 55 + "\n")

    if is_send:
        print("🚀 Đang tiến hành gửi lên nhóm Telegram Miền Tây 01 (Chủ đề Báo Cáo)...")
        send_telegram_alert(msg)
    else:
        print("💡 Chế độ Dry-Run (chưa gửi). Để gửi thực tế, dùng cờ: --send")

if __name__ == "__main__":
    main()

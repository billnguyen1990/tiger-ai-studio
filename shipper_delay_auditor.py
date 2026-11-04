import os
import json
import requests

DIR_NAME = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(DIR_NAME, "headers_found.json")
if not os.path.exists(HEADERS_FILE):
    HEADERS_FILE = os.path.join(os.path.dirname(DIR_NAME), "headers_found.json")

try:
    with open(HEADERS_FILE, "r", encoding="utf-8") as f:
        HEADERS = json.load(f)
except Exception:
    HEADERS = {}

def audit_shipper_delay_for_order(order_code):
    order_code = order_code.strip().upper()
    
    url_common = "https://nhanh-api.ghn.vn/api/lastmile/v2/order/search/common-info"
    common_info = {}
    try:
        r = requests.post(url_common, json={"order_code": order_code}, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            common_info = r.json().get("data", {}) or {}
    except Exception:
        pass

    url_hist = "https://nhanh-api.ghn.vn/api/lastmile/history/get-order-history"
    history_items = []
    try:
        r_h = requests.post(url_hist, json={"orderCode": order_code, "paging": {"offset": 0, "limit": 1000}}, headers=HEADERS, timeout=8)
        if r_h.status_code == 200:
            history_items = r_h.json().get("data", {}).get("data", []) or []
    except Exception:
        pass

    if not common_info and not history_items:
        return None

    # Parse status and shipper
    status = common_info.get("status", "N/A")
    items = common_info.get("items", []) or []
    prod_name = items[0].get("name", "Hàng hóa") if items else "Hàng hóa"
    receiver_info = common_info.get("receiverInfo", {}) or {}
    receiver_phone = receiver_info.get("phone", "—")
    if receiver_phone and len(receiver_phone) > 6:
        receiver_phone = receiver_phone[:3] + "****" + receiver_phone[-3:]

    calls = []
    last_shipper = "Không rõ"
    fail_reason = ""
    fail_time = ""

    for it in history_items:
        h_type = it.get("historyType", "")
        actor = it.get("createdByName") or it.get("actorName") or "Hệ Thống"
        c_time = it.get("createdTime") or it.get("actionTime") or ""
        
        data_raw = it.get("data") or ""
        parsed_data = {}
        if isinstance(data_raw, str) and data_raw.strip().startswith(("{", "[")):
            try:
                parsed_data = json.loads(data_raw)
            except Exception:
                pass
        elif isinstance(data_raw, dict):
            parsed_data = data_raw

        if h_type == "ADD_TO_TRIP":
            last_shipper = actor
        elif h_type == "CALL_LOG":
            if isinstance(parsed_data, dict):
                dur = parsed_data.get("duration", 0)
                ring = parsed_data.get("duration_ring", 0)
                is_fake = (dur == 0 and ring < 5)
                calls.append({
                    "time": c_time,
                    "actor": actor,
                    "duration": dur,
                    "ring": ring,
                    "is_fake": is_fake
                })
        elif h_type == "UPDATE_ITEM":
            if isinstance(parsed_data, dict):
                fn = parsed_data.get("failNote")
                if fn:
                    fail_reason = fn
                    fail_time = c_time

    # Determine violation
    total_calls = len(calls)
    real_calls = [c for c in calls if not c["is_fake"] and c["duration"] > 0]
    fake_calls = [c for c in calls if c["is_fake"]]

    is_violation = False
    verdict = ""
    evidence = ""

    if total_calls == 0:
        is_violation = True
        verdict = "🔴 VI PHẠM NGHIÊM TRỌNG: HOÃN ẢO 100%"
        evidence = "Tài xế KHÔNG thực hiện bất kỳ cuộc gọi nào cho khách hàng qua ứng dụng trước khi báo hoãn!"
    elif len(real_calls) == 0:
        is_violation = True
        verdict = "⚠️ VI PHẠM: NHÁ MÁY / GỌI ẢO"
        evidence = f"Tài xế chỉ nhá máy {total_calls} cuộc (thời lượng 0 giây, chuông < 5s), khách chưa kịp bắt máy!"
    else:
        verdict = "🟢 ĐÚNG QUY TRÌNH"
        evidence = f"Tài xế đã gọi cho khách {len(real_calls)} cuộc thực tế (cuộc gọi thành công, thời lượng hợp lệ)."

    report = (
        f"🔍 <b>BÁO CÁO TỪ BAN THANH TRA & KIỂM SOÁT NỘI BỘ</b>\n<i>(Hồ sơ điều tra độc lập được thẩm tra bởi Thanh Tra Trưởng Tiger AI)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Mã đơn:</b> <code>{order_code}</code>\n"
        f"🛍️ <b>Sản phẩm:</b> {prod_name[:40]}\n"
        f"👤 <b>Tài xế phụ trách:</b> <b>{last_shipper}</b>\n"
        f"📞 <b>Khách hàng:</b> <code>{receiver_phone}</code>\n"
        f"📊 <b>Trạng thái đơn:</b> <code>{status}</code>\n"
    )
    if fail_reason:
        report += f"📝 <b>Lý do báo hoãn:</b> {fail_reason} ({fail_time[:16] if fail_time else ''})\n"
        
    report += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>KẾT LUẬN:</b> <b>{verdict}</b>\n"
        f"🔍 <b>Bằng chứng đối soát:</b> {evidence}\n"
        f"📞 <b>Tổng số cuộc gọi qua App:</b> {total_calls} cuộc (Cuộc gọi thật: {len(real_calls)} | Nhá máy: {len(fake_calls)})\n"
    )
    if is_violation:
        report += f"\n👉 <b>Đề xuất NVXL:</b> Lập biên bản chế tài tài xế <b>{last_shipper}</b> về hành vi báo hoãn sai quy định, ảnh hưởng KPI giao hàng!"
    else:
        report += f"\n👉 <b>Đề xuất NVXL:</b> Xác nhận lý do hoãn là khách quan, phối hợp khách hàng hẹn lịch giao chuyến tiếp theo."
        
    return report

if __name__ == "__main__":
    for c in ["PSD26-CH-05070-03_CPTT", "VNGH80162470615"]:
        print(f"=== Testing {c} ===")
        print(audit_shipper_delay_for_order(c))

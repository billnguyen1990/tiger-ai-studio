import os
import requests
import json
from datetime import datetime

DIR_NAME = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(DIR_NAME, "headers_found.json")
if not os.path.exists(HEADERS_FILE):
    HEADERS_FILE = "headers_found.json"

try:
    with open(HEADERS_FILE, "r", encoding="utf-8") as f:
        HEADERS = json.load(f)
except Exception:
    HEADERS = {}

HUBS_MAP_FILE = os.path.join(DIR_NAME, "ghn_hubs_map.json")
HUBS_MAP = {}
if os.path.exists(HUBS_MAP_FILE):
    try:
        with open(HUBS_MAP_FILE, "r", encoding="utf-8") as f:
            HUBS_MAP = json.load(f)
    except Exception:
        pass

def get_order_deep_investigation(order_code):
    order_code = order_code.strip().upper()

    # 1. Common info
    url_common = "https://nhanh-api.ghn.vn/api/lastmile/v2/order/search/common-info"
    common_info = {}
    try:
        r = requests.post(url_common, json={"order_code": order_code}, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            common_info = r.json().get("data", {}) or {}
    except Exception as e:
        print("Common info error:", e)

    # 2. History detail (scans, calls, drivers, trips)
    url_hist = "https://nhanh-api.ghn.vn/api/lastmile/history/get-order-history"
    history_items = []
    try:
        r_h = requests.post(url_hist, json={"orderCode": order_code, "paging": {"offset": 0, "limit": 1000}}, headers=HEADERS, timeout=8)
        if r_h.status_code == 200:
            history_items = r_h.json().get("data", {}).get("data", []) or []
    except Exception as e:
        print("History error:", e)

    if not common_info and not history_items:
        return f"⚠️ <b>Tiger AI không tìm thấy dữ liệu đơn hàng <code>{order_code}</code> trên hệ thống GHN.</b>\n<i>Vui lòng kiểm tra lại mã vận đơn chính xác hoặc liên hệ NVXL!</i>"

    # Parse common info
    status = common_info.get("status", "N/A")
    weight = common_info.get("weight", 0) / 1000.0
    tags = ", ".join(common_info.get("tags", [])) or "Chuẩn"
    order_val = common_info.get("orderValue", 0)

    # Products & Warehouse
    items = common_info.get("items", []) or []
    prod_names = [it.get("name") for it in items if it.get("name")]
    prod_str = ", ".join(prod_names) if prod_names else "Hàng tiêu chuẩn"

    curr_id = str(common_info.get("currentId", ""))
    curr_hub = HUBS_MAP.get(curr_id, f"Kho {curr_id}" if curr_id else "N/A")

    length = common_info.get("length", 0)
    width = common_info.get("width", 0)
    height = common_info.get("height", 0)
    dim_str = f" ({length}x{width}x{height} cm)" if (length and width and height) else ""

    # Analyze chronological events
    trips = []
    calls = []
    pods = []
    updates = []
    sms_list = []
    shippers = {}

    for it in history_items:
        h_type = it.get("historyType", "")
        created_time = it.get("actionTime") or it.get("createdTime") or ""
        actor = it.get("actorName") or it.get("createdByName") or "Hệ Thống Auto"
        data_raw = it.get("data") or ""

        parsed_data = {}
        if isinstance(data_raw, str) and data_raw.strip().startswith(("{", "[")):
            try:
                parsed_data = json.loads(data_raw)
            except Exception:
                pass
        elif isinstance(data_raw, (dict, list)):
            parsed_data = data_raw

        if h_type == "ADD_TO_TRIP":
            trip_code = it.get("note") or ""
            if not trip_code and isinstance(parsed_data, dict):
                trip_code = parsed_data.get("tripCode", "")
            trips.append({
                "time": created_time,
                "actor": actor,
                "trip": trip_code
            })
            shippers[actor] = shippers.get(actor, 0) + 1
        elif h_type == "CALL_LOG":
            if isinstance(parsed_data, dict):
                dur = parsed_data.get("duration", 0)
                ring = parsed_data.get("duration_ring", 0)
                c_time = parsed_data.get("time") or created_time
                phone = parsed_data.get("phoneNumber", "")
                is_fake = (dur == 0 and ring < 5)
                calls.append({
                    "time": c_time,
                    "actor": actor,
                    "phone": phone,
                    "duration": dur,
                    "ring": ring,
                    "is_fake": is_fake
                })
        elif h_type == "UPLOAD_POD":
            pod_count = len(parsed_data) if isinstance(parsed_data, list) else 1
            pods.append({
                "time": created_time,
                "actor": actor,
                "count": pod_count
            })
        elif h_type == "UPDATE_ITEM":
            act = parsed_data.get("action", "") if isinstance(parsed_data, dict) else ""
            fail_reason = parsed_data.get("failNote", "") if isinstance(parsed_data, dict) else ""
            updates.append({
                "time": created_time,
                "actor": actor,
                "action": act,
                "note": fail_reason
            })
        elif h_type == "SMS":
            sms_list.append({"time": created_time, "actor": actor})

    # Build structured response
    msg = f"🔎 <b>TIGER AI - HỒ SƠ ĐIỀU TRA ĐƠN HÀNG {order_code}</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📦 <b>Trạng thái:</b> <code>{status}</code>\n"
    msg += f"🏢 <b>Vị trí hiện tại:</b> <b>{curr_hub}</b>\n"
    msg += f"🛍️ <b>Sản phẩm:</b> {prod_str}{dim_str}\n"
    msg += f"⚖️ <b>Khối lượng:</b> {weight:.1f} kg | 🏷️ <b>Phân loại:</b> {tags}\n"
    if order_val:
        msg += f"💵 <b>Giá trị đơn:</b> {order_val:,.0f} đ\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━\n"

    # Trip assignment & Drivers
    msg += f"🚚 <b>Điều phối & Chuyến đi ({len(trips)} lần gán):</b>\n"
    if trips:
        for tr in trips[-3:]: # 3 most recent
            t_dt = tr['time'].replace('T', ' ')[:16]
            msg += f"• <code>{t_dt}</code>: <b>{tr['actor']}</b> (Chuyến: <code>{tr['trip']}</code>)\n"
    else:
        msg += f"• <i>Chưa có thông tin gán chuyến trên hệ thống</i>\n"

    # Calls Analysis
    msg += f"\n📞 <b>Nhật ký cuộc gọi Shipper ({len(calls)} cuộc):</b>\n"
    if calls:
        for c in calls[:3]:
            c_dt = c['time'].replace('T', ' ')[:16]
            fake_badge = " ⚠️ <b>[CẢNH BÁO: Cuộc gọi ảo/Fake]</b>" if c['is_fake'] else ""
            msg += f"• <code>{c_dt}</code>: <b>{c['actor']}</b> gọi {c['phone']} ({c['duration']}s, chuông {c['ring']}s){fake_badge}\n"
    else:
        msg += f"• ⚠️ <i>Tài xế KHÔNG thực hiện cuộc gọi nào qua App!</i>\n"

    # Delivery & POD
    if pods:
        p_latest = pods[0]
        p_dt = p_latest['time'].replace('T', ' ')[:16]
        msg += f"\n📸 <b>Bằng chứng giao hàng (POD):</b> Đã chụp <b>{p_latest['count']} ảnh</b> lúc <code>{p_dt}</code> bởi <b>{p_latest['actor']}</b>\n"

    # Status updates / Fails
    if updates:
        latest_upd = updates[0]
        act_name = latest_upd['action']
        if "SUCCESS" in act_name:
            msg += f"\n✅ <b>Kết quả cuối:</b> Giao hàng thành công bởi <b>{latest_upd['actor']}</b>\n"
        elif "FAIL" in act_name or latest_upd['note']:
            msg += f"\n⚠️ <b>Ghi chú giao thất bại:</b> {latest_upd['note']} (Tài xế: {latest_upd['actor']})\n"

    # AI Diagnostics
    partner_status = str(common_info.get("partnerStatus", "")).lower()
    action = str(common_info.get("action", "")).upper()

    msg += f"\n🤖 <b>TIGER AI KẾT LUẬN & ĐỀ XUẤT:</b>\n"
    if status == "DELIVERED":
        msg += f"• <b>Đánh giá:</b> Đơn đã hoàn tất giao thành công. Có đầy đủ ảnh POD và xác nhận.\n"
    elif "return" in partner_status or action == "RETURN":
        msg += f"• <b>Trạng thái:</b> Đơn đang chờ CHUYỂN HOÀN (RETURN / STORING) do khách từ chối nhận hoặc đổi ý không mua.\n"
        msg += f"• <b>Đề xuất:</b> NVXL xác nhận thông tin hoàn với người gửi và tạo chuyến hoàn về kho gửi, tránh để tồn quá 48h tại kho {curr_hub}.\n"
    elif any(c['is_fake'] for c in calls):
        msg += f"• <b>Cảnh báo gian lận:</b> Hệ thống ghi nhận tài xế có cuộc gọi dưới ngưỡng chuẩn hoặc bị hệ thống quét là Call ảo. Cần trưởng kho kiểm tra lại tài xế!\n"
    elif len(calls) == 0 and len(trips) > 0:
        msg += f"• <b>Lỗi quy trình:</b> Shipper đã nhận chuyến nhưng không bấm gọi cho khách hàng qua ứng dụng trước khi hoãn.\n"
        msg += f"• <b>Đề xuất:</b> Yêu cầu NVXL liên hệ khách ngay lập tức để xác thực và tránh đơn bị khiếu nại.\n"
    else:
        msg += f"• <b>Đề xuất:</b> Đơn đang luân chuyển tại {curr_hub}. Đốc thúc chuyến kế tiếp để đạt KPI.\n"

    return msg

if __name__ == '__main__':
    rep = get_order_deep_investigation('VNGH80162470615')
    print(rep)

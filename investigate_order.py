import os
import re
import requests
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

DIR_NAME = os.path.dirname(os.path.abspath(__file__))

STATUS_VN_MAP = {
    "STORING": "Lưu kho giao (Sẵn sàng giao hàng)",
    "UNPACKED_AT_LASTMILE": "Lưu kho giao (Đã dỡ tải tại kho)",
    "DELIVERING": "Đang đi giao hàng",
    "DELIVERED": "Giao hàng thành công",
    "FAIL_TO_DELIVER": "Giao hàng thất bại",
    "DELIVERY_FAIL": "Giao hàng thất bại",
    "PICKING": "Đang đi lấy hàng",
    "PICKED": "Đã lấy hàng thành công",
    "READY_TO_PICK": "Chờ lấy hàng",
    "WAITING_TO_RETURN": "Chờ xác nhận giao lại / chuyển hoàn",
    "RETURNING": "Đang chuyển hoàn",
    "RETURN": "Đang chuyển hoàn",
    "RETURNED": "Đã hoàn trả hàng",
    "CANCELLED": "Đơn đã hủy",
    "CANCEL": "Đơn đã hủy"
}

PARTNER_STATUS_VN_MAP = {
    "storing": "Sẵn sàng giao hàng",
    "delivering": "Đang giao hàng",
    "delivered": "Giao hàng thành công",
    "delivery_fail": "Giao hàng không thành công",
    "picking": "Đang lấy hàng",
    "picked": "Lấy hàng thành công",
    "waiting_to_return": "Chờ xác nhận giao lại/chuyển hoàn",
    "return": "Đang chuyển hoàn",
    "returned": "Đã trả hàng",
    "cancel": "Đơn đã hủy",
    "ready_to_pick": "Chờ lấy hàng"
}

def _load_headers():
    candidates = [
        os.path.join(DIR_NAME, "headers_found.json"),
        os.path.join(os.path.dirname(DIR_NAME), "headers_found.json"),
        "headers_found.json"
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                with open(c, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

def _load_hubs_map():
    candidates = [
        os.path.join(DIR_NAME, "ghn_hubs_map.json"),
        os.path.join(os.path.dirname(DIR_NAME), "ghn_hubs_map.json"),
        "ghn_hubs_map.json"
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                with open(c, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

def _resolve_hub_display(hub_id, hubs_map):
    if not hub_id or str(hub_id) == "0":
        return "—"
    sid = str(hub_id).strip()
    hname = hubs_map.get(sid, f"Kho {sid}")
    return f"{sid} - {hname}"

def _extract_unmasked_address_from_a5(order_code, headers):
    """Lấy địa chỉ chi tiết không bị che (***) từ phiếu in A5 của GHN"""
    try:
        r_a5 = requests.post(
            "https://nhanh-api.ghn.vn/api/lastmile/order/gen-a5-token",
            json={"order_codes": order_code},
            headers=headers,
            timeout=5
        )
        if r_a5.status_code == 200:
            tok = (r_a5.json().get("data") or {}).get("token", "")
            if tok:
                r_html = requests.get(
                    f"https://online-gateway.ghn.vn/a5/public-api/printA5?token={tok}",
                    timeout=5
                )
                if r_html.status_code == 200:
                    html_txt = r_html.text
                    idx = html_txt.find("Bên nhận")
                    if idx != -1:
                        chunk = html_txt[idx:idx + 1200]
                        bolds = re.findall(r'<div[^>]*class="module line-clamp-1"[^>]*>\s*<b>(.*?)</b>', chunk, flags=re.S)
                        if len(bolds) >= 2:
                            addr = re.sub(r'\s+', ' ', bolds[1]).strip()
                            if addr and "***" not in addr:
                                return addr
    except Exception:
        pass
    return ""

def get_order_deep_investigation(order_code):
    order_code = order_code.strip().upper()
    headers = _load_headers()
    hubs_map = _load_hubs_map()

    # 1. Common info
    url_common = "https://nhanh-api.ghn.vn/api/lastmile/v2/order/search/common-info"
    common_info = {}
    try:
        r = requests.post(url_common, json={"order_code": order_code}, headers=headers, timeout=8)
        if r.status_code == 200:
            common_info = r.json().get("data", {}) or {}
    except Exception as e:
        print("Common info error:", e)

    # 2. History detail (scans, calls, drivers, trips)
    url_hist = "https://nhanh-api.ghn.vn/api/lastmile/history/get-order-history"
    history_items = []
    try:
        r_h = requests.post(url_hist, json={"orderCode": order_code, "paging": {"offset": 0, "limit": 1000}}, headers=headers, timeout=8)
        if r_h.status_code == 200:
            history_items = r_h.json().get("data", {}).get("data", []) or []
    except Exception as e:
        print("History error:", e)

    if not common_info and not history_items:
        return f"⚠️ <b>Tiger AI không tìm thấy dữ liệu đơn hàng <code>{order_code}</code> trên hệ thống GHN.</b>\n<i>Vui lòng kiểm tra lại mã vận đơn chính xác hoặc liên hệ NVXL!</i>"

    curr_id = str(common_info.get("currentId") or (history_items[0].get("hubId") if history_items else "") or "")
    deliver_id = str(common_info.get("deliverId") or "")
    pick_id = str(common_info.get("pickId") or "")

    # Tạo header gắn đúng mã kho hiện tại/kho giao để lấy SĐT, Tên KH, COD và Địa chỉ không bị ẩn
    hub_headers = headers.copy()
    if deliver_id and deliver_id != "0":
        hub_headers["x-warehouseid"] = deliver_id
    elif curr_id and curr_id != "0":
        hub_headers["x-warehouseid"] = curr_id

    # 3. Truy vấn song song: Tên & SĐT khách hàng, COD, OMS Delivery Info, và Địa chỉ đầy đủ từ A5
    recv_info = {}
    cod_info = {}
    oms_info = {}
    unmasked_a5_addr = ""

    def _fetch_receiver():
        try:
            rr = requests.post(
                "https://nhanh-api.ghn.vn/api/lastmile/order/search/receiver-info",
                json={"order_code": order_code},
                headers=hub_headers,
                timeout=5
            )
            if rr.status_code == 200:
                return rr.json().get("data") or {}
        except Exception:
            pass
        return {}

    def _fetch_cod():
        try:
            rc = requests.post(
                "https://nhanh-api.ghn.vn/api/lastmile/order/get-collected-amount",
                json={"order_code": order_code, "orderCode": order_code},
                headers=hub_headers,
                timeout=5
            )
            if rc.status_code == 200:
                return rc.json().get("data") or {}
        except Exception:
            pass
        return {}

    def _fetch_oms():
        try:
            ro = requests.post(
                "https://nhanh-api.ghn.vn/api/core/oms/get-multi",
                json={"orderCodes": [order_code], "data": ["core", "location", "operation", "delivery", "return"]},
                headers=hub_headers,
                timeout=5
            )
            if ro.status_code == 200:
                d_list = ro.json().get("data") or []
                if d_list and isinstance(d_list, list):
                    return d_list[0]
        except Exception:
            pass
        return {}

    with ThreadPoolExecutor(max_workers=4) as ex:
        f_recv = ex.submit(_fetch_receiver)
        f_cod = ex.submit(_fetch_cod)
        f_oms = ex.submit(_fetch_oms)
        f_a5 = ex.submit(_extract_unmasked_address_from_a5, order_code, hub_headers)
        recv_info = f_recv.result()
        cod_info = f_cod.result()
        oms_info = f_oms.result()
        unmasked_a5_addr = f_a5.result()

    # Parse Status, Hubs, Customer, Address, COD
    raw_status = str(common_info.get("status") or "N/A").upper()
    raw_partner_status = str(common_info.get("partnerStatus") or "").lower()
    status_vn = STATUS_VN_MAP.get(raw_status, PARTNER_STATUS_VN_MAP.get(raw_partner_status, raw_status))

    curr_hub = _resolve_hub_display(curr_id, hubs_map)
    deliver_hub = _resolve_hub_display(deliver_id, hubs_map)
    pick_hub = _resolve_hub_display(pick_id, hubs_map)

    customer_name = (
        recv_info.get("receiver_name")
        or (common_info.get("receiverInfo") or {}).get("receiverName")
        or (oms_info.get("delivery") or {}).get("name")
        or "—"
    )
    customer_phone = (
        recv_info.get("receiver_phone")
        or (common_info.get("receiverInfo") or {}).get("receiverPhone")
        or (oms_info.get("delivery") or {}).get("phone")
        or "—"
    )

    oms_deliv = oms_info.get("delivery") or {}
    ward_dist_city = ", ".join(filter(None, [
        oms_deliv.get("wardName"),
        oms_deliv.get("districtName"),
        oms_deliv.get("cityName")
    ]))
    if unmasked_a5_addr:
        customer_address = unmasked_a5_addr
        if oms_deliv.get("districtName") and oms_deliv.get("districtName") not in customer_address:
            customer_address += f" ({oms_deliv.get('wardName', '')}, {oms_deliv.get('districtName', '')})"
    elif ward_dist_city:
        raw_addr = oms_deliv.get("address") or ""
        if raw_addr and not raw_addr.startswith("***"):
            customer_address = f"{raw_addr}, {ward_dist_city}"
        else:
            customer_address = ward_dist_city
    else:
        customer_address = "—"

    cod_amount = cod_info.get("codAmount") or 0
    total_collect = cod_info.get("totalAmount") or cod_amount or 0
    order_val = common_info.get("orderValue") or 0
    cod_str = f"{int(total_collect):,} đ".replace(",", ".") if total_collect else "0 đ (Không thu hộ)"

    weight = (common_info.get("weight") or 0) / 1000.0

    # Phân loại nhóm đơn B2B vs Đơn lẻ C2C/B2C (Căn cứ cốt lõi: Kho lấy B2B)
    raw_tags = common_info.get("tags") or []
    oms_op = oms_info.get("operation") or {}
    if not raw_tags and oms_op.get("tags"):
        raw_tags = oms_op.get("tags")
    sv_id = common_info.get("serviceTypeID") or oms_op.get("serviceTypeID")
    oms_core = oms_info.get("core") or {}
    ext_code = oms_core.get("externalCode") or ""
    doc_ret = oms_op.get("documentReturn") or common_info.get("documentReturn") or {}
    has_doc_return = bool(doc_ret.get("flag"))
    doc_note = doc_ret.get("note") or ""

    # Kho lấy B2B là tiêu chí quyết định 100% đơn B2B
    B2B_HUB_IDS = {"21098000", "22328000", "22873000", "22958000", "23064000", "23065000", "23085000", "23121000"}
    is_pick_b2b = (pick_id in B2B_HUB_IDS) or ("b2b" in pick_hub.lower())

    if is_pick_b2b:
        is_b2b = True
        order_group_str = "100% Đơn B2B (Giao Hàng Nặng - Xuất phát từ Kho B2B / Điều phối Rillnet)"
    elif has_doc_return or ("PXK" in ext_code.upper() or "PO" in ext_code.upper()):
        is_b2b = True
        order_group_str = "Đơn B2B Doanh Nghiệp (Có chứng từ PXK/PO đối tác)"
    else:
        is_b2b = False
        order_group_str = "Đơn lẻ C2C/B2C thường (❌ Không thuộc nhóm B2B / Ngoài phạm vi Rillnet)"

    tag_map = {
        "bulky": "📦 Hàng cồng kềnh (bulky)",
        "multiple": "🔢 Nhiều kiện (multiple)",
        "truck": "🚛 Giao xe tải (truck)"
    }
    tag_labels = [tag_map.get(t, t) for t in raw_tags]
    tags_display = " • ".join(tag_labels) if tag_labels else "Hàng tiêu chuẩn"

    # Products & Dimensions
    items = common_info.get("items", []) or []
    prod_names = [it.get("name") for it in items if it.get("name")]
    prod_str = ", ".join(prod_names) if prod_names else "Hàng tiêu chuẩn"
    items_cnt = len(items) if items else 1

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

    for it in history_items:
        h_type = it.get("historyType", "")
        created_time = it.get("actionTime") or it.get("createdTime") or ""
        actor = it.get("actorName") or it.get("createdByName") or "Hệ Thống Auto"
        data_raw = it.get("data") or ""
        ev_trip = it.get("tripCode") or ""

        parsed_data = {}
        if isinstance(data_raw, str) and data_raw.strip().startswith(("{", "[")):
            try:
                parsed_data = json.loads(data_raw)
            except Exception:
                pass
        elif isinstance(data_raw, (dict, list)):
            parsed_data = data_raw

        if h_type == "ADD_TO_TRIP":
            trip_code = ev_trip or it.get("note") or ""
            if not trip_code and isinstance(parsed_data, dict):
                trip_code = parsed_data.get("tripCode", "")
            trips.append({
                "time": created_time,
                "actor": actor,
                "trip": trip_code
            })
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

    # Build structured response with all requested fields
    msg = f"🔎 <b>TIGER AI - HỒ SƠ CHI TIẾT ĐƠN HÀNG <code>{order_code}</code></b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🏢 <b>Nhóm đơn hàng:</b> <b>{order_group_str}</b>\n"
    msg += f"🏷️ <b>Phân loại vận hành:</b> <b>{tags_display}</b>\n"
    if has_doc_return or ext_code:
        doc_label = f"Mã: <code>{ext_code}</code>" if ext_code else (f"Ghi chú: {doc_note}" if doc_note else "Có biên bản/PXK")
        msg += f"📑 <b>Chứng từ B2B:</b> Có thu hồi chứng từ/PXK ({doc_label})\n"
    elif not is_b2b:
        msg += f"ℹ️ <b>Nhận diện Rillnet:</b> Đơn gửi từ bưu cục lẻ thường, không nằm trong danh mục B2B của Rillnet.\n"
    msg += f"📊 <b>Trạng thái đơn hàng:</b> <b>{status_vn}</b> (<code>{raw_status}</code>)\n"
    msg += f"🏢 <b>Kho hiện tại:</b> <b>{curr_hub}</b>\n"
    msg += f"🎯 <b>Kho giao:</b> <b>{deliver_hub}</b>\n"
    if pick_hub and pick_hub != "—":
        pick_b2b_tag = " (✅ Tổng kho B2B)" if is_pick_b2b else " (Bưu cục nhận lẻ)"
        msg += f"🏭 <b>Kho lấy:</b> {pick_hub}{pick_b2b_tag}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"👤 <b>Tên khách hàng:</b> <b>{customer_name}</b>\n"
    msg += f"📞 <b>SĐT khách nhận:</b> <code>{customer_phone}</code>\n"
    msg += f"📍 <b>Địa chỉ giao:</b> {customer_address}\n"
    msg += f"💵 <b>Tiền thu hộ COD:</b> <b>{cod_str}</b>\n"
    if order_val:
        msg += f"💎 <b>Giá trị khai giá:</b> {int(order_val):,} đ\n".replace(",", ".")
    msg += f"🛍️ <b>Sản phẩm ({items_cnt} kiện):</b> {prod_str}{dim_str}\n"
    msg += f"⚖️ <b>Khối lượng:</b> {weight:.1f} kg\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━\n"

    # Trip assignment & Drivers
    msg += f"🚚 <b>Điều phối & Chuyến đi ({len(trips)} lần gán):</b>\n"
    if trips:
        for tr in trips[-3:]:
            t_dt = tr['time'].replace('T', ' ')[:16]
            t_code_disp = f" (Chuyến: <code>{tr['trip']}</code>)" if tr['trip'] else ""
            msg += f"• <code>{t_dt}</code>: <b>{tr['actor']}</b>{t_code_disp}\n"
    else:
        msg += f"• <i>Chưa có thông tin gán chuyến trên hệ thống</i>\n"

    # Calls Analysis
    msg += f"\n📞 <b>Nhật ký cuộc gọi NV ({len(calls)} cuộc):</b>\n"
    if calls:
        for c in calls[:3]:
            c_dt = c['time'].replace('T', ' ')[:16]
            fake_badge = " ⚠️ <b>[CẢNH BÁO: Cuộc gọi ảo/Fake]</b>" if c['is_fake'] else ""
            msg += f"• <code>{c_dt}</code>: <b>{c['actor']}</b> gọi {c['phone']} ({c['duration']}s, chuông {c['ring']}s){fake_badge}\n"
    else:
        msg += f"• ℹ️ <i>Chưa ghi nhận cuộc gọi qua App</i>\n"

    # Delivery & POD
    if pods:
        p_latest = pods[0]
        p_dt = p_latest['time'].replace('T', ' ')[:16]
        msg += f"\n📸 <b>Bằng chứng giao hàng (POD):</b> Đã chụp <b>{p_latest['count']} ảnh</b> lúc <code>{p_dt}</code> bởi <b>{p_latest['actor']}</b>\n"

    # Status updates / Fails
    has_deliver_fail = any("DELIVER_FAIL" in u["action"] or (u["note"] and "PICK" not in u["action"]) for u in updates)
    if updates:
        latest_upd = updates[0]
        act_name = latest_upd['action']
        if act_name == "PICK_SUCCESS":
            msg += f"\n📦 <b>Thao tác lấy hàng:</b> Đã lấy hàng thành công bởi NV <b>{latest_upd['actor']}</b>\n"
        elif "SUCCESS" in act_name:
            msg += f"\n✅ <b>Kết quả giao:</b> Giao hàng thành công bởi NV <b>{latest_upd['actor']}</b>\n"
        elif "FAIL" in act_name or latest_upd['note']:
            msg += f"\n⚠️ <b>Ghi chú giao thất bại:</b> {latest_upd['note']} (NV: {latest_upd['actor']})\n"

    # AI Diagnostics
    action = str(common_info.get("action", "")).upper()

    msg += f"\n🤖 <b>TIGER AI KẾT LUẬN & ĐỀ XUẤT:</b>\n"
    if raw_status == "DELIVERED":
        msg += f"• <b>Đánh giá:</b> Đơn đã hoàn tất giao thành công. Có đầy đủ ảnh POD và xác nhận.\n"
    elif "return" in raw_partner_status or action == "RETURN":
        msg += f"• <b>Trạng thái:</b> Đơn đang chờ CHUYỂN HOÀN (RETURN / STORING) do khách từ chối nhận hoặc đổi ý không mua.\n"
        msg += f"• <b>Đề xuất:</b> NVXL xác nhận thông tin hoàn với người gửi và tạo chuyến hoàn về kho gửi, tránh để tồn quá 48h tại {curr_hub}.\n"
    elif any(c['is_fake'] for c in calls):
        msg += f"• <b>Cảnh báo gian lận:</b> Hệ thống ghi nhận NV có cuộc gọi dưới ngưỡng chuẩn hoặc bị hệ thống quét là Call ảo. Cần trưởng kho kiểm tra lại!\n"
    elif len(calls) == 0 and has_deliver_fail:
        msg += f"• <b>Lỗi quy trình:</b> NV đã nhận chuyến nhưng không bấm gọi cho khách hàng qua ứng dụng trước khi cập nhật giao thất bại.\n"
        msg += f"• <b>Đề xuất:</b> Yêu cầu NVXL liên hệ khách ngay lập tức để xác thực và tránh đơn bị khiếu nại.\n"
    elif raw_status in ("STORING", "UNPACKED_AT_LASTMILE") and not has_deliver_fail:
        msg += f"• <b>Trạng thái kho:</b> Đơn hàng đang lưu kho tại <b>{curr_hub}</b> (Chờ phân tuyến gán chuyến giao).\n"
        msg += f"• <b>Đề xuất:</b> NVXL ưu tiên gán chuyến xuất bến sớm để đẩy nhanh tiến độ GTC.\n"
    else:
        msg += f"• <b>Đề xuất:</b> Đơn đang luân chuyển tại {curr_hub}. Đốc thúc chuyến kế tiếp để đạt KPI.\n"
    msg += f"• 🔗 <a href='https://tracuunoibo.ghn.vn/internal?order_code={order_code}'>Mở Tracuunoibo GHN ↗</a> | <a href='https://rillnet.ghn.vn/'>Mở Rillnet B2B ↗</a>\n"

    return msg

if __name__ == '__main__':
    rep = get_order_deep_investigation('GYECQKKL')
    print(rep)

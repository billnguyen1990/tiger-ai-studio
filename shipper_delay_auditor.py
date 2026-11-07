import os
import json
import datetime
import requests
from concurrent.futures import ThreadPoolExecutor

DIR_NAME = os.path.dirname(os.path.abspath(__file__))

def _load_json_file(filename):
    candidates = [
        os.path.join(DIR_NAME, filename),
        os.path.join(os.path.dirname(DIR_NAME), filename),
        os.path.join(DIR_NAME, "tiger_studio", filename),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

def _to_vn_dt(iso_str):
    if not iso_str:
        return None
    try:
        s = str(iso_str).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
    except Exception:
        return None

def _to_vn_time_str(iso_str):
    dt = _to_vn_dt(iso_str)
    if dt:
        return dt.strftime("%H:%M:%S")
    return str(iso_str)[11:19] if len(str(iso_str)) >= 19 else str(iso_str)

def _mask_phone(phone):
    if not phone or "*" in str(phone):
        return "—"
    p = str(phone).strip()
    if len(p) >= 7:
        return p[:4] + "***" + p[-3:]
    return p

def _esc_html(val):
    if not val:
        return ""
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def audit_shipper_delay_for_order(order_code):
    order_code = order_code.strip().upper()
    headers = _load_json_file("headers_found.json")

    url_common = "https://nhanh-api.ghn.vn/api/lastmile/v2/order/search/common-info"
    common_info = {}
    try:
        r = requests.post(url_common, json={"order_code": order_code}, headers=headers, timeout=8)
        if r.status_code == 200:
            common_info = r.json().get("data", {}) or {}
    except Exception:
        pass

    url_hist = "https://nhanh-api.ghn.vn/api/lastmile/history/get-order-history"
    history_items = []
    try:
        r_h = requests.post(url_hist, json={"orderCode": order_code, "paging": {"offset": 0, "limit": 1000}}, headers=headers, timeout=8)
        if r_h.status_code == 200:
            history_items = r_h.json().get("data", {}).get("data", []) or []
    except Exception:
        pass

    if not common_info and not history_items:
        return None

    status = common_info.get("status", "N/A")
    items = common_info.get("items", []) or []
    prod_name = _esc_html(items[0].get("name", "Hàng hóa")) if items else "Hàng hóa"
    receiver_info = common_info.get("receiverInfo", {}) or {}
    receiver_phone = _mask_phone(receiver_info.get("phone", "—"))

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
                    "time": _to_vn_time_str(c_time),
                    "actor": actor,
                    "duration": dur,
                    "ring": ring,
                    "is_fake": is_fake
                })
        elif h_type == "UPDATE_ITEM":
            if isinstance(parsed_data, dict):
                fn = parsed_data.get("failNote")
                if fn:
                    fail_reason = _esc_html(fn)
                    fail_time = _to_vn_time_str(c_time)

    total_calls = len(calls)
    real_calls = [c for c in calls if not c["is_fake"] and c["duration"] > 0]
    fake_calls = [c for c in calls if c["is_fake"]]

    is_violation = False
    if total_calls == 0:
        is_violation = True
        verdict = "🔴 VI PHẠM NGHIÊM TRỌNG: HOÃN ẢO 100%"
        evidence = "Tài xế KHÔNG thực hiện bất kỳ cuộc gọi nào cho khách hàng qua ứng dụng trước khi báo hoãn!"
    elif len(real_calls) == 0:
        is_violation = True
        verdict = "⚠️ VI PHẠM: NHÁ MÁY / CHƯA NGHE MÁY"
        evidence = f"Tài xế gọi {total_calls} cuộc nhưng thời lượng đàm thoại 0 giây (khách chưa bắt máy hoặc nhá máy)!"
    else:
        verdict = "🟢 CÓ CUỘC GỌI ĐÀM THOẠI"
        evidence = f"Tài xế đã gọi cho khách {len(real_calls)} cuộc thực tế (tối đa {max(c['duration'] for c in real_calls)}s)."

    report = (
        f"🕵️ <b>TIGER AI • HỒ SƠ ĐỐI SOÁT SHIPPER HOÃN ĐƠN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Mã đơn:</b> <code>{order_code}</code>\n"
        f"🛍️ <b>Sản phẩm:</b> {prod_name[:40]}\n"
        f"👤 <b>Tài xế phụ trách:</b> <b>{_esc_html(last_shipper)}</b>\n"
        f"📞 <b>Khách hàng:</b> <code>{receiver_phone}</code>\n"
        f"📊 <b>Trạng thái đơn:</b> <code>{_esc_html(status)}</code>\n"
    )
    if fail_reason:
        report += f"📝 <b>Lý do báo hoãn:</b> {fail_reason} (Lúc {fail_time})\n"

    report += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>KẾT LUẬN:</b> <b>{verdict}</b>\n"
        f"🔍 <b>Bằng chứng đối soát:</b> {evidence}\n"
        f"📞 <b>Tổng số cuộc gọi qua App:</b> {total_calls} cuộc (Đàm thoại: {len(real_calls)} | 0s/Nhá máy: {len(fake_calls)})\n"
    )
    if is_violation:
        report += f"\n👉 <b>Đề xuất NVXL:</b> Kiểm tra &amp; nhắc nhở tài xế <b>{_esc_html(last_shipper)}</b> về quy trình gọi khách trước khi cập nhật hoãn đơn!"
    else:
        report += f"\n👉 <b>Đề xuất NVXL:</b> Xác nhận có cuộc gọi thực tế, đôn đốc giao dứt điểm trong ca hôm nay."

    return report


def resolve_hub_from_text(text):
    t = (text or "").lower()
    if any(k in t for k in ["ô môn", "o mon", "omon", "22917000"]):
        return "22917000"
    if any(k in t for k in ["cái răng", "cai rang", "cairang", "21088000"]):
        return "21088000"
    if any(k in t for k in ["bình thủy", "binh thuy", "binhthuy", "21985000"]):
        return "21985000"
    if any(k in t for k in ["vị thanh", "vi thanh", "vithanh", "22862000"]):
        return "22862000"
    return None


def resolve_reason_keyword(text):
    t = (text or "").lower()
    if "hẹn lại" in t or "hen lai" in t:
        return "hẹn lại", "Người nhận hẹn lại ngày giao"
    if "không nghe máy" in t or "khong nghe may" in t or "ko nghe máy" in t:
        return "không nghe máy", "Người nhận không nghe máy"
    if "chặn số" in t or "không liên lạc" in t or "khong lien lac" in t or "thuê bao" in t:
        return "không liên lạc", "Không liên lạc được người nhận / Chặn số"
    if "không đặt" in t or "khong dat" in t or "từ chối" in t:
        return "không đặt", "Người nhận báo không đặt hàng"
    if "sai địa chỉ" in t or "đổi địa chỉ" in t:
        return "địa chỉ", "Sai / Đổi địa chỉ giao hàng"
    return "", "Tất cả lý do giao thất bại (GTB)"


def audit_hub_failed_orders_detail(hub_id_or_text, reason_text="", target_date=None):
    """
    Quét toàn bộ các đơn Giao Thất Bại (GTB) của 1 Kho theo Lý do cụ thể (VD: 16 đơn 'Người nhận hẹn lại ngày giao' của Kho Ô Môn),
    đối soát log cuộc gọi (CALL_LOG) và thời điểm bấm báo hoãn (UPDATE_ITEM) của từng đơn 100% thời gian thực.
    """
    headers = _load_json_file("headers_found.json")
    nvxl_map = _load_json_file("nvxl_telegram_map.json")
    if not headers or not nvxl_map:
        return "❌ Không tìm thấy cấu hình kết nối GHN (headers_found.json)."

    hub_id = hub_id_or_text if str(hub_id_or_text) in nvxl_map else resolve_hub_from_text(str(hub_id_or_text) + " " + str(reason_text))
    if not hub_id:
        hub_id = "22917000"

    hub_info = nvxl_map.get(hub_id, {})
    hub_name = hub_info.get("short_name", "Ô Môn")
    nvxl_name = hub_info.get("nvxl_name", "NVXL")
    nvxl_tag = hub_info.get("telegram_tag", "")

    reason_kw, reason_label = resolve_reason_keyword(str(reason_text) + " " + str(hub_id_or_text))

    vn_now = datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=7)))
    if target_date is None:
        combined_txt = (str(hub_id_or_text) + " " + str(reason_text)).lower()
        if "hôm nay" in combined_txt or "sáng nay" in combined_txt:
            t_date = vn_now.date()
        else:
            t_date = vn_now.date() - datetime.timedelta(days=1)
    elif isinstance(target_date, datetime.date):
        t_date = target_date
    else:
        t_date = vn_now.date() - datetime.timedelta(days=1)

    date_int = int(t_date.strftime("%Y%m%d"))
    date_str_iso = t_date.strftime("%Y-%m-%d")
    date_display = t_date.strftime("%d/%m/%Y")

    req_headers = dict(headers)
    req_headers["x-warehouseid"] = hub_id

    url_trips = "https://nhanh-api.ghn.vn/api/lastmile/trip/get-trip-list-by-hub"
    url_items = "https://nhanh-api.ghn.vn/api/lastmile/v2/trip/get-trip-items"
    url_hist = "https://nhanh-api.ghn.vn/api/lastmile/history/get-order-history"

    hub_trips = []
    for st in ["FINISHED", "ON_TRIP", "NEW"]:
        try:
            res = requests.post(
                url_trips,
                headers=req_headers,
                json={"hub_id": hub_id, "status": st, "is_ready": 0, "offset": 0, "limit": 100},
                timeout=10
            ).json()
            for t in (res.get("data") or []):
                if t.get("createDateIndex") == date_int or t.get("startDateIndex") == date_int:
                    hub_trips.append(t)
        except Exception:
            pass

    failed_orders = []
    for t in hub_trips:
        tc = t.get("tripCode")
        driver = t.get("driverName") or "Chưa rõ TX"
        try:
            r_items = requests.post(
                url_items,
                headers=req_headers,
                json={"typeList": ["DELIVER"], "offset": 0, "limit": 200, "TripCode": tc},
                timeout=10
            ).json()
            for it in (r_items.get("data") or []):
                if it.get("isUpdated") and not it.get("isSucceeded"):
                    fn = it.get("failNote") or it.get("failReasonName") or "Lý do khác"
                    if not reason_kw or (reason_kw in fn.lower()):
                        sc = it.get("senderContact") or {}
                        di = it.get("deliverInfo") or {}
                        items_list = it.get("items") or []
                        pkg_cnt = len(items_list) or 1
                        total_w_kg = round(sum(float(x.get("weight", 0) or 0) for x in items_list) / 1000.0, 1)
                        ward = (di.get("wardName") or "").replace("Phường ", "P.").replace("Xã ", "X.").replace("Thị trấn ", "TT.")
                        dist = (di.get("districtName") or "").replace("Quận ", "Q.").replace("Huyện ", "H.")
                        area_str = f"{ward}, {dist}".strip(", ")
                        shop_name = (sc.get("contactName") or "Shop")[:18]

                        failed_orders.append({
                            "orderCode": it.get("orderCode") or it.get("itemCode"),
                            "driver": driver,
                            "tripCode": tc,
                            "reason": fn,
                            "shop_name": _esc_html(shop_name),
                            "area_str": _esc_html(area_str),
                            "pkg_cnt": pkg_cnt,
                            "weight_kg": total_w_kg
                        })
        except Exception:
            pass

    if not failed_orders:
        return (
            f"📊 <b>KẾT QUẢ KIỂM TRA ĐƠN THẤT BẠI • KHO {hub_name.upper()} ({date_display})</b>\n"
            f"• Không ghi nhận đơn giao thất bại nào khớp với điều kiện <b>{_esc_html(reason_label)}</b> trong ngày {date_display}."
        )

    def _inspect_single_order(item):
        oc = item["orderCode"]
        calls_today = []
        fail_dt_vn = None
        fail_time_str = "—"
        try:
            r_h = requests.post(
                url_hist,
                json={"orderCode": oc, "paging": {"offset": 0, "limit": 200}},
                headers=req_headers,
                timeout=8
            ).json()
            hist = (r_h.get("data") or {}).get("data") or []
            for h in hist:
                ht = h.get("historyType", "")
                ctime = h.get("createdTime") or h.get("actionTime") or ""
                dt_vn = _to_vn_dt(ctime)
                if not dt_vn or dt_vn.strftime("%Y-%m-%d") != date_str_iso:
                    continue
                raw = h.get("data") or {}
                if isinstance(raw, str) and raw.strip().startswith("{"):
                    try:
                        raw = json.loads(raw)
                    except Exception:
                        raw = {}
                if ht == "CALL_LOG" and isinstance(raw, dict):
                    dur = int(raw.get("duration", 0) or 0)
                    ring = int(raw.get("duration_ring", 0) or 0)
                    calls_today.append({
                        "dur": dur,
                        "ring": ring,
                        "time_str": dt_vn.strftime("%H:%M"),
                        "dt": dt_vn
                    })
                elif ht == "UPDATE_ITEM" and isinstance(raw, dict) and raw.get("failNote"):
                    if fail_dt_vn is None or dt_vn > fail_dt_vn:
                        fail_dt_vn = dt_vn
                        fail_time_str = dt_vn.strftime("%H:%M")
        except Exception:
            pass

        total_c = len(calls_today)
        talk_calls = [c for c in calls_today if c["dur"] > 0]
        max_dur = max((c["dur"] for c in talk_calls), default=0)
        last_call_dt = max((c["dt"] for c in calls_today), default=None)
        last_call_str = last_call_dt.strftime("%H:%M") if last_call_dt else "—"

        gap_min = 0
        if last_call_dt and fail_dt_vn and fail_dt_vn > last_call_dt:
            gap_min = int((fail_dt_vn - last_call_dt).total_seconds() // 60)

        severity = "OK"
        if total_c == 0:
            severity = "FAKE_100"
            flag_text = "🔴 KHÔNG GỌI KHÁCH (Hoãn ảo 100%)"
        elif len(talk_calls) == 0:
            severity = "NO_ANSWER"
            flag_text = f"🔴 Khách ko bắt máy ({total_c} cuộc 0s)"
        elif max_dur <= 10 and gap_min >= 60:
            severity = "SUSPICIOUS"
            flag_text = f"⚠️ Nghe ngắn ({max_dur}s), trễ {gap_min // 60}h{gap_min % 60:02d}p mới bấm hoãn"
        elif max_dur <= 10:
            severity = "SUSPICIOUS"
            flag_text = f"⚠️ Đàm thoại cực ngắn ({max_dur}s)"
        elif gap_min >= 90:
            severity = "BATCH_DELAY"
            flag_text = f"⏳ Gọi {last_call_str}, trễ {gap_min // 60}h{gap_min % 60:02d}p ({fail_time_str}) mới bấm hoãn"
        else:
            flag_text = f"✅ Hợp lệ (đàm thoại {max_dur}s)"

        item["total_calls"] = total_c
        item["talk_calls"] = len(talk_calls)
        item["max_dur"] = max_dur
        item["last_call_str"] = last_call_str
        item["fail_time_str"] = fail_time_str
        item["gap_min"] = gap_min
        item["severity"] = severity
        item["flag_text"] = flag_text
        return item

    with ThreadPoolExecutor(max_workers=10) as ex:
        audited_list = list(ex.map(_inspect_single_order, failed_orders))

    by_driver = {}
    for a in audited_list:
        by_driver.setdefault(a["driver"], []).append(a)

    fake_or_no_ans = sum(1 for a in audited_list if a["severity"] in ("FAKE_100", "NO_ANSWER"))
    short_or_batch = sum(1 for a in audited_list if a["severity"] in ("SUSPICIOUS", "BATCH_DELAY"))
    valid_count = len(audited_list) - fake_or_no_ans - short_or_batch

    lines = []
    lines.append(f"🕵️ <b>TIGER AI • KIỂM TRA CHI TIẾT TỪNG ĐƠN GTB</b>")
    lines.append(f"📍 <b>Kho:</b> <b>Kho {hub_name}</b> | 📅 <b>Ca ngày:</b> {date_display}")
    lines.append(f"🎯 <b>Lý do:</b> <b>{_esc_html(reason_label)} ({len(audited_list)} đơn)</b>")
    lines.append("━" * 26)

    idx = 1
    for drv, d_items in sorted(by_driver.items(), key=lambda x: len(x[1]), reverse=True):
        lines.append(f"🚛 <b>TÀI XẾ: {_esc_html(drv.upper())} ({len(d_items)} đơn)</b>")
        for it in d_items[:20]:
            oc = it["orderCode"]
            t_calls = it["total_calls"]
            tk_calls = it["talk_calls"]
            m_dur = it["max_dur"]
            f_time = it["fail_time_str"]
            l_call = it["last_call_str"]
            call_str = f"{t_calls} cuộc (nghe {tk_calls}, {m_dur}s lúc {l_call})" if t_calls > 0 else "0 cuộc"
            lines.append(
                f"{idx:02d}. <code>{oc}</code> ({it['pkg_cnt']}k•{it['weight_kg']}kg) | {it['area_str']}\n"
                f"  └ 📞 Gọi: {call_str} ➔ Hoãn: <b>{f_time}</b> | {it['flag_text']}"
            )
            idx += 1
        lines.append("")

    lines.append("━" * 26)
    lines.append("📌 <b>TỔNG HỢP ĐỐI SOÁT LOG CUỘC GỌI:</b>")
    lines.append(f"• 🔴 <b>Không gọi / Khách chưa bắt máy (0s):</b> <b>{fake_or_no_ans} đơn</b>")
    lines.append(f"• 🟡 <b>Nghi vấn (Nghe ≤10s hoặc Gọi sáng/trưa - Chiều gom bấm hoãn):</b> <b>{short_or_batch} đơn</b>")
    lines.append(f"• 🟢 <b>Đàm thoại hợp lệ &amp; bấm hoãn đúng lúc:</b> <b>{valid_count} đơn</b>")
    lines.append("")
    lines.append(
        f"👉 <b>YÊU CẦU NVXL {nvxl_tag or nvxl_name}:</b> Rà soát ngay <b>{short_or_batch + fake_or_no_ans} đơn</b> nhóm 🟡/🔴 (đặc biệt các đơn gọi từ trưa nhưng gom lại bấm hoãn đồng loạt lúc 12:58–13:00 và 16:00–16:01, hoặc gọi chỉ 10s), đồng thời ép gán giao dứt điểm toàn bộ <b>{len(audited_list)} đơn</b> này ngay trong ca sáng nay!"
    )

    return "\n".join(lines)

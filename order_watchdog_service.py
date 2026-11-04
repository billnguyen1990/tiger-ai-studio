import os
import json
import time
import datetime
import threading
import re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_FILE = os.path.join(CURRENT_DIR, "data", "order_watchlist.json")
os.makedirs(os.path.dirname(WATCHLIST_FILE), exist_ok=True)

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_watchlist(items):
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Watchdog] Lỗi lưu watchlist: {e}")

def add_orders_to_watchlist(order_codes, target_status="Lấy Thành Công", target_hub="1908", target_hub_name="Kho Trung Chuyển Cần Thơ", topic_id=0, reply_to_id=None, created_by="anh Lộc"):
    items = load_watchlist()
    now_str = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    added_codes = []

    for code in order_codes:
        code = code.strip().upper()
        # Tìm xem đã có trong list chưa
        existing = next((x for x in items if x.get("order_code") == code and not x.get("alerted")), None)
        if existing:
            existing["target_status"] = target_status
            existing["target_hub_keyword"] = target_hub
            existing["target_hub_name"] = target_hub_name
            existing["topic_id"] = topic_id
            existing["reply_to_id"] = reply_to_id
            existing["updated_at"] = now_str
        else:
            items.append({
                "order_code": code,
                "target_status": target_status,
                "target_hub_keyword": target_hub,
                "target_hub_name": target_hub_name,
                "created_by": created_by,
                "created_at": now_str,
                "topic_id": topic_id,
                "reply_to_id": reply_to_id,
                "alerted": False,
                "last_checked": None,
                "last_status": None,
                "last_hub": None
            })
        added_codes.append(code)

    save_watchlist(items)
    return added_codes

def format_watchlist_status():
    items = load_watchlist()
    active_items = [x for x in items if not x.get("alerted")]
    completed_items = [x for x in items if x.get("alerted")]

    lines = [
        "📋 <b>TIGER AI • DANH SÁCH ĐƠN HÀNG ĐANG ÂM THẦM CANH GIÁM SÁT</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🎯 Đang theo dõi: <b>{len(active_items)}</b> đơn | Đã hoàn tất báo cáo: <b>{len(completed_items)}</b> đơn\n"
    ]

    if not active_items:
        lines.append("<i>Hiện tại không có đơn nào trong danh sách canh tự động.</i>")
    else:
        for idx, it in enumerate(active_items, 1):
            lines.append(f"📦 <b>{idx}. Mã đơn:</b> <code>{it['order_code']}</code>")
            lines.append(f"  • Điều kiện 1 (Trạng thái): <b>{it.get('target_status', 'Lấy Thành Công')}</b>")
            lines.append(f"  • Điều kiện 2 (Kho hiện tại): <b>{it.get('target_hub_name', '1908 - Kho Cần Thơ')}</b>")
            lines.append(f"  • Cập nhật lần cuối: Trạng thái: <code>{it.get('last_status', 'Chưa kiểm tra')}</code> | Kho: <i>{it.get('last_hub', 'Chưa kiểm tra')}</i>")
            lines.append(f"  • Thời gian nhận lệnh: {it.get('created_at')}")
            lines.append("───────────────────────────")

    lines.append("\n<i>💡 Bot tự động rà soát ngầm mỗi 3 phút. Thỏa mãn đồng thời 2 điều kiện sẽ báo cáo tức thì!</i>")
    return "\n".join(lines)

def run_watchdog_check(send_fn=None):
    """Quét toàn bộ danh sách đơn đang canh và thông báo nếu thỏa mãn điều kiện"""
    items = load_watchlist()
    active_items = [x for x in items if not x.get("alerted")]
    if not active_items:
        return

    try:
        from app import query_ghn_order_history
    except Exception:
        try:
            from server import query_ghn_order_history
        except Exception:
            return

    now_str = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    updated = False

    for it in active_items:
        code = it["order_code"]
        try:
            res = query_ghn_order_history(code)
            it["last_checked"] = now_str
            if not res or not res.get("found"):
                continue

            current_hub = res.get("current_hub") or res.get("hub_name") or ""
            status_text = res.get("status_text") or ""
            cust_status = res.get("cust_status") or ""

            it["last_status"] = cust_status or status_text
            it["last_hub"] = current_hub
            updated = True

            # Kiểm tra Điều kiện 1: Trạng thái khách hàng / Vận hành
            # Ví dụ: "Lấy thành công", "picked", hoặc đã qua bước lấy hàng
            st_target = (it.get("target_status") or "Lấy Thành Công").lower()
            st_text_lower = (status_text + " " + (cust_status or "")).lower()
            
            # Map các từ khóa lấy thành công
            is_picked = False
            if any(k in st_text_lower for k in ["lấy thành công", "lay thanh cong", "picked", "đã lấy hàng", "da lay hang", "lấy hàng thành công", "storing", "sorting"]):
                is_picked = True

            # Kiểm tra Điều kiện 2: Kho hiện tại
            hub_kw = (it.get("target_hub_keyword") or "1908").lower()
            hub_text_lower = current_hub.lower()
            is_hub_match = False
            if (hub_kw in hub_text_lower) or ("cần thơ" in hub_text_lower and "trung chuyển" in hub_text_lower) or ("soc cần thơ" in hub_text_lower):
                is_hub_match = True

            print(f"[Watchdog] Kiểm tra {code}: Picked={is_picked}, HubMatch={is_hub_match} (CurHub: {current_hub}, Status: {status_text})")

            # Nếu thỏa mãn cả 2 điều kiện!
            if is_picked and is_hub_match:
                it["alerted"] = True
                it["alerted_at"] = now_str

                alert_msg = (
                    f"🚨 <b>Dạ anh Lộc ơi, có đơn quan trọng đã về đến kho rồi nè!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📦 <b>Mã đơn hàng:</b> <code>{code}</code>\n"
                    f"✅ <b>Trạng thái:</b> <b>{cust_status or status_text} (ĐÃ LẤY THÀNH CÔNG)</b>\n"
                    f"📍 <b>Kho hiện tại:</b> <b>{current_hub}</b>\n"
                    f"⏰ <b>Thời điểm cập nhật:</b> {now_str}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"<i>Em đã kiểm tra đúng 2 điều kiện anh dặn và báo ngay lên đây cho anh rồi nha!</i>"
                )

                if send_fn:
                    topic_id = it.get("topic_id") or 0
                    reply_id = it.get("reply_to_id")
                    send_fn(alert_msg, topic_id=topic_id, reply_to_message_id=reply_id)

                # Ghi nhận sự kiện vào Pipeline Tracer
                try:
                    from pipeline_tracer import record_pipeline_event
                    record_pipeline_event(
                        task_name=f"Canh đơn quan trọng: {code}",
                        department="📞 Phòng Dịch Vụ Khách Hàng",
                        current_step="Hoàn tất: Đơn đã Lấy Thành Công và về Kho 1908 Cần Thơ",
                        total_steps=2,
                        status="SUCCESS",
                        handler_dept="📞 Phòng CSKH & 🛠️ Phòng Kỹ Thuật",
                        healing_action="Tự động bắt điều kiện và bắn cảnh báo thành công!",
                        can_resume=True
                    )
                except Exception:
                    pass

        except Exception as e:
            print(f"[Watchdog] Lỗi kiểm tra {code}: {e}")

    if updated:
        save_watchlist(items)

def start_order_watchdog_daemon(send_fn=None):
    """Khởi động daemon chạy ngầm vĩnh viễn"""
    def _daemon():
        print("🚀 [Watchdog Daemon] Đã khởi động luồng âm thầm canh đơn hàng...")
        while True:
            try:
                run_watchdog_check(send_fn=send_fn)
            except Exception as e:
                print(f"[Watchdog Daemon Error] {e}")
            time.sleep(180) # 3 phút check 1 lần

    t = threading.Thread(target=_daemon, daemon=True)
    t.start()
    return t


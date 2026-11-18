# -*- coding: utf-8 -*-
"""
TIGER AI • TOOL TỰ ĐỘNG NHẮC NHỞ NVXL HỌP VÀ BÁO CÁO ĐỊNH KỲ (08:00 AM THỨ HAI & THỨ NĂM)
Tác giả: Lisa • Trợ lý điều hành cá nhân Sếp Lộc & Tiger AI Copilot MT01
Lịch chạy: 08:00 AM (Giờ Việt Nam) vào Thứ Hai & Thứ Năm hàng tuần
Kênh gửi: Telegram Group "Miền Tây 01" (Chat ID: -1003940889949, Topic Báo Cáo: 2690)
"""

import os
import sys
import json
import datetime
import argparse
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAP_FILE = os.path.join(BASE_DIR, "nvxl_telegram_map.json")

# Cấu hình Telegram mặc định (Group: Miền Tây 01 - Topic: Báo Cáo)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1003940889949")
TELEGRAM_MESSAGE_THREAD_ID = int(os.environ.get("TELEGRAM_THREAD_ID", "2690"))

# Danh sách fallback 4 NVXL MT01 nếu không đọc được file json
DEFAULT_NVXL_LIST = [
    {
        "hub_name": "Kho Giao Hàng Nặng - Cái Răng - Cần Thơ",
        "short_name": "Cái Răng",
        "nvxl_name": "Công Bằng",
        "telegram_tag": "@CONGBANGCAIRANGCANTHO"
    },
    {
        "hub_name": "Kho Giao Hàng Nặng - Bình Thủy - Cần Thơ",
        "short_name": "Bình Thủy",
        "nvxl_name": "Nguyễn Phước Bảo Toàn",
        "telegram_tag": "@Nguyen_Toan"
    },
    {
        "hub_name": "Kho Giao Hàng Nặng - TP Vị Thanh - Hậu Giang",
        "short_name": "Vị Thanh",
        "nvxl_name": "Huỳnh Diệp Đức Trung",
        "telegram_tag": "@DUCTRUNG17TUOI"
    },
    {
        "hub_name": "Kho Giao Hàng Nặng - Ô Môn - Cần Thơ",
        "short_name": "Ô Môn",
        "nvxl_name": "Trần Trọng Bằng",
        "telegram_tag": "@pinca0602"
    }
]

def get_vietnam_now():
    """Lấy thời gian hiện tại chuẩn múi giờ Việt Nam (UTC+7)"""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    vn_tz = datetime.timezone(datetime.timedelta(hours=7))
    return utc_now.astimezone(vn_tz)

def load_nvxl_map():
    """Đọc cấu hình NVXL từ nvxl_telegram_map.json"""
    if os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return list(data.values())
        except Exception as e:
            print(f"⚠️ Không thể đọc {MAP_FILE} ({e}), sử dụng fallback mặc định.")
    return DEFAULT_NVXL_LIST

def generate_reminder_message(now=None):
    """Tạo nội dung thông báo nhắc họp & báo cáo định kỳ cho NVXL 4 kho"""
    if now is None:
        now = get_vietnam_now()

    weekday = now.weekday()  # 0: Thứ Hai, 3: Thứ Năm
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%H:%M")

    # Xác định chủ đề cuộc họp theo ngày
    if weekday == 0:
        session_title = "HỌP GIAO BAN ĐẦU TUẦN & TRIỂN KHAI KẾ HOẠCH"
        session_focus = "Phổ biến chỉ tiêu KPI tuần mới, phân bổ nhân sự, tối ưu chi phí xe tải và kế hoạch giải phóng tồn kho."
        weekday_name = "Thứ Hai"
    elif weekday == 3:
        session_title = "HỌP ĐÁNH GIÁ TIẾN ĐỘ & BÁO CÁO GIỮA TUẦN"
        session_focus = "Rà soát tỷ lệ GTC lũy kế, xử lý các nút thắt tồn đọng, đối soát ODO 365 và bứt phá mục tiêu cuối tuần."
        weekday_name = "Thứ Năm"
    else:
        weekday_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        weekday_name = weekday_names[weekday]
        session_title = "HỌP GIAO BAN & BÁO CÁO ĐỊNH KỲ VẬN HÀNH"
        session_focus = "Rà soát vận hành, kiểm soát hàng tồn và tối ưu chi phí các tuyến kho Miền Tây 01."

    nvxl_list = load_nvxl_map()

    # Tạo danh sách tag NVXL
    tags_line = " ".join([item.get("telegram_tag", "") for item in nvxl_list if item.get("telegram_tag")])

    hub_rows = []
    for idx, item in enumerate(nvxl_list, start=1):
        short_name = item.get("short_name", "")
        nvxl_name = item.get("nvxl_name", "")
        tag = item.get("telegram_tag", "")
        hub_rows.append(f"  <b>{idx}. Kho {short_name}:</b> {nvxl_name} ({tag})")

    hub_list_str = "\n".join(hub_rows)

    msg = f"""📢 <b>[TIGER AI • NHẮC LỊCH HỌP & BÁO CÁO ĐỊNH KỲ MT01]</b>
⏰ <i>Thời gian: {time_str} • {weekday_name}, ngày {date_str}</i>

Thân gửi các bạn Nhân Viên Xử Lý (NVXL) Cụm 4 Kho <b>Miền Tây 01</b>:
{hub_list_str}

🎯 <b>NỘI DUNG CUỘC HỌP HÔM NAY:</b>
👉 <b>{session_title}</b>
<i>{session_focus}</i>

📋 <b>CÁC HẠNG MỤC NVXL CẦN CHUẨN BỊ BÁO CÁO:</b>
1️⃣ <b>Sản Lượng & Tiến Độ Giao Hàng:</b>
   • Sản lượng nhập/xuất kho đầu ca sáng.
   • Tỷ lệ Gán chuyến xuất bến và tỷ lệ GTC lũy kế theo từng shipper.
2️⃣ <b>Hàng Tồn Kho & Đơn Hẹn Lại:</b>
   • Rà soát 100% đơn chưa gán chuyến và đơn lưu kho qua ngày.
   • Phân loại nguyên nhân GTB (khách hẹn lại / không liên lạc được).
3️⃣ <b>Vận Tải & Đối Soát ODO Xe Tải 365:</b>
   • Thời gian xe xuất bến và hoàn thành tuyến.
   • Đối chiếu số KM thực tế và ODO trên hệ thống.
4️⃣ <b>Nhân Sự & Kỷ Luật Vận Hành:</b>
   • Điểm danh quân số tài xế & shipper đi làm thực tế đầu ca.
   • Bố trí hỗ trợ tăng cường cho các tuyến tải nặng.

🔔 <b>Trân trọng nhắc nhở:</b> {tags_line}
<i>Các bạn vui lòng chủ động chuẩn bị đầy đủ số liệu kho mình trước giờ họp giao ban để buổi làm việc diễn ra nhanh gọn và hiệu quả nhất nhé!</i>

Chúc Cụm Miền Tây 01 một ngày vận hành an toàn, bùng nổ sản lượng và đạt 100% KPI! 💪🔥
────────────────────
🤖 <i>Hệ thống tự động nhắc lịch bởi Lisa • Tiger AI Copilot Miền Tây 01</i>"""
    return msg

def send_telegram_message(text, bot_token=None, chat_id=None, thread_id=None):
    """Gửi tin nhắn trực tiếp lên nhóm Telegram theo Topic chỉ định"""
    token = bot_token or TELEGRAM_BOT_TOKEN
    target_chat = chat_id or TELEGRAM_CHAT_ID
    target_thread = thread_id if thread_id is not None else TELEGRAM_MESSAGE_THREAD_ID

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": str(target_chat),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if target_thread:
        payload["message_thread_id"] = int(target_thread)

    print(f"🚀 Đang gửi thông báo nhắc họp tới Telegram (Chat: {target_chat}, Topic: {target_thread})...")
    try:
        res = requests.post(url, json=payload, timeout=15)
        data = res.json()
        if data.get("ok"):
            print("✅ Đã gửi thông báo nhắc họp NVXL lên Telegram thành công!")
            return True, data
        else:
            print(f"❌ Telegram API trả về lỗi: {data}")
            return False, data
    except Exception as e:
        print(f"❌ Ngoại lệ khi gửi Telegram: {e}")
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(description="Tool Auto nhắc nhở NVXL họp và báo cáo MT01")
    parser.add_argument("--send", action="store_true", help="Gửi thông báo thật lên Telegram")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in nội dung ra màn hình, không gửi")
    parser.add_argument("--force", action="store_true", help="Gửi bỏ qua kiểm tra thứ trong tuần (để test)")
    parser.add_argument("--chat-id", type=str, default=None, help="Telegram Chat ID tùy chọn")
    parser.add_argument("--thread-id", type=int, default=None, help="Telegram Topic ID tùy chọn")
    args = parser.parse_args()

    vn_now = get_vietnam_now()
    weekday = vn_now.weekday()

    # Kiểm tra ngày trong tuần (0: Thứ Hai, 3: Thứ Năm)
    if not args.force and weekday not in (0, 3):
        print(f"ℹ️ Hôm nay là thứ {weekday + 2} (không phải Thứ Hai hoặc Thứ Năm). Bỏ qua gửi thông báo.")
        print("💡 Dùng thêm cờ --force nếu muốn chạy thử nghiệm ngay lập tức.")
        if not args.dry_run and not args.send:
            return 0

    msg = generate_reminder_message(vn_now)

    if args.dry_run or not args.send:
        print("\n" + "=" * 60)
        print("📄 XEM TRƯỚC NỘI DUNG THÔNG BÁO (DRY-RUN):")
        print("=" * 60)
        print(msg)
        print("=" * 60 + "\n")
        if not args.send:
            print("💡 Chạy lại với cờ --send (hoặc --send --force) để gửi thật lên Telegram.")
            return 0

    if args.send:
        success, res = send_telegram_message(
            text=msg,
            chat_id=args.chat_id,
            thread_id=args.thread_id
        )
        if success:
            return 0
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()

import os
import sys
import json
import time
import subprocess
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MEETINGS_FILE = os.path.join(DATA_DIR, "meetings.json")
SCRATCH_DIR = os.path.dirname(BASE_DIR)
PDF_EXPORT_DIR = os.path.join(SCRATCH_DIR, "meeting_exports")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PDF_EXPORT_DIR, exist_ok=True)

# Active bot process tracker
_ACTIVE_MEETING_PROCESS = None
_ACTIVE_MEETING_ID = None

def load_meetings():
    if not os.path.exists(MEETINGS_FILE):
        seed_data = [
            {
                "id": "meet_20261106_hisense",
                "title": "Họp Triển Khai Vận Hành Dự Án Hisense (HiSen) - B2B LTL",
                "meet_url": "https://meet.google.com/ias-xknx-jrn",
                "department": "Khối Vận Hành B2B • Xe Tải Cần Thơ",
                "chair": "Tú Tống Duy (Ops Project Lead)",
                "created_at": "2026-11-06 14:03:00",
                "ended_at": "2026-11-06 14:25:00",
                "status": "PUBLISHED",  # LIVE, REVIEW_PENDING, MEDIA_READY, PUBLISHED
                "summary": "Triển khai lại mô hình LTL B2B cho khách hàng Hisense (KCN Đồng An 2, Bình Dương). Chạy 2 khu vực Miền Trung (7 tỉnh) & Miền Tây (3 tỉnh dồn về Cần Thơ điều tiết). Đóng gói tivi Toshiba bắt buộc quấn màng bubble chống bể vỡ, cấm quấn gom cụm. Bắt buộc thu hồi 02 Phiếu xuất kho có đủ chữ ký và kiểm tra thùng xe trước khi de giao tránh bị từ chối nguyên lô.",
                "notes_markdown": """# BIÊN BẢN HỌP TRIỂN KHAI VẬN HÀNH DỰ ÁN HISENSE (HISEN) - B2B LTL
- **Thời gian:** 14:03 – 14:25, Thứ Sáu, ngày 06/11/2026
- **Khách hàng:** Hisense (HiSen) - Lấy hàng tại KCN Đồng An 2, Bình Dương.
- **Mặt hàng:** Tivi Toshiba (>50 inch), Tủ lạnh, Máy giặt.
- **Phạm vi:** Miền Trung (7 tỉnh) & Miền Tây (Cần Thơ, An Giang, Đồng Tháp - dồn về kho Cần Thơ điều tiết).
- **Quy cách:** Tivi bắt buộc bọc màng bubble, cấm quấn gom cục làm mất tem GHN.
- **Chứng từ:** Thu hồi 2 tờ Phiếu xuất kho đủ chữ ký, chụp POD lên app, chuyển bản cứng về VP Thành Thái.
- **Xếp dỡ:** Bắt buộc kiểm tra thùng xe trước khi de giao hàng, tránh tivi nằm ngửa, máy giặt ngã đổ bị khách từ chối nguyên lô.""",
                "pdf_filename": "Bien_Ban_Hop_Du_An_Hisense_B2B.pdf",
                "pdf_path": os.path.join(SCRATCH_DIR, "Bien_Ban_Hop_Du_An_Hisense_B2B.pdf"),
                "telegram_topic_id": 2046,
                "telegram_topic_name": "📓 Quan Trọng",
                "telegram_message_id": 4144,
                "published_at": "2026-11-06 14:49:30"
            }
        ]
        save_meetings(seed_data)
        return seed_data
    try:
        with open(MEETINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_meetings(data):
    with open(MEETINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_meeting(meeting_id):
    meetings = load_meetings()
    for m in meetings:
        if m.get("id") == meeting_id:
            return m
    return None

def create_and_start_meeting(title, meet_url, department="Vận Hành"):
    global _ACTIVE_MEETING_PROCESS, _ACTIVE_MEETING_ID
    
    meeting_id = f"meet_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    new_meeting = {
        "id": meeting_id,
        "title": title or f"Cuộc họp {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "meet_url": meet_url.strip(),
        "department": department or "Khối Vận Hành",
        "chair": "Đang xác định...",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ended_at": None,
        "status": "LIVE",
        "summary": "Đang ghi nhận nội dung cuộc họp thời gian thực...",
        "notes_markdown": f"# BIÊN BẢN HỌP: {title}\n\n- **Phòng họp:** `{meet_url}`\n- **Bắt đầu:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n- **Thư ký:** Tiger AI Note Bot 🐯\n\n*(Đang lắng nghe trực tiếp từ phòng họp...)*",
        "pdf_filename": None,
        "pdf_path": None,
        "telegram_topic_id": 2046,
        "telegram_topic_name": "📓 Quan Trọng",
        "telegram_message_id": None,
        "published_at": None
    }
    
    meetings = load_meetings()
    meetings.insert(0, new_meeting)
    save_meetings(meetings)
    _ACTIVE_MEETING_ID = meeting_id
    
    # Launch Meet Bot background script
    bot_script = os.path.join(SCRATCH_DIR, "tiger_meet_bot.py")
    if os.path.exists(bot_script):
        # Update meet url in bot script or launch via args
        try:
            cmd = [sys.executable, bot_script]
            # Use subprocess without blocking
            _ACTIVE_MEETING_PROCESS = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False
            )
        except Exception as e:
            print(f"Error launching meet bot process: {e}")
            
    return new_meeting

def get_live_status():
    global _ACTIVE_MEETING_ID
    status_file = os.path.join(SCRATCH_DIR, "MEET_STATUS.json")
    transcript_file = os.path.join(SCRATCH_DIR, "MEET_TRANSCRIPT.txt")
    
    status_info = {"state": "IDLE", "details": "Chưa có cuộc họp nào đang diễn ra", "lines_count": 0}
    if os.path.exists(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status_info = json.load(f)
        except Exception:
            pass
            
    recent_speeches = []
    lines_count = 0
    if os.path.exists(transcript_file):
        try:
            with open(transcript_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                lines_count = len(lines)
                for l in lines[-25:]:
                    l = l.strip()
                    if l and not any(ign in l for ign in ['language', 'format_size', 'circle', 'settings']):
                        recent_speeches.append(l)
        except Exception:
            pass
            
    return {
        "active_meeting_id": _ACTIVE_MEETING_ID,
        "status": status_info.get("state", "IDLE"),
        "details": status_info.get("details", ""),
        "timestamp": status_info.get("timestamp", ""),
        "transcript_lines": lines_count,
        "recent_speeches": recent_speeches[-10:]
    }

def stop_meeting(meeting_id):
    global _ACTIVE_MEETING_PROCESS, _ACTIVE_MEETING_ID
    if _ACTIVE_MEETING_PROCESS:
        try:
            _ACTIVE_MEETING_PROCESS.terminate()
        except Exception:
            pass
        _ACTIVE_MEETING_PROCESS = None
        
    meetings = load_meetings()
    target = None
    for m in meetings:
        if m.get("id") == meeting_id:
            m["status"] = "REVIEW_PENDING"
            m["ended_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            target = m
            break
            
    if target:
        save_meetings(meetings)
    _ACTIVE_MEETING_ID = None
    return target

def update_meeting_review(meeting_id, title, summary, notes_markdown, chair=""):
    meetings = load_meetings()
    target = None
    for m in meetings:
        if m.get("id") == meeting_id:
            if title: m["title"] = title
            if summary: m["summary"] = summary
            if notes_markdown: m["notes_markdown"] = notes_markdown
            if chair: m["chair"] = chair
            m["status"] = "MEDIA_READY"
            target = m
            break
    if target:
        save_meetings(meetings)
    return target

def generate_meeting_pdf_render(meeting_id):
    meeting = get_meeting(meeting_id)
    if not meeting:
        return None, "Meeting not found"
        
    title = meeting.get("title", "Biên Bản Họp")
    created_at = meeting.get("created_at", "")
    ended_at = meeting.get("ended_at", "")
    chair = meeting.get("chair", "Đại diện Chủ trì")
    dept = meeting.get("department", "Khối Vận Hành")
    summary = meeting.get("summary", "")
    notes_md = meeting.get("notes_markdown", "")
    
    # Format notes to HTML paragraphs
    notes_html = ""
    for line in notes_md.split("\n"):
        line = line.strip()
        if not line: continue
        if line.startswith("# "):
            notes_html += f"<h1 class='doc-title'>{line[2:]}</h1>"
        elif line.startswith("## "):
            notes_html += f"<h2>{line[3:]}</h2>"
        elif line.startswith("### "):
            notes_html += f"<h3>{line[4:]}</h3>"
        elif line.startswith("- **") or line.startswith("* **"):
            notes_html += f"<p class='bullet'>• {line[2:]}</p>"
        else:
            notes_html += f"<p>{line}</p>"
            
    safe_filename = f"Bien_Ban_Hop_{meeting_id}.pdf"
    pdf_out_path = os.path.join(PDF_EXPORT_DIR, safe_filename)
    
    html_template = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        @page {{ size: A4; margin: 15mm; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            color: #1e293b; line-height: 1.5; font-size: 9.5pt; margin: 0; padding: 0;
        }}
        .header {{
            display: flex; justify-content: space-between; align-items: flex-start;
            border-bottom: 2px solid #ea580c; padding-bottom: 10px; margin-bottom: 14px;
        }}
        .logo-badge {{
            background: linear-gradient(135deg, #ea580c, #c2410c);
            color: white; font-weight: 800; font-size: 13pt; padding: 5px 12px; border-radius: 6px;
            display: inline-block;
        }}
        .company-name {{ font-size: 10.5pt; font-weight: 700; color: #0f172a; text-transform: uppercase; margin-top: 3px; }}
        .doc-meta {{ text-align: right; font-size: 8pt; color: #475569; }}
        .doc-title {{ font-size: 14pt; font-weight: 800; color: #0f172a; text-transform: uppercase; text-align: center; margin: 10px 0 4px 0; }}
        .meta-grid {{
            display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px;
            background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;
            padding: 8px 12px; margin-bottom: 14px; font-size: 8.5pt;
        }}
        .highlight-box {{
            background: #fff7ed; border-left: 4px solid #ea580c; padding: 10px 12px;
            border-radius: 4px; margin-bottom: 14px; font-size: 9pt; color: #9a3412;
        }}
        h2 {{ font-size: 11pt; color: #0f172a; border-left: 4px solid #ea580c; padding-left: 8px; margin: 14px 0 8px 0; }}
        h3 {{ font-size: 10pt; color: #334155; margin: 10px 0 4px 0; }}
        p {{ margin: 0 0 6px 0; }}
        .bullet {{ margin-left: 12px; }}
        .signatures {{
            display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;
            margin-top: 25px; page-break-inside: avoid; text-align: center;
        }}
        .sig-block {{ border-top: 1px solid #cbd5e1; padding-top: 8px; }}
        .sig-title {{ font-weight: 700; font-size: 8.5pt; color: #334155; text-transform: uppercase; }}
        .sig-space {{ height: 40px; }}
        .sig-name {{ font-weight: 600; font-size: 8.5pt; color: #0f172a; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <div class="logo-badge">GHN</div>
            <div class="company-name">GIAO HÀNG NHANH • {dept.upper()}</div>
        </div>
        <div class="doc-meta">
            <div>Mã số: <strong>BBH-{meeting_id.upper()}</strong></div>
            <div>Ngày phát hành: <strong>{datetime.now().strftime('%d/%m/%Y')}</strong></div>
            <div>Bản quyền: <strong>Tiger AI Logistics</strong></div>
        </div>
    </div>

    <h1 class="doc-title">{title}</h1>

    <div class="meta-grid">
        <div><strong>⏰ Thời gian:</strong> {created_at} - {ended_at or 'Hoàn tất'}</div>
        <div><strong>💻 Hình thức:</strong> Trực tuyến qua Google Meet</div>
        <div><strong>👤 Chủ trì:</strong> {chair}</div>
        <div><strong>🤖 Thư ký ghi chép:</strong> Tiger AI Note Bot 🐯</div>
    </div>

    <div class="highlight-box">
        <strong>📌 TÓM TẮT ĐIỂM NÓNG & KẾT LUẬN CUỘC HỌP:</strong><br>
        {summary}
    </div>

    <div>
        {notes_html}
    </div>

    <div class="signatures">
        <div class="sig-block">
            <div class="sig-title">Đại Diện Chủ Trì Cuộc Họp</div>
            <div class="sig-space"></div>
            <div class="sig-name">{chair}</div>
        </div>
        <div class="sig-block">
            <div class="sig-title">Trợ Lý Thư Ký Họp & Truyền Thông AI</div>
            <div class="sig-space"></div>
            <div class="sig-name">Tiger AI Studio 🐯</div>
        </div>
    </div>
</body>
</html>
"""
    
    temp_html = os.path.join(PDF_EXPORT_DIR, f"{meeting_id}.html")
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html_template)
        
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"file:///{temp_html.replace(os.sep, '/')}", wait_until="networkidle")
            page.pdf(
                path=pdf_out_path,
                format="A4",
                print_background=True,
                margin={"top": "12mm", "bottom": "12mm", "left": "12mm", "right": "12mm"}
            )
            browser.close()
            
        meetings = load_meetings()
        for m in meetings:
            if m.get("id") == meeting_id:
                m["pdf_filename"] = safe_filename
                m["pdf_path"] = pdf_out_path
                m["status"] = "MEDIA_READY"
                break
        save_meetings(meetings)
        return pdf_out_path, None
    except Exception as e:
        return None, str(e)

def publish_meeting_telegram(meeting_id, topic_id=2046):
    meeting = get_meeting(meeting_id)
    if not meeting:
        return False, "Meeting not found"
        
    pdf_path = meeting.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        # Generate PDF first
        pdf_path, err = generate_meeting_pdf_render(meeting_id)
        if err:
            return False, f"Lỗi tạo PDF: {err}"
            
    bot_token = "8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk"
    chat_id = "-1003940889949"
    target_topic = topic_id or 2046
    
    title = meeting.get("title", "Biên Bản Họp")
    summary = meeting.get("summary", "")
    chair = meeting.get("chair", "Chủ trì cuộc họp")
    
    caption = (
        f"📋 <b>BIÊN BẢN HỌP: {title.upper()}</b>\n\n"
        f"⏰ <b>Thời gian:</b> {meeting.get('created_at', '')}\n"
        f"👤 <b>Chủ trì:</b> {chair}\n"
        f"📢 <b>Phòng Truyền Thông Tiger AI thông báo:</b>\n\n"
        f"🎯 <b>NỘI DUNG CỐT LÕI:</b>\n"
        f"{summary[:700]}\n\n"
        f"📎 <i>Chi tiết toàn văn kính mời các anh em xem tệp PDF đính kèm!</i>"
    )
    
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(pdf_path, "rb") as f:
            files = {"document": (meeting.get("pdf_filename", "Bien_Ban_Hop.pdf"), f, "application/pdf")}
            data = {
                "chat_id": chat_id,
                "message_thread_id": target_topic,
                "caption": caption,
                "parse_mode": "HTML"
            }
            res = requests.post(url, data=data, files=files, timeout=30)
            res_json = res.json()
            if res_json.get("ok"):
                msg_id = res_json.get("result", {}).get("message_id")
                meetings = load_meetings()
                for m in meetings:
                    if m.get("id") == meeting_id:
                        m["status"] = "PUBLISHED"
                        m["telegram_message_id"] = msg_id
                        m["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        break
                save_meetings(meetings)
                return True, f"Bắn thành công vào Room Quan Trọng (Msg #{msg_id})"
            else:
                return False, res_json.get("description", "Telegram API Error")
    except Exception as e:
        return False, str(e)

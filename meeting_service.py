import os
import re
import sys
import json
import time
import subprocess
import requests
from datetime import datetime
try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_SCRATCH_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
MEETINGS_FILE = os.path.join(DATA_DIR, "meetings.json")
SCRATCH_DIR = BASE_DIR
PDF_EXPORT_DIR = os.path.join(DATA_DIR, "meeting_exports")
try:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(PDF_EXPORT_DIR, exist_ok=True)
except Exception:
    pass


def _find_existing_file(filename):
    """Tìm file trong các thư mục dữ liệu của dự án"""
    if not filename:
        return None
    candidates = [
        os.path.join(PDF_EXPORT_DIR, filename),
        os.path.join(DATA_DIR, filename),
        os.path.join(BASE_DIR, filename),
        os.path.join(PARENT_SCRATCH_DIR, "meeting_exports", filename),
        os.path.join(PARENT_SCRATCH_DIR, filename),
    ]
    for p in candidates:
        if os.path.exists(p) and os.path.isfile(p):
            return p
    return None

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
    
    # 1. Dừng process cũ nếu có
    if _ACTIVE_MEETING_PROCESS:
        try:
            _ACTIVE_MEETING_PROCESS.terminate()
            time.sleep(1)
        except Exception:
            pass
        _ACTIVE_MEETING_PROCESS = None

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

    # 2. Reset / backup file transcript và notes cho cuộc họp mới
    t_file = _find_existing_file("MEET_TRANSCRIPT.txt") or os.path.join(PARENT_SCRATCH_DIR, "MEET_TRANSCRIPT.txt")
    if os.path.exists(t_file) and os.path.getsize(t_file) > 100:
        backup_t = os.path.join(DATA_DIR, f"transcript_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        try:
            import shutil
            shutil.copy2(t_file, backup_t)
        except Exception:
            pass
    try:
        with open(t_file, "w", encoding="utf-8") as f:
            f.write(f"=== BIÊN BẢN GHI ÂM GOOGLE MEET: {meet_url} ===\nBắt đầu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    except Exception:
        pass

    s_file = _find_existing_file("MEET_STATUS.json") or os.path.join(PARENT_SCRATCH_DIR, "MEET_STATUS.json")
    try:
        with open(s_file, "w", encoding="utf-8") as f:
            json.dump({
                "state": "CONNECTING",
                "details": "Đang kết nối vào Google Meet...",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    
    # 3. Launch Meet Bot background script (hỗ trợ cả thư mục gốc & thư mục cha)
    bot_candidates = [
        os.path.join(BASE_DIR, "tiger_meet_bot.py"),
        os.path.join(PARENT_SCRATCH_DIR, "tiger_meet_bot.py")
    ]
    bot_script = next((p for p in bot_candidates if os.path.exists(p)), None)
    if bot_script:
        try:
            cmd = [sys.executable, bot_script, meet_url.strip()]
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
    status_file = _find_existing_file("MEET_STATUS.json") or os.path.join(BASE_DIR, "MEET_STATUS.json")
    transcript_file = _find_existing_file("MEET_TRANSCRIPT.txt") or os.path.join(BASE_DIR, "MEET_TRANSCRIPT.txt")
    
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

def ai_summarize_meeting_transcript(meeting_id):
    """Dùng Local AI (Ollama Qwen 2.5 3B • Auto-Unload 2m) tự động bóc tách phụ đề Google Meet thành Biên bản chuẩn (Kèm Fallback thông minh trên Cloud)"""
    meeting = get_meeting(meeting_id)
    if not meeting:
        return None, "Không tìm thấy cuộc họp"

    transcript_file = _find_existing_file("MEET_TRANSCRIPT.txt") or os.path.join(BASE_DIR, "MEET_TRANSCRIPT.txt")
    raw_lines = []
    if os.path.exists(transcript_file):
        try:
            with open(transcript_file, "r", encoding="utf-8") as f:
                for l in f.readlines()[-120:]:
                    l = l.strip()
                    if l and not any(ign in l for ign in ['language', 'format_size', 'circle', 'settings']):
                        raw_lines.append(l)
        except Exception:
            pass

    raw_text = "\n".join(raw_lines[-60:]) if raw_lines else meeting.get("notes_markdown", "")
    if not raw_text:
        return meeting, None

    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
    sys_prompt = (
        "Bạn là Thư Ký Điều Hành Cấp Cao Tiger AI của Giao Hàng Nhanh (GHN - Cụm Miền Tây 01).\n"
        "Nhiệm vụ: Đọc bản ghi phụ đề cuộc họp tiếng Việt dưới đây, sửa lỗi chính tả/lặp từ của Google Meet và viết thành Biên Bản Họp chuyên nghiệp, súc tích.\n"
        "Hãy trả lời theo đúng định dạng:\n"
        "TOM_TAT: <Đoạn tóm tắt điều hành cốt lõi 3-4 câu>\n"
        "CHI_TIET:\n"
        "# BIÊN BẢN HỌP: <Tiêu đề>\n"
        "## 1. Nội dung trọng tâm & Số liệu\n"
        "- **...**\n"
        "## 2. Các điểm nóng & Quy định vận hành bắt buộc\n"
        "- **...**\n"
        "## 3. Phân công & Hành động tiếp theo\n"
        "- **...**"
    )
    payload = {
        "model": ollama_model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Tiêu đề cuộc họp: {meeting.get('title', '')}\nNội dung ghi nhận:\n{raw_text[:3500]}"}
        ],
        "stream": False,
        "keep_alive": "2m",
        "options": {"temperature": 0.25, "num_predict": 700, "num_ctx": 4096}
    }
    try:
        r = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=35)
        if r.status_code == 200:
            content = (r.json().get("message") or {}).get("content", "").strip()
            if content:
                summary_part = meeting.get("summary", "")
                notes_part = content
                if "CHI_TIET:" in content:
                    parts = content.split("CHI_TIET:", 1)
                    s_raw = parts[0].replace("TOM_TAT:", "").strip()
                    if s_raw:
                        summary_part = s_raw
                    notes_part = parts[1].strip()
                updated = update_meeting_review(
                    meeting_id,
                    meeting.get("title"),
                    summary_part,
                    notes_part,
                    meeting.get("chair")
                )
                return updated, None
    except Exception:
        pass

    # Fallback thông minh khi chạy trên Cloud Render (không có Local Ollama)
    if raw_lines:
        clean_bullets = "\n".join(f"- {l}" for l in raw_lines[-18:])
        fallback_notes = (
            f"# BIÊN BẢN HỌP: {meeting.get('title', '').upper()}\n\n"
            f"- **Thời gian:** {meeting.get('created_at', '')}\n"
            f"- **Bộ phận:** {meeting.get('department', 'Khối Vận Hành')}\n"
            f"- **Chủ trì:** {meeting.get('chair', 'Đại diện Chủ trì')}\n\n"
            f"## 📌 Các phát biểu & nội dung trọng tâm ghi nhận\n{clean_bullets}"
        )
        updated = update_meeting_review(
            meeting_id,
            meeting.get("title"),
            meeting.get("summary") or "Đã tổng hợp tự động các phát biểu trọng tâm từ phụ đề trực tiếp.",
            fallback_notes,
            meeting.get("chair")
        )
        return updated, None

    return meeting, None

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

def delete_meeting(meeting_id):
    meetings = load_meetings()
    new_meetings = [m for m in meetings if m.get("id") != meeting_id]
    if len(new_meetings) == len(meetings):
        return False, "Không tìm thấy biên bản cuộc họp."
    save_meetings(new_meetings)
    return True, "Đã xóa biên bản cuộc họp."

def _md_inline_to_html(text):
    if not text:
        return ""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(text))

def build_meeting_a4_html(meeting_id, include_print_toolbar=False):
    meeting = get_meeting(meeting_id)
    if not meeting:
        return None, "Meeting not found"

    title = meeting.get("title", "Biên Bản Họp")
    created_at = meeting.get("created_at", "")
    ended_at = meeting.get("ended_at", "")
    chair = meeting.get("chair", "Đại diện Chủ trì")
    dept = meeting.get("department", "Khối Vận Hành")
    summary = _md_inline_to_html(meeting.get("summary", ""))
    notes_md = meeting.get("notes_markdown", "")

    notes_html = ""
    for line in notes_md.split("\n"):
        line = line.strip()
        if not line:
            continue
        formatted = _md_inline_to_html(line)
        if line.startswith("# "):
            notes_html += f"<h1 class='doc-title'>{_md_inline_to_html(line[2:])}</h1>"
        elif line.startswith("## "):
            notes_html += f"<h2>{_md_inline_to_html(line[3:])}</h2>"
        elif line.startswith("### "):
            notes_html += f"<h3>{_md_inline_to_html(line[4:])}</h3>"
        elif line.startswith("- ") or line.startswith("* "):
            notes_html += f"<p class='bullet'>• {_md_inline_to_html(line[2:])}</p>"
        else:
            notes_html += f"<p>{formatted}</p>"

    toolbar_html = ""
    if include_print_toolbar:
        toolbar_html = """
        <div class="print-toolbar no-print">
            <span>📄 Bản Chuẩn A4 Biên Bản Họp — Tiger AI Studio</span>
            <button onclick="window.print()">🖨️ In / Lưu Thành PDF (Ctrl+P)</button>
        </div>
        """

    html_template = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        @page {{ size: A4; margin: 14mm; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            color: #1e293b; line-height: 1.55; font-size: 9.5pt; margin: 0; padding: {('18px 24px' if include_print_toolbar else '0')};
            background: #ffffff;
        }}
        .print-toolbar {{
            display: flex; justify-content: space-between; align-items: center;
            background: #0f172a; color: #f8fafc; padding: 8px 14px; border-radius: 8px;
            margin-bottom: 16px; font-size: 8.5pt; font-weight: 600;
        }}
        .print-toolbar button {{
            background: linear-gradient(135deg, #ea580c, #c2410c); color: #fff;
            border: none; padding: 5px 12px; border-radius: 6px; font-weight: 700; cursor: pointer; font-size: 8pt;
        }}
        @media print {{
            .no-print {{ display: none !important; }}
            body {{ padding: 0; }}
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
        .doc-title {{ font-size: 13.5pt; font-weight: 800; color: #0f172a; text-transform: uppercase; text-align: center; margin: 10px 0 6px 0; }}
        .meta-grid {{
            display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px;
            background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;
            padding: 8px 12px; margin-bottom: 14px; font-size: 8.5pt;
        }}
        .highlight-box {{
            background: #fff7ed; border-left: 4px solid #ea580c; padding: 10px 12px;
            border-radius: 4px; margin-bottom: 14px; font-size: 9pt; color: #9a3412;
        }}
        h2 {{ font-size: 10.5pt; color: #0f172a; border-left: 4px solid #ea580c; padding-left: 8px; margin: 14px 0 8px 0; }}
        h3 {{ font-size: 9.8pt; color: #334155; margin: 10px 0 4px 0; }}
        p {{ margin: 0 0 6px 0; }}
        .bullet {{ margin-left: 12px; }}
        .signatures {{
            display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;
            margin-top: 25px; page-break-inside: avoid; text-align: center;
        }}
        .sig-block {{ border-top: 1px solid #cbd5e1; padding-top: 8px; }}
        .sig-title {{ font-weight: 700; font-size: 8.5pt; color: #334155; text-transform: uppercase; }}
        .sig-space {{ height: 38px; }}
        .sig-name {{ font-weight: 600; font-size: 8.5pt; color: #0f172a; }}
    </style>
</head>
<body>
    {toolbar_html}
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
    return html_template, None

def generate_meeting_pdf_render(meeting_id):
    meeting = get_meeting(meeting_id)
    if not meeting:
        return None, "Meeting not found"

    html_template, err = build_meeting_a4_html(meeting_id, include_print_toolbar=False)
    if err:
        return None, err

    safe_filename = f"Bien_Ban_Hop_{meeting_id}.pdf"
    pdf_out_path = os.path.join(PDF_EXPORT_DIR, safe_filename)

    temp_html = os.path.join(PDF_EXPORT_DIR, f"{meeting_id}.html")
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html_template)

    if sync_playwright is not None:
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
        except Exception:
            pass

    # Fallback khi chạy trên Cloud Linux không có Chromium binary:
    # Kiểm tra xem có file PDF dựng sẵn của cuộc họp này không
    existing_pdf = _find_existing_file(meeting.get("pdf_filename", ""), safe_filename, meeting.get("pdf_path", ""))
    if existing_pdf and existing_pdf.lower().endswith(".pdf"):
        meetings = load_meetings()
        for m in meetings:
            if m.get("id") == meeting_id:
                m["pdf_filename"] = os.path.basename(existing_pdf)
                m["pdf_path"] = existing_pdf
                m["status"] = "MEDIA_READY"
                break
        save_meetings(meetings)
        return existing_pdf, None

    # Lưu bản HTML chuẩn A4 có thanh công cụ in PDF trực tiếp
    html_with_toolbar, _ = build_meeting_a4_html(meeting_id, include_print_toolbar=True)
    html_filename = f"Bien_Ban_Hop_{meeting_id}.html"
    html_out_path = os.path.join(PDF_EXPORT_DIR, html_filename)
    with open(html_out_path, "w", encoding="utf-8") as f:
        f.write(html_with_toolbar)

    meetings = load_meetings()
    for m in meetings:
        if m.get("id") == meeting_id:
            m["pdf_filename"] = html_filename
            m["pdf_path"] = html_out_path
            m["status"] = "MEDIA_READY"
            break
    save_meetings(meetings)
    return html_out_path, None

def publish_meeting_telegram(meeting_id, topic_id=2046, custom_caption=None):
    meeting = get_meeting(meeting_id)
    if not meeting:
        return False, "Meeting not found"

    doc_path = _find_existing_file(
        meeting.get("pdf_path", ""),
        meeting.get("pdf_filename", ""),
        f"Bien_Ban_Hop_{meeting_id}.pdf"
    )
    if not doc_path or not os.path.exists(doc_path):
        doc_path, err = generate_meeting_pdf_render(meeting_id)
        if err or not doc_path:
            return False, f"Lỗi tạo tài liệu: {err}"

    bot_token = "8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk"
    chat_id = "-1003940889949"
    target_topic = int(topic_id or 2046)

    topic_names = {
        2046: "Room Quan Trọng (#2046)",
        2690: "Room Báo Cáo Vận Hành (#2690)",
        506: "Room Đơn Tạo B2B (#506)"
    }
    room_label = topic_names.get(target_topic, f"Topic #{target_topic}")

    title = meeting.get("title", "Biên Bản Họp")
    summary = meeting.get("summary", "")
    chair = meeting.get("chair", "Chủ trì cuộc họp")

    if custom_caption and str(custom_caption).strip():
        caption = str(custom_caption).strip()[:1000]
        parse_mode = None
    else:
        caption = (
            f"📋 <b>BIÊN BẢN HỌP: {title.upper()}</b>\n\n"
            f"⏰ <b>Thời gian:</b> {meeting.get('created_at', '')}\n"
            f"👤 <b>Chủ trì:</b> {chair}\n"
            f"📢 <b>Phòng Truyền Thông Tiger AI thông báo:</b>\n\n"
            f"🎯 <b>NỘI DUNG CỐT LÕI:</b>\n"
            f"{summary[:650]}\n\n"
            f"📎 <i>Chi tiết toàn văn kính mời các anh em xem tệp biên bản đính kèm!</i>"
        )
        parse_mode = "HTML"

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        doc_filename = os.path.basename(doc_path)
        mime_type = "application/pdf" if doc_filename.lower().endswith(".pdf") else "text/html"
        with open(doc_path, "rb") as f:
            files = {"document": (doc_filename, f, mime_type)}
            data = {
                "chat_id": chat_id,
                "message_thread_id": target_topic,
                "caption": caption,
            }
            if parse_mode:
                data["parse_mode"] = parse_mode
            res = requests.post(url, data=data, files=files, timeout=30)
            res_json = res.json()
            if res_json.get("ok"):
                msg_id = res_json.get("result", {}).get("message_id")
                meetings = load_meetings()
                for m in meetings:
                    if m.get("id") == meeting_id:
                        m["status"] = "PUBLISHED"
                        m["telegram_message_id"] = msg_id
                        m["telegram_topic_id"] = target_topic
                        m["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        break
                save_meetings(meetings)
                return True, f"Bắn thành công vào {room_label} (Msg #{msg_id})"
            else:
                return False, res_json.get("description", "Telegram API Error")
    except Exception as e:
        return False, str(e)


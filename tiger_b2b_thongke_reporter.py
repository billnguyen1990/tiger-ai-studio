# -*- coding: utf-8 -*-
import os
import sys
import requests
import csv
import io
import re
import unicodedata
from datetime import datetime, timedelta
from collections import defaultdict
from playwright.sync_api import sync_playwright

DIR_NAME = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(DIR_NAME, "credentials.json")
if not os.path.exists(CREDS_FILE):
    sub_creds = os.path.join(os.path.dirname(DIR_NAME), "tool_11h_bao_cao_telegram", "credentials.json")
    if os.path.exists(sub_creds):
        CREDS_FILE = sub_creds
    else:
        auth_file = os.path.join(DIR_NAME, "google_auth_storage.json")
        if os.path.exists(auth_file):
            try:
                import json
                with open(auth_file, "r", encoding="utf-8") as f_auth:
                    sa_data = json.load(f_auth)
                if "service_account" in sa_data and isinstance(sa_data["service_account"], dict):
                    with open(CREDS_FILE, "w", encoding="utf-8") as f_out:
                        json.dump(sa_data["service_account"], f_out, indent=2)
            except Exception:
                pass

BOT_TOKEN = "8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk"
CHAT_ID = "-1003940889949"
TOPIC_IDS = [506]  # CHỈ GỬI DUY NHẤT Topic 506 (📅 Đơn Tạo) - Tuyệt đối không gửi vào room Báo Cáo (Topic 2690)

ALL_BUU_CUC_LIST = [
    'Kho Giao Hàng Nặng - Cái Răng - Cần Thơ',
    'Kho Giao Hàng Nặng - Bình Thủy - Cần Thơ',
    'Kho Giao Hàng Nặng - TP Vị Thanh - Hậu Giang',
    'Kho Giao Hàng Nặng - Ô Môn - Cần Thơ',
    'Kho Giao Hàng Nặng - Tam Nông - Đồng Tháp',
    'Kho Giao Hàng Nặng - TP Cao Lãnh - Đồng Tháp',
    'Kho Giao Hàng Nặng - TP Cà Mau - Cà Mau',
    'Kho Giao Hàng Nặng - TP Rạch Giá - Kiên Giang',
    'Kho Giao Hàng Nặng - TP Hà Tiên - Kiên Giang',
    'Kho Giao Hàng Nặng - TX Cai Lậy - Tiền Giang',
    'Kho Giao Hàng Nặng - Đức Hòa - Long An',
    'Kho Giao Hàng Nặng - TP Mỹ Tho - Tiền Giang',
    'Kho Giao Hàng Nặng - TP Bến Tre - Bến Tre',
    'Kho Giao Hàng Nặng - TP Tân An - Long An',
    'Kho Giao Hàng Nặng - Gò Công - Tiền Giang',
    'Kho Giao Hàng Nặng - TP Bạc Liêu - Bạc Liêu',
    'Kho Giao Hàng Nặng - TP Sóc Trăng - Sóc Trăng',
    'Kho Giao Hàng Nặng - TP Trà Vinh - Trà Vinh',
    'Kho Giao Hàng Nặng - TP Châu Đốc - An Giang',
    'Kho Giao Hàng Nặng - TP Vĩnh Long - Vĩnh Long',
    'Kho Giao Hàng Nặng - TP Long Xuyên - An Giang',
    'Kho Giao Hàng Nặng TNB'
]

MT01_5_KHO = [
    'Kho Giao Hàng Nặng - Cái Răng - Cần Thơ',
    'Kho Giao Hàng Nặng - Bình Thủy - Cần Thơ',
    'Kho Giao Hàng Nặng - TP Vị Thanh - Hậu Giang',
    'Kho Giao Hàng Nặng - Ô Môn - Cần Thơ',
    'Kho Giao Hàng Nặng TNB'
]

def normalize_text(text):
    if not text:
        return ""
    text = str(text).lower().strip()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.replace('đ', 'd')
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def match_warehouse_name(raw_name):
    if not raw_name:
        return None
    norm = normalize_text(raw_name)
    for std_name in ALL_BUU_CUC_LIST:
        norm_std = normalize_text(std_name)
        if norm == norm_std:
            return std_name
        short_key = norm_std.replace('kho giao hang nang - ', '').replace('kho giao hang nang ', '')
        parts = short_key.split(' - ')
        main_place = parts[0].strip()
        if main_place in norm:
            return std_name
    return None

def parse_vn_date_time(val):
    if not val:
        return None
    val_str = str(val).strip()
    m1 = re.search(r'(\d{1,2})\s*thg\s*(\d{1,2}),?\s*(\d{4})', val_str, re.IGNORECASE)
    if m1:
        return datetime(int(m1.group(3)), int(m1.group(2)), int(m1.group(1)))
    m2 = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', val_str)
    if m2:
        return datetime(int(m2.group(3)), int(m2.group(2)), int(m2.group(1)))
    m3 = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', val_str)
    if m3:
        return datetime(int(m3.group(1)), int(m3.group(2)), int(m3.group(3)))
    return None

def parse_weight_int(val):
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(round(val))
    s = str(val).strip().replace('.', '').replace(',', '')
    try:
        return int(s)
    except Exception:
        return 0

def fetch_and_compute_b2b_tables():
    """Tự động kéo dữ liệu CSV công khai từ tab Data của Google Sheet và tổng hợp bảng Thống Kê chuẩn 100%."""
    url = 'https://docs.google.com/spreadsheets/d/1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI/export?format=csv&gid=0'
    print("📡 Đang tải trực tiếp dữ liệu CSV từ Google Sheet Data tab...")
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} fetching Data CSV")
    
    reader = csv.reader(io.StringIO(r.text))
    headers = [h.strip().lower() for h in next(reader)]
    
    col_code = headers.index('mã đơn')
    col_lay = headers.index('ngày lấy')
    col_tao = headers.index('ngày tạo')
    col_kho = headers.index('bưu cục giao')
    col_w = headers.index('cân nặng')

    dates = []
    rows_data = []
    for row in reader:
        if len(row) <= max(col_code, col_lay, col_tao, col_kho, col_w):
            continue
        raw_lay = row[col_lay]
        if not raw_lay or str(raw_lay).strip().lower() in ('null', ''):
            continue
        raw_kho = row[col_kho]
        matched_kho = match_warehouse_name(raw_kho)
        if not matched_kho:
            continue
        d = parse_vn_date_time(row[col_tao])
        if not d:
            continue
        w = parse_weight_int(row[col_w])
        dates.append(d)
        rows_data.append((matched_kho, d, w))

    today = max(dates) if dates else datetime.now()
    from_date = today - timedelta(days=7)
    print(f"✓ Đã nạp {len(rows_data):,} dòng hợp lệ (Khoảng ngày: {from_date.strftime('%d/%m')} -> {today.strftime('%d/%m/%Y')})")

    date_list = []
    cur_d = from_date
    while cur_d <= today:
        date_list.append(cur_d)
        cur_d += timedelta(days=1)

    date_keys = [d.strftime("%Y-%m-%d") for d in date_list]
    date_labels = [f"{d.day}/{d.month}/{d.year}" for d in date_list]

    counts = defaultdict(lambda: defaultdict(int))
    weights = defaultdict(lambda: defaultdict(int))

    for kho, dt, w in rows_data:
        if from_date <= dt <= today:
            dk = dt.strftime("%Y-%m-%d")
            counts[kho][dk] += 1
            weights[kho][dk] += w

    num_cols = 2 + len(date_labels) + 1
    blank_row = [''] * num_cols

    def fmt_vn(n):
        return f"{int(n):,}".replace(",", ".")

    def build_pivot_block(title, kho_list, metric_dict):
        block = []
        title_row = [title] + [''] * (num_cols - 1)
        header_row = ['STT', 'Nhãn Hàng'] + date_labels + ['Tổng Cuối']
        block.append(title_row)
        block.append(header_row)
        col_totals = [0] * len(date_keys)
        grand_total = 0
        for idx, kho in enumerate(kho_list, start=1):
            vals = [metric_dict[kho][dk] for dk in date_keys]
            row_sum = sum(vals)
            for c_i, v in enumerate(vals):
                col_totals[c_i] += v
            grand_total += row_sum
            block.append([str(idx), kho] + [fmt_vn(v) for v in vals] + [fmt_vn(row_sum)])
        block.append(['', 'Tổng Cuối'] + [fmt_vn(v) for v in col_totals] + [fmt_vn(grand_total)])
        return block

    t1 = build_pivot_block('Count of mã đơn', MT01_5_KHO, counts)
    t2 = build_pivot_block('Tổng của cân nặng', MT01_5_KHO, weights)
    t3 = build_pivot_block('Count of mã đơn', ALL_BUU_CUC_LIST, counts)
    t4 = build_pivot_block('Tổng của cân nặng', ALL_BUU_CUC_LIST, weights)

    all_rows = t1 + [blank_row] + t2 + [blank_row] + t3 + [blank_row] + t4
    return all_rows, date_labels[-1]

def run_b2b_report(send_telegram=True):
    print("=" * 60)
    print("🚀 BẮT ĐẦU QUY TRÌNH BÁO CÁO ĐƠN TẠO MT01 (18:00)")
    print("=" * 60)
    
    all_rows = None
    today_str = None

    # Bước 1: Thử lấy từ ThongKe qua Service Account nếu có
    if os.path.exists(CREDS_FILE):
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            creds = Credentials.from_service_account_file(
                CREDS_FILE,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            client = gspread.authorize(creds)
            sh = client.open_by_key('1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI')
            tk = sh.worksheet('ThongKe')
            candidate_rows = tk.get_all_values()

            now = datetime.now()
            expected_today = [
                f"{now.day}/{now.month}/{now.year}",
                f"{now.day:02d}/{now.month:02d}/{now.year}",
                f"{now.day}/{now.month:02d}/{now.year}",
                now.strftime("%d/%m/%Y")
            ]
            cur_header1 = candidate_rows[1] if len(candidate_rows) > 1 else []
            cur_dates = [c for c in cur_header1 if '/' in c]
            latest_in_sheet = cur_dates[-1] if cur_dates else ""
            if latest_in_sheet in expected_today:
                all_rows = candidate_rows
                print(f"✓ Nạp ThongKe từ Google Sheet thành công (ngày: {latest_in_sheet})")
            else:
                print(f"⚠️ ThongKe trên Sheet đang ở ngày cũ ({latest_in_sheet}) -> Tự động tính toán lại từ Data CSV!")
        except Exception as e_sa:
            print(f"⚠️ Service account xác thực không thành công ({e_sa}) -> Kích hoạt cơ chế Fallback tự động!")

    # Bước 2: Tự động Fallback sang tính toán trực tiếp từ Data CSV (100% không phụ thuộc Service Account)
    if not all_rows:
        try:
            all_rows, today_str = fetch_and_compute_b2b_tables()
            print("✓ Đã tính toán bảng thống kê độc lập thành công!")
        except Exception as e_comp:
            print(f"❌ Lỗi tính toán fallback: {e_comp}")
            return {"success": False, "error": str(e_comp)}

    # Table 1: Count of mã đơn (Phòng 1: 5 kho)
    t1 = []
    header1 = all_rows[1]
    num_cols = len([c for c in header1 if c.strip()])
    t1.append(header1[:num_cols])
    for r in all_rows[2:8]:
        t1.append(r[:num_cols])

    # Table 2: Tổng của cân nặng (Phòng 1: 5 kho)
    t2 = []
    header2 = all_rows[10]
    t2.append(header2[:num_cols])
    for r in all_rows[11:17]:
        t2.append(r[:num_cols])

    date_headers = [c for c in header1 if '/' in c]
    today_str = date_headers[-1] if date_headers else datetime.now().strftime("%d/%m/%Y")
    today_idx = header1.index(today_str)
    total_idx = header1.index("Tổng Cuối") if "Tổng Cuối" in header1 else -1

    so_don_today = t1[-1][today_idx]
    so_don_total = t1[-1][total_idx]
    can_nang_today = t2[-1][today_idx]
    can_nang_total = t2[-1][total_idx]

    print(f"✓ Ngày dữ liệu: {today_str}")
    print(f"✓ Số đơn: Hôm nay {so_don_today} đơn | Tổng {so_don_total} đơn")
    print(f"✓ Cân nặng: Hôm nay {can_nang_today} g | Tổng {can_nang_total} g")

    def build_table_html(rows, title):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
              background: #ffffff;
              padding: 24px;
              margin: 0;
            }}
            table {{
              border-collapse: collapse;
              width: 100%;
              border: 1px solid #dcdcdc;
              box-shadow: 0 4px 12px rgba(0,0,0,0.05);
              border-radius: 8px;
              overflow: hidden;
            }}
            th, td {{
              padding: 12px 14px;
              font-size: 14px;
              border-bottom: 1px solid #eee;
              border-right: 1px solid #f0f0f0;
              white-space: nowrap;
            }}
            th {{
              background: #f8fafc;
              font-weight: 600;
              color: #334155;
              text-align: center;
              border-bottom: 2px solid #cbd5e1;
            }}
            tr:nth-child(even) td {{
              background-color: #fafbfc;
            }}
            .title-row {{
              background: #1e293b !important;
              color: #ffffff !important;
              font-size: 18px;
              font-weight: 700;
              text-align: left;
              padding: 16px 20px;
              border: none;
            }}
            .total-row td {{
              background: #eff6ff !important;
              font-weight: 700;
              color: #1d4ed8;
              border-top: 2px solid #93c5fd;
            }}
            .today-col {{
              background-color: #fff8e1 !important;
              font-weight: bold;
            }}
            .text-left {{ text-align: left; }}
            .text-right {{ text-align: right; }}
            .text-center {{ text-align: center; font-weight: bold; }}
          </style>
        </head>
        <body>
          <table>
            <tr>
              <td colspan="{len(rows[0])}" class="title-row">📊 {title}</td>
            </tr>
            <tr>
        """
        for idx, col in enumerate(rows[0]):
            cls = ' class="today-col"' if idx == today_idx else ''
            html += f"<th{cls}>{col}</th>"
        html += "</tr>"
        
        for row in rows[1:]:
            is_total = ("Tổng Cuối" in row[1])
            tr_cls = ' class="total-row"' if is_total else ''
            html += f"<tr{tr_cls}>"
            for idx, val in enumerate(row):
                align = "text-center" if idx == 0 else ("text-left" if idx == 1 else "text-right")
                td_cls = f"{align}"
                if idx == today_idx and not is_total:
                    td_cls += " today-col"
                html += f'<td class="{td_cls}">{val}</td>'
            html += "</tr>"
            
        html += """
          </table>
        </body>
        </html>
        """
        return html

    html1 = build_table_html(t1, "Count of mã đơn")
    html2 = build_table_html(t2, "Tổng của cân nặng")

    img1_path = os.path.join(DIR_NAME, "b2b_so_don_latest.png")
    img2_path = os.path.join(DIR_NAME, "b2b_can_nang_latest.png")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        
        page.set_content(html1)
        page.locator("table").screenshot(path=img1_path)
        
        page.set_content(html2)
        page.locator("table").screenshot(path=img2_path)
        
        browser.close()

    print("✓ Đã render ảnh 2 bảng thành công!")

    if not send_telegram:
        return {"success": True, "today": today_str, "so_don": so_don_today, "can_nang": can_nang_today}

    send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    # Định dạng kg dễ đọc
    try:
        can_nang_today_num = int(str(can_nang_today).replace('.', '').replace(',', ''))
        can_nang_today_kg = f"{round(can_nang_today_num / 1000, 1):,}".replace(",", ".")
    except Exception:
        can_nang_today_kg = can_nang_today

    try:
        can_nang_total_num = int(str(can_nang_total).replace('.', '').replace(',', ''))
        can_nang_total_kg = f"{round(can_nang_total_num / 1000, 1):,}".replace(",", ".")
    except Exception:
        can_nang_total_kg = can_nang_total

    cap1 = f"""📊 <b>Data Đơn Tạo Miền Tây 01 (SỐ ĐƠN)</b>
- TỔNG SỐ ĐƠN : Ngày {today_str}
- Hôm nay: <b>{so_don_today}</b> đơn
- Tổng cộng: <b>{so_don_total}</b> đơn"""

    cap2 = f"""📊 <b>Data Đơn Tạo Miền Tây 01 (CÂN NẶNG)</b>
- TỔNG CÂN NẶNG : Ngày {today_str}
- Hôm nay: <b>{can_nang_today}</b> g (~{can_nang_today_kg} kg)
- Tổng cộng: <b>{can_nang_total}</b> g (~{can_nang_total_kg} kg)"""

    success_topics = []
    for top_id in TOPIC_IDS:
        try:
            with open(img1_path, "rb") as f1:
                res1 = requests.post(
                    send_url,
                    data={
                        "chat_id": CHAT_ID,
                        "message_thread_id": top_id,
                        "caption": cap1,
                        "parse_mode": "HTML"
                    },
                    files={"photo": f1},
                    timeout=25
                )
            with open(img2_path, "rb") as f2:
                res2 = requests.post(
                    send_url,
                    data={
                        "chat_id": CHAT_ID,
                        "message_thread_id": top_id,
                        "caption": cap2,
                        "parse_mode": "HTML"
                    },
                    files={"photo": f2},
                    timeout=25
                )
            if res1.status_code == 200 and res2.status_code == 200:
                success_topics.append(top_id)
                print(f"✓ Gửi Topic {top_id} thành công!")
            else:
                print(f"❌ Gửi Topic {top_id} lỗi: Photo 1 ({res1.status_code}), Photo 2 ({res2.status_code})")
        except Exception as e:
            print(f"❌ Lỗi gửi Telegram Topic {top_id}: {e}")

    return {
        "success": len(success_topics) > 0,
        "topics": success_topics,
        "today": today_str,
        "so_don": so_don_today,
        "can_nang": can_nang_today
    }

if __name__ == "__main__":
    send = ("--send" in sys.argv or "--dry-run" not in sys.argv)
    res = run_b2b_report(send_telegram=send)
    print("Kết quả:", res)

import os
import sys
import requests
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

DIR_NAME = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(DIR_NAME, "credentials.json")
if not os.path.exists(CREDS_FILE):
    CREDS_FILE = os.path.join(os.path.dirname(DIR_NAME), "tool_11h_bao_cao_telegram", "credentials.json")

BOT_TOKEN = "8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk"
CHAT_ID = "-1003940889949"
TOPIC_IDS = [506, 2690]  # Gửi Topic 506 (Báo cáo B2B) và Topic 2690 (Chỉ huy)

def run_b2b_report(send_telegram=True):
    print("=" * 60)
    print("🚀 BẮT ĐẦU QUY TRÌNH BÁO CÁO ĐƠN TẠO MT01 (18:00)")
    print("=" * 60)
    
    # 1. Fetch ThongKe from Google Sheet via Service Account (Không bao giờ hết hạn)
    creds = Credentials.from_service_account_file(
        CREDS_FILE,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    client = gspread.authorize(creds)
    sh = client.open_by_key('1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI')
    tk = sh.worksheet('ThongKe')
    all_rows = tk.get_all_values()

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
    today_str = date_headers[-1] if date_headers else "31/10/2026"
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
              font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
              background: #ffffff;
              margin: 0;
              padding: 16px;
              display: inline-block;
            }}
            table {{
              border-collapse: collapse;
              font-size: 13px;
              color: #111;
              background: #ffffff;
            }}
            .title-row {{
              font-weight: bold;
              font-size: 15px;
              padding: 8px 6px;
              border: none;
              text-align: left;
              background: #ffffff;
              color: #1a73e8;
            }}
            th {{
              background-color: #d2e3fc;
              font-weight: bold;
              border: 1px solid #707070;
              padding: 7px 12px;
              text-align: center;
              white-space: nowrap;
            }}
            td {{
              border: 1px solid #707070;
              padding: 7px 12px;
              white-space: nowrap;
            }}
            .total-row td {{
              background-color: #e8f0fe;
              font-weight: bold;
              color: #d93025;
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

    cap1 = f"""📊 <b>Data Đơn Tạo Miền Tây 01 (SỐ ĐƠN)</b>
- TỔNG SỐ ĐƠN : Ngày {today_str}
- Hôm nay: <b>{so_don_today}</b> đơn
- Tổng cộng: <b>{so_don_total}</b> đơn"""

    cap2 = f"""📊 <b>Data Đơn Tạo Miền Tây 01 (CÂN NẶNG)</b>
- TỔNG CÂN NẶNG : Ngày {today_str}
- Hôm nay: <b>{can_nang_today}</b> g
- Tổng cộng: <b>{can_nang_total}</b> g"""

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

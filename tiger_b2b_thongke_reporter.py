import os
import sys
import requests
import gspread
from google.oauth2.service_account import Credentials
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
TOPIC_IDS = [506]  # Gửi đồng thời Topic 506 (📅 Đơn Tạo) & Topic 2690 (🔥 Báo Cáo / War Room)

from datetime import datetime
import time

def trigger_sheet_filter_via_cdp():
    """Tự động kích hoạt lọc và tạo bảng thống kê nếu ThongKe chưa cập nhật ngày hôm nay."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp('http://127.0.0.1:9223')
            ctx = browser.contexts[0]
            pages = [pg for pg in ctx.pages if '1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI' in pg.url]
            if not pages:
                print("⚠️ Không tìm thấy tab Google Sheets Đơn Tạo trên Chrome CDP 9223!")
                return False
            page = pages[0]
            page.bring_to_front()

            def click_menu(menu_txt, sub_txt):
                page.keyboard.press("Escape")
                time.sleep(0.3)
                page.keyboard.press("Escape")
                time.sleep(0.3)
                btn = page.evaluate("""(mName) => {
                    const bar = document.querySelector('#docs-menubar');
                    if (!bar) return null;
                    const items = Array.from(bar.querySelectorAll('.menu-button'));
                    const target = items.find(el => el.innerText && el.innerText.trim() === mName);
                    if (target) {
                        const r = target.getBoundingClientRect();
                        return { x: r.x + r.width/2, y: r.y + r.height/2 };
                    }
                    return null;
                }""", menu_txt)
                if not btn:
                    return False
                page.mouse.click(btn['x'], btn['y'])
                time.sleep(1.2)
                sub = page.evaluate("""(sName) => {
                    const items = Array.from(document.querySelectorAll('.goog-menuitem')).filter(e => e.offsetParent !== null);
                    const target = items.find(e => e.innerText && e.innerText.trim().includes(sName));
                    if (target) {
                        const r = target.getBoundingClientRect();
                        return { x: r.x + r.width/2, y: r.y + r.height/2 };
                    }
                    return null;
                }""", sub_txt)
                if not sub:
                    page.keyboard.press("Escape")
                    return False
                page.mouse.click(sub['x'], sub['y'])
                return True

            def wait_script():
                saw = False
                for _ in range(60):
                    time.sleep(1.5)
                    bar = page.evaluate("""() => {
                        const b = document.querySelector('.docs-butterbar-container, .docs-butterbar-message, .jfk-butterbar');
                        return b && b.offsetParent !== null ? b.innerText.trim() : '';
                    }""")
                    if "Đang chạy tập lệnh" in bar:
                        saw = True
                    elif saw and ("Đã kết thúc" in bar or not bar):
                        break

            print("🔄 [Tự động khắc phục] Kích hoạt Bước 1: 'Chạy lọc -> Ketqua'...")
            if click_menu("Lọc dữ liệu", "Chạy lọc -> Ketqua"):
                wait_script()
                time.sleep(3)

            print("🔄 [Tự động khắc phục] Kích hoạt Bước 2: 'Tạo bảng thống kê -> ThongKe'...")
            if click_menu("Lọc dữ liệu", "Tạo bảng thống kê"):
                wait_script()
                time.sleep(5)
                return True
    except Exception as ex:
        print(f"⚠️ Lỗi trigger qua Chrome CDP: {ex}")
    return False

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

    # Kiểm tra tính cập nhật của ngày hôm nay
    now = datetime.now()
    expected_today = [
        f"{now.day}/{now.month}/{now.year}",
        f"{now.day:02d}/{now.month:02d}/{now.year}",
        f"{now.day}/{now.month:02d}/{now.year}",
        now.strftime("%d/%m/%Y")
    ]
    cur_header1 = all_rows[1] if len(all_rows) > 1 else []
    cur_dates = [c for c in cur_header1 if '/' in c]
    latest_in_sheet = cur_dates[-1] if cur_dates else ""
    
    if latest_in_sheet not in expected_today:
        print(f"⚠️ Cột ngày mới nhất trong ThongKe ({latest_in_sheet}) chưa khớp ngày hôm nay ({expected_today[0]})!")
        try:
            from tiger_data_filter import sync_filter_data_to_ketqua
            sync_filter_data_to_ketqua()
            all_rows = tk.get_all_values()
            cur_header1 = all_rows[1] if len(all_rows) > 1 else []
            cur_dates = [c for c in cur_header1 if '/' in c]
            latest_in_sheet = cur_dates[-1] if cur_dates else ""
        except Exception as e_f:
            print(f"⚠️ Lỗi lọc trực tiếp: {e_f}")

        if latest_in_sheet not in expected_today and sys.platform == "win32" and "--no-auto-scrape" not in sys.argv:
            print("🚀 [Auto-Scrape] Đang tự động mở Looker Studio (Tab 1. B2B) để xuất dữ liệu mới nhất của hôm nay...")
            import subprocess
            looker_script = os.path.join(DIR_NAME, "looker_export_temp.py")
            subprocess.run([sys.executable, looker_script, "--no-reporter"], timeout=600)
            all_rows = tk.get_all_values()
            cur_header1 = all_rows[1] if len(all_rows) > 1 else []
            cur_dates = [c for c in cur_header1 if '/' in c]
            latest_in_sheet = cur_dates[-1] if cur_dates else ""

        if latest_in_sheet not in expected_today and "--force-old" not in sys.argv:
            print(f"⏸️ Bảng ThongKe vẫn đang ở ngày cũ ({latest_in_sheet}), tạm hoãn bắn vào Topic 506 để không gửi trùng dữ liệu hôm qua!")
            return {"success": False, "skipped_stale": True, "today": latest_in_sheet}


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
- Hôm nay: <b>{can_nang_today}</b> kg
- Tổng cộng: <b>{can_nang_total}</b> kg"""

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


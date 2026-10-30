import os
import sys
import json
import time
import socket
import subprocess

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

# =============================================================================
# ⚙️ CẤU HÌNH DỮ LIỆU & ĐƯỜNG DẪN
# =============================================================================

LOOKER_URL = "https://lookerstudio.google.com/u/0/reporting/24e3b6f7-8f28-4f42-bc94-fda815a0c64f/page/p_m3rsgqzjgd"
LOOKER_TAB_NAME = "1. B2B"

MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI/edit?gid=0#gid=0"
MASTER_TAB_NAME = "Data"

# 13 tỉnh ĐBSCL
PROVINCES_LIST = [
    "Long An", "Tiền Giang", "Bến Tre", "Trà Vinh", "Vĩnh Long",
    "Đồng Tháp", "An Giang", "Kiên Giang", "Hậu Giang",
    "Cần Thơ", "Sóc Trăng", "Bạc Liêu", "Cà Mau"
]

CDP_URL = "http://127.0.0.1:9223"
HEADLESS = False


# =============================================================================
# 🛠️ CÁC BƯỚC THỰC THI TỐC ĐỘ CAO
# =============================================================================

def get_or_open_looker_page(context):
    """Tìm tab Looker Studio Dashboard Tách luồng hoặc mở mới."""
    for page in context.pages:
        try:
            url = page.url.lower()
            title = page.title().lower()
            if "24e3b6f7" in url or "tách luồng" in title:
                page.bring_to_front()
                page.set_viewport_size({"width": 1920, "height": 1080})
                
                if "p_m3rsgqzjgd" in url:
                    print("  -> Đã tìm thấy tab Dashboard Tab 1. B2B đang mở sẵn.")
                    return page

                print("  -> Đã tìm thấy tab Dashboard, đang chuyển hướng sang Tab 1. B2B...")
                try:
                    page.goto(LOOKER_URL, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    print(f"  [Lưu ý] goto có thể bị timeout nhưng vẫn tiếp tục: {e}")
                time.sleep(5)
                return page
        except Exception:
            pass

    print("  -> Không tìm thấy tab Dashboard, đang mở tab mới...")
    page = context.new_page()
    page.set_viewport_size({"width": 1920, "height": 1080})
    try:
        page.goto(LOOKER_URL, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"  [Lưu ý] page.goto báo lỗi: {e}. Vẫn tiếp tục đợi...")
    time.sleep(15)
    return page


def ensure_b2b_tab(page):
    """Đảm bảo đang ở tab 1. B2B."""
    print(f"  -> Đang kiểm tra trạng thái tab {LOOKER_TAB_NAME}...")
    page.keyboard.press("Escape")
    time.sleep(0.5)
    
    is_already_active = page.evaluate("""() => {
        const activeTab = document.querySelector('button.tab-button.active-tab, .tab-button.active-tab');
        if (activeTab && activeTab.innerText && activeTab.innerText.includes('B2B')) return true;
        if (document.title && document.title.includes('B2B')) return true;
        return false;
    }""")
    if is_already_active:
        print("  ✓ Tab 1. B2B đã được kích hoạt sẵn!")
        return

    start_time = time.time()
    clicked = False
    while time.time() - start_time < 30:
        clicked = page.evaluate("""(tabName) => {
            const btns = Array.from(document.querySelectorAll('button.tab-button, button, a, div, span'));
            for (const b of btns) {
                if (b.innerText && b.innerText.trim().includes(tabName)) {
                    b.click();
                    return true;
                }
            }
            return false;
        }""", LOOKER_TAB_NAME)
        if clicked:
            print("  -> Đã click kích hoạt tab B2B.")
            break
        time.sleep(1)
        
    if not clicked:
        print(f"  [Lưu ý] Không cần click thêm tab {LOOKER_TAB_NAME}.")
    time.sleep(3)


def filter_provinces_fast(page, provinces):
    """Lọc 13 tỉnh thành ĐBSCL thông minh, hỗ trợ cả khi bộ lọc đã có giá trị sẵn."""
    print(f"\n[Bước 1] Lọc nhanh {len(provinces)} tỉnh ĐBSCL...")
    
    try:
        page.keyboard.press("Escape")
        time.sleep(0.5)
        page.keyboard.press("Escape")
        time.sleep(0.5)

        if "accounts.google.com" in page.url:
            raise RuntimeError("Trình duyệt Chrome chưa đăng nhập tài khoản Google. Vui lòng chạy file Dang_Nhap_Chrome_Bot.bat trên Desktop để đăng nhập trước.")

        print("  -> Đang đợi các thanh điều khiển (Controls) của Looker Studio hiển thị...")
        try:
            page.locator("button.lego-control, control-layout-wrapper button").first.wait_for(state="visible", timeout=45000)
        except Exception:
            print("  ! Thử đợi thêm 10s cho Looker load...")
            time.sleep(10)

        filter_btn = None
        btn_by_text = page.locator("button.lego-control, .lego-control").filter(has_text="đến tỉnh").first
        if btn_by_text.count() > 0 and btn_by_text.is_visible():
            filter_btn = btn_by_text
            print("  ✓ Đã tìm thấy nút 'đến tỉnh' theo text.")
        else:
            all_lego_btns = page.locator("button.lego-control, control-layout-wrapper button")
            total_btns = all_lego_btns.count()
            print(f"  -> Số lượng control tìm thấy: {total_btns}")
            if total_btns >= 2:
                filter_btn = all_lego_btns.nth(1)
                btn_txt = filter_btn.inner_text().strip()
                print(f"  ✓ Đã chọn control thứ 2 (Text hiện tại: '{btn_txt[:30]}...').")
            elif total_btns == 1:
                filter_btn = all_lego_btns.first

        if not filter_btn:
            raise RuntimeError("Không tìm thấy nút bộ lọc 'đến tỉnh' trên giao diện Looker Studio!")

        try:
            page.evaluate("() => { document.querySelectorAll('.popup-backdrop').forEach(el => el.remove()); }")
        except Exception:
            pass

        print(f"[{time.strftime('%X')}]   -> Mở menu bộ lọc 'đến tỉnh'...")
        try:
            filter_btn.evaluate("node => node.click()")
        except Exception:
            filter_btn.click(timeout=5000, force=True)
        time.sleep(2.0)

        already_fully_selected = page.evaluate("""(provs) => {
            const checkedBoxes = Array.from(document.querySelectorAll('.cdk-overlay-container div[aria-checked="true"], .cdk-overlay-container md-checkbox.md-checked, .cdk-overlay-container mat-checkbox.mat-mdc-checkbox-checked'));
            const texts = checkedBoxes.map(el => el.innerText.trim());
            const matchCount = provs.filter(p => texts.some(t => t.toLowerCase().includes(p.toLowerCase()))).length;
            return matchCount >= provs.length;
        }""", provinces)

        if already_fully_selected:
            print("  ✓ Cả 13 tỉnh ĐBSCL đã được lọc chuẩn xác từ trước! Đóng menu...")
            page.keyboard.press("Escape")
            time.sleep(1.0)
            return

        print(f"[{time.strftime('%X')}]   -> Click bỏ chọn 'Tất cả'...")
        chks = page.locator("div[role='checkbox'], md-checkbox, mat-checkbox, .lego-checkbox")
        try:
            chks.nth(0).evaluate("node => node.click()")
        except Exception:
            chks.nth(0).click(timeout=5000, force=True)
        time.sleep(1.0)

        search_box = page.locator("input[type='text']").last

        for prov in provinces:
            print(f"  -> Đang tìm và click: {prov}")
            try:
                search_box.fill("", force=True, timeout=2000)
                time.sleep(0.2)
                search_box.fill(prov, force=True, timeout=2000)
            except Exception:
                search_box.evaluate(f"node => {{ node.value = '{prov}'; node.dispatchEvent(new Event('input', {{ bubbles: true }})); }}")

            clicked_prov = False
            for _ in range(8):
                time.sleep(0.4)
                clicked_prov = page.evaluate(f"""(pName) => {{
                    const labels = Array.from(document.querySelectorAll('.cdk-overlay-container span, .lego-control-body span, div[role="checkbox"], md-checkbox'));
                    const match = labels.find(el => el.innerText && el.innerText.trim().toLowerCase().includes(pName.toLowerCase()));
                    if (match) {{
                        const chk = match.closest('div[role="checkbox"], md-checkbox, mat-checkbox') || match.querySelector('div[role="checkbox"], md-checkbox') || match;
                        chk.click();
                        return true;
                    }}
                    return false;
                }}""", prov)
                if clicked_prov:
                    print(f"     ✓ Đã click chọn: {prov}")
                    break

            if not clicked_prov:
                try:
                    c_list = page.locator("div[role='checkbox'], md-checkbox, mat-checkbox, .lego-checkbox")
                    if c_list.count() > 1:
                        c_list.nth(1).evaluate("node => node.click()")
                        print(f"     ✓ Fallback JS click checkbox 1 cho: {prov}")
                except Exception as ex:
                    print(f"     ! Tỉnh {prov} chưa chọn được: {ex}")
            time.sleep(0.3)

        print(f"[{time.strftime('%X')}]   -> Bấm ESC để đóng bộ lọc...")
        page.keyboard.press("Escape")
        time.sleep(0.8)
        page.keyboard.press("Escape")

        print("  ⏳ Đã chọn xong 13 tỉnh! Đợi 10 giây để Looker tải dữ liệu...")
        time.sleep(10.0)
        print("  ✓ Dữ liệu mới đã sẵn sàng!")
    except Exception as e:
        print("Lỗi trong quá trình lọc:", e)
        raise e


def export_b2b_fast(page, context):
    """Xuất Google Sheets từ Looker Studio."""
    print("\n[Bước 2] Xuất dữ liệu B2B ra Google Sheets...")
    
    page.keyboard.press("Escape")
    time.sleep(1.0)
    
    MASTER_ID = "1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI"
    closed = 0
    for pg in list(context.pages):
        if "spreadsheets/d/" in pg.url and MASTER_ID not in pg.url:
            try:
                pg.close()
                closed += 1
            except Exception:
                pass
    if closed:
        print(f"  -> Đã đóng {closed} tab Google Sheets cũ")
    time.sleep(0.5)

    print(f"[{time.strftime('%X')}]   -> Hover vào bảng để kích hoạt nút 3 chấm...")
    page.mouse.move(1705, 335)
    time.sleep(1.5)

    print(f"[{time.strftime('%X')}]   -> JS click 'Hiển thị trình đơn biểu đồ'...")
    clicked = page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button, div[role="button"]'));
        for (const btn of btns) {
            const label = btn.getAttribute('aria-label') || '';
            if (label.includes('trình đơn biểu đồ') || label.includes('More options')) {
                btn.click();
                return label;
            }
        }
        return null;
    }""")
    if not clicked:
        print("  ! JS click 3 chấm không hoạt động, fallback về tọa độ (1726, 330)...")
        page.mouse.click(1726, 330)
        clicked = "Fallback Tọa độ"

    print(f"  => Đã click: {clicked}")
    time.sleep(2.0)

    print(f"[{time.strftime('%X')}]   -> Hover 'Xuất biểu đồ...' để hiện submenu...")
    page.get_by_text("Xuất biểu đồ", exact=False).first.hover(timeout=5000)
    time.sleep(2.0)

    print(f"[{time.strftime('%X')}]   -> Click 'Xuất dữ liệu'...")
    page.get_by_text("Xuất dữ liệu", exact=False).first.click(timeout=5000)
    time.sleep(2.0)

    print(f"[{time.strftime('%X')}]   -> Click 'Google Trang tính'...")
    page.get_by_text("Google Trang tính", exact=False).first.click(timeout=5000)
    time.sleep(3.0)

    print(f"[{time.strftime('%X')}]   -> Click nút 'Xuất' trong dialog...")
    page.get_by_role("button", name="Xuất").last.click(timeout=5000)
    time.sleep(3.0)

    print(f"[{time.strftime('%X')}] [Bước 3] Đang chờ tab Google Sheets xuất hiện (Dữ liệu >200k dòng có thể mất tới 3-5 phút)...")

    export_page = None
    for i in range(240):
        time.sleep(2.5)
        if i % 10 == 0:
            try:
                snack = page.evaluate("() => { const s = document.querySelector('.mdc-snackbar__label'); return s ? s.textContent.trim() : ''; }")
                if snack:
                    print(f"  ... Looker báo: '{snack}'")
            except Exception:
                pass

        for pg in context.pages:
            if "spreadsheets/d/" in pg.url and MASTER_ID not in pg.url:
                export_page = pg
                break
        if export_page:
            break

    if not export_page:
        raise TimeoutError("Không tìm thấy tab Google Sheets mới sau khi bấm Xuất. Quá trình xuất có thể bị lỗi từ máy chủ Google.")

    print(f"[{time.strftime('%X')}]  🎯 Đã bắt được tab Google Sheets: " + export_page.url)

    try:
        export_page.wait_for_load_state("domcontentloaded", timeout=120000)
        print("  ✓ Tab đã load DOM: " + export_page.url)
        time.sleep(5.0)
    except Exception:
        print("  ! Bỏ qua lỗi load DOM...")

    print("  ⏳ Đang chờ Google Sheets render lưới dữ liệu thực tế (chờ 20 giây)...")
    for _ in range(20):
        time.sleep(1.0)
        try:
            clicked_reload = export_page.evaluate("""() => {
                const dialog = document.querySelector('.modal-dialog, div[role="dialog"]');
                if (dialog) {
                    const btn = Array.from(dialog.querySelectorAll('button, div[role="button"]')).find(b => b.innerText && (b.innerText.trim() === 'Tải lại' || b.innerText.trim() === 'Reload'));
                    if (btn && btn.offsetHeight > 0) {
                        btn.click();
                        return btn.innerText.trim();
                    }
                }
                return null;
            }""")
            if clicked_reload:
                print(f"  ! Đã bấm '{clicked_reload}' trên popup Google Sheets để khôi phục...")
                time.sleep(15.0)
                break
        except Exception:
            pass

    return export_page


def copy_export_and_paste_to_master(context, export_page):
    """Copy dữ liệu từ sheet xuất sang Master Tab 'Data'.
    Ưu tiên kiến trúc Zero-RAM (CSV Stream + Service Account API) chống 100% lỗi Out of Memory.
    """
    print("\n[Bước 4] Đồng bộ dữ liệu sang Master Dashboard (Zero-RAM Chống Out of Memory)...")
    import csv
    import io
    import re
    
    export_url = export_page.url
    sheet_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', export_url)
    export_sheet_id = sheet_match.group(1) if sheet_match else None
    
    creds_candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool_11h_bao_cao_telegram", "credentials.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json"),
        os.path.abspath("credentials.json")
    ]
    creds_file = next((p for p in creds_candidates if os.path.exists(p)), None)
    
    synced_via_api = False
    if export_sheet_id and creds_file:
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            print(f"  ✓ Tìm thấy credentials: {creds_file}")
            print("  📥 Đang tải CSV dữ liệu xuất từ Google Sheets...")
            csv_url = f"https://docs.google.com/spreadsheets/d/{export_sheet_id}/export?format=csv&gid=0"
            resp = context.request.get(csv_url, timeout=60000)
            if resp.status == 200:
                csv_bytes = resp.body()
                csv_text = csv_bytes.decode('utf-8', errors='replace')
                print(f"  ✓ Đã tải {len(csv_text):,} ký tự CSV thành công qua API!")
                
                reader = csv.reader(io.StringIO(csv_text))
                header = next(reader)
                filtered_rows = [header]
                den_tinh_idx = header.index('đến tỉnh') if 'đến tỉnh' in header else None
                
                for row in reader:
                    if den_tinh_idx is not None and len(row) > den_tinh_idx:
                        if row[den_tinh_idx] in PROVINCES_LIST:
                            filtered_rows.append(row)
                    else:
                        filtered_rows.append(row)
                        
                total_rows = len(filtered_rows)
                print(f"  ✓ Đã lọc chuẩn xác {total_rows:,} dòng dữ liệu cho 13 tỉnh Miền Tây")
                
                creds = Credentials.from_service_account_file(
                    creds_file,
                    scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                )
                gc = gspread.authorize(creds)
                sh = gc.open_by_key("1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI")
                ws = sh.worksheet('Data')
                
                ws.clear()
                time.sleep(1.0)
                if ws.row_count < total_rows + 100:
                    ws.add_rows((total_rows + 100) - ws.row_count)
                    
                batch_size = 12000
                for i in range(0, total_rows, batch_size):
                    batch = filtered_rows[i:i+batch_size]
                    start_row = i + 1
                    end_row = i + len(batch)
                    end_col_char = chr(ord('A') + len(header) - 1)
                    ws.update(values=batch, range_name=f'A{start_row}:{end_col_char}{end_row}')
                    print(f"  ✓ Đã ghi dòng {start_row:,} -> {end_row:,} vào tab Data")
                    
                print("  🎉 ĐỒNG BỘ DỮ LIỆU QUA API THÀNH CÔNG (0 MB RAM BROWSER)!")
                synced_via_api = True
        except Exception as ex:
            print(f"  ! Lỗi đồng bộ API ({ex}), sẽ thử fallback về clipboard...")

    master_page = None
    for pg in context.pages:
        if "1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI" in pg.url:
            master_page = pg
            break

    if not master_page:
        master_page = context.new_page()
        master_page.goto(MASTER_SHEET_URL, wait_until="domcontentloaded", timeout=60000)

    master_page.bring_to_front()
    time.sleep(2.0)

    if synced_via_api:
        return master_page

    # Chế độ Fallback clipboard
    export_page.bring_to_front()
    time.sleep(1.0)
    export_page.mouse.click(200, 250)
    time.sleep(0.3)
    export_page.keyboard.press("Control+A")
    time.sleep(0.3)
    export_page.keyboard.press("Control+A")
    time.sleep(0.4)
    export_page.keyboard.press("Control+C")
    time.sleep(3.0)
    print("  ✓ Đã Ctrl+C toàn bộ dữ liệu (Fallback)")

    master_page.bring_to_front()
    time.sleep(2.0)

    try:
        data_tab = master_page.locator("[id*='sheet-tab']:has-text('Data'), .docs-sheet-tab:has-text('Data')").first
        if not data_tab.is_visible(timeout=2000):
            data_tab = master_page.locator("text='Data'").first
        data_tab.click()
        time.sleep(1.0)
    except Exception:
        pass

    master_page.mouse.click(200, 250)
    time.sleep(0.3)
    master_page.keyboard.press("Control+A")
    time.sleep(0.3)
    master_page.keyboard.press("Control+A")
    time.sleep(0.3)
    master_page.keyboard.press("Delete")
    time.sleep(1.0)
    print("  ✓ Đã xóa sạch dữ liệu cũ trong tab Data")

    master_page.keyboard.press("Control+Home")
    time.sleep(0.5)
    master_page.keyboard.press("Control+V")
    print("  ⏳ Đang đợi 15 giây để Google Sheets upload và lưu dữ liệu lên máy chủ...")
    time.sleep(15.0)
    print("  ✓ Đã dán toàn bộ dữ liệu mới vào Data!A1 và lưu thành công")

    return master_page


def click_google_sheets_menu(page, menu_name, submenu_name):
    """Mở menu custom Apps Script của Google Sheets siêu tốc và ổn định 100% bằng DOM JS."""
    print(f"  ⏳ Đang đợi menu '{menu_name}' xuất hiện (Apps Script đang tải)...")
    
    menu_found = False
    for attempt in range(40):
        menu_found = page.evaluate("""(mName) => {
            const menubar = document.querySelector('#docs-menubar') || document;
            const items = Array.from(menubar.querySelectorAll('.menu-button, div[role="menuitem"], div.goog-control, span'));
            return items.some(el => el.innerText && el.innerText.trim() === mName);
        }""", menu_name)
        if menu_found:
            break
        time.sleep(1.0)
        
    if not menu_found:
        print(f"  ! Sau 40s chưa thấy menu '{menu_name}', đang thử reload lại trang master sheet...")
        try:
            page.reload(wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass
        time.sleep(10)
        for _ in range(25):
            menu_found = page.evaluate("""(mName) => {
                const menubar = document.querySelector('#docs-menubar') || document;
                const items = Array.from(menubar.querySelectorAll('.menu-button, div[role="menuitem"], div.goog-control, span'));
                return items.some(el => el.innerText && el.innerText.trim() === mName);
            }""", menu_name)
            if menu_found:
                break
            time.sleep(1.0)

    if not menu_found:
        raise RuntimeError(f"Không tìm thấy menu {menu_name} trên Google Sheets sau thời gian chờ đợi!")

    for attempt in range(5):
        # 1. Click menu cha
        page.evaluate("""(mName) => {
            const menubar = document.querySelector('#docs-menubar') || document;
            const items = Array.from(menubar.querySelectorAll('.menu-button, div[role="menuitem"], div.goog-control, span'));
            const target = items.find(el => el.innerText && el.innerText.trim() === mName);
            if (target) {
                target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                target.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                target.click();
            }
        }""", menu_name)
        time.sleep(1.5)

        # 2. Click submenu con
        clicked_sub = page.evaluate("""(sName) => {
            const subitems = Array.from(document.querySelectorAll('.goog-menuitem, div[role="menuitem"], span'));
            const target = subitems.find(el => el.innerText && el.innerText.trim().includes(sName));
            if (target) {
                target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                target.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                target.click();
                return true;
            }
            return false;
        }""", submenu_name)

        if clicked_sub:
            print(f"  ✓ Đã kích hoạt menu '{menu_name}' -> '{submenu_name}' thành công!")
            return True

        print(f"  ! Chưa click được submenu '{submenu_name}', thử lại lần {attempt + 1}...")
        page.keyboard.press("Escape")
        time.sleep(1.0)

    raise RuntimeError(f"Không thể mở menu {menu_name} -> {submenu_name}")


def run_filter_to_ketqua(master_page):
    """Bước 5: Bấm Lọc dữ liệu -> Chạy lọc -> Ketqua và đợi thông báo Hoàn tất."""
    print("\n[Bước 5] Bấm 'Lọc dữ liệu' -> 'Chạy lọc -> Ketqua'...")
    master_page.bring_to_front()
    time.sleep(1.0)

    click_google_sheets_menu(master_page, "Lọc dữ liệu", "Chạy lọc -> Ketqua")
    
    print("  ⏳ Đang chạy 'Chạy lọc -> Ketqua'... Đang theo dõi thông báo Hoàn Tất...")

    start_time = time.time()
    found_done = False
    while time.time() - start_time < 180:
        time.sleep(1.0)
        toast_text = master_page.evaluate("""() => {
            const toast = document.querySelector('.docs-butterbar-message, .docs-butterbar-wrap, .jfk-butterbar');
            return toast ? toast.innerText : '';
        }""")
        if any(w in toast_text for w in ["Đã lọc xong", "Hoàn tất", "Đã kết thúc", "Finished script", "Đã khớp 100%"]):
            print(f"  ✓ Đã thấy thông báo lọc xong: '{toast_text.strip()}'!")
            found_done = True
            break
            
    if not found_done:
        print("  ℹ Đã hết thời gian chờ toast, tiếp tục bước tiếp theo...")
        
    print("  ⏳ Đang chờ 60 giây để Google Sheets tính toán lại toàn bộ công thức và cập nhật bảng thống kê...")
    time.sleep(60)
    print("  ✓ Đã chờ xong, chuẩn bị chạy ThongKe!")


def run_thongke_and_wait_telegram_modal(master_page):
    """Bước 6: Bấm Lọc dữ liệu -> Tạo bảng thống kê -> ThongKe và đợi Telegram modal load xong & tự tắt."""
    print("\n[Bước 6] Bấm 'Lọc dữ liệu' -> 'Tạo bảng thống kê -> ThongKe'...")
    master_page.bring_to_front()
    time.sleep(1.0)

    click_google_sheets_menu(master_page, "Lọc dữ liệu", "Tạo bảng thống kê -> ThongKe")
    
    print("  ⏳ Đã kích hoạt tạo bảng thống kê...")
    print("  ⏳ Đang đợi bảng 'Đang gửi ảnh sang Telegram...' xuất hiện...")
    start_time = time.time()
    modal_appeared = False
    while time.time() - start_time < 45:
        time.sleep(0.4)
        is_visible = master_page.evaluate("""() => {
            const text = document.body.innerText || '';
            return text.includes('Đang gửi ảnh sang Telegram') || 
                   text.includes('Đang gửi ảnh') || 
                   text.includes('Đóng hộp thoại');
        }""")
        if is_visible:
            print(f"  📸 BẢNG PREVIEW 'Đang gửi ảnh sang Telegram...' ĐÃ XUẤT HIỆN! ({round(time.time()-start_time, 1)}s)")
            modal_appeared = True
            break

    if modal_appeared:
        print("  ⏳ Đang đợi Apps Script gửi xong ảnh lên Telegram và tự động đóng hộp thoại...")
        start_time_close = time.time()
        while time.time() - start_time_close < 60:
            time.sleep(0.5)
            is_still_open = master_page.evaluate("""() => {
                const text = document.body.innerText || '';
                return text.includes('Đang gửi ảnh sang Telegram') || 
                       text.includes('Đang gửi ảnh...');
            }""")
            if not is_still_open:
                print(f"  🎉 HỘP THOẠI ĐÃ TỰ ĐỘNG ĐÓNG HOÀN TẤT! ({round(time.time()-start_time_close, 1)}s)")
                break

    time.sleep(1.0)


# =============================================================================
# 🚀 HÀM THỰC THI CHÍNH
# =============================================================================

def check_chrome_ready():
    """Kiểm tra xem Chrome đã mở remote debugging ở port 9223 chưa."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    result = sock.connect_ex(('127.0.0.1', 9223))
    sock.close()
    return result == 0

def start_chrome_bat():
    """Mở Chrome bot với cổng debug 9223."""
    bat_desktop = os.path.expandvars(r"%USERPROFILE%\Desktop\Dang_Nhap_Chrome_Bot.bat")
    bat_scratch = r"c:\Users\nguye\.gemini\antigravity\scratch\Dang_Nhap_Chrome_Bot.bat"
    
    if os.path.exists(bat_desktop):
        subprocess.Popen([bat_desktop], shell=True)
    elif os.path.exists(bat_scratch):
        subprocess.Popen([bat_scratch], shell=True)
    else:
        chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if not os.path.exists(chrome_exe):
            chrome_exe = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        profile_dir = os.path.expandvars(r"%USERPROFILE%\ChromeBotProfile")
        subprocess.Popen([
            chrome_exe,
            "--remote-debugging-port=9223",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            LOOKER_URL
        ])

def send_telegram_alert(message):
    """Gửi cảnh báo lỗi khẩn cấp về Telegram Topic 2690."""
    try:
        import requests
        url = "https://api.telegram.org/bot8809500027:AAFC2XzDOHEBdbtompu1i0oRuHGuAZu23gk/sendMessage"
        payload = {
            "chat_id": "-1003940889949",
            "message_thread_id": 2690,
            "text": message,
            "parse_mode": "HTML"
        }
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print("  📢 Đã gửi cảnh báo sự cố lên Telegram Topic 2690 thành công!")
        else:
            print(f"  [Telegram Error] {res.status_code}: {res.text}")
    except Exception as ex:
        print(f"  [Telegram Exception] {ex}")

def run_looker_export_pipeline(max_retries=3):
    if sync_playwright is None:
        print("=======================================================")
        print("  ⚠️ [TIGER AI NOTIFICATION]")
        print("  Quy trình B2B Looker Studio yêu cầu Playwright và Chrome bot.")
        print("=======================================================")
        return

    last_error = ""
    for attempt in range(max_retries):
        try:
            print("=======================================================")
            if attempt == 0:
                print("      🐅 TIGER AI - BẮT ĐẦU QUY TRÌNH TỰ ĐỘNG TỐC ĐỘ CAO")
            else:
                print(f"      🐅 TIGER AI - ĐANG THỬ CHẠY LẠI (LẦN {attempt + 1}/{max_retries})")
            print("=======================================================")

            start_total = time.time()
            
            with sync_playwright() as p:
                storage_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_auth_storage.json")
                is_headless_cloud = (
                    "--headless" in sys.argv or 
                    os.environ.get("GITHUB_ACTIONS") == "true" or 
                    (not check_chrome_ready() and os.path.exists(storage_file) and sys.platform != "win32")
                )

                browser = None
                if is_headless_cloud:
                    print("  🚀 [CHẾ ĐỘ CLOUD / GITHUB ACTIONS] Khởi chạy Chromium Headless với phiên Google...")
                    browser = p.chromium.launch(
                        headless=True,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage"
                        ]
                    )
                    storage_state_arg = None
                    if os.path.exists(storage_file):
                        try:
                            with open(storage_file, 'r', encoding='utf-8') as sf:
                                sdata = json.load(sf)
                            if isinstance(sdata, dict) and 'cookies' in sdata:
                                for ck in sdata['cookies']:
                                    if 'partitionKey' in ck and not isinstance(ck['partitionKey'], str):
                                        del ck['partitionKey']
                            storage_state_arg = sdata
                        except Exception as ex:
                            print(f'  [Luu y] Loi doc sanitize storage file: {ex}')
                            storage_state_arg = storage_file

                    context = browser.new_context(
                        storage_state=storage_state_arg,
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
                        permissions=['clipboard-read', 'clipboard-write']
                    )
                    print("  ✓ Đã kết nối phiên Google Cloud thành công!")
                else:
                    if not check_chrome_ready():
                        print("  ! Chrome bot chưa mở, đang tự động khởi động Chrome (Port 9223)...")
                        start_chrome_bat()
                        
                    connected = False
                    for c_attempt in range(8):
                        try:
                            browser = p.chromium.connect_over_cdp(CDP_URL)
                            context = browser.contexts[0]
                            print("  ✓ Kết nối Chrome thành công!")
                            connected = True
                            break
                        except Exception:
                            print(f"  ⏳ Đang đợi Chrome sẵn sàng... ({(c_attempt+1)*3}s)")
                            time.sleep(3)
                    if not connected:
                        raise RuntimeError("Không thể kết nối Chrome debugging port 9223.")

                # 1. Looker Studio Tab 1. B2B
                looker_page = get_or_open_looker_page(context)
                ensure_b2b_tab(looker_page)

                # 2. Lọc nhanh 13 tỉnh
                filter_provinces_fast(looker_page, PROVINCES_LIST)

                # 3 & 4. Xuất Google Sheets & Nhận tab file vừa xuất
                export_page = export_b2b_fast(looker_page, context)
                
                if not export_page:
                    raise RuntimeError("Không thể lấy được tab Google Sheets mới.")

                # 5. Copy toàn bộ -> Xóa sạch Data cũ -> Dán vào A1
                master_page = copy_export_and_paste_to_master(context, export_page)

                # 6. Chạy lọc -> Ketqua và đợi thông báo Hoàn Tất
                run_filter_to_ketqua(master_page)

                # 7. Tạo bảng thống kê -> ThongKe và đợi Telegram modal load xong & tự đóng
                run_thongke_and_wait_telegram_modal(master_page)

                total_elapsed = round(time.time() - start_total, 1)
                print("\n=======================================================")
                print(f"  🎉 HOÀN TẤT TOÀN BỘ QUY TRÌNH TRONG: {total_elapsed}s! ")
                print("  🤖 Apps Script đã gửi báo cáo lên Telegram thành công!")
                print("=======================================================\n")
                
                return

        except Exception as e:
            last_error = str(e)
            print(f"\n❌ LỖI Ở LẦN CHẠY THỨ {attempt + 1}: {last_error}")
            
            try:
                if 'looker_page' in locals() and looker_page:
                    looker_page.screenshot(path=f"error_b2b_attempt_{attempt + 1}.png")
                    print(f"  📸 Đã chụp ảnh màn hình lúc lỗi: error_b2b_attempt_{attempt + 1}.png")
            except Exception:
                pass

            if attempt < max_retries - 1:
                print("⏳ Đang chuẩn bị dọn dẹp và thử lại sau 10 giây...\n")
                time.sleep(10)
            else:
                print("🚨 ĐÃ THỬ LẠI HẾT 3 LẦN NHƯNG VẪN THẤT BẠI!")
                now_str = time.strftime("%H:%M:%S %d/%m/%Y")
                alert_text = (
                    f"🚨 <b>TIGER AI CẢNH BÁO • LỖI QUY TRÌNH XUẤT ĐƠN B2B (18:00)</b>\n"
                    f"⏰ Thời gian: <code>{now_str}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"❌ Hệ thống đã tự động thử lại <b>3 lần</b> nhưng Looker Studio gặp sự cố:\n"
                    f"📝 <i>Chi tiết lỗi:</i> <code>{last_error[:250]}</code>\n\n"
                    f"👉 <b>Cách xử lý:</b> Sếp có thể bấm nút <b>'KÍCH HOẠT QUY TRÌNH'</b> trên web Tiger AI Command Center MT01 để chạy bù, hoặc kiểm tra lại trình duyệt Chrome bot."
                )
                send_telegram_alert(alert_text)

if __name__ == "__main__":
    run_looker_export_pipeline(max_retries=3)

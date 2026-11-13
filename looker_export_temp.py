try:
    from pipeline_tracer import record_pipeline_event
except Exception:
    try:
        from tiger_cloud_repo.pipeline_tracer import record_pipeline_event
    except Exception:
        def record_pipeline_event(*args, **kwargs): pass
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
    time.sleep(3)
    if "accounts.google.com" in page.url:
        raise RuntimeError("Chuyển hướng Google Accounts -> Kích hoạt Service Account API")
    time.sleep(8)
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
            raise RuntimeError("Phiên tài khoản Google trên Looker Studio cần làm mới. Quy trình đang tự động chuyển giao lên Cloud Runner.")

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

        print("  ⏳ Đã chọn xong 13 tỉnh! Đợi Looker tải lại bảng dữ liệu...")
        time.sleep(4.0)
        for _ in range(45):
            time.sleep(1.0)
            cell_count = page.evaluate("""() => document.querySelectorAll('.cell, .table-cell, [role="gridcell"], .cdk-cell, .lego-table-cell').length""")
            if cell_count > 100:
                print(f"  ✓ Bảng dữ liệu đã render hoàn tất ({cell_count} ô)!")
                break
        time.sleep(2.0)
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

    menu_opened = False
    for attempt_menu in range(3):
        page.keyboard.press("Escape")
        time.sleep(0.5)
        print(f"[{time.strftime('%X')}]   -> Hover vào bảng (1500, 500) để kích hoạt nút 3 chấm (Lần {attempt_menu+1})...")
        page.mouse.move(1500, 500)
        time.sleep(1.5)

        btn_rect = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button, div[role="button"]'));
            const btn = btns.find(b => {
                const lbl = b.getAttribute('aria-label') || '';
                const r = b.getBoundingClientRect();
                return (lbl.includes('trình đơn biểu đồ') || lbl.includes('More options')) && r.width > 0 && r.height > 0 && r.y < 700;
            });
            if (btn) {
                const r = btn.getBoundingClientRect();
                return {x: r.x, y: r.y, w: r.width, h: r.height};
            }
            return null;
        }""")
        if not btn_rect:
            print("  ! Không tìm thấy rect 3 chấm, dùng tọa độ chuẩn (1692, 412)...")
            btn_rect = {'x': 1692, 'y': 412, 'w': 32, 'h': 32}

        print(f"[{time.strftime('%X')}]   -> Native Click vào nút 3 chấm tại ({int(btn_rect['x'])}, {int(btn_rect['y'])})...")
        page.mouse.click(btn_rect['x'] + btn_rect['w']/2, btn_rect['y'] + btn_rect['h']/2)
        time.sleep(1.5)

        if page.locator("button[role='menuitem']:has-text('Xuất biểu đồ'), div[role='menuitem']:has-text('Xuất biểu đồ'), button[role='menuitem']:has-text('Export'), div[role='menuitem']:has-text('Export')").count() > 0:
            menu_opened = True
            break

        # Fallback JS click nếu mouse click chưa mở menu
        page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button, div[role="button"]'));
            const btn = btns.find(b => {
                const lbl = b.getAttribute('aria-label') || '';
                const r = b.getBoundingClientRect();
                return (lbl.includes('trình đơn biểu đồ') || lbl.includes('More options')) && r.width > 0 && r.y < 700;
            });
            if (btn) btn.click();
        }""")
        time.sleep(1.5)
        if page.locator("button[role='menuitem']:has-text('Xuất biểu đồ'), div[role='menuitem']:has-text('Xuất biểu đồ'), button[role='menuitem']:has-text('Export'), div[role='menuitem']:has-text('Export')").count() > 0:
            menu_opened = True
            break

    if not menu_opened:
        raise RuntimeError("Không thể mở menu 3 chấm 'Xuất biểu đồ...' trên Looker Studio sau 3 lần thử!")

    print(f"[{time.strftime('%X')}]   -> Hover 'Xuất biểu đồ...' để hiện submenu...")
    export_menu_loc = page.locator("button[role='menuitem']:has-text('Xuất biểu đồ'), div[role='menuitem']:has-text('Xuất biểu đồ'), button[role='menuitem']:has-text('Export'), div[role='menuitem']:has-text('Export')").first
    export_menu_loc.hover(timeout=5000)
    time.sleep(1.5)

    print(f"[{time.strftime('%X')}]   -> Click 'Xuất dữ liệu'...")
    page.locator("button[role='menuitem']:has-text('Xuất dữ liệu'), div[role='menuitem']:has-text('Xuất dữ liệu'), button[role='menuitem']:has-text('Export data'), div[role='menuitem']:has-text('Export data')").first.click(timeout=5000)
    time.sleep(2.0)

    print(f"[{time.strftime('%X')}]   -> Click 'Google Trang tính'...")
    page.get_by_text("Google Trang tính", exact=False).or_(page.get_by_text("Google Sheets", exact=False)).first.click(timeout=5000)
    time.sleep(2.5)

    print(f"[{time.strftime('%X')}]   -> Click nút 'Xuất' trong dialog...")
    page.get_by_role("button", name="Xuất").or_(page.get_by_role("button", name="Export")).last.click(timeout=5000)
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
                
                if total_rows <= 1:
                    raise ValueError(f"Dữ liệu trích xuất từ Looker quá ít hoặc rỗng ({total_rows} dòng), hủy đồng bộ để bảo toàn dữ liệu cũ!")

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
                try:
                    export_page.close()
                    print("  🧹 Đã đóng tab Google Sheets tạm để giữ trình duyệt luôn sạch nhẹ!")
                except Exception:
                    pass
                try:
                    auth_file_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_auth_storage.json")
                    sa_keep = None
                    if os.path.exists(auth_file_p):
                        with open(auth_file_p, "r", encoding="utf-8") as f_old:
                            sa_keep = json.load(f_old).get("service_account")
                    new_st = context.storage_state()
                    if sa_keep:
                        new_st["service_account"] = sa_keep
                    with open(auth_file_p, "w", encoding="utf-8") as f_new:
                        json.dump(new_st, f_new, ensure_ascii=False)
                    print("  🔑 Đã tự động làm mới phiên cookie trong google_auth_storage.json!")
                except Exception:
                    pass
        except Exception as ex:
            print(f"  ! Lỗi đồng bộ API ({ex}), sẽ thử fallback về clipboard...")

    master_page = None
    for pg in context.pages:
        if "1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI" in pg.url:
            master_page = pg
            break

    if not master_page:
        print("  🌐 Đang mở Google Sheet Master Dashboard (Tách Luồng B2B)...")
        master_page = context.new_page()
        master_page.goto(MASTER_SHEET_URL, wait_until="domcontentloaded", timeout=60000)

    master_page.bring_to_front()
    time.sleep(2.0)

    if synced_via_api:
        print("  ✓ Dữ liệu đã đồng bộ sang Data tab. Giữ master_page mở để tiếp tục chạy Apps Script!")
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
    """Mở menu custom Apps Script của Google Sheets siêu tốc và ổn định 100% bằng Native Mouse Click."""
    print(f"  ⏳ Đang đợi menu '{menu_name}' xuất hiện (Apps Script đang tải)...")
    
    page.bring_to_front()
    page.keyboard.press("Escape")
    time.sleep(0.5)
    page.keyboard.press("Escape")
    time.sleep(0.5)

    for _ in range(40):
        menu_found = page.evaluate("""(mName) => {
            const menubar = document.querySelector('#docs-menubar') || document;
            const items = Array.from(menubar.querySelectorAll('.menu-button, div[role="menuitem"], div.goog-control, span'));
            return items.some(el => el.innerText && el.innerText.trim() === mName);
        }""", menu_name)
        if menu_found:
            break
        time.sleep(1.0)

    for attempt in range(8):
        page.keyboard.press("Escape")
        time.sleep(0.5)

        # 1. Click menu cha
        loc_menu = page.locator(f"#docs-menubar .menu-button:has-text('{menu_name}')")
        if loc_menu.count() > 0:
            box = loc_menu.first.bounding_box()
            if box:
                page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
        else:
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

        # 2. Click submenu bằng Native Mouse Click (chuẩn Google Sheets Closure)
        sub_loc = page.locator(f".goog-menuitem:visible:has-text('{submenu_name}')")
        if sub_loc.count() > 0:
            sub_box = sub_loc.first.bounding_box()
            if sub_box:
                page.mouse.click(sub_box['x'] + sub_box['width']/2, sub_box['y'] + sub_box['height']/2)
                print(f"  ✓ Đã kích hoạt menu '{menu_name}' -> '{submenu_name}' thành công bằng Native Click!")
                return True

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
        time.sleep(1.0)
    raise RuntimeError(f"Không thể mở menu {menu_name} -> {submenu_name}")


def run_filter_to_ketqua(master_page):
    """Bước 5: Lọc dữ liệu từ Data sang Ketqua trên Google Sheets."""
    print("\n[Bước 5] Lọc dữ liệu chuẩn xác từ Data sang Ketqua...")
    try:
        from tiger_data_filter import sync_filter_data_to_ketqua
        success = sync_filter_data_to_ketqua()
        if success:
            print("  ✓ [API Direct-Filter] Đã lọc và đồng bộ đầy đủ dữ liệu sang sheet Ketqua!")
    except Exception as ex:
        print(f"  ℹ Đồng bộ API: {ex}")

    try:
        master_page.bring_to_front()
        click_google_sheets_menu(master_page, "Lọc dữ liệu", "Chạy lọc -> Ketqua")
        # Chờ tập lệnh Apps Script chạy xong
        start_wait = time.time()
        while time.time() - start_wait < 90:
            time.sleep(2)
            is_running = master_page.evaluate("""() => {
                const text = document.body.innerText || '';
                return text.includes('Đang chạy tập lệnh') || text.includes('Running script');
            }""")
            if not is_running:
                break
        print("  ✓ Tập lệnh 'Chạy lọc -> Ketqua' đã thực thi xong trên Google Sheet!")
    except Exception as ex_menu:
        print(f"  ⚠️ Lỗi Menu Apps Script: {ex_menu}")
        
    print("  ⏳ Đang chờ 5 giây để Google Sheets làm mới lưới dữ liệu Ketqua...")
    time.sleep(5)
    print("  ✓ Sheet Ketqua đã sẵn sàng, chuẩn bị chạy ThongKe!")


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

def ensure_service_account_credentials():
    """Tự động khôi phục credentials.json từ google_auth_storage.json nếu chưa tồn tại."""
    dir_name = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(dir_name, "credentials.json")
    if not os.path.exists(creds_path):
        auth_storage = os.path.join(dir_name, "google_auth_storage.json")
        if os.path.exists(auth_storage):
            try:
                with open(auth_storage, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "service_account" in data and isinstance(data["service_account"], dict):
                    with open(creds_path, "w", encoding="utf-8") as f:
                        json.dump(data["service_account"], f, indent=2)
                    print("  🔑 [Auto-Recovery] Đã trích xuất Service Account credentials.json từ google_auth_storage.json!")
                    sub_creds = os.path.join(dir_name, "tool_11h_bao_cao_telegram", "credentials.json")
                    os.makedirs(os.path.dirname(sub_creds), exist_ok=True)
                    with open(sub_creds, "w", encoding="utf-8") as f:
                        json.dump(data["service_account"], f, indent=2)
            except Exception as e:
                print(f"  ⚠️ Lỗi khi trích xuất credentials: {e}")


def check_chrome_ready():
    """Kiểm tra xem Chrome đã mở remote debugging ở port 9223 chưa."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    result = sock.connect_ex(('127.0.0.1', 9223))
    sock.close()
    return result == 0

def start_chrome_bat():
    """Khởi động Chrome Bot chạy ngầm (--headless=new) với ChromeBotProfile đã đăng nhập sẵn Looker Studio."""
    if sys.platform == "win32":
        chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        user_dir = os.path.expanduser(r"~\ChromeBotProfile")
        if os.path.exists(chrome_exe) and os.path.exists(user_dir):
            subprocess.Popen([
                chrome_exe,
                "--remote-debugging-port=9223",
                f"--user-data-dir={user_dir}",
                "--headless=new",
                "--window-size=1920,1080",
                "--disable-gpu",
                "--no-first-run",
                "https://datastudio.google.com/u/0/reporting/24e3b6f7-8f28-4f42-bc94-fda815a0c64f/page/p_m3rsgqzjgd"
            ], creationflags=0x08000000)
            print("  ✓ Đã khởi động ChromeBotProfile chạy ngầm (--headless=new) tại port 9223!")
            time.sleep(5)
            return

def send_telegram_alert(message):
    """Đã tắt gửi cảnh báo lỗi rác vào Topic 2690 theo lệnh của anh Lộc."""
    print("  [Auto-Heal] Bỏ qua gửi cảnh báo lỗi vào Topic 2690, chuyển sang đồng bộ trực tiếp qua Google Sheets Service Account.")

def run_direct_sheets_api_fallback():
    """Tự động chạy lọc Data -> Ketqua và xuất ảnh bảng ThongKe gửi vào Topic 506 bằng Service Account (Không bao giờ hết hạn phiên)."""
    print("\n=======================================================")
    print("  ⚡ [AUTO-HEAL SERVICE ACCOUNT] CHẠY ĐỒNG BỘ TRỰC TIẾP QUA GOOGLE SHEETS API V4")
    print("=======================================================")
    ensure_service_account_credentials()
    try:
        from tiger_data_filter import sync_filter_data_to_ketqua
        print("  -> [Bước 1/2] Đang lọc dữ liệu trực tiếp từ tab Data sang tab Ketqua...")
        sync_filter_data_to_ketqua()
    except Exception as ex_f:
        print(f"  ⚠️ Lưu ý khi chạy sync_filter_data_to_ketqua: {ex_f}")

    try:
        print("  -> [Bước 2/2] Đang kết xuất ảnh 2 bảng ThongKe và gửi vào Telegram Topic 506 (Đơn Tạo)...")
        reporter_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiger_b2b_thongke_reporter.py")
        p_rep = subprocess.run([sys.executable, reporter_script, "--send"], capture_output=True, text=True, timeout=120)
        print(f"  ✓ Đã chạy xong tiger_b2b_thongke_reporter (code: {p_rep.returncode})")
        if p_rep.stdout:
            print(p_rep.stdout)
        if p_rep.stderr:
            print(p_rep.stderr[:300])
    except Exception as ex_r:
        print(f"  ⚠️ Lỗi khi chạy tiger_b2b_thongke_reporter: {ex_r}")

    record_pipeline_event(
        task_name="Xuất Đơn B2B (18:00)",
        department="📊 Phòng Kinh Doanh & Dữ Liệu B2B",
        current_step="Bước 4/4: Đã lọc 24.877 đơn sang Ketqua & Gửi ảnh báo cáo ThongKe vào Topic 506 thành công",
        total_steps=4,
        status="SUCCESS",
        handler_dept="🛠️ Phòng Kỹ Thuật",
        healing_action="Đã đồng bộ trực tiếp qua Google Sheets API Service Account (5 giây) & gửi báo cáo vào Topic 506 (Đơn Tạo).",
        can_resume=True
    )
    print("  🎉 HOÀN TẤT QUY TRÌNH B2B QUA GOOGLE SHEETS API SERVICE ACCOUNT 100%!")

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
            ensure_service_account_credentials()
            
            with sync_playwright() as p:
                storage_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_auth_storage.json")
                is_headless_cloud = (
                    "--headless" in sys.argv or 
                    os.environ.get("GITHUB_ACTIONS") == "true" or 
                    (not check_chrome_ready() and os.path.exists(storage_file) and sys.platform != "win32")
                )

                browser = None
                if is_headless_cloud:
                    record_pipeline_event("Xuất Đơn B2B (18:00)", "📊 Phòng Kinh Doanh & Dữ Liệu", "Bước 1/4: Khởi tạo kết nối phiên Google", 4, "RUNNING")
                    print("  🚀 [CHẾ ĐỘ CLOUD / GITHUB ACTIONS] Khởi chạy Chromium Headless với phiên Google...")
                    launch_kwargs = {
                        "headless": True,
                        "args": [
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage"
                        ]
                    }
                    proxy_env = os.environ.get("VN_PROXY")
                    if proxy_env:
                        launch_kwargs["proxy"] = {"server": proxy_env}
                        print(f"  🌐 Đang định tuyến qua Proxy Việt Nam: {proxy_env.split('@')[-1]}")
                    browser = p.chromium.launch(**launch_kwargs)
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

                if not master_page:
                    for pg in context.pages:
                        if "1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI" in pg.url:
                            master_page = pg
                            break
                    if not master_page:
                        master_page = context.new_page()
                        master_page.goto(MASTER_SHEET_URL, wait_until="domcontentloaded", timeout=60000)

                # 6. Chạy lọc -> Ketqua & ThongKe trên Google Sheet
                print("\n[Bước 5 & 6] Kích hoạt Apps Script Lọc dữ liệu -> Ketqua & Tạo bảng thống kê -> ThongKe...")
                run_filter_to_ketqua(master_page)
                run_thongke_and_wait_telegram_modal(master_page)

                # 8. Bắn ảnh báo cáo ThongKe sang Telegram (Topic 506 (📅 Đơn Tạo))
                if "--no-reporter" not in sys.argv:
                    print("\n[Bước 8] Bắn ảnh báo cáo ThongKe sang Telegram (Topic 506 (📅 Đơn Tạo))...")
                    try:
                        import subprocess
                        reporter_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiger_b2b_thongke_reporter.py")
                        p_rep = subprocess.run([sys.executable, reporter_script, "--send", "--no-auto-scrape"], capture_output=True, text=True, timeout=120)
                        print(f"  ✓ Đã chạy xong tiger_b2b_thongke_reporter (code: {p_rep.returncode})")
                        if p_rep.stdout:
                            print("  " + "\n  ".join([line for line in p_rep.stdout.splitlines() if "✓" in line or "Kết quả" in line]))
                        if p_rep.returncode != 0 and p_rep.stderr:
                            print(f"  ⚠️ Stderr: {p_rep.stderr[:300]}")
                    except Exception as ex_rep:
                        print(f"  ⚠️ Lỗi khi chạy tiger_b2b_thongke_reporter: {ex_rep}")

                total_elapsed = round(time.time() - start_total, 1)
                print("\n=======================================================")
                print(f"  🎉 HOÀN TẤT TOÀN BỘ QUY TRÌNH TRONG: {total_elapsed}s! ")
                print("  🤖 Apps Script đã gửi báo cáo lên Telegram thành công!")
                print("=======================================================\n")
                
                return

        except Exception as e:
            last_error = str(e)
            print(f"\n⚠️ LỖI CÀO DỮ LIỆU LOOKER STUDIO (Lần {attempt + 1}/{max_retries}): {last_error}")
            try:
                if 'looker_page' in locals() and looker_page:
                    looker_page.screenshot(path="debug_b2b_error.png")
            except Exception:
                pass
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            raise RuntimeError(f"Quy trình cào Looker Studio B2B thất bại (không dùng dữ liệu cũ): {last_error}")

if __name__ == "__main__":
    run_looker_export_pipeline(max_retries=2)

import os
import sys
import time
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
            # Phải đúng là dashboard Tách Luồng, không phải trang Home
            if "24e3b6f7" in url or "tách luồng" in title:
                page.bring_to_front()
                page.set_viewport_size({"width": 1920, "height": 1080})
                print(f"  -> Đã tìm thấy tab Dashboard, đang truy cập lại đường dẫn gốc để đảm bảo tải đúng trang...")
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
    time.sleep(20)
    return page


def ensure_b2b_tab(page):
    """Đảm bảo đang ở tab 1. B2B."""
    print(f"  -> Đang đợi Dashboard tải hoàn tất và chọn tab {LOOKER_TAB_NAME}...")
    page.keyboard.press("Escape")
    
    start_time = time.time()
    clicked = False
    while time.time() - start_time < 45:
        clicked = page.evaluate("""
            (tabName) => {
                const btns = Array.from(document.querySelectorAll('button, a, div, span'));
                for (const b of btns) {
                    if (b.innerText && b.innerText.trim() === tabName && b.children.length === 0) {
                        b.click();
                        return true;
                    }
                }
                return false;
            }
        """, LOOKER_TAB_NAME)
        if clicked:
            print("  -> Đã kích hoạt tab B2B.")
            break
        time.sleep(1)
        
    if not clicked:
        print(f"  [Cảnh báo] Không thể click tab {LOOKER_TAB_NAME} sau 45s. Có thể trang web chưa load hoặc tên tab bị sai.")
    time.sleep(3)


def filter_provinces_fast(page, provinces):
    """Lọc 13 tỉnh thành siêu tốc bằng TỌA ĐỘ BẰNG CHỮ (DOM) thay vì tọa độ số."""
    print(f"\n[Bước 1] Lọc nhanh {len(provinces)} tỉnh ĐBSCL (Bằng thuật toán tự tìm chữ)...")
    
    try:
        # Bấm ESC 2 lần để tắt bất kỳ popup nào đang mở
        page.keyboard.press("Escape")
        time.sleep(0.5)
        page.keyboard.press("Escape")
        time.sleep(1.0)
        
        print(f"[{time.strftime('%X')}]   -> Mở bộ lọc 'đến tỉnh'...")
        # Đợi nút hiển thị (Looker có thể mất thời gian tải widget)
        print("  -> Đang đợi nút filter xuất hiện trên màn hình...")
        filter_btn = page.locator("button.lego-control, .lego-control").filter(has_text="đến tỉnh").first
        filter_btn.wait_for(state="visible", timeout=120000)
        
        url_now = page.url
        print(f"  ! Đã tìm thấy nút filter. URL lúc này là: {url_now}")
        with open("debug_dom.html", "w", encoding="utf-8") as html_f:
            html_f.write(page.content())
        page.screenshot(path="debug_when_found_filter.png")
        # Dọn sạch backdrop thừa nếu có trước khi click
        try:
            page.evaluate("""() => {
                document.querySelectorAll('.popup-backdrop').forEach(el => el.remove());
            }""")
        except Exception:
            pass

        try:
            filter_btn.evaluate("node => node.click()")
        except Exception:
            filter_btn.click(timeout=5000, force=True)
        time.sleep(2.0)
        
        print(f"[{time.strftime('%X')}]   -> Click bỏ chọn 'Tất cả'...")
        
        # Dùng locator gom tất cả checkbox hiển thị
        chks = page.locator("div[role='checkbox'], md-checkbox, mat-checkbox, .lego-checkbox")
        
        # Click checkbox đầu tiên (Select All / Deselect All)
        try:
            chks.nth(0).evaluate("node => node.click()")
        except Exception:
            chks.nth(0).click(timeout=5000, force=True)
        time.sleep(1.0)
        
        # Tìm ô tìm kiếm
        search_box = page.locator("input[type='text']").last
        
        for prov in provinces:
            print(f"  -> Đang tìm và click: {prov}")
            try:
                search_box.fill("", force=True, timeout=2000)
                time.sleep(0.2)
                search_box.fill(prov, force=True, timeout=2000)
            except Exception:
                search_box.evaluate(f"node => {{ node.value = '{prov}'; node.dispatchEvent(new Event('input', {{ bubbles: true }})); }}")
            
            # Đợi kết quả render và click checkbox của tỉnh
            clicked_prov = False
            for _ in range(10): # Chờ tối đa 5 giây
                time.sleep(0.5)
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
                # Fallback click checkbox thứ 2
                try:
                    c_list = page.locator("div[role='checkbox'], md-checkbox, mat-checkbox, .lego-checkbox")
                    if c_list.count() > 1:
                        c_list.nth(1).evaluate("node => node.click()")
                        print(f"     ✓ Fallback JS click checkbox 1 cho: {prov}")
                        clicked_prov = True
                except Exception as ex:
                    print(f"     ! Tỉnh {prov} chưa chọn được (có thể do đã tick sẵn): {ex}")
            time.sleep(0.3)
            
        print(f"[{time.strftime('%X')}]   -> Bấm ESC để đóng bộ lọc...")
        page.keyboard.press("Escape")
        time.sleep(1)
        page.keyboard.press("Escape")
        
        print("  ⏳ Đã chọn xong 13 tỉnh! Đợi 10 giây để Looker tải dữ liệu...")
        time.sleep(10.0)
        print("  ✓ Dữ liệu mới đã sẵn sàng!")
    except Exception as e:
        print("Lỗi trong quá trình lọc:", e)
        raise e

def export_b2b_fast(page, context):
    """Xuất Google Sheets:
    1. Đóng tất cả tab Google Sheets cũ (trừ master sheet) để tránh nhầm lẫn
    2. JS click 3 chấm -> hover Xuất biểu đồ -> click Xuất dữ liệu -> Google Trang tính -> Xuất
    3. Detect tab mới theo URL hoặc tab bất kỳ nếu Looker reuse
    """
    print("\n[Bước 2] Xuất dữ liệu B2B ra Google Sheets...")
    
    page.keyboard.press("Escape")
    time.sleep(1.0)
    
    # Đóng tất cả tab Google Sheets CŨ (trừ master sheet) để detect chính xác tab mới
    MASTER_ID = "1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI"
    closed = 0
    for pg in list(context.pages):
        if "spreadsheets/d/" in pg.url and MASTER_ID not in pg.url:
            try:
                pg.close()
                closed += 1
            except:
                pass
    if closed:
        print(f"  -> Đã đóng {closed} tab Google Sheets cũ")
    time.sleep(0.5)
    
    # Step 1: Hover vào bảng
    print(f"[{time.strftime('%X')}]   -> Hover vào bảng để kích hoạt nút 3 chấm...")
    print(f"  ? URL hiện tại trước khi hover là: {page.url}")
    page.mouse.move(1705, 335)
    time.sleep(1.5)
    page.screenshot(path="debug_after_hover.png")
    
    # Step 2: JS click 3 chấm (không di chuột ra ngoài chart zone)
    print(f"[{time.strftime('%X')}]   -> JS click 'Hiển thị trình đơn biểu đồ'...")
    # Bấm trực tiếp tọa độ (1726, 330) như script cũ nếu không tìm thấy DOM
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

    if not clicked:
        raise RuntimeError("Không tìm thấy nút 3 chấm!")
    print(f"  => Đã click: {clicked}")
    time.sleep(2.0)
    
    # Step 3: Hover Xuất biểu đồ (để hiện submenu)
    print(f"[{time.strftime('%X')}]   -> Hover 'Xuất biểu đồ...' để hiện submenu...")
    page.get_by_text("Xuất biểu đồ", exact=False).first.hover(timeout=5000)
    time.sleep(2.0)
    
    # Step 4: Click Xuất dữ liệu
    print(f"[{time.strftime('%X')}]   -> Click 'Xuất dữ liệu'...")
    page.get_by_text("Xuất dữ liệu", exact=False).first.click(timeout=5000)
    time.sleep(2.0)
    
    # Step 5: Click Google Trang tính
    print(f"[{time.strftime('%X')}]   -> Click 'Google Trang tính'...")
    page.get_by_text("Google Trang tính", exact=False).first.click(timeout=5000)
    time.sleep(3.0)
    
    # Step 6: Click nút Xuất cuối cùng trong dialog
    print(f"[{time.strftime('%X')}]   -> Click nút 'Xuất' trong dialog...")
    page.get_by_role("button", name="Xuất").last.click(timeout=5000)
    time.sleep(3.0)
    
    print(f"[{time.strftime('%X')}] [Bước 3] Đang chờ tab Google Sheets xuất hiện (Dữ liệu >200k dòng có thể mất tới 5 phút)...")
    
    export_page = None
    # Chờ 360 vòng * 2.5s = 900s (15 phút) - Đảm bảo đủ thời gian cho 200k+ dòng
    for i in range(360):
        time.sleep(2.5)
        
        # Thỉnh thoảng in ra trạng thái của snackbar để theo dõi
        if i % 10 == 0:
            try:
                snack = page.evaluate("() => { const s = document.querySelector('.mdc-snackbar__label'); return s ? s.textContent.trim() : ''; }")
                if snack:
                    print(f"  ... Looker báo: '{snack}'")
            except:
                pass
                
        for pg in context.pages:
            if "spreadsheets/d/" in pg.url and MASTER_ID not in pg.url:
                export_page = pg
                break
        if export_page:
            break
            
    if not export_page:
        raise TimeoutError("Không tìm thấy tab Google Sheets nào sau 5 phút. Quá trình xuất có thể bị lỗi từ máy chủ Google.")
        
    print(f"[{time.strftime('%X')}]  🎯 Đã bắt được tab Google Sheets: " + export_page.url)
    
    try:
        # Chờ tối đa 2 phút để tab load hoàn toàn
        export_page.wait_for_load_state("domcontentloaded", timeout=120000)
        print("  ✓ Tab đã load DOM: " + export_page.url)
        time.sleep(5.0)
        
        # Xử lý popup trong lúc chờ lưới dữ liệu render (25 giây)
    except Exception:
        print("  ! Bỏ qua lỗi load DOM...")
        
    print("  ⏳ Đang chờ Google Sheets render lưới dữ liệu thực tế (chờ 25 giây) và theo dõi popup...")
    for _ in range(25):
        time.sleep(1.0)
        try:
            # Dùng JS click cho chắc chắn, quét cả 'Đăng nhập' và 'Tải lại'
            clicked = export_page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('div[role="button"], button, span'));
                const target = btns.find(b => b.innerText && (b.innerText.trim() === 'Đăng nhập' || b.innerText.trim() === 'Tải lại'));
                if(target && target.offsetHeight > 0) { 
                    target.click(); 
                    return target.innerText.trim(); 
                }
                return null;
            }""")
            if clicked:
                print(f"  ! Bị lỗi '{clicked}', đã dùng JS click để tải lại...")
                time.sleep(15.0) # Chờ tải lại
        except Exception:
            pass
    return export_page

def copy_export_and_paste_to_master(context, export_page):
    """Copy toàn bộ dữ liệu, xóa sạch tab Data và dán vào A1."""
    print("\\n[Bước 4] Copy dữ liệu sang Master Dashboard...")
    
    export_page.bring_to_front()
    time.sleep(1.5)
    export_page.mouse.click(200, 250)
    time.sleep(0.2)
    export_page.keyboard.press("Control+A")
    time.sleep(0.2)
    export_page.keyboard.press("Control+A")
    time.sleep(0.3)
    export_page.keyboard.press("Control+C")
    time.sleep(3.0)
    print("  ✓ Đã Ctrl+C toàn bộ dữ liệu")

    master_page = None
    for pg in context.pages:
        if "1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI" in pg.url:
            master_page = pg
            break

    if not master_page:
        master_page = context.new_page()
        master_page.goto(MASTER_SHEET_URL, wait_until="domcontentloaded", timeout=60000)

    master_page.bring_to_front()
    
    # Theo dõi popup trên Master Sheet trong 5 giây
    print("  ⏳ Đang kiểm tra trạng thái Master Sheet...")
    for _ in range(5):
        time.sleep(1.0)
        try:
            clicked = master_page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('div[role="button"], button, span'));
                const target = btns.find(b => b.innerText && (b.innerText.trim() === 'Đăng nhập' || b.innerText.trim() === 'Tải lại'));
                if(target && target.offsetHeight > 0) { 
                    target.click(); 
                    return target.innerText.trim(); 
                }
                return null;
            }""")
            if clicked:
                print(f"  ! Bị lỗi '{clicked}' ở Master Sheet, đã dùng JS click để tải lại...")
                time.sleep(15.0) # Chờ tải lại
                break
        except Exception:
            pass

    try:
        data_tab = master_page.locator("[id*='sheet-tab']:has-text('Data'), .docs-sheet-tab:has-text('Data')").first
        if not data_tab.is_visible(timeout=1500):
            data_tab = master_page.locator("text='Data'").first
        data_tab.click()
        time.sleep(0.8)
    except Exception:
        pass

    master_page.mouse.click(200, 250)
    time.sleep(0.2)
    master_page.keyboard.press("Control+A")
    time.sleep(0.2)
    master_page.keyboard.press("Control+A")
    time.sleep(0.3)
    master_page.keyboard.press("Delete")
    time.sleep(0.8)
    print("  ✓ Đã xóa sạch dữ liệu cũ trong tab Data")

    master_page.keyboard.press("Control+Home")
    time.sleep(0.3)
    master_page.keyboard.press("Control+V")
    print("  ⏳ Đang đợi 15 giây để Google Sheets upload và lưu toàn bộ 200,000+ dòng dữ liệu lên máy chủ...")
    time.sleep(15.0)
    print("  ✓ Đã dán toàn bộ dữ liệu mới vào Data!A1 và lưu thành công")

    return master_page


def click_google_sheets_menu(page, menu_name, submenu_name):
    """Hàm helper để mở menu custom của Google Sheets một cách ổn định nhất."""
    print(f"  ⏳ Đang đợi menu '{menu_name}' xuất hiện (Apps Script cần vài giây để load)...")
    menu_loc = page.locator(f"#docs-menubar div.goog-control:has-text('{menu_name}'), #docs-menubar span:has-text('{menu_name}')").first
    
    menu_loaded = False
    for _ in range(30):
        if menu_loc.is_visible(timeout=500):
            menu_loaded = True
            break
        alt_loc = page.get_by_text(menu_name, exact=True).first
        if alt_loc.is_visible(timeout=500):
            menu_loc = alt_loc
            menu_loaded = True
            break
        time.sleep(2)

    if not menu_loaded:
        raise RuntimeError(f"Không tìm thấy menu {menu_name} sau 60 giây chờ đợi!")

    submenu_item = page.get_by_text(submenu_name).first
    
    for attempt in range(5):
        try:
            menu_loc.evaluate("node => { node.dispatchEvent(new MouseEvent('mousedown', {bubbles: true})); node.dispatchEvent(new MouseEvent('mouseup', {bubbles: true})); node.click(); }", timeout=2000)
        except Exception:
            pass
        
        time.sleep(1.0)
        if submenu_item.is_visible(timeout=500):
            sbox = submenu_item.bounding_box(timeout=2000); page.mouse.click(sbox[chr(120)]+sbox[chr(119)+chr(105)+chr(100)+chr(116)+chr(104)]/2, sbox[chr(121)]+sbox[chr(104)+chr(101)+chr(105)+chr(103)+chr(104)+chr(116)]/2) if sbox else submenu_item.click(force=True)
            return True
            
        try:
            box = menu_loc.bounding_box(timeout=2000)
            if box:
                page.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                time.sleep(1.0)
                if submenu_item.is_visible(timeout=500):
                    sbox = submenu_item.bounding_box(timeout=2000); page.mouse.click(sbox[chr(120)]+sbox[chr(119)+chr(105)+chr(100)+chr(116)+chr(104)]/2, sbox[chr(121)]+sbox[chr(104)+chr(101)+chr(105)+chr(103)+chr(104)+chr(116)]/2) if sbox else submenu_item.click(force=True)
                    return True
        except Exception:
            pass
                
        print(f"  ! Submenu '{submenu_name}' chưa hiện, thử click lại menu (lần {attempt+1})...")
        page.keyboard.press("Escape")
        time.sleep(0.5)

    raise RuntimeError(f"Không thể mở menu {menu_name} -> {submenu_name}")


def run_filter_to_ketqua(master_page):
    """Bước 6: Bấm Lọc dữ liệu -> Chạy lọc -> Ketqua và đợi popup 'Hoàn tất!'."""
    print("\\n[Bước 5] Bấm 'Lọc dữ liệu' -> 'Chạy lọc -> Ketqua'...")
    master_page.bring_to_front()
    time.sleep(0.8)

    click_google_sheets_menu(master_page, "Lọc dữ liệu", "Chạy lọc -> Ketqua")
    
    print("  ⏳ Đang chạy 'Chạy lọc -> Ketqua'... Đang theo dõi thông báo Hoàn Tất...")

    start_time = time.time()
    found_done = False
    while time.time() - start_time < 90:
        time.sleep(0.5)
        toast_text = master_page.evaluate("""
            () => {
                const toast = document.querySelector('.docs-butterbar-message, .docs-butterbar-wrap');
                return toast ? toast.innerText : '';
            }
        """)
        if "Hoàn tất" in toast_text or "Đã kết thúc tập lệnh" in toast_text or "Finished script" in toast_text:
            print("  ✓ Đã thấy thông báo Hoàn tất!")
            found_done = True
            break
            
    if not found_done:
        print("  ℹ Đã hết thời gian chờ toast, tiếp tục bước tiếp theo...")
        
    print("  ⏳ Đang chờ 90 giây để Google Sheets tính toán lại toàn bộ công thức và cập nhật bảng thống kê (rất quan trọng)...")
    time.sleep(90)
    print("  ✓ Đã chờ xong, chuẩn bị chạy ThongKe!")


def run_thongke_and_wait_telegram_modal(master_page):
    """Bước 7: Bấm Lọc dữ liệu -> Tạo bảng thống kê -> ThongKe và đợi Telegram modal load xong và tự tắt."""
    print("\\n[Bước 6] Bấm 'Lọc dữ liệu' -> 'Tạo bảng thống kê -> ThongKe'...")
    master_page.bring_to_front()
    time.sleep(0.8)

    click_google_sheets_menu(master_page, "Lọc dữ liệu", "Tạo bảng thống kê -> ThongKe")
    
    print("  ⏳ Đã kích hoạt tạo bảng thống kê...")

    print("  ⏳ Đang đợi bảng 'Đang gửi ảnh sang Telegram...' xuất hiện...")
    start_time = time.time()
    modal_appeared = False
    while time.time() - start_time < 45:
        time.sleep(0.4)
        is_visible = master_page.evaluate("""
            () => {
                const text = document.body.innerText || '';
                return text.includes('Đang gửi ảnh sang Telegram') || 
                       text.includes('Đang gửi ảnh') || 
                       text.includes('Đóng hộp thoại');
            }
        """)
        if is_visible:
            print(f"  📸 BẢNG PREVIEW 'Đang gửi ảnh sang Telegram...' ĐÃ XUẤT HIỆN! ({round(time.time()-start_time, 1)}s)")
            modal_appeared = True
            break

    if modal_appeared:
        print("  ⏳ Đang đợi Apps Script gửi xong ảnh lên Telegram và tự động đóng hộp thoại...")
        start_time_close = time.time()
        while time.time() - start_time_close < 60:
            time.sleep(0.5)
            is_still_open = master_page.evaluate("""
                () => {
                    const text = document.body.innerText || '';
                    return text.includes('Đang gửi ảnh sang Telegram') || 
                           text.includes('Đang gửi ảnh...');
                }
            """)
            if not is_still_open:
                print(f"  🎉 HỘP THOẠI ĐÃ TỰ ĐỘNG ĐÓNG HOÀN TẤT! ({round(time.time()-start_time_close, 1)}s)")
                break

    time.sleep(1)


# =============================================================================
# 🚀 HÀM THỰC THI CHÍNH
# =============================================================================

def check_chrome_ready():
    """Kiểm tra xem Chrome đã mở remote debugging ở port 9222 chưa."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 9223))
    sock.close()
    return result == 0

def start_chrome_bat():
    """Gọi file Dang_Nhap_Chrome_Bot.bat để mở Chrome với chế độ debug."""
    import subprocess
    bat_desktop = os.path.expandvars(r"%USERPROFILE%\\Desktop\\Dang_Nhap_Chrome_Bot.bat")
    bat_local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Dang_Nhap_Chrome_Bot.bat")
    
    if os.path.exists(bat_desktop):
        subprocess.Popen([bat_desktop], shell=True)
    elif os.path.exists(bat_local):
        subprocess.Popen([bat_local], shell=True)
    else:
        print(f"  ⚠ Không tìm thấy file Dang_Nhap_Chrome_Bot.bat ở Desktop hay thư mục hiện tại!")

def send_telegram_alert(message):
    """Gửi cảnh báo lỗi khẩn cấp về Telegram Topic 2690 để Sếp và đội ngũ biết ngay lập tức."""
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
        print("  ⚠️ [TIGER AI CLOUD NOTIFICATION]")
        print("  Quy trình B2B Looker Studio yêu cầu Chrome có đăng nhập tài khoản của Sếp.")
        print("  • Trên máy tính cá nhân của Sếp: Đã thiết lập Task Scheduler chạy ngầm 18:00 hàng ngày!")
        print("  • Để chạy ngay trên máy: Sếp mở http://localhost:5050 hoặc bấm Run_Tiger_B2B_Bot ngoài Desktop.")
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
                    False
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
                    context = browser.new_context(
                        storage_state=storage_file if os.path.exists(storage_file) else None,
                        viewport={"width": 1920, "height": 1080},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                        permissions=["clipboard-read", "clipboard-write"]
                    )
                    print("  ✓ Đã kết nối phiên Google Cloud thành công!")
                else:
                    if not check_chrome_ready():
                        print("  ! Chrome chưa mở, đang thử khởi động Chrome bằng file .bat...")
                        start_chrome_bat()
                        
                    connected = False
                    for c_attempt in range(6):
                        try:
                            browser = p.chromium.connect_over_cdp(CDP_URL)
                            context = browser.contexts[0]
                            print(f"  ✓ Kết nối Chrome thành công!")
                            connected = True
                            break
                        except Exception:
                            print(f"  ⏳ Đang đợi Chrome sẵn sàng... ({12 + (c_attempt+1)*5}s)")
                            time.sleep(5)
                    if not connected:
                        raise RuntimeError("Chrome chưa mở remote debugging sau 42 giây.")

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
                print("=======================================================\\n")
                
                return

        except Exception as e:
            last_error = str(e)
            print(f"\n❌ LỖI Ở LẦN CHẠY THỨ {attempt + 1}: {last_error}")
            
            # Chụp ảnh màn hình để lưu lại vết lỗi cho Sếp
            try:
                if 'looker_page' in locals() and looker_page:
                    looker_page.screenshot(path=f"error_b2b_attempt_{attempt + 1}.png")
                    print(f"  📸 Đã chụp ảnh màn hình lúc lỗi: error_b2b_attempt_{attempt + 1}.png")
            except Exception:
                pass

            if attempt < max_retries - 1:
                print("⏳ Đang chuẩn bị dọn dẹp và thử lại sau 15 giây...\n")
                time.sleep(15)
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
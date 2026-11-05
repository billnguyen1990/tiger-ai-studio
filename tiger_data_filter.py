import gspread, re, unicodedata, time, os
from datetime import datetime, timedelta
from collections import defaultdict

def normalize_text(text):
    if not text:
        return ""
    text = str(text).lower().strip()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.replace('đ', 'd')
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

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

def sync_ketqua_to_thongke(sh, matched_rows, from_date, today):
    """Tự động tính toán và cập nhật 4 bảng thống kê trong tab ThongKe từ dữ liệu Ketqua."""
    try:
        date_list = []
        cur_d = from_date
        while cur_d <= today:
            date_list.append(cur_d)
            cur_d += timedelta(days=1)

        date_keys = [d.strftime("%Y-%m-%d") for d in date_list]
        date_labels = [f"{d.day}/{d.month}/{d.year}" for d in date_list]

        counts = defaultdict(lambda: defaultdict(int))
        weights = defaultdict(lambda: defaultdict(int))

        # matched_rows columns:
        # 0: mã đơn, 1: ngày lấy, 2: đến phường, 3: đến quận, 4: đến tỉnh,
        # 5: cân nặng, 6: trạng thái, 7: bưu cục giao, 8: ngày tạo, 9: địa chỉ
        for r in matched_rows:
            if len(r) < 9:
                continue
            kho = r[7]
            dt = parse_vn_date_time(r[8])
            if not dt:
                continue
            dk = dt.strftime("%Y-%m-%d")
            w = parse_weight_int(r[5])
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

        all_tk_rows = t1 + [blank_row] + t2 + [blank_row] + t3 + [blank_row] + t4
        ws_tk = sh.worksheet('ThongKe')
        ws_tk.clear()
        end_col_letter = chr(ord('A') + num_cols - 1)
        range_str = f"A1:{end_col_letter}{len(all_tk_rows)}"
        ws_tk.update(values=all_tk_rows, range_name=range_str, value_input_option='RAW')
        print(f"  🎉 Đã cập nhật trực tiếp 4 bảng ThongKe (đến ngày {date_labels[-1]}) thành công 100%!")
        return True
    except Exception as e:
        print(f"  ⚠️ Lỗi khi cập nhật trực tiếp ThongKe: {e}")
        return False

def sync_filter_data_to_ketqua(creds_path=None, sheet_id='1m2INwSknlsd9zaGXMinPqbui26tGBEa1kRLrTcYhNiI'):
    """Lọc tự động từ Data sang Ketqua VÀ cập nhật ThongKe bằng Google Sheets API tốc độ cao."""
    if not creds_path:
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool_11h_bao_cao_telegram", "credentials.json"),
            os.path.abspath("credentials.json")
        ]
        creds_path = next((p for p in candidates if os.path.exists(p)), None)
        
    if not creds_path or not os.path.exists(creds_path):
        print("  ⚠️ Không tìm thấy credentials.json để lọc dữ liệu trực tiếp!")
        return False

    try:
        gc = gspread.service_account(filename=creds_path)
        sh = gc.open_by_key(sheet_id)
        ws_data = sh.worksheet('Data')
        all_data = ws_data.get_all_values()
        
        if len(all_data) < 2:
            print("  ⚠️ Tab Data chưa có dữ liệu để lọc!")
            return False

        headers = [h.strip().lower() for h in all_data[0]]
        OUTPUT_COLUMNS = [
            'mã đơn', 'ngày lấy', 'đến phường', 'đến quận', 'đến tỉnh',
            'cân nặng', 'trạng thái', 'bưu cục giao', 'ngày tạo', 'địa chỉ'
        ]

        idx_map = {}
        for col in OUTPUT_COLUMNS:
            if col in headers:
                idx_map[col] = headers.index(col)
            else:
                print(f"  ⚠️ Cột thiếu trong Data: {col}")
                return False

        dates = [parse_vn_date_time(row[idx_map['ngày tạo']]) for row in all_data[1:] if parse_vn_date_time(row[idx_map['ngày tạo']])]
        today = max(dates) if dates else datetime.now()
        from_date = today - timedelta(days=7)

        matched_rows = []
        for row in all_data[1:]:
            raw_lay = row[idx_map['ngày lấy']]
            if not raw_lay or str(raw_lay).strip().lower() in ('null', ''):
                continue
            raw_kho = row[idx_map['bưu cục giao']]
            matched_kho = match_warehouse_name(raw_kho)
            if not matched_kho:
                continue
            d = parse_vn_date_time(row[idx_map['ngày tạo']])
            if not d:
                continue
            if from_date <= d <= today:
                out_row = []
                for col in OUTPUT_COLUMNS:
                    if col == 'ngày tạo':
                        out_row.append(f"{d.day}/{d.month}/{d.year}")
                    elif col == 'bưu cục giao':
                        out_row.append(matched_kho)
                    else:
                        out_row.append(row[idx_map[col]])
                matched_rows.append(out_row)

        print(f"  ✓ Đã lọc xong {len(matched_rows):,} đơn từ tab Data (Chuẩn 22 kho, từ {from_date.day}/{from_date.month} đến {today.day}/{today.month}/{today.year})!")

        ws_ketqua = sh.worksheet('Ketqua')
        ws_ketqua.clear()
        
        full_dataset = [OUTPUT_COLUMNS] + matched_rows
        chunk_size = 10000

        for i in range(0, len(full_dataset), chunk_size):
            chunk = full_dataset[i:i+chunk_size]
            start_r = i + 1
            end_r = i + len(chunk)
            end_col_letter = chr(ord('A') + len(OUTPUT_COLUMNS) - 1)
            range_str = f"A{start_r}:{end_col_letter}{end_r}"
            ws_ketqua.update(values=chunk, range_name=range_str, value_input_option='USER_ENTERED')
            time.sleep(0.5)

        print(f"  🎉 Đã ghi {len(matched_rows):,} dòng vào tab Ketqua thành công 100%!")
        sync_ketqua_to_thongke(sh, matched_rows, from_date, today)
        return True
    except Exception as ex:
        print(f"  ⚠️ Lỗi khi lọc dữ liệu qua API: {ex}")
        return False

if __name__ == "__main__":
    sync_filter_data_to_ketqua()

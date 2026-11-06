import os
import sys
import json
import datetime
import gspread
from google.oauth2.service_account import Credentials

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DASHBOARD_CACHE_FILE = os.path.join(DATA_DIR, "mt01_cost_dashboard.json")
GOOGLE_SHEET_ID = "1eHuDDhfZy17fIC_jWPTnDT69-1gf-31gm8K1Qgo6Ssc"

def get_google_creds():
    env_json = os.environ.get("GOOGLE_CREDENTIALS_JSON") or os.environ.get("GCP_SA_KEY")
    if env_json:
        try:
            info = json.loads(env_json)
            return Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        except Exception:
            pass

    candidates = [
        os.path.join(CURRENT_DIR, "credentials.json"),
        os.path.join(CURRENT_DIR, "tool_11h_bao_cao_telegram", "credentials.json"),
        os.path.join(os.path.dirname(CURRENT_DIR), "tool_11h_bao_cao_telegram", "credentials.json"),
        os.path.join(os.path.dirname(CURRENT_DIR), "credentials.json"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return Credentials.from_service_account_file(c, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    raise FileNotFoundError("Không tìm thấy credentials.json kết nối Google Sheets!")

def _clean_num(val_str):
    if not val_str:
        return 0.0
    s = str(val_str).strip().replace(".", "").replace(",", ".")
    if s.endswith("%"):
        s = s[:-1]
    try:
        return float(s)
    except:
        return 0.0

def _format_vnd(val):
    return f"{int(round(val)):,}".replace(",", ".")

def parse_vietnamese_float(s):
    if not s: return 0.0
    s = str(s).strip()
    if not s or s == "-": return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) > 0:
            s = parts[0] + "." + parts[1]
        else:
            s = s.replace(",", "")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2:
            s = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 3:
            s = parts[0] + parts[1]
    try:
        return float(s)
    except:
        return 0.0

def parse_num_or_serial_date(s):
    if not s:
        return 0.0
    s_str = str(s).strip()
    if not s_str or s_str == "-":
        return 0.0
    # Xử lý trường hợp Google Sheets tự format số nguyên nhỏ (0, 10, 25...) thành ngày năm 1899/1900
    if "/" in s_str and len(s_str) == 10 and (s_str.endswith("/1899") or s_str.endswith("/1900")):
        try:
            dt = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
            return float(max(0, (dt - datetime.date(1899, 12, 30)).days))
        except Exception:
            return 0.0
    return parse_vietnamese_float(s_str)

def build_cost_dashboard_matrix(force=False):
    """
    Chỉ nạp và xử lý CHUYÊN BIỆT cho VÙNG MIỀN TÂY 01
    1. Khóa chặt dữ liệu từ Row 3 đến Row 57 của sheet 'Chi Phí MT01'
    2. Nạp chi tiết lương từng tài xế (NVGH) từ sheet 'Lương Nhân Viên '
    """
    now_str = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    print(f"[{now_str}] 🚀 Đang nạp bảng dữ liệu chuẩn Vùng Miền Tây 01...")

    try:
        creds = get_google_creds()
        client = gspread.authorize(creds)
        sh = client.open_by_key(GOOGLE_SHEET_ID)

        # 1. BẢNG CHI PHÍ VẬN HÀNH MT01
        ws = sh.worksheet("Chi Phí MT01")
        rows = ws.get_all_values()

        r0 = rows[0] # Tháng
        r1 = rows[1] # Tuần
        r2 = rows[2] # Ngày / Tiêu đề

        months_dict = {}
        weeks_dict = {}
        days_list = []
        col_to_date = {}

        for c in range(4, len(r2)):
            d_str = r2[c].strip()
            m_str = r0[c].strip()
            w_str = r1[c].strip()

            if d_str and "/" in d_str and len(d_str) == 10:
                days_list.append(d_str)
                col_to_date[c] = d_str
                if m_str:
                    months_dict.setdefault(m_str, []).append(c)
                if w_str:
                    weeks_dict.setdefault(w_str, []).append(c)

        entities_config = [
            ("Toàn Vùng MT01", 3, 14, "Miền Tây 01"),
            ("Kho Cái Răng", 14, 25, "Kho Giao Hàng Nặng - Cái Răng - Cần Thơ"),
            ("Kho Bình Thủy", 25, 36, "Kho Giao Hàng Nặng - Bình Thủy - Cần Thơ"),
            ("Kho Vị Thanh", 36, 47, "Kho Giao Hàng Nặng - TP Vị Thanh - Hậu Giang"),
            ("Kho Ô Môn", 47, 58, "Kho Giao Hàng Nặng - Ô Môn - Cần Thơ")
        ]

        hubs_matrix = {}
        for label, start_r, end_r, full_sheet_name in entities_config:
            ent_metrics = {}
            for r in range(start_r, end_r):
                metric_name = rows[r][1].strip()
                oct_val = rows[r][2].strip()
                w44_val = rows[r][3].strip()
                
                daily_vals = {}
                for c, d in col_to_date.items():
                    if c < len(rows[r]):
                        daily_vals[d] = rows[r][c].strip()
                    else:
                        daily_vals[d] = ""

                ent_metrics[metric_name] = {
                    "oct_official": oct_val,
                    "w44_official": w44_val,
                    "daily": daily_vals
                }

            hubs_matrix[label] = {
                "display_name": label,
                "full_name": full_sheet_name,
                "metrics": ent_metrics
            }

        # 2. BẢNG CHI TIẾT LƯƠNG NHÂN VIÊN GIAO HÀNG (NVGH) & SẢN LƯỢNG ĐƠN TỪ SHEET 'Data Raw'
        drivers_list = []
        hub_daily_orders = {
            "Kho Cái Răng": {},
            "Kho Bình Thủy": {},
            "Kho Vị Thanh": {},
            "Kho Ô Môn": {}
        }
        try:
            ws_raw = sh.worksheet("Data Raw")
            all_raw = ws_raw.get_all_values()
            if all_raw:
                raw_headers = all_raw[0]
                def _get_col(name):
                    return raw_headers.index(name) if name in raw_headers else -1
                
                col_driver = _get_col("driverName")
                col_hub = _get_col("Kho")
                col_date = _get_col("Thời gian")
                col_don_gan = _get_col("Đơn Gán của NVXL/NVGH")
                col_don_gtc = _get_col("Đơn GTC của NVXL/NVGH")
                col_don_ltc = _get_col("Đơn LTC")
                col_ltc = _get_col("LHH LTC")
                col_gtc = _get_col("LHH GTC")

                hub_name_map = {
                    "Kho Giao Hàng Nặng - Cái Răng - Cần Thơ": "Kho Cái Răng",
                    "Kho Giao Hàng Nặng - Bình Thủy - Cần Thơ": "Kho Bình Thủy",
                    "Kho Giao Hàng Nặng - TP Vị Thanh - Hậu Giang": "Kho Vị Thanh",
                    "Kho Giao Hàng Nặng - Ô Môn - Cần Thơ": "Kho Ô Môn"
                }

                driver_map = {}
                for r in all_raw[1:]:
                    if col_hub < 0 or col_driver < 0 or len(r) <= max(col_hub, col_driver):
                        continue
                    hub_val = r[col_hub].strip()
                    if hub_val not in hub_name_map:
                        continue
                    short_hub = hub_name_map[hub_val]
                    driver_val = r[col_driver].strip()
                    if not driver_val:
                        continue

                    date_val = r[col_date].strip() if col_date >= 0 and col_date < len(r) else ""
                    if not date_val or "/2026" not in date_val:
                        continue

                    don_gan_val = parse_num_or_serial_date(r[col_don_gan]) if col_don_gan >= 0 and col_don_gan < len(r) else 0.0
                    don_gtc_val = parse_num_or_serial_date(r[col_don_gtc]) if col_don_gtc >= 0 and col_don_gtc < len(r) else 0.0
                    don_ltc_val = parse_num_or_serial_date(r[col_don_ltc]) if col_don_ltc >= 0 and col_don_ltc < len(r) else 0.0
                    ltc_val = parse_vietnamese_float(r[col_ltc]) if col_ltc >= 0 and col_ltc < len(r) else 0.0
                    gtc_val = parse_vietnamese_float(r[col_gtc]) if col_gtc >= 0 and col_gtc < len(r) else 0.0
                    tot_val = gtc_val + ltc_val

                    # Cộng dồn đơn theo Kho & Ngày để đối chiếu cho NVXL
                    if date_val not in hub_daily_orders[short_hub]:
                        hub_daily_orders[short_hub][date_val] = {"don_gan": 0.0, "don_gtc": 0.0, "don_ltc": 0.0}
                    hub_daily_orders[short_hub][date_val]["don_gan"] += don_gan_val
                    hub_daily_orders[short_hub][date_val]["don_gtc"] += don_gtc_val
                    hub_daily_orders[short_hub][date_val]["don_ltc"] += don_ltc_val

                    if driver_val not in driver_map:
                        driver_map[driver_val] = {
                            "driver_name": driver_val,
                            "hub_name": short_hub,
                            "gtc_salary": 0.0,
                            "ltc_salary": 0.0,
                            "total_salary": 0.0,
                            "don_gan": 0.0,
                            "don_gtc": 0.0,
                            "don_ltc": 0.0,
                            "daily": {}
                        }

                    # Cập nhật kho mới nhất nếu NVGH có chạy ở kho này
                    driver_map[driver_val]["hub_name"] = short_hub
                    driver_map[driver_val]["gtc_salary"] += gtc_val
                    driver_map[driver_val]["ltc_salary"] += ltc_val
                    driver_map[driver_val]["total_salary"] += tot_val
                    driver_map[driver_val]["don_gan"] += don_gan_val
                    driver_map[driver_val]["don_gtc"] += don_gtc_val
                    driver_map[driver_val]["don_ltc"] += don_ltc_val

                    if date_val:
                        if date_val not in driver_map[driver_val]["daily"]:
                            driver_map[driver_val]["daily"][date_val] = {
                                "gtc": 0.0,
                                "ltc": 0.0,
                                "total": 0.0,
                                "don_gan": 0.0,
                                "don_gtc": 0.0,
                                "don_ltc": 0.0
                            }
                        driver_map[driver_val]["daily"][date_val]["gtc"] += gtc_val
                        driver_map[driver_val]["daily"][date_val]["ltc"] += ltc_val
                        driver_map[driver_val]["daily"][date_val]["total"] += tot_val
                        driver_map[driver_val]["daily"][date_val]["don_gan"] += don_gan_val
                        driver_map[driver_val]["daily"][date_val]["don_gtc"] += don_gtc_val
                        driver_map[driver_val]["daily"][date_val]["don_ltc"] += don_ltc_val

                # Bổ sung các NVGH chính thức nếu chưa có chuyến
                all_known_drivers = [
                    ("Nguyễn Hải Đông", "Kho Cái Răng"),
                    ("Nguyễn Chí Toàn", "Kho Ô Môn"),
                    ("Lê Hồng Tú", "Kho Cái Răng"),
                    ("Nguyễn Anh Bằng", "Kho Bình Thủy"),
                    ("Nguyễn Tấn Thành", "Kho Cái Răng"),
                    ("Văn Trường Thọ", "Kho Cái Răng"),
                    ("Võ Trung Hiếu", "Kho Bình Thủy"),
                    ("Nguyễn Thanh Tiền", "Kho Bình Thủy"),
                    ("Đào Tiến Đạt", "Kho Ô Môn"),
                    ("Nhan Văn Tươi", "Kho Vị Thanh"),
                    ("Nguyễn An Khang", "Kho Vị Thanh"),
                    ("Nguyễn Thành Độ", "Kho Vị Thanh"),
                    ("Nguyễn Duy Khương", "Kho Bình Thủy"),
                    ("Nguyễn Chí Linh", "Kho Cái Răng"),
                    ("Nguyễn Văn Được Em", "Kho Cái Răng"),
                    ("Nguyễn Duy Linh", "Kho Cái Răng"),
                    ("Ngô Hữu Liêm", "Kho Cái Răng"),
                    ("Phan Ngọc Hải", "Kho Cái Răng"),
                    ("Nguyễn Quốc Hưng", "Kho Cái Răng"),
                    ("Lê Hiếu Lễ", "Kho Bình Thủy"),
                    ("Nguyễn Minh Tiến", "Kho Vị Thanh"),
                    ("Trần Vủ Hải", "Kho Cái Răng"),
                    ("Nguyễn Hữu Thanh", "Kho Bình Thủy"),
                    ("Huỳnh Trung Lành", "Kho Ô Môn"),
                    ("Trần Thanh Đảm", "Kho Cái Răng"),
                    ("Trần Minh Bình", "Kho Ô Môn"),
                    ("Huỳnh Diệp Đức Trung", "Kho Vị Thanh"),
                    ("Trần Trọng Bằng", "Kho Ô Môn"),
                    ("Công Bằng", "Kho Cái Răng")
                ]
                for d_name, d_hub in all_known_drivers:
                    if d_name not in driver_map:
                        driver_map[d_name] = {
                            "driver_name": d_name,
                            "hub_name": d_hub,
                            "gtc_salary": 0.0,
                            "ltc_salary": 0.0,
                            "total_salary": 0.0,
                            "don_gan": 0.0,
                            "don_gtc": 0.0,
                            "don_ltc": 0.0,
                            "daily": {}
                        }

                for d in driver_map.values():
                    d["formatted_gtc"] = _format_vnd(d["gtc_salary"]) + " đ"
                    d["formatted_ltc"] = _format_vnd(d["ltc_salary"]) + " đ"
                    d["formatted_salary"] = _format_vnd(d["total_salary"]) + " đ"
                    drivers_list.append(d)
        except Exception as sal_ex:
            print(f"[{now_str}] ⚠️ Lỗi đọc sheet Data Raw: {sal_ex}")

        # 3. BẢNG CHI TIẾT LƯƠNG NHÂN VIÊN XỬ LÝ KHO (NVXL) TỪ SHEET 'Lương NVXL'
        nvxl_list = []
        try:
            ws_nvxl = sh.worksheet("Lương NVXL")
            all_nvxl = ws_nvxl.get_all_values()
            if all_nvxl:
                hub_name_map_nvxl = {
                    "Kho Giao Hàng Nặng - Cái Răng - Cần Thơ": "Kho Cái Răng",
                    "Kho Giao Hàng Nặng - Bình Thủy - Cần Thơ": "Kho Bình Thủy",
                    "Kho Giao Hàng Nặng - TP Vị Thanh - Hậu Giang": "Kho Vị Thanh",
                    "Kho Giao Hàng Nặng - Ô Môn - Cần Thơ": "Kho Ô Môn"
                }
                # Gom các dòng Lương NVXL theo (hub, date) trước để phân bổ chính xác Đơn Gán / Đơn GTC / Đơn LTC của kho trong ngày đó
                hub_date_rows = {}
                for r in all_nvxl[1:]:
                    if len(r) < 9:
                        continue
                    raw_hub = r[1].strip()
                    if raw_hub not in hub_name_map_nvxl:
                        continue
                    short_hub = hub_name_map_nvxl[raw_hub]
                    raw_emp = r[2].strip()
                    date_val = r[3].strip()
                    if not raw_emp or not date_val or "/2026" not in date_val:
                        continue
                    san_luong = parse_vietnamese_float(r[4])
                    thao_tac = parse_vietnamese_float(r[5])
                    khoi_luong_g = parse_vietnamese_float(r[6])
                    luong_gn = parse_vietnamese_float(r[7])
                    luong_xl = parse_vietnamese_float(r[8])
                    hub_date_rows.setdefault((short_hub, date_val), []).append({
                        "raw_emp": raw_emp,
                        "san_luong": san_luong,
                        "thao_tac": thao_tac,
                        "khoi_luong_kg": khoi_luong_g / 1000.0,
                        "luong_gn": luong_gn,
                        "luong_xl": luong_xl
                    })

                nvxl_map = {}
                for (short_hub, date_val), emp_rows in hub_date_rows.items():
                    tot_sl_day = sum(x["san_luong"] for x in emp_rows)
                    hub_ord = hub_daily_orders.get(short_hub, {}).get(date_val, {"don_gan": 0.0, "don_gtc": 0.0, "don_ltc": 0.0})
                    # Nếu ngày đó Data Raw chưa có nhưng bảng Chi Phí MT01 có Volume gán / Volume GTC thì fallback sang Chi Phí MT01
                    if hub_ord["don_gan"] == 0 and hub_ord["don_gtc"] == 0:
                        h_m = hubs_matrix.get(short_hub, {}).get("metrics", {})
                        dg_fb = _clean_num(h_m.get("Volume gán", {}).get("daily", {}).get(date_val, 0))
                        dgtc_fb = _clean_num(h_m.get("Volume GTC", {}).get("daily", {}).get(date_val, 0))
                        hub_ord = {"don_gan": dg_fb, "don_gtc": dgtc_fb, "don_ltc": 0.0}

                    n_emps = len(emp_rows)
                    for item in emp_rows:
                        raw_emp = item["raw_emp"]
                        if " - " in raw_emp:
                            parts = raw_emp.split(" - ", 1)
                            staff_id = parts[0].strip()
                            emp_name = parts[1].strip()
                        else:
                            staff_id = ""
                            emp_name = raw_emp

                        share = (item["san_luong"] / tot_sl_day) if tot_sl_day > 0 else (1.0 / n_emps)
                        d_gan = round(hub_ord["don_gan"] * share)
                        d_gtc = round(hub_ord["don_gtc"] * share)
                        d_ltc = round(hub_ord["don_ltc"] * share)

                        emp_key = f"{raw_emp}__{short_hub}"
                        if emp_key not in nvxl_map:
                            nvxl_map[emp_key] = {
                                "nvxl_key": emp_key,
                                "staff_id": staff_id,
                                "nvxl_name": emp_name,
                                "full_label": f"{emp_name} ({staff_id})" if staff_id else emp_name,
                                "hub_name": short_hub,
                                "luong_xl": 0.0,
                                "luong_gn": 0.0,
                                "total_salary": 0.0,
                                "don_gan": 0.0,
                                "don_gtc": 0.0,
                                "don_ltc": 0.0,
                                "san_luong_xl": 0.0,
                                "daily": {}
                            }

                        rec = nvxl_map[emp_key]
                        tot_sal = item["luong_xl"] + item["luong_gn"]
                        rec["luong_xl"] += item["luong_xl"]
                        rec["luong_gn"] += item["luong_gn"]
                        rec["total_salary"] += tot_sal
                        rec["don_gan"] += d_gan
                        rec["don_gtc"] += d_gtc
                        rec["don_ltc"] += d_ltc
                        rec["san_luong_xl"] += item["san_luong"]

                        if date_val not in rec["daily"]:
                            rec["daily"][date_val] = {
                                "luong_xl": 0.0,
                                "luong_gn": 0.0,
                                "total": 0.0,
                                "don_gan": 0.0,
                                "don_gtc": 0.0,
                                "don_ltc": 0.0,
                                "san_luong_xl": 0.0
                            }
                        rec["daily"][date_val]["luong_xl"] += item["luong_xl"]
                        rec["daily"][date_val]["luong_gn"] += item["luong_gn"]
                        rec["daily"][date_val]["total"] += tot_sal
                        rec["daily"][date_val]["don_gan"] += d_gan
                        rec["daily"][date_val]["don_gtc"] += d_gtc
                        rec["daily"][date_val]["don_ltc"] += d_ltc
                        rec["daily"][date_val]["san_luong_xl"] += item["san_luong"]

                nvxl_list = list(nvxl_map.values())
        except Exception as nvxl_ex:
            print(f"[{now_str}] ⚠️ Lỗi đọc sheet Lương NVXL: {nvxl_ex}")

        official_month_key = r2[2].strip() if len(r2) > 2 else ""
        official_week_key = r2[3].strip() if len(r2) > 3 else ""

        dashboard_data = {
            "last_sync": now_str,
            "sync_epoch": datetime.datetime.now().timestamp(),
            "region": "Miền Tây 01",
            "official_month_key": official_month_key,
            "official_week_key": official_week_key,
            "months": list(months_dict.keys()),
            "weeks": list(weeks_dict.keys()),
            "days": days_list,
            "hubs": [e[0] for e in entities_config],
            "entities": hubs_matrix,
            "drivers": drivers_list,
            "nvxl": nvxl_list,
            "months_cols": months_dict,
            "weeks_cols": weeks_dict
        }

        with open(DASHBOARD_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, ensure_ascii=False, indent=2)

        print(f"[{now_str}] ✅ Đã lưu ma trận Miền Tây 01 ({len(drivers_list)} NVGH & {len(nvxl_list)} NVXL) thành công!")
        return dashboard_data

    except Exception as ex:
        print(f"[{now_str}] ⚠️ Lỗi build cost dashboard MT01: {ex}")
        if os.path.exists(DASHBOARD_CACHE_FILE):
            with open(DASHBOARD_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        raise ex

def get_cost_dashboard_matrix():
    if os.path.exists(DASHBOARD_CACHE_FILE):
        try:
            # Tự động đồng bộ mới từ Google Sheets nếu file cache đã cũ quá 15 phút (900s)
            mtime = os.path.getmtime(DASHBOARD_CACHE_FILE)
            if (datetime.datetime.now().timestamp() - mtime) < 900:
                with open(DASHBOARD_CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    return build_cost_dashboard_matrix(force=True)

def query_mt01_cost_data(hub="all", mode="month", key=None):
    matrix = get_cost_dashboard_matrix()
    available_months = matrix.get("months", [])
    available_weeks = matrix.get("weeks", [])
    available_days = matrix.get("days", [])
    available_hubs = matrix.get("hubs", [])
    entities = matrix.get("entities", {})
    all_drivers = matrix.get("drivers", [])
    all_nvxl = matrix.get("nvxl", [])
    official_month_key = matrix.get("official_month_key", "")
    official_week_key = matrix.get("official_week_key", "")

    # Nếu file cache cũ chưa có trường nvxl hoặc chưa có don_gan trong drivers thì tự động rebuild
    if not all_nvxl or (all_drivers and "don_gan" not in all_drivers[0]):
        matrix = build_cost_dashboard_matrix(force=True)
        available_months = matrix.get("months", [])
        available_weeks = matrix.get("weeks", [])
        available_days = matrix.get("days", [])
        available_hubs = matrix.get("hubs", [])
        entities = matrix.get("entities", {})
        all_drivers = matrix.get("drivers", [])
        all_nvxl = matrix.get("nvxl", [])
        official_month_key = matrix.get("official_month_key", "")
        official_week_key = matrix.get("official_week_key", "")

    # Lọc các ngày đã có phát sinh dữ liệu thật (Volume gán > 0) để làm mặc định ngày mới nhất & vẽ biểu đồ
    mt01_vol_daily = entities.get("Toàn Vùng MT01", {}).get("metrics", {}).get("Volume gán", {}).get("daily", {})
    active_days = [d for d in available_days if _clean_num(mt01_vol_daily.get(d, 0)) > 0]
    if not active_days:
        active_days = available_days

    if mode == "month":
        if not key or key not in available_months:
            key = available_months[-1] if available_months else ""
    elif mode == "week":
        if not key or key not in available_weeks:
            key = available_weeks[-1] if available_weeks else ""
    elif mode == "day":
        if not key or key not in available_days:
            key = active_days[-1] if active_days else ""

    selected_ent_label = "Toàn Vùng MT01"
    if hub and hub != "all":
        for h_l in available_hubs:
            if hub.lower() in h_l.lower():
                selected_ent_label = h_l
                break

    # Xác định danh sách ngày thuộc kỳ đang chọn & các ngày đã có phát sinh số liệu
    if mode == "day" and key:
        period_all_days = [key]
    elif mode == "week" and key:
        w_cols = matrix.get("weeks_cols", {}).get(key, [])
        period_all_days = [available_days[c - 4] for c in w_cols if 0 <= c - 4 < len(available_days)]
    elif mode == "month" and key:
        m_cols = matrix.get("months_cols", {}).get(key, [])
        period_all_days = [available_days[c - 4] for c in m_cols if 0 <= c - 4 < len(available_days)]
    else:
        period_all_days = list(available_days)

    period_active_days = [d for d in period_all_days if d in active_days]
    if not period_active_days and period_all_days:
        period_active_days = period_all_days

    start_date_str = period_active_days[0] if period_active_days else (key or "")
    end_date_str = period_active_days[-1] if period_active_days else (key or "")
    active_days_cnt = len([d for d in period_all_days if d in active_days])

    if mode == "day":
        mode_vn = "Theo Ngày"
        date_range_text = f"Chốt số liệu Ngày {key} (1 ngày)"
        full_period_label = f"📅 NGÀY {key} • {selected_ent_label}"
    elif mode == "week":
        mode_vn = "Theo Tuần"
        year_suffix = end_date_str[-4:] if len(end_date_str) == 10 else "2026"
        date_range_text = f"Từ {start_date_str} ➔ {end_date_str} ({active_days_cnt}/{len(period_all_days)} ngày có số liệu)"
        full_period_label = f"📅 TUẦN {key} (Năm {year_suffix}) • Từ {start_date_str} ➔ {end_date_str} ({active_days_cnt} ngày chốt số)"
    else:
        mode_vn = "Theo Tháng"
        date_range_text = f"Từ {start_date_str} ➔ {end_date_str} ({active_days_cnt}/{len(period_all_days)} ngày có số liệu)"
        full_period_label = f"📅 {key.upper()} • Từ ngày {start_date_str} ➔ {end_date_str} ({active_days_cnt} ngày đã chốt số)"

    period_info = {
        "mode": mode,
        "mode_vn": mode_vn,
        "key": key,
        "hub": selected_ent_label,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "active_days_count": active_days_cnt,
        "total_days_in_period": len(period_all_days),
        "date_range_text": date_range_text,
        "full_label": full_period_label
    }

    ent_obj = entities.get(selected_ent_label, {})
    metrics_map = ent_obj.get("metrics", {})

    metric_keys = [
        "Volume gán", "Volume GTC", "Kg GTC", "Tỷ lệ GTC", "Stop GTC",
        "Lương giao", "Lương NVXL", "Chi phí xe tải",
        "Chi phí giao hàng + xe tải / đơn",
        "Chi phí giao hàng + xe tải / stop",
        "Chi phí giao hàng + Cost / kg"
    ]

    def extract_entity_values(target_metrics):
        out = {}
        if mode == "month" and official_month_key and key == official_month_key:
            for m in metric_keys:
                raw_v = target_metrics.get(m, {}).get("oct_official", "")
                num_v = _clean_num(raw_v)
                out[m] = {
                    "raw": raw_v,
                    "numeric": num_v,
                    "formatted": raw_v or (f"{num_v:.1f}%" if m == "Tỷ lệ GTC" else _format_vnd(num_v))
                }
        elif mode == "week" and official_week_key and key == official_week_key:
            for m in metric_keys:
                raw_v = target_metrics.get(m, {}).get("w44_official", "")
                num_v = _clean_num(raw_v)
                out[m] = {
                    "raw": raw_v,
                    "numeric": num_v,
                    "formatted": raw_v or (f"{num_v:.1f}%" if m == "Tỷ lệ GTC" else _format_vnd(num_v))
                }
        elif mode == "day" and key:
            for m in metric_keys:
                raw_v = target_metrics.get(m, {}).get("daily", {}).get(key, "")
                num_v = _clean_num(raw_v)
                out[m] = {
                    "raw": raw_v,
                    "numeric": num_v,
                    "formatted": raw_v or (f"{num_v:.1f}%" if m == "Tỷ lệ GTC" else _format_vnd(num_v))
                }
        else:
            col_indices = matrix.get("months_cols", {}).get(key, []) if mode == "month" else matrix.get("weeks_cols", {}).get(key, [])
            days_in_period = [available_days[c - 4] for c in col_indices if 0 <= c - 4 < len(available_days)]
            
            vol_gan = sum(_clean_num(target_metrics.get("Volume gán", {}).get("daily", {}).get(d, 0)) for d in days_in_period)
            vol_gtc = sum(_clean_num(target_metrics.get("Volume GTC", {}).get("daily", {}).get(d, 0)) for d in days_in_period)
            kg_gtc = sum(_clean_num(target_metrics.get("Kg GTC", {}).get("daily", {}).get(d, 0)) for d in days_in_period)
            stop_gtc = sum(_clean_num(target_metrics.get("Stop GTC", {}).get("daily", {}).get(d, 0)) for d in days_in_period)
            luong_giao = sum(_clean_num(target_metrics.get("Lương giao", {}).get("daily", {}).get(d, 0)) for d in days_in_period)
            luong_xl = sum(_clean_num(target_metrics.get("Lương NVXL", {}).get("daily", {}).get(d, 0)) for d in days_in_period)
            chi_phi_xe = sum(_clean_num(target_metrics.get("Chi phí xe tải", {}).get("daily", {}).get(d, 0)) for d in days_in_period)

            tot_cost = luong_giao + luong_xl + chi_phi_xe
            cost_per_order = (tot_cost / vol_gtc) if vol_gtc > 0 else 0
            cost_per_stop = (tot_cost / stop_gtc) if stop_gtc > 0 else 0
            cost_per_kg = (tot_cost / kg_gtc) if kg_gtc > 0 else 0
            rate_gtc = (vol_gtc / vol_gan * 100) if vol_gan > 0 else 0

            computed = {
                "Volume gán": (vol_gan, _format_vnd(vol_gan)),
                "Volume GTC": (vol_gtc, _format_vnd(vol_gtc)),
                "Kg GTC": (kg_gtc, _format_vnd(kg_gtc)),
                "Tỷ lệ GTC": (rate_gtc, f"{rate_gtc:.0f}%"),
                "Stop GTC": (stop_gtc, _format_vnd(stop_gtc)),
                "Lương giao": (luong_giao, _format_vnd(luong_giao)),
                "Lương NVXL": (luong_xl, _format_vnd(luong_xl)),
                "Chi phí xe tải": (chi_phi_xe, _format_vnd(chi_phi_xe)),
                "Chi phí giao hàng + xe tải / đơn": (cost_per_order, _format_vnd(cost_per_order)),
                "Chi phí giao hàng + xe tải / stop": (cost_per_stop, _format_vnd(cost_per_stop)),
                "Chi phí giao hàng + Cost / kg": (cost_per_kg, _format_vnd(cost_per_kg))
            }
            for m in metric_keys:
                num_v, fmt_v = computed[m]
                out[m] = {"raw": fmt_v, "numeric": num_v, "formatted": fmt_v}

        return out

    result_metrics = extract_entity_values(metrics_map)

    # Bảng phân rã 4 Kho trong MT01
    hubs_breakdown = []
    for h_label in ["Kho Cái Răng", "Kho Bình Thủy", "Kho Vị Thanh", "Kho Ô Môn"]:
        h_ent = entities.get(h_label, {})
        h_vals = extract_entity_values(h_ent.get("metrics", {}))
        row = {"hub_name": h_label}
        for m in metric_keys:
            row[m] = h_vals.get(m, {}).get("formatted", "-")
        hubs_breakdown.append(row)

    # PHÂN RÃ CHI TIẾT LƯƠNG & ĐƠN CỦA NHÂN VIÊN GIAO HÀNG (NVGH) THEO KHO & KỲ BÁO CÁO
    filtered_drivers = []
    for d in all_drivers:
        if selected_ent_label == "Toàn Vùng MT01" or d["hub_name"] == selected_ent_label:
            gtc_p = 0.0
            ltc_p = 0.0
            don_gan_p = 0.0
            don_gtc_p = 0.0
            don_ltc_p = 0.0
            for day_str in period_all_days:
                day_val = d.get("daily", {}).get(day_str)
                if isinstance(day_val, dict):
                    gtc_p += day_val.get("gtc", 0.0)
                    ltc_p += day_val.get("ltc", 0.0)
                    don_gan_p += day_val.get("don_gan", 0.0)
                    don_gtc_p += day_val.get("don_gtc", 0.0)
                    don_ltc_p += day_val.get("don_ltc", 0.0)
                elif day_val:
                    gtc_p += float(day_val)
            sal_period = gtc_p + ltc_p
            gtc_rate = (don_gtc_p / don_gan_p * 100.0) if don_gan_p > 0 else 0.0

            filtered_drivers.append({
                "driver_name": d["driver_name"],
                "hub_name": d["hub_name"],
                "don_gan": int(round(don_gan_p)),
                "formatted_don_gan": _format_vnd(don_gan_p),
                "don_gtc": int(round(don_gtc_p)),
                "formatted_don_gtc": _format_vnd(don_gtc_p),
                "don_ltc": int(round(don_ltc_p)),
                "formatted_don_ltc": _format_vnd(don_ltc_p),
                "gtc_rate": round(gtc_rate, 1),
                "formatted_gtc_rate": f"{gtc_rate:.1f}%" if don_gan_p > 0 else "0%",
                "gtc_salary": gtc_p,
                "formatted_gtc": _format_vnd(gtc_p) + " đ",
                "ltc_salary": ltc_p,
                "formatted_ltc": _format_vnd(ltc_p) + " đ",
                "period_salary": sal_period,
                "formatted_period_salary": _format_vnd(sal_period) + " đ",
                "total_salary": d.get("total_salary", 0.0),
                "formatted_total_salary": d.get("formatted_salary", _format_vnd(sal_period) + " đ")
            })

    # Sắp xếp NVGH theo lương kỳ cao nhất -> đơn GTC cao nhất
    filtered_drivers.sort(key=lambda x: (x["period_salary"], x["don_gtc"], x["don_gan"]), reverse=True)
    
    tot_driver_sal = sum(d["period_salary"] for d in filtered_drivers)
    tot_gtc_sal = sum(d["gtc_salary"] for d in filtered_drivers)
    tot_ltc_sal = sum(d["ltc_salary"] for d in filtered_drivers)
    tot_drv_gan = sum(d["don_gan"] for d in filtered_drivers)
    tot_drv_gtc = sum(d["don_gtc"] for d in filtered_drivers)
    tot_drv_ltc = sum(d["don_ltc"] for d in filtered_drivers)
    overall_drv_rate = (tot_drv_gtc / tot_drv_gan * 100.0) if tot_drv_gan > 0 else 0.0
    active_drv_cnt = sum(1 for d in filtered_drivers if d["period_salary"] > 0 or d["don_gan"] > 0)

    for idx, d in enumerate(filtered_drivers, 1):
        d["rank"] = idx
        pct = (d["period_salary"] / tot_driver_sal * 100) if tot_driver_sal > 0 else 0
        d["percentage"] = f"{pct:.1f}%"
        if pct >= 5.5:
            d["badge"] = "Top Thu Nhập"
            d["badge_color"] = "#10b981"
        elif d["period_salary"] > 0:
            if d["gtc_rate"] >= 85.0:
                d["badge"] = "Đạt KPI GTC"
                d["badge_color"] = "#3b82f6"
            else:
                d["badge"] = "Tích Cực"
                d["badge_color"] = "#f59e0b"
        else:
            d["badge"] = "Nghỉ / Dự Bị"
            d["badge_color"] = "#94a3b8"

    driver_summary = {
        "count": len(filtered_drivers),
        "active_count": active_drv_cnt,
        "total_don_gan": tot_drv_gan,
        "formatted_don_gan": _format_vnd(tot_drv_gan),
        "total_don_gtc": tot_drv_gtc,
        "formatted_don_gtc": _format_vnd(tot_drv_gtc),
        "total_don_ltc": tot_drv_ltc,
        "formatted_don_ltc": _format_vnd(tot_drv_ltc),
        "overall_gtc_rate": f"{overall_drv_rate:.1f}%",
        "total_salary": tot_driver_sal,
        "formatted_total": _format_vnd(tot_driver_sal) + " đ",
        "total_gtc": tot_gtc_sal,
        "formatted_gtc": _format_vnd(tot_gtc_sal) + " đ",
        "total_ltc": tot_ltc_sal,
        "formatted_ltc": _format_vnd(tot_ltc_sal) + " đ",
        "avg_salary": (tot_driver_sal / active_drv_cnt) if active_drv_cnt else 0,
        "formatted_avg": _format_vnd(tot_driver_sal / active_drv_cnt) + " đ" if active_drv_cnt else "0 đ"
    }

    # PHÂN RÃ CHI TIẾT LƯƠNG & ĐƠN CỦA NHÂN VIÊN XỬ LÝ KHO (NVXL) THEO KHO & KỲ BÁO CÁO
    filtered_nvxl = []
    for nv in all_nvxl:
        if selected_ent_label == "Toàn Vùng MT01" or nv["hub_name"] == selected_ent_label:
            l_xl = 0.0
            l_gn = 0.0
            d_gan = 0.0
            d_gtc = 0.0
            d_ltc = 0.0
            sl_xl = 0.0
            days_worked = 0
            for day_str in period_all_days:
                dv = nv.get("daily", {}).get(day_str)
                if isinstance(dv, dict):
                    l_xl += dv.get("luong_xl", 0.0)
                    l_gn += dv.get("luong_gn", 0.0)
                    d_gan += dv.get("don_gan", 0.0)
                    d_gtc += dv.get("don_gtc", 0.0)
                    d_ltc += dv.get("don_ltc", 0.0)
                    sl_xl += dv.get("san_luong_xl", 0.0)
                    if dv.get("luong_xl", 0.0) > 0 or dv.get("luong_gn", 0.0) > 0 or dv.get("don_gan", 0.0) > 0:
                        days_worked += 1

            tot_sal = l_xl + l_gn
            # Chỉ hiển thị NVXL có phát sinh trong kỳ hoặc thuộc danh sách 4 NVXL chính của 4 kho
            if tot_sal <= 0 and d_gan <= 0:
                continue

            gtc_rate_nv = (d_gtc / d_gan * 100.0) if d_gan > 0 else 0.0
            filtered_nvxl.append({
                "staff_id": nv.get("staff_id", ""),
                "nvxl_name": nv.get("nvxl_name", ""),
                "full_label": nv.get("full_label", nv.get("nvxl_name", "")),
                "hub_name": nv.get("hub_name", ""),
                "days_worked": days_worked,
                "don_gan": int(round(d_gan)),
                "formatted_don_gan": _format_vnd(d_gan),
                "don_gtc": int(round(d_gtc)),
                "formatted_don_gtc": _format_vnd(d_gtc),
                "don_ltc": int(round(d_ltc)),
                "formatted_don_ltc": _format_vnd(d_ltc),
                "gtc_rate": round(gtc_rate_nv, 1),
                "formatted_gtc_rate": f"{gtc_rate_nv:.1f}%" if d_gan > 0 else "0%",
                "luong_xl": l_xl,
                "formatted_luong_xl": _format_vnd(l_xl) + " đ",
                "luong_gn": l_gn,
                "formatted_luong_gn": _format_vnd(l_gn) + " đ",
                "period_salary": tot_sal,
                "formatted_period_salary": _format_vnd(tot_sal) + " đ"
            })

    filtered_nvxl.sort(key=lambda x: (x["period_salary"], x["luong_xl"], x["don_gtc"]), reverse=True)

    tot_nvxl_sal = sum(x["period_salary"] for x in filtered_nvxl)
    tot_nvxl_xl = sum(x["luong_xl"] for x in filtered_nvxl)
    tot_nvxl_gn = sum(x["luong_gn"] for x in filtered_nvxl)
    tot_nvxl_gan = sum(x["don_gan"] for x in filtered_nvxl)
    tot_nvxl_gtc = sum(x["don_gtc"] for x in filtered_nvxl)
    tot_nvxl_ltc = sum(x["don_ltc"] for x in filtered_nvxl)
    overall_nvxl_rate = (tot_nvxl_gtc / tot_nvxl_gan * 100.0) if tot_nvxl_gan > 0 else 0.0

    for idx, nv in enumerate(filtered_nvxl, 1):
        nv["rank"] = idx
        pct = (nv["period_salary"] / tot_nvxl_sal * 100) if tot_nvxl_sal > 0 else 0
        nv["percentage"] = f"{pct:.1f}%"
        if nv["gtc_rate"] >= 85.0:
            nv["badge"] = "Đạt Chuẩn KPI (≥85%)"
            nv["badge_color"] = "#10b981"
        elif nv["gtc_rate"] >= 80.0:
            nv["badge"] = "Cần Cố Gắng (80-84%)"
            nv["badge_color"] = "#f59e0b"
        else:
            nv["badge"] = "Cảnh Báo GTC (<80%)"
            nv["badge_color"] = "#ef4444"

    nvxl_summary = {
        "count": len(filtered_nvxl),
        "active_count": len(filtered_nvxl),
        "total_don_gan": tot_nvxl_gan,
        "formatted_don_gan": _format_vnd(tot_nvxl_gan),
        "total_don_gtc": tot_nvxl_gtc,
        "formatted_don_gtc": _format_vnd(tot_nvxl_gtc),
        "total_don_ltc": tot_nvxl_ltc,
        "formatted_don_ltc": _format_vnd(tot_nvxl_ltc),
        "overall_gtc_rate": f"{overall_nvxl_rate:.1f}%",
        "total_luong_xl": tot_nvxl_xl,
        "formatted_luong_xl": _format_vnd(tot_nvxl_xl) + " đ",
        "total_luong_gn": tot_nvxl_gn,
        "formatted_luong_gn": _format_vnd(tot_nvxl_gn) + " đ",
        "total_salary": tot_nvxl_sal,
        "formatted_total": _format_vnd(tot_nvxl_sal) + " đ",
        "avg_salary": (tot_nvxl_sal / len(filtered_nvxl)) if filtered_nvxl else 0,
        "formatted_avg": _format_vnd(tot_nvxl_sal / len(filtered_nvxl)) + " đ" if filtered_nvxl else "0 đ"
    }

    recent_days = active_days[-14:] if len(active_days) >= 14 else active_days
    trend_labels = []
    trend_volume = []
    trend_cost_per_order = []
    trend_total_cost = []

    vol_daily = metrics_map.get("Volume GTC", {}).get("daily", {})
    cost_per_order_daily = metrics_map.get("Chi phí giao hàng + xe tải / đơn", {}).get("daily", {})
    luong_giao_daily = metrics_map.get("Lương giao", {}).get("daily", {})
    truck_cost_daily = metrics_map.get("Chi phí xe tải", {}).get("daily", {})

    for d in recent_days:
        trend_labels.append(d[:5])
        v_num = _clean_num(vol_daily.get(d, 0))
        c_num = _clean_num(cost_per_order_daily.get(d, 0))
        tot_c = _clean_num(luong_giao_daily.get(d, 0)) + _clean_num(truck_cost_daily.get(d, 0))
        trend_volume.append(v_num)
        trend_cost_per_order.append(c_num)
        trend_total_cost.append(tot_c)

    return {
        "success": True,
        "last_sync": matrix.get("last_sync"),
        "region": "Miền Tây 01",
        "period_info": period_info,
        "filter": {
            "hub": selected_ent_label,
            "mode": mode,
            "key": key
        },
        "available_filters": {
            "hubs": ["Toàn Vùng MT01", "Kho Cái Răng", "Kho Bình Thủy", "Kho Vị Thanh", "Kho Ô Môn"],
            "months": available_months,
            "weeks": available_weeks,
            "days": available_days,
            "latest_active_day": active_days[-1] if active_days else (available_days[-1] if available_days else "")
        },
        "metrics": result_metrics,
        "hubs_breakdown": hubs_breakdown,
        "drivers_breakdown": {
            "summary": driver_summary,
            "list": filtered_drivers
        },
        "nvxl_breakdown": {
            "summary": nvxl_summary,
            "list": filtered_nvxl
        },
        "trend_chart": {
            "labels": trend_labels,
            "volume_gtc": trend_volume,
            "cost_per_order": trend_cost_per_order,
            "total_cost": trend_total_cost
        }
    }


def generate_mt01_cost_excel_report(hub="all", mode="month", key=None):
    """
    Xuất báo cáo Excel đối soát Chi Phí, Sản Lượng Đơn & Bảng Lương (NVGH + NVXL + Xe Tải 365)
    được thiết kế chuẩn Executive: tự động căn chỉnh độ rộng cột, định dạng số nguyên VNĐ (#,##0 "đ"),
    tô màu cảnh báo KPI, đóng khung viền và ghim dòng tiêu đề.
    """
    import re
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    data = query_mt01_cost_data(hub=hub, mode=mode, key=key)
    p_info = data.get("period_info", {})
    flt = data.get("filter", {})
    hub_label = flt.get("hub", "Toàn Vùng MT01")
    period_title = p_info.get("period_title") or flt.get("key") or "Kỳ Hiện Tại"
    date_range_str = p_info.get("date_range_str") or "Đang cập nhật"
    active_days_cnt = p_info.get("active_days_count", 0)
    total_days_cnt = p_info.get("total_days_in_period", 0)
    last_sync_str = data.get("last_sync") or datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")

    wb = Workbook()

    # Bảng màu & Style chuẩn GHN Executive
    FONT_FAMILY = "Segoe UI"
    f_banner_title = Font(name=FONT_FAMILY, size=14, bold=True, color="FFFFFF")
    f_banner_sub = Font(name=FONT_FAMILY, size=10, bold=True, color="065F46")
    f_sec_title = Font(name=FONT_FAMILY, size=11, bold=True, color="0F172A")
    f_tbl_header = Font(name=FONT_FAMILY, size=10, bold=True, color="FFFFFF")
    f_total_row = Font(name=FONT_FAMILY, size=10, bold=True, color="065F46")
    f_data_reg = Font(name=FONT_FAMILY, size=10, bold=False, color="0F172A")
    f_data_bold = Font(name=FONT_FAMILY, size=10, bold=True, color="0F172A")
    f_data_muted = Font(name=FONT_FAMILY, size=9, italic=True, color="475569")

    fill_banner = PatternFill("solid", fgColor="064E3B")      # Deep Emerald
    fill_sub = PatternFill("solid", fgColor="ECFDF5")         # Mint Tint
    fill_sec = PatternFill("solid", fgColor="E2E8F0")         # Slate Section Header
    fill_header = PatternFill("solid", fgColor="0F172A")      # Dark Slate Header
    fill_header_nvxl = PatternFill("solid", fgColor="1E3A8A") # Navy Header for NVXL
    fill_total = PatternFill("solid", fgColor="D1FAE5")       # Emerald Summary Row
    fill_zebra_even = PatternFill("solid", fgColor="FFFFFF")
    fill_zebra_odd = PatternFill("solid", fgColor="F8FAFC")

    # Màu cảnh báo KPI
    fill_good = PatternFill("solid", fgColor="DCFCE7")
    font_good = Font(name=FONT_FAMILY, size=10, bold=True, color="166534")
    fill_warn = PatternFill("solid", fgColor="FEF3C7")
    font_warn = Font(name=FONT_FAMILY, size=10, bold=True, color="92400E")
    fill_bad = PatternFill("solid", fgColor="FEE2E2")
    font_bad = Font(name=FONT_FAMILY, size=10, bold=True, color="991B1B")
    fill_info = PatternFill("solid", fgColor="DBEAFE")
    font_info = Font(name=FONT_FAMILY, size=10, bold=True, color="1E40AF")

    thin_side = Side(style="thin", color="CBD5E1")
    med_emerald = Side(style="medium", color="059669")
    med_dark = Side(style="medium", color="0F172A")

    b_data = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    b_header = Border(left=thin_side, right=thin_side, top=med_dark, bottom=med_dark)
    b_total = Border(left=thin_side, right=thin_side, top=med_emerald, bottom=med_emerald)

    al_center = Alignment(horizontal="center", vertical="center", wrap_text=False)
    al_left = Alignment(horizontal="left", vertical="center", wrap_text=False)
    al_right = Alignment(horizontal="right", vertical="center", wrap_text=False)

    FMT_VND = '#,##0 "đ"'
    FMT_INT = '#,##0'
    FMT_PCT = '0.0%'

    def _add_sheet_banner(ws, title_text, max_col):
        last_col_letter = get_column_letter(max_col)
        ws.merge_cells(f"A1:{last_col_letter}1")
        ws.merge_cells(f"A2:{last_col_letter}2")

        c1 = ws["A1"]
        c1.value = title_text
        c1.font = f_banner_title
        c1.fill = fill_banner
        c1.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[1].height = 34

        c2 = ws["A2"]
        c2.value = (
            f"📅 Kỳ báo cáo: {period_title}   |   📆 Ngày có số liệu: {date_range_str} "
            f"({active_days_cnt}/{total_days_cnt} ngày)   |   📍 Phạm vi: {hub_label}   |   🕒 Đồng bộ: {last_sync_str}"
        )
        c2.font = f_banner_sub
        c2.fill = fill_sub
        c2.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[2].height = 24
        ws.row_dimensions[3].height = 10

    def _style_rate_cell(cell, rate_pct):
        if rate_pct >= 85.0:
            cell.fill = fill_good
            cell.font = font_good
        elif rate_pct >= 80.0:
            cell.fill = fill_warn
            cell.font = font_warn
        else:
            cell.fill = fill_bad
            cell.font = font_bad

    def _style_badge_cell(cell, badge_text):
        txt = str(badge_text or "")
        if "Top" in txt or "Đạt Chuẩn" in txt or "Chuẩn Đối Soát" in txt:
            cell.fill = fill_good
            cell.font = font_good
        elif "Đạt KPI" in txt:
            cell.fill = fill_info
            cell.font = font_info
        elif "Cố Gắng" in txt or "Tích Cực" in txt:
            cell.fill = fill_warn
            cell.font = font_warn
        elif "Cảnh Báo" in txt:
            cell.fill = fill_bad
            cell.font = font_bad
        else:
            cell.font = f_data_muted

    def _auto_fit_and_polish_sheet(ws, start_row=4, freeze_cell="A6", filter_range=None):
        ws.views.sheetView[0].showGridLines = True
        if freeze_cell:
            ws.freeze_panes = freeze_cell
        if filter_range:
            ws.auto_filter.ref = filter_range

        ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0

        for col_idx in range(1, ws.max_column + 1):
            col_letter = get_column_letter(col_idx)
            max_len = 0
            for row_idx in range(start_row, ws.max_row + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                val = cell.value
                if val is None:
                    continue
                num_fmt = cell.number_format or ""
                if isinstance(val, (int, float)):
                    if "đ" in num_fmt:
                        s_len = len(f"{int(round(val)):,} đ") + 2
                    elif "%" in num_fmt:
                        s_len = len(f"{val * 100:.1f}%") + 2
                    else:
                        s_len = len(f"{int(round(val)):,}") + 2
                else:
                    s_len = len(str(val).strip())
                if s_len > max_len:
                    max_len = s_len
            ws.column_dimensions[col_letter].width = max(max_len + 5, 13)

    # =========================================================================
    # SHEET 1: TỔNG QUAN 11 CHỈ SỐ & SO SÁNH 4 KHO MIỀN TÂY 01
    # =========================================================================
    ws1 = wb.active
    ws1.title = "1_Tong_Quan_&_4_Kho_MT01"
    _add_sheet_banner(ws1, f"BÁO CÁO ĐỐI SOÁT CHI PHÍ & HIỆU QUẢ VẬN HÀNH MIỀN TÂY 01 — {period_title.upper()}", 12)

    headers_s1 = [
        "Đơn Vị / Kho Vận Hành",
        "Volume Gán",
        "Volume GTC",
        "Kg GTC",
        "Tỷ Lệ GTC",
        "Stop GTC",
        "Lương Giao NVGH (VNĐ)",
        "Lương NVXL Kho (VNĐ)",
        "Chi Phí Xe Tải 365 (VNĐ)",
        "CP Giao + Xe / Đơn",
        "CP Giao + Xe / Stop",
        "CP Giao + Cost / Kg"
    ]
    metric_keys_s1 = [
        "Volume gán",
        "Volume GTC",
        "Kg GTC",
        "Tỷ lệ GTC",
        "Stop GTC",
        "Lương giao",
        "Lương NVXL",
        "Chi phí xe tải",
        "Chi phí giao hàng + xe tải / đơn",
        "Chi phí giao hàng + xe tải / stop",
        "Chi phí giao hàng + Cost / kg"
    ]
    money_metrics_s1 = {
        "Lương giao", "Lương NVXL", "Chi phí xe tải",
        "Chi phí giao hàng + xe tải / đơn", "Chi phí giao hàng + xe tải / stop", "Chi phí giao hàng + Cost / kg"
    }

    r_idx = 4
    ws1.row_dimensions[r_idx].height = 28
    for c_idx, h_text in enumerate(headers_s1, 1):
        c = ws1.cell(row=r_idx, column=c_idx, value=h_text)
        c.font = f_tbl_header
        c.fill = fill_header
        c.border = b_header
        c.alignment = al_center if c_idx > 1 else al_left

    # Dòng Tổng Toàn Vùng MT01 (ghim đầu bảng)
    r_idx = 5
    ws1.row_dimensions[r_idx].height = 25
    tot_metrics = data.get("metrics", {})
    c_hub = ws1.cell(row=r_idx, column=1, value=f"∑ {hub_label.upper()} (TỔNG HỢP)")
    c_hub.font = f_total_row
    c_hub.fill = fill_total
    c_hub.border = b_total
    c_hub.alignment = al_left

    for c_idx, m_key in enumerate(metric_keys_s1, 2):
        m_obj = tot_metrics.get(m_key, {})
        num_val = float(m_obj.get("numeric", 0.0) or 0.0)
        cell = ws1.cell(row=r_idx, column=c_idx)
        cell.fill = fill_total
        cell.border = b_total
        if m_key == "Tỷ lệ GTC":
            cell.value = round(num_val / 100.0, 4)
            cell.number_format = FMT_PCT
            cell.alignment = al_center
            _style_rate_cell(cell, num_val)
        elif m_key in money_metrics_s1:
            cell.value = int(round(num_val))
            cell.number_format = FMT_VND
            cell.font = f_total_row
            cell.alignment = al_right
        else:
            cell.value = int(round(num_val))
            cell.number_format = FMT_INT
            cell.font = f_total_row
            cell.alignment = al_right

    # 4 Kho chi tiết
    for idx_h, h_row in enumerate(data.get("hubs_breakdown", []), 1):
        r_idx += 1
        ws1.row_dimensions[r_idx].height = 23
        z_fill = fill_zebra_odd if idx_h % 2 == 1 else fill_zebra_even

        c_name = ws1.cell(row=r_idx, column=1, value=h_row.get("hub_name", ""))
        c_name.font = f_data_bold
        c_name.fill = z_fill
        c_name.border = b_data
        c_name.alignment = al_left

        for c_idx, m_key in enumerate(metric_keys_s1, 2):
            raw_str = h_row.get(m_key, "0")
            num_val = _clean_num(raw_str)
            cell = ws1.cell(row=r_idx, column=c_idx)
            cell.fill = z_fill
            cell.border = b_data
            if m_key == "Tỷ lệ GTC":
                cell.value = round(num_val / 100.0, 4)
                cell.number_format = FMT_PCT
                cell.alignment = al_center
                _style_rate_cell(cell, num_val)
            elif m_key in money_metrics_s1:
                cell.value = int(round(num_val))
                cell.number_format = FMT_VND
                cell.font = f_data_reg
                cell.alignment = al_right
            else:
                cell.value = int(round(num_val))
                cell.number_format = FMT_INT
                cell.font = f_data_reg
                cell.alignment = al_right

    _auto_fit_and_polish_sheet(ws1, start_row=4, freeze_cell="B6", filter_range=f"A4:L{r_idx}")

    # =========================================================================
    # SHEET 2: BẢNG LƯƠNG & ĐƠN CHI TIẾT NV GIAO HÀNG (NVGH)
    # =========================================================================
    ws2 = wb.create_sheet(title="2_Bang_Luong_&_Don_NVGH")
    _add_sheet_banner(ws2, f"BẢNG LƯƠNG & SẢN LƯỢNG ĐƠN NHÂN VIÊN GIAO HÀNG (NVGH) — {period_title.upper()}", 12)

    headers_s2 = [
        "Hạng",
        "Họ & Tên NV Giao Hàng (NVGH)",
        "Kho Trực Thuộc",
        "Đơn Gán",
        "Đơn GTC",
        "Đơn LTC",
        "Tỷ Lệ GTC",
        "Lương GTC (VNĐ)",
        "LHH LTC (VNĐ)",
        "Tổng Thu Nhập (VNĐ)",
        "Tỷ Trọng",
        "Đánh Giá KPI"
    ]
    ws2.row_dimensions[4].height = 28
    for c_idx, h_text in enumerate(headers_s2, 1):
        c = ws2.cell(row=4, column=c_idx, value=h_text)
        c.font = f_tbl_header
        c.fill = fill_header
        c.border = b_header
        c.alignment = al_center if c_idx not in (2, 3) else al_left

    drv_sum = data.get("drivers_breakdown", {}).get("summary", {})
    drv_list = data.get("drivers_breakdown", {}).get("list", [])
    tot_drv_sal = float(drv_sum.get("total_salary", 0.0) or 0.0)
    tot_drv_gan = int(round(drv_sum.get("total_don_gan", 0) or 0))
    tot_drv_gtc = int(round(drv_sum.get("total_don_gtc", 0) or 0))
    tot_drv_ltc = int(round(drv_sum.get("total_don_ltc", 0) or 0))
    tot_drv_rate = (tot_drv_gtc / tot_drv_gan * 100.0) if tot_drv_gan > 0 else 0.0

    # Dòng Tổng Cộng NVGH (Row 5)
    ws2.row_dimensions[5].height = 25
    sum_row_s2 = [
        "∑",
        f"TỔNG CỘNG TOÀN BẢNG ({drv_sum.get('active_count', len(drv_list))} NVGH có phát sinh)",
        hub_label,
        tot_drv_gan,
        tot_drv_gtc,
        tot_drv_ltc,
        round(tot_drv_rate / 100.0, 4),
        int(round(drv_sum.get("total_gtc", 0.0) or 0.0)),
        int(round(drv_sum.get("total_ltc", 0.0) or 0.0)),
        int(round(tot_drv_sal)),
        1.0,
        "Chuẩn Đối Soát"
    ]
    for c_idx, val in enumerate(sum_row_s2, 1):
        c = ws2.cell(row=5, column=c_idx, value=val)
        c.font = f_total_row
        c.fill = fill_total
        c.border = b_total
        if c_idx in (1, 7, 11, 12):
            c.alignment = al_center
        elif c_idx in (2, 3):
            c.alignment = al_left
        else:
            c.alignment = al_right

        if c_idx in (4, 5, 6):
            c.number_format = FMT_INT
        elif c_idx in (7, 11):
            c.number_format = FMT_PCT
        elif c_idx in (8, 9, 10):
            c.number_format = FMT_VND

    r_idx = 5
    for idx_d, d in enumerate(drv_list, 1):
        r_idx += 1
        ws2.row_dimensions[r_idx].height = 22
        z_fill = fill_zebra_odd if idx_d % 2 == 1 else fill_zebra_even
        pct_ratio = (float(d.get("period_salary", 0.0)) / tot_drv_sal) if tot_drv_sal > 0 else 0.0
        rate_val = float(d.get("gtc_rate", 0.0) or 0.0)

        row_vals = [
            f"#{d.get('rank', idx_d)}",
            d.get("driver_name", ""),
            d.get("hub_name", ""),
            int(round(d.get("don_gan", 0) or 0)),
            int(round(d.get("don_gtc", 0) or 0)),
            int(round(d.get("don_ltc", 0) or 0)),
            round(rate_val / 100.0, 4),
            int(round(d.get("gtc_salary", 0.0) or 0.0)),
            int(round(d.get("ltc_salary", 0.0) or 0.0)),
            int(round(d.get("period_salary", 0.0) or 0.0)),
            round(pct_ratio, 4),
            d.get("badge", "")
        ]
        for c_idx, val in enumerate(row_vals, 1):
            c = ws2.cell(row=r_idx, column=c_idx, value=val)
            c.fill = z_fill
            c.border = b_data
            c.font = f_data_bold if c_idx in (1, 2, 10) else f_data_reg

            if c_idx in (1, 7, 11, 12):
                c.alignment = al_center
            elif c_idx in (2, 3):
                c.alignment = al_left
            else:
                c.alignment = al_right

            if c_idx in (4, 5, 6):
                c.number_format = FMT_INT
            elif c_idx == 7:
                c.number_format = FMT_PCT
                if d.get("don_gan", 0) > 0:
                    _style_rate_cell(c, rate_val)
            elif c_idx in (8, 9, 10):
                c.number_format = FMT_VND
            elif c_idx == 11:
                c.number_format = FMT_PCT
            elif c_idx == 12:
                _style_badge_cell(c, val)

    _auto_fit_and_polish_sheet(ws2, start_row=4, freeze_cell="C6", filter_range=f"A4:L{r_idx}")

    # =========================================================================
    # SHEET 3: BẢNG LƯƠNG & ĐƠN CHI TIẾT NV XỬ LÝ KHO (NVXL)
    # =========================================================================
    ws3 = wb.create_sheet(title="3_Bang_Luong_&_Don_NVXL")
    _add_sheet_banner(ws3, f"BẢNG LƯƠNG & SẢN LƯỢNG ĐƠN NHÂN VIÊN XỬ LÝ KHO (NVXL) — {period_title.upper()}", 14)

    headers_s3 = [
        "Hạng",
        "Mã NV",
        "Họ & Tên NV Xử Lý Kho (NVXL)",
        "Kho Trực Thuộc",
        "Số Ngày Có Số Liệu",
        "Đơn Gán",
        "Đơn GTC",
        "Đơn LTC",
        "Tỷ Lệ GTC",
        "Lương Xử Lý Kho (VNĐ)",
        "Lương Giao Nhận Kiêm Nhiệm (VNĐ)",
        "Tổng Thu Nhập (VNĐ)",
        "Tỷ Trọng",
        "Đánh Giá KPI"
    ]
    ws3.row_dimensions[4].height = 28
    for c_idx, h_text in enumerate(headers_s3, 1):
        c = ws3.cell(row=4, column=c_idx, value=h_text)
        c.font = f_tbl_header
        c.fill = fill_header_nvxl
        c.border = b_header
        c.alignment = al_center if c_idx not in (3, 4) else al_left

    nvxl_sum = data.get("nvxl_breakdown", {}).get("summary", {})
    nvxl_list = data.get("nvxl_breakdown", {}).get("list", [])
    tot_nvxl_sal = float(nvxl_sum.get("total_salary", 0.0) or 0.0)
    tot_nvxl_gan = int(round(nvxl_sum.get("total_don_gan", 0) or 0))
    tot_nvxl_gtc = int(round(nvxl_sum.get("total_don_gtc", 0) or 0))
    tot_nvxl_ltc = int(round(nvxl_sum.get("total_don_ltc", 0) or 0))
    tot_nvxl_rate = (tot_nvxl_gtc / tot_nvxl_gan * 100.0) if tot_nvxl_gan > 0 else 0.0

    ws3.row_dimensions[5].height = 25
    sum_row_s3 = [
        "∑",
        "ALL",
        f"TỔNG CỘNG TOÀN BẢNG ({nvxl_sum.get('count', len(nvxl_list))} NVXL)",
        hub_label,
        active_days_cnt,
        tot_nvxl_gan,
        tot_nvxl_gtc,
        tot_nvxl_ltc,
        round(tot_nvxl_rate / 100.0, 4),
        int(round(nvxl_sum.get("total_luong_xl", 0.0) or 0.0)),
        int(round(nvxl_sum.get("total_luong_gn", 0.0) or 0.0)),
        int(round(tot_nvxl_sal)),
        1.0,
        "Chuẩn Đối Soát"
    ]
    for c_idx, val in enumerate(sum_row_s3, 1):
        c = ws3.cell(row=5, column=c_idx, value=val)
        c.font = f_total_row
        c.fill = fill_total
        c.border = b_total
        if c_idx in (1, 2, 5, 9, 13, 14):
            c.alignment = al_center
        elif c_idx in (3, 4):
            c.alignment = al_left
        else:
            c.alignment = al_right

        if c_idx in (5, 6, 7, 8):
            c.number_format = FMT_INT
        elif c_idx in (9, 13):
            c.number_format = FMT_PCT
        elif c_idx in (10, 11, 12):
            c.number_format = FMT_VND

    r_idx = 5
    for idx_nv, nv in enumerate(nvxl_list, 1):
        r_idx += 1
        ws3.row_dimensions[r_idx].height = 23
        z_fill = fill_zebra_odd if idx_nv % 2 == 1 else fill_zebra_even
        pct_ratio = (float(nv.get("period_salary", 0.0)) / tot_nvxl_sal) if tot_nvxl_sal > 0 else 0.0
        rate_val = float(nv.get("gtc_rate", 0.0) or 0.0)

        row_vals = [
            f"#{nv.get('rank', idx_nv)}",
            nv.get("staff_id", "") or "-",
            nv.get("nvxl_name", "") or nv.get("full_label", ""),
            nv.get("hub_name", ""),
            int(nv.get("days_worked", 0) or 0),
            int(round(nv.get("don_gan", 0) or 0)),
            int(round(nv.get("don_gtc", 0) or 0)),
            int(round(nv.get("don_ltc", 0) or 0)),
            round(rate_val / 100.0, 4),
            int(round(nv.get("luong_xl", 0.0) or 0.0)),
            int(round(nv.get("luong_gn", 0.0) or 0.0)),
            int(round(nv.get("period_salary", 0.0) or 0.0)),
            round(pct_ratio, 4),
            nv.get("badge", "")
        ]
        for c_idx, val in enumerate(row_vals, 1):
            c = ws3.cell(row=r_idx, column=c_idx, value=val)
            c.fill = z_fill
            c.border = b_data
            c.font = f_data_bold if c_idx in (1, 3, 12) else f_data_reg

            if c_idx in (1, 2, 5, 9, 13, 14):
                c.alignment = al_center
            elif c_idx in (3, 4):
                c.alignment = al_left
            else:
                c.alignment = al_right

            if c_idx in (5, 6, 7, 8):
                c.number_format = FMT_INT
            elif c_idx == 9:
                c.number_format = FMT_PCT
                if nv.get("don_gan", 0) > 0:
                    _style_rate_cell(c, rate_val)
            elif c_idx in (10, 11, 12):
                c.number_format = FMT_VND
            elif c_idx == 13:
                c.number_format = FMT_PCT
            elif c_idx == 14:
                _style_badge_cell(c, val)

    _auto_fit_and_polish_sheet(ws3, start_row=4, freeze_cell="D6", filter_range=f"A4:N{r_idx}")

    # =========================================================================
    # SHEET 4: ĐỐI SOÁT XE TẢI CỐ ĐỊNH NCC VẬN TẢI 365
    # =========================================================================
    ws4 = wb.create_sheet(title="4_Xe_Co_Dinh_NCC_365")
    _add_sheet_banner(ws4, f"BẢNG ĐỐI SOÁT XE TẢI CỐ ĐỊNH (NCC VẬN TẢI 365) — {period_title.upper()}", 9)

    headers_s4 = [
        "Ngày Vận Hành",
        "Kho Cái Răng (Chuẩn 6)",
        "Kho Bình Thủy (Chuẩn 3)",
        "Kho Vị Thanh (Chuẩn 2)",
        "Kho Ô Môn (Chuẩn 2)",
        "Tổng Xe Chạy Thực Tế",
        "Định Mức Vùng (13 Xe)",
        "Chênh Lệch (Xe)",
        "Ghi Chú / Trạng Thái"
    ]
    ws4.row_dimensions[4].height = 28
    for c_idx, h_text in enumerate(headers_s4, 1):
        c = ws4.cell(row=4, column=c_idx, value=h_text)
        c.font = f_tbl_header
        c.fill = fill_header
        c.border = b_header
        c.alignment = al_center if c_idx < 9 else al_left

    truck_records = []
    cost_cache_path = os.path.join(DATA_DIR, "mt01_cost_analytics.json")
    if os.path.exists(cost_cache_path):
        try:
            with open(cost_cache_path, "r", encoding="utf-8") as f:
                t_cache = json.load(f)
                truck_records = t_cache.get("truck_analytics", {}).get("daily_records", [])
        except Exception:
            truck_records = []

    tot_cr = sum(int(r.get("hubs", {}).get("Cái Răng", {}).get("running", 0)) for r in truck_records)
    tot_bt = sum(int(r.get("hubs", {}).get("Bình Thủy", {}).get("running", 0)) for r in truck_records)
    tot_vt = sum(int(r.get("hubs", {}).get("Vị Thanh", {}).get("running", 0)) for r in truck_records)
    tot_om = sum(int(r.get("hubs", {}).get("Ô Môn", {}).get("running", 0)) for r in truck_records)
    tot_run = sum(int(r.get("total_running", 0)) for r in truck_records)
    tot_norm = len(truck_records) * 13
    tot_diff = tot_run - tot_norm

    ws4.row_dimensions[5].height = 25
    sum_row_s4 = [
        f"∑ TỔNG ({len(truck_records)} ngày)",
        tot_cr,
        tot_bt,
        tot_vt,
        tot_om,
        tot_run,
        tot_norm,
        tot_diff,
        "Tổng hợp lượt xe chạy thực tế so với định mức"
    ]
    for c_idx, val in enumerate(sum_row_s4, 1):
        c = ws4.cell(row=5, column=c_idx, value=val)
        c.font = f_total_row
        c.fill = fill_total
        c.border = b_total
        c.alignment = al_center if c_idx < 9 else al_left
        if 2 <= c_idx <= 8:
            c.number_format = FMT_INT

    r_idx = 5
    for idx_t, rec in enumerate(truck_records, 1):
        r_idx += 1
        ws4.row_dimensions[r_idx].height = 22
        z_fill = fill_zebra_odd if idx_t % 2 == 1 else fill_zebra_even

        cr_v = int(rec.get("hubs", {}).get("Cái Răng", {}).get("running", 0))
        bt_v = int(rec.get("hubs", {}).get("Bình Thủy", {}).get("running", 0))
        vt_v = int(rec.get("hubs", {}).get("Vị Thanh", {}).get("running", 0))
        om_v = int(rec.get("hubs", {}).get("Ô Môn", {}).get("running", 0))
        tot_v = int(rec.get("total_running", 0))
        norm_v = int(rec.get("standard_norm", 13))
        diff_v = int(rec.get("diff", tot_v - norm_v))

        if tot_v == 0:
            note_str = "Chưa phát sinh / Nghỉ"
        elif diff_v == 0:
            note_str = "Đủ định mức (13/13 xe)"
        elif diff_v < 0:
            notes = []
            if cr_v < 6: notes.append(f"CR -{6-cr_v}")
            if bt_v < 3: notes.append(f"BT -{3-bt_v}")
            if vt_v < 2: notes.append(f"VT -{2-vt_v}")
            if om_v < 2: notes.append(f"OM -{2-om_v}")
            note_str = f"Giảm {abs(diff_v)} xe ({', '.join(notes)})"
        else:
            note_str = f"Tăng cường +{diff_v} xe"

        row_vals = [rec.get("date", ""), cr_v, bt_v, vt_v, om_v, tot_v, norm_v, diff_v, note_str]
        for c_idx, val in enumerate(row_vals, 1):
            c = ws4.cell(row=r_idx, column=c_idx, value=val)
            c.fill = z_fill
            c.border = b_data
            c.font = f_data_bold if c_idx in (1, 6) else f_data_reg
            c.alignment = al_center if c_idx < 9 else al_left
            if 2 <= c_idx <= 8:
                c.number_format = FMT_INT
            if c_idx == 8:
                if diff_v == 0 and tot_v > 0:
                    c.fill = fill_good
                    c.font = font_good
                elif diff_v < 0 and tot_v > 0:
                    c.fill = fill_warn
                    c.font = font_warn

    _auto_fit_and_polish_sheet(ws4, start_row=4, freeze_cell="B6", filter_range=f"A4:I{r_idx}")

    # Lưu ra file chuẩn và trả về tên file tải về theo kỳ báo cáo
    excel_path = os.path.join(DATA_DIR, "Bao_Cao_Doi_Soat_MT01_Latest.xlsx")
    wb.save(excel_path)

    safe_key = re.sub(r"[^0-9A-Za-zÀ-ỹ_\-]+", "_", str(flt.get("key") or "Latest")).strip("_")
    download_filename = f"Bao_Cao_Doi_Soat_MT01_{safe_key}.xlsx"
    return excel_path, download_filename


if __name__ == "__main__":
    build_cost_dashboard_matrix(force=True)
    res = query_mt01_cost_data(hub="all", mode="month", key="Tháng 10-Năm 2026")
    print("\n--- MT01 DRIVERS SUMMARY ---")
    print(res["drivers_breakdown"]["summary"])
    print(f"Top 5 Drivers:")
    for d in res["drivers_breakdown"]["list"][:5]:
        print(f"  #{d['rank']} {d['driver_name']} ({d['hub_name']}): {d['formatted_period_salary']} ({d['percentage']})")

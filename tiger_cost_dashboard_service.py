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

        # 2. BẢNG CHI TIẾT LƯƠNG TÀI XẾ (NVGH) TỪ SHEET 'Data Raw' (BAO GỒM LHH GTC VÀ LHH LTC)
        drivers_list = []
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
                    driver_val = r[col_driver].strip()
                    if not driver_val:
                        continue

                    date_val = r[col_date].strip() if col_date >= 0 and col_date < len(r) else ""
                    if not date_val or "/2026" not in date_val:
                        continue

                    ltc_val = parse_vietnamese_float(r[col_ltc]) if col_ltc >= 0 and col_ltc < len(r) else 0.0
                    gtc_val = parse_vietnamese_float(r[col_gtc]) if col_gtc >= 0 and col_gtc < len(r) else 0.0
                    tot_val = gtc_val + ltc_val

                    if driver_val not in driver_map:
                        driver_map[driver_val] = {
                            "driver_name": driver_val,
                            "hub_name": hub_name_map[hub_val],
                            "gtc_salary": 0.0,
                            "ltc_salary": 0.0,
                            "total_salary": 0.0,
                            "daily": {}
                        }

                    driver_map[driver_val]["gtc_salary"] += gtc_val
                    driver_map[driver_val]["ltc_salary"] += ltc_val
                    driver_map[driver_val]["total_salary"] += tot_val

                    if date_val:
                        if date_val not in driver_map[driver_val]["daily"]:
                            driver_map[driver_val]["daily"][date_val] = {"gtc": 0.0, "ltc": 0.0, "total": 0.0}
                        driver_map[driver_val]["daily"][date_val]["gtc"] += gtc_val
                        driver_map[driver_val]["daily"][date_val]["ltc"] += ltc_val
                        driver_map[driver_val]["daily"][date_val]["total"] += tot_val

                # Bổ sung các tài xế chính thức nếu chưa có chuyến
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
                            "daily": {}
                        }

                for d in driver_map.values():
                    d["formatted_gtc"] = _format_vnd(d["gtc_salary"]) + " đ"
                    d["formatted_ltc"] = _format_vnd(d["ltc_salary"]) + " đ"
                    d["formatted_salary"] = _format_vnd(d["total_salary"]) + " đ"
                    drivers_list.append(d)
        except Exception as sal_ex:
            print(f"[{now_str}] ⚠️ Lỗi đọc sheet Data Raw: {sal_ex}")

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
            "months_cols": months_dict,
            "weeks_cols": weeks_dict
        }

        with open(DASHBOARD_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, ensure_ascii=False, indent=2)

        print(f"[{now_str}] ✅ Đã lưu ma trận Miền Tây 01 & {len(drivers_list)} tài xế thành công!")
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

    # PHÂN RÃ CHI TIẾT LƯƠNG TÀI XẾ (NVGH) THEO BỘ LỌC KHO & KỲ BÁO CÁO (BAO GỒM LHH GTC VÀ LHH LTC)
    filtered_drivers = []
    for d in all_drivers:
        if selected_ent_label == "Toàn Vùng MT01" or d["hub_name"] == selected_ent_label:
            if mode == "day" and key:
                day_val = d.get("daily", {}).get(key, {})
                if isinstance(day_val, dict):
                    gtc_p = day_val.get("gtc", 0.0)
                    ltc_p = day_val.get("ltc", 0.0)
                    sal_period = day_val.get("total", gtc_p + ltc_p)
                else:
                    sal_period = float(day_val) if day_val else 0.0
                    gtc_p = sal_period
                    ltc_p = 0.0
            elif mode == "week" and key and key in matrix.get("weeks_cols", {}) and available_days:
                w_col_indices = matrix.get("weeks_cols", {}).get(key, [])
                days_in_week = [available_days[c - 4] for c in w_col_indices if 0 <= c - 4 < len(available_days)]
                gtc_p = sum(d.get("daily", {}).get(day_str, {}).get("gtc", 0.0) if isinstance(d.get("daily", {}).get(day_str), dict) else 0.0 for day_str in days_in_week)
                ltc_p = sum(d.get("daily", {}).get(day_str, {}).get("ltc", 0.0) if isinstance(d.get("daily", {}).get(day_str), dict) else 0.0 for day_str in days_in_week)
                sal_period = gtc_p + ltc_p
            elif mode == "month" and key and key in matrix.get("months_cols", {}) and available_days:
                m_col_indices = matrix.get("months_cols", {}).get(key, [])
                days_in_month = [available_days[c - 4] for c in m_col_indices if 0 <= c - 4 < len(available_days)]
                gtc_p = sum(d.get("daily", {}).get(day_str, {}).get("gtc", 0.0) if isinstance(d.get("daily", {}).get(day_str), dict) else 0.0 for day_str in days_in_month)
                ltc_p = sum(d.get("daily", {}).get(day_str, {}).get("ltc", 0.0) if isinstance(d.get("daily", {}).get(day_str), dict) else 0.0 for day_str in days_in_month)
                sal_period = gtc_p + ltc_p
            else:
                gtc_p = d.get("gtc_salary", 0.0)
                ltc_p = d.get("ltc_salary", 0.0)
                sal_period = d.get("total_salary", gtc_p + ltc_p)

            filtered_drivers.append({
                "driver_name": d["driver_name"],
                "hub_name": d["hub_name"],
                "gtc_salary": gtc_p,
                "formatted_gtc": _format_vnd(gtc_p) + " đ",
                "ltc_salary": ltc_p,
                "formatted_ltc": _format_vnd(ltc_p) + " đ",
                "period_salary": sal_period,
                "formatted_period_salary": _format_vnd(sal_period) + " đ",
                "total_salary": d.get("total_salary", 0.0),
                "formatted_total_salary": d.get("formatted_salary", _format_vnd(sal_period) + " đ")
            })

    # Sắp xếp tài xế theo lương cao nhất trước
    filtered_drivers.sort(key=lambda x: x["period_salary"], reverse=True)
    
    # Tính tổng lương, tổng GTC, tổng LTC và tỷ trọng
    tot_driver_sal = sum(d["period_salary"] for d in filtered_drivers)
    tot_gtc_sal = sum(d["gtc_salary"] for d in filtered_drivers)
    tot_ltc_sal = sum(d["ltc_salary"] for d in filtered_drivers)

    for idx, d in enumerate(filtered_drivers, 1):
        d["rank"] = idx
        pct = (d["period_salary"] / tot_driver_sal * 100) if tot_driver_sal > 0 else 0
        d["percentage"] = f"{pct:.1f}%"
        if pct >= 5.5:
            d["badge"] = "Top Thu Nhập"
            d["badge_color"] = "#10b981"
        elif d["period_salary"] > 0:
            d["badge"] = "Tích Cực"
            d["badge_color"] = "#3b82f6"
        else:
            d["badge"] = "NVXL / Dự Bị"
            d["badge_color"] = "#94a3b8"

    driver_summary = {
        "count": len(filtered_drivers),
        "total_salary": tot_driver_sal,
        "formatted_total": _format_vnd(tot_driver_sal) + " đ",
        "total_gtc": tot_gtc_sal,
        "formatted_gtc": _format_vnd(tot_gtc_sal) + " đ",
        "total_ltc": tot_ltc_sal,
        "formatted_ltc": _format_vnd(tot_ltc_sal) + " đ",
        "avg_salary": (tot_driver_sal / len(filtered_drivers)) if filtered_drivers else 0,
        "formatted_avg": _format_vnd(tot_driver_sal / len(filtered_drivers)) + " đ" if filtered_drivers else "0 đ"
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
        "filter": {
            "hub": selected_ent_label,
            "mode": mode,
            "key": key
        },
        "available_filters": {
            "hubs": ["Toàn Vùng MT01", "Kho Cái Răng", "Kho Bình Thủy", "Kho Vị Thanh", "Kho Ô Môn"],
            "months": available_months,
            "weeks": available_weeks,
            "days": available_days
        },
        "metrics": result_metrics,
        "hubs_breakdown": hubs_breakdown,
        "drivers_breakdown": {
            "summary": driver_summary,
            "list": filtered_drivers
        },
        "trend_chart": {
            "labels": trend_labels,
            "volume_gtc": trend_volume,
            "cost_per_order": trend_cost_per_order,
            "total_cost": trend_total_cost
        }
    }

if __name__ == "__main__":
    build_cost_dashboard_matrix(force=True)
    res = query_mt01_cost_data(hub="all", mode="month", key="Tháng 10-Năm 2026")
    print("\n--- MT01 DRIVERS SUMMARY ---")
    print(res["drivers_breakdown"]["summary"])
    print(f"Top 5 Drivers:")
    for d in res["drivers_breakdown"]["list"][:5]:
        print(f"  #{d['rank']} {d['driver_name']} ({d['hub_name']}): {d['formatted_period_salary']} ({d['percentage']})")

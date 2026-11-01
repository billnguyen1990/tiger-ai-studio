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

def build_cost_dashboard_matrix(force=False):
    """
    Chỉ nạp và xử lý CHUYÊN BIỆT cho VÙNG MIỀN TÂY 01
    Khóa chặt dữ liệu từ Row 3 đến Row 57 của sheet 'Chi Phí MT01'
    Đảm bảo 100% chuẩn xác không bị đè bởi bảng phụ!
    """
    now_str = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    print(f"[{now_str}] 🚀 Đang nạp bảng dữ liệu chuẩn Vùng Miền Tây 01...")

    try:
        creds = get_google_creds()
        client = gspread.authorize(creds)
        sh = client.open_by_key(GOOGLE_SHEET_ID)

        ws = sh.worksheet("Chi Phí MT01")
        rows = ws.get_all_values()

        r0 = rows[0] # Tháng
        r1 = rows[1] # Tuần
        r2 = rows[2] # Ngày / Tiêu đề

        # 1. Danh sách mốc thời gian
        months_dict = {} # "Tháng 10-Năm 2026": [c1, c2, ...]
        weeks_dict = {}  # "Tuần 44-Năm 2026": [c1, c2, ...]
        days_list = []   # ["26/05/2026", ...]
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

        # 2. Định nghĩa cấu trúc chính xác các thực thể MT01
        # Row 3 to 13: Miền Tây 01
        # Row 14 to 24: Kho Cái Răng
        # Row 25 to 35: Kho Bình Thủy
        # Row 36 to 46: Kho TP Vị Thanh
        # Row 47 to 57: Kho Ô Môn
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
                oct_val = rows[r][2].strip() # Cột Tháng 10 chuẩn
                w44_val = rows[r][3].strip() # Cột Tuần 44 chuẩn
                
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

        dashboard_data = {
            "last_sync": now_str,
            "region": "Miền Tây 01",
            "months": list(months_dict.keys()),
            "weeks": list(weeks_dict.keys()),
            "days": days_list,
            "hubs": [e[0] for e in entities_config],
            "entities": hubs_matrix,
            "months_cols": months_dict,
            "weeks_cols": weeks_dict
        }

        with open(DASHBOARD_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, ensure_ascii=False, indent=2)

        print(f"[{now_str}] ✅ Đã lưu ma trận Miền Tây 01 thành công vào {DASHBOARD_CACHE_FILE}!")
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
            with open(DASHBOARD_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return build_cost_dashboard_matrix(force=True)

def query_mt01_cost_data(hub="all", mode="month", key=None):
    """
    Truy vấn dữ liệu chi phí chuẩn xác 100% cho Miền Tây 01:
    - hub: 'all' (Toàn Vùng MT01) hoặc 'Kho Cái Răng', 'Kho Bình Thủy', 'Kho Vị Thanh', 'Kho Ô Môn'
    - mode: 'month' | 'week' | 'day'
    - key: Mốc thời gian (VD: 'Tháng 10-Năm 2026', 'Tuần 44-Năm 2026', '31/10/2026')
    """
    matrix = get_cost_dashboard_matrix()
    available_months = matrix.get("months", [])
    available_weeks = matrix.get("weeks", [])
    available_days = matrix.get("days", [])
    available_hubs = matrix.get("hubs", [])
    entities = matrix.get("entities", {})

    # Mặc định thời gian
    if mode == "month":
        if not key or key not in available_months:
            key = "Tháng 10-Năm 2026" if "Tháng 10-Năm 2026" in available_months else available_months[-1]
    elif mode == "week":
        if not key or key not in available_weeks:
            key = "Tuần 44-Năm 2026" if "Tuần 44-Năm 2026" in available_weeks else available_weeks[-1]
    elif mode == "day":
        if not key or key not in available_days:
            key = available_days[-1] if available_days else ""

    # Chọn thực thể
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

    # Hàm lấy giá trị của 1 thực thể tại kỳ được chọn
    def extract_entity_values(target_metrics):
        out = {}
        if mode == "month" and key == "Tháng 10-Năm 2026":
            # Sử dụng cột tổng hợp chính thức Tháng 10
            for m in metric_keys:
                raw_v = target_metrics.get(m, {}).get("oct_official", "")
                num_v = _clean_num(raw_v)
                out[m] = {
                    "raw": raw_v,
                    "numeric": num_v,
                    "formatted": raw_v or (f"{num_v:.1f}%" if m == "Tỷ lệ GTC" else _format_vnd(num_v))
                }
        elif mode == "week" and key == "Tuần 44-Năm 2026":
            # Sử dụng cột tổng hợp chính thức Tuần 44
            for m in metric_keys:
                raw_v = target_metrics.get(m, {}).get("w44_official", "")
                num_v = _clean_num(raw_v)
                out[m] = {
                    "raw": raw_v,
                    "numeric": num_v,
                    "formatted": raw_v or (f"{num_v:.1f}%" if m == "Tỷ lệ GTC" else _format_vnd(num_v))
                }
        elif mode == "day" and key:
            # Sử dụng ngày cụ thể
            for m in metric_keys:
                raw_v = target_metrics.get(m, {}).get("daily", {}).get(key, "")
                num_v = _clean_num(raw_v)
                out[m] = {
                    "raw": raw_v,
                    "numeric": num_v,
                    "formatted": raw_v or (f"{num_v:.1f}%" if m == "Tỷ lệ GTC" else _format_vnd(num_v))
                }
        else:
            # Tự động tính tổng hợp theo danh sách cột của Tháng/Tuần
            col_indices = matrix.get("months_cols", {}).get(key, []) if mode == "month" else matrix.get("weeks_cols", {}).get(key, [])
            days_in_period = [available_days[c - 4] for c in col_indices if 0 <= c - 4 < len(available_days)]
            
            # Tính tổng các chỉ số số lượng
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

    # Chuỗi xu hướng 14 ngày gần nhất
    recent_days = available_days[-14:] if len(available_days) >= 14 else available_days
    trend_labels = []
    trend_volume = []
    trend_cost_per_order = []
    trend_total_cost = []

    vol_daily = metrics_map.get("Volume GTC", {}).get("daily", {})
    cost_per_order_daily = metrics_map.get("Chi phí giao hàng + xe tải / đơn", {}).get("daily", {})
    luong_giao_daily = metrics_map.get("Lương giao", {}).get("daily", {})
    truck_cost_daily = metrics_map.get("Chi phí xe tải", {}).get("daily", {})

    for d in recent_days:
        trend_labels.append(d[:5]) # DD/MM
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
    print("\n--- MT01 THÁNG 10 OFFICIAL CHECK ---")
    for k, v in res["metrics"].items():
        print(f"  {k:35}: {v['formatted']}")

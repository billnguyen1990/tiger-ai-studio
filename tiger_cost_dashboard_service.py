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

def build_cost_dashboard_matrix(force=False):
    now_str = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    print(f"[{now_str}] 🚀 Đang nạp toàn diện ma trận Chi Phí Vận Hành...")

    try:
        creds = get_google_creds()
        client = gspread.authorize(creds)
        sh = client.open_by_key(GOOGLE_SHEET_ID)

        regions_config = [
            ("Miền Tây 01", "Chi Phí MT01"),
            ("Miền Tây 02", "Chi Phí MT02"),
            ("Miền Tây 03", "Chi Phí MT03"),
            ("Miền Tây 04", "Chi Phí MT04"),
            ("Miền Tây 05", "Chi Phí MT05")
        ]

        dashboard_data = {
            "last_sync": now_str,
            "regions": {}
        }

        # Bắt đầu duyệt từng Vùng
        for reg_name, sheet_name in regions_config:
            try:
                ws = sh.worksheet(sheet_name)
                all_rows = ws.get_all_values()
                if len(all_rows) < 15:
                    continue

                r0 = all_rows[0] # Tháng
                r1 = all_rows[1] # Tuần
                r2 = all_rows[2] # Ngày / Tiêu đề

                # Xây dựng danh sách mốc thời gian
                months_dict = {}
                weeks_dict = {}
                days_list = []

                for c in range(4, len(r2)):
                    d_str = r2[c].strip()
                    m_str = r0[c].strip()
                    w_str = r1[c].strip()

                    if d_str and "/" in d_str:
                        days_list.append({"col": c, "date": d_str, "month": m_str, "week": w_str})
                        if m_str:
                            months_dict.setdefault(m_str, []).append(c)
                        if w_str:
                            weeks_dict.setdefault(w_str, []).append(c)

                # Bóc tách các thực thể (Vùng và từng Kho) cùng 11 chỉ số
                hubs_data = {}
                current_ent = None

                # Quét từ hàng 3 đến hàng 65 (khu vực 11 chỉ số chi phí)
                for r_idx in range(3, min(len(all_rows), 70)):
                    col0 = all_rows[r_idx][0].strip()
                    col1 = all_rows[r_idx][1].strip()
                    
                    if col0 and not col0.lower().startswith("chi phí"):
                        current_ent = col0

                    if current_ent and col1:
                        if current_ent not in hubs_data:
                            hubs_data[current_ent] = {"metrics": {}}

                        # Giá trị pre-computed ở cột 2 (Tháng 10) và cột 3 (Tuần 44) nếu có
                        val_oct = all_rows[r_idx][2].strip() if len(all_rows[r_idx]) > 2 else ""
                        val_w44 = all_rows[r_idx][3].strip() if len(all_rows[r_idx]) > 3 else ""

                        # Toàn bộ giá trị theo từng cột ngày
                        col_vals = {}
                        for item in days_list:
                            c_idx = item["col"]
                            v_raw = all_rows[r_idx][c_idx].strip() if c_idx < len(all_rows[r_idx]) else ""
                            col_vals[item["date"]] = v_raw

                        hubs_data[current_ent]["metrics"][col1] = {
                            "oct_official": val_oct,
                            "w44_official": val_w44,
                            "daily": col_vals
                        }

                # Lưu vào cấu trúc vùng
                dashboard_data["regions"][reg_name] = {
                    "sheet": sheet_name,
                    "months": list(months_dict.keys()),
                    "weeks": list(weeks_dict.keys()),
                    "days": [item["date"] for item in days_list],
                    "hubs": list(hubs_data.keys()),
                    "entities": hubs_data,
                    "months_cols": months_dict,
                    "weeks_cols": weeks_dict
                }
                print(f" -> Đã bóc tách xong {reg_name}: {len(hubs_data)} thực thể, {len(months_dict)} tháng, {len(weeks_dict)} tuần, {len(days_list)} ngày.")

            except Exception as e:
                print(f" -> Lỗi nạp {reg_name}: {e}")

        # Ghi vào cache JSON
        with open(DASHBOARD_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, ensure_ascii=False, indent=2)

        print(f"[{now_str}] ✅ Đã lưu ma trận Dashboard vào {DASHBOARD_CACHE_FILE}!")
        return dashboard_data

    except Exception as ex:
        print(f"[{now_str}] ⚠️ Lỗi build cost dashboard: {ex}")
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

def query_cost_data(region="Miền Tây 01", hub="all", mode="month", key=None):
    """
    Truy vấn dữ liệu chi phí đã chuẩn hóa theo:
    - region: Miền Tây 01 -> Miền Tây 05
    - hub: 'all' hoặc tên kho cụ thể
    - mode: 'month' | 'week' | 'day'
    - key: Tên tháng / Tuần / Ngày cụ thể (VD: 'Tháng 10-Năm 2026', 'Tuần 44-Năm 2026', '31/10/2026')
    """
    matrix = get_cost_dashboard_matrix()
    reg_obj = matrix.get("regions", {}).get(region)
    if not reg_obj:
        # Fallback về Miền Tây 01
        reg_obj = matrix.get("regions", {}).get("Miền Tây 01", {})

    available_months = reg_obj.get("months", [])
    available_weeks = reg_obj.get("weeks", [])
    available_days = reg_obj.get("days", [])
    available_hubs = reg_obj.get("hubs", [])

    # Xác định key mặc định nếu không truyền
    if mode == "month":
        if not key or key not in available_months:
            key = "Tháng 10-Năm 2026" if "Tháng 10-Năm 2026" in available_months else (available_months[-1] if available_months else "")
    elif mode == "week":
        if not key or key not in available_weeks:
            key = "Tuần 44-Năm 2026" if "Tuần 44-Năm 2026" in available_weeks else (available_weeks[-1] if available_weeks else "")
    elif mode == "day":
        if not key or key not in available_days:
            key = available_days[-1] if available_days else ""

    # Xác định danh sách ngày tương ứng với kỳ được chọn
    target_dates = []
    if mode == "month":
        m_cols = reg_obj.get("months_cols", {}).get(key, [])
        # Lấy các ngày có cột nằm trong tháng đó
        for d in available_days:
            # Kiểm tra xem ngày đó có thuộc tháng này không
            target_dates.append(d)
        # Giới hạn ngày theo tháng nếu cần, hoặc lấy theo tháng
    elif mode == "week":
        w_cols = reg_obj.get("weeks_cols", {}).get(key, [])
    elif mode == "day":
        target_dates = [key] if key else []

    entities = reg_obj.get("entities", {})

    # Chuẩn hóa tên thực thể cần xem
    target_entities = []
    if hub == "all" or not hub:
        # Toàn vùng
        region_entity_name = region
        target_entities = [region_entity_name] if region_entity_name in entities else list(entities.keys())[:1]
    else:
        # Tìm kho khớp
        matched = [h for h in available_hubs if hub.lower() in h.lower()]
        target_entities = matched if matched else [available_hubs[0]] if available_hubs else []

    selected_ent = target_entities[0] if target_entities else region
    metrics_dict = entities.get(selected_ent, {}).get("metrics", {})

    # 11 chỉ số cốt tử
    metric_keys = [
        "Volume gán", "Volume GTC", "Kg GTC", "Tỷ lệ GTC", "Stop GTC",
        "Lương giao", "Lương NVXL", "Chi phí xe tải",
        "Chi phí giao hàng + xe tải / đơn",
        "Chi phí giao hàng + xe tải / stop",
        "Chi phí giao hàng + Cost / kg"
    ]

    result_metrics = {}
    for m in metric_keys:
        m_info = metrics_dict.get(m, {})
        val_display = ""
        val_numeric = 0.0

        if mode == "month" and key == "Tháng 10-Năm 2026" and m_info.get("oct_official"):
            val_display = m_info.get("oct_official")
            val_numeric = _clean_num(val_display)
        elif mode == "week" and key == "Tuần 44-Năm 2026" and m_info.get("w44_official"):
            val_display = m_info.get("w44_official")
            val_numeric = _clean_num(val_display)
        elif mode == "day" and key:
            val_display = m_info.get("daily", {}).get(key, "")
            val_numeric = _clean_num(val_display)
        else:
            # Fallback lấy giá trị gần nhất
            daily_map = m_info.get("daily", {})
            if key in daily_map:
                val_display = daily_map[key]
                val_numeric = _clean_num(val_display)
            else:
                val_display = m_info.get("oct_official") or (list(daily_map.values())[-1] if daily_map else "0")
                val_numeric = _clean_num(val_display)

        result_metrics[m] = {
            "name": m,
            "raw": val_display,
            "numeric": val_numeric,
            "formatted": val_display or f"{val_numeric:,.0f}"
        }

    # Tính toán bảng so sánh các Kho trong vùng (Hubs Breakdown)
    hubs_breakdown = []
    for h_name in available_hubs:
        if h_name == region:
            continue
        h_metrics = entities.get(h_name, {}).get("metrics", {})
        h_row = {"hub_name": h_name.replace("Kho Giao Hàng Nặng - ", "")}
        for m in metric_keys:
            m_obj = h_metrics.get(m, {})
            if mode == "month" and key == "Tháng 10-Năm 2026" and m_obj.get("oct_official"):
                v = m_obj.get("oct_official")
            elif mode == "week" and key == "Tuần 44-Năm 2026" and m_obj.get("w44_official"):
                v = m_obj.get("w44_official")
            elif mode == "day" and key:
                v = m_obj.get("daily", {}).get(key, "")
            else:
                v = m_obj.get("oct_official") or ""
            h_row[m] = v
        hubs_breakdown.append(h_row)

    # Chuỗi xu hướng thời gian (Trend series) để vẽ Chart
    recent_days = available_days[-14:] if len(available_days) >= 14 else available_days
    trend_labels = []
    trend_volume = []
    trend_cost_per_order = []
    trend_total_cost = []

    vol_daily = metrics_dict.get("Volume GTC", {}).get("daily", {})
    cost_per_order_daily = metrics_dict.get("Chi phí giao hàng + xe tải / đơn", {}).get("daily", {})
    luong_giao_daily = metrics_dict.get("Lương giao", {}).get("daily", {})
    truck_cost_daily = metrics_dict.get("Chi phí xe tải", {}).get("daily", {})

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
        "filter": {
            "region": region,
            "hub": hub,
            "mode": mode,
            "key": key
        },
        "available_filters": {
            "regions": list(matrix.get("regions", {}).keys()),
            "hubs": available_hubs,
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
    matrix = build_cost_dashboard_matrix(force=True)
    q = query_cost_data(region="Miền Tây 01", hub="all", mode="month", key="Tháng 10-Năm 2026")
    print("\n--- Test Query MT01 Tháng 10 ---")
    print("Selected:", q["filter"])
    print("Metrics sample:")
    for k, v in list(q["metrics"].items())[:6]:
        print(f"  {k}: {v['formatted']}")

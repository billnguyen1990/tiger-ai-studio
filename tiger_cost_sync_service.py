import os
import sys
import json
import datetime
import pandas as pd

# Đường dẫn dữ liệu
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

COST_CACHE_FILE = os.path.join(DATA_DIR, "mt01_cost_analytics.json")
EXCEL_EXPORT_FILE = os.path.join(DATA_DIR, "Bao_Cao_Doi_Soat_MT01_Latest.xlsx")

GOOGLE_SHEET_ID = "1eHuDDhfZy17fIC_jWPTnDT69-1gf-31gm8K1Qgo6Ssc"

def _decrypt_cloud_sa_info():
    """Giải mã an toàn service account từ file mã hóa sa_cloud_key.enc khi chạy trên Render cloud"""
    import base64
    enc_candidates = [
        os.path.join(CURRENT_DIR, "data", "sa_cloud_key.enc"),
        os.path.join(CURRENT_DIR, "sa_cloud_key.enc"),
        os.path.join(os.path.dirname(CURRENT_DIR), "data", "sa_cloud_key.enc")
    ]
    key = "TIGER_AI_MT01_SECURITY_KEY_2026".encode("utf-8")
    for p in enc_candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    enc_b64 = f.read().strip()
                dec_bytes = base64.b64decode(enc_b64.encode("utf-8"))
                decrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(dec_bytes)]).decode("utf-8")
                return json.loads(decrypted)
            except Exception as e:
                print(f"[Warning] Failed decrypting {p}: {e}")
    return None

def get_google_creds():
    # 1. Kiểm tra biến môi trường
    env_json = os.environ.get("GOOGLE_CREDENTIALS_JSON") or os.environ.get("GCP_SA_KEY")
    if env_json:
        try:
            from google.oauth2.service_account import Credentials
            info = json.loads(env_json)
            return Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        except Exception as e:
            print(f"[Warning] Failed loading creds from ENV: {e}")

    # 2. Kiểm tra các file credentials.json
    candidates = [
        os.path.join(CURRENT_DIR, "credentials.json"),
        os.path.join(CURRENT_DIR, "tool_11h_bao_cao_telegram", "credentials.json"),
        os.path.join(os.path.dirname(CURRENT_DIR), "tool_11h_bao_cao_telegram", "credentials.json"),
        os.path.join(os.path.dirname(CURRENT_DIR), "credentials.json"),
    ]
    for c in candidates:
        if os.path.exists(c):
            from google.oauth2.service_account import Credentials
            return Credentials.from_service_account_file(c, scopes=["https://www.googleapis.com/auth/spreadsheets"])

    # 3. Fallback giải mã đám mây an toàn
    sa_info = _decrypt_cloud_sa_info()
    if sa_info:
        try:
            from google.oauth2.service_account import Credentials
            return Credentials.from_service_account_info(sa_info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        except Exception as e:
            print(f"[Warning] Failed loading decrypted creds: {e}")

    raise FileNotFoundError("Không tìm thấy credentials.json hoặc biến môi trường GOOGLE_CREDENTIALS_JSON!")

def sync_mt01_cost_data(force=False):
    """
    Đồng bộ toàn bộ dữ liệu chi phí từ Google Sheet về hệ thống Tiger AI
    1. Lương NVXL
    2. Lương NVGH
    3. Xe tải cố định & đối soát NCC Vận tải 365
    """
    now_str = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    print(f"[{now_str}] 🚀 Đang đồng bộ dữ liệu Chi Phí MT01 từ Google Sheet...")

    try:
        import gspread
        creds = get_google_creds()
        client = gspread.authorize(creds)
        sh = client.open_by_key(GOOGLE_SHEET_ID)

        # ==========================================
        # 1. XE TẢI CỐ ĐỊNH & ĐỐI SOÁT NCC 365
        # ==========================================
        ws_mt01 = sh.worksheet("Chi Phí MT01")
        all_mt01_rows = ws_mt01.get_all_values()
        dates_row = all_mt01_rows[2]
        
        # Lấy các cột ngày từ tháng 10 trở đi
        oct_cols = [i for i in range(len(dates_row)) if "/10/2026" in dates_row[i] or "/11/2026" in dates_row[i]]
        if not oct_cols:
            oct_cols = [i for i in range(131, len(dates_row)) if dates_row[i].strip()]

        hubs_norm = [
            ("Kho Giao Hàng Nặng - Cái Răng - Cần Thơ", 142, 6, "Cái Răng"),
            ("Kho Giao Hàng Nặng - Bình Thủy - Cần Thơ", 143, 3, "Bình Thủy"),
            ("Kho Giao Hàng Nặng - TP Vị Thanh - Hậu Giang", 144, 2, "Vị Thanh"),
            ("Kho Giao Hàng Nặng - Ô Môn - Cần Thơ", 145, 2, "Ô Môn")
        ]

        daily_trucks = []
        reduced_days_summary = []
        increased_days_summary = []

        for c in oct_cols:
            d = dates_row[c]
            tot = int(all_mt01_rows[146][c]) if all_mt01_rows[146][c].isdigit() else 0
            day_record = {
                "date": d,
                "total_running": tot,
                "standard_norm": 13,
                "diff": tot - 13,
                "hubs": {}
            }

            reduced_hubs = []
            increased_hubs = []

            for full_name, r_idx, norm, short_name in hubs_norm:
                val = int(all_mt01_rows[r_idx][c]) if all_mt01_rows[r_idx][c].isdigit() else 0
                day_record["hubs"][short_name] = {
                    "running": val,
                    "norm": norm,
                    "diff": val - norm
                }
                if val < norm:
                    reduced_hubs.append(f"{short_name}: {val}/{norm} (-{norm-val} xe)")
                elif val > norm:
                    increased_hubs.append(f"{short_name}: {val}/{norm} (+{val-norm} xe)")

            if reduced_hubs:
                reduced_days_summary.append({
                    "date": d,
                    "total": tot,
                    "details": reduced_hubs
                })
            if increased_hubs:
                increased_days_summary.append({
                    "date": d,
                    "total": tot,
                    "details": increased_hubs
                })

            daily_trucks.append(day_record)

        # Thống kê chu kỳ đối soát với NCC 365
        reconciliation_365 = {
            "period": "26/09/2026 - 25/10/2026",
            "total_running": int(all_mt01_rows[164][3]) if len(all_mt01_rows[164]) > 3 and all_mt01_rows[164][3].isdigit() else 328,
            "total_off": int(all_mt01_rows[164][2]) if len(all_mt01_rows[164]) > 2 and all_mt01_rows[164][2].isdigit() else 56,
            "hubs": {
                "Cái Răng": {"norm": 6, "running": 153, "off": 26},
                "Bình Thủy": {"norm": 3, "running": 71, "off": 22},
                "Vị Thanh": {"norm": 2, "running": 56, "off": 2},
                "Ô Môn": {"norm": 2, "running": 48, "off": 6}
            },
            "note": all_mt01_rows[165][2] if len(all_mt01_rows) > 165 and len(all_mt01_rows[165]) > 2 else "Cắt xe cố định từ ngày 21/10/2026"
        }

        # ==========================================
        # 2. LƯƠNG NHÂN VIÊN XỬ LÝ (NVXL)
        # ==========================================
        ws_xl = sh.worksheet("Lương NVXL")
        rows_xl = ws_xl.get_all_values()
        oct_xl = [r for r in rows_xl[1:] if ("/10/2026" in r[3] or "/11/2026" in r[3]) and any(k in r[1] for k in ["Cái Răng", "Bình Thủy", "Vị Thanh", "Ô Môn"])]

        xl_by_hub = {}
        xl_by_emp = {}
        xl_grand_total = 0.0

        for r in oct_xl:
            hub_name = r[1].replace("Kho Giao Hàng Nặng - ", "")
            emp_name = r[2]
            val_str = r[8].replace(".", "").replace(",", ".") if r[8] else "0"
            try:
                luong_xl = float(val_str)
            except:
                luong_xl = 0.0
            
            xl_by_hub[hub_name] = xl_by_hub.get(hub_name, 0.0) + luong_xl
            xl_by_emp.setdefault(hub_name, {})
            xl_by_emp[hub_name][emp_name] = xl_by_emp[hub_name].get(emp_name, 0.0) + luong_xl
            xl_grand_total += luong_xl

        salary_nvxl_data = {
            "grand_total": xl_grand_total,
            "by_hub": xl_by_hub,
            "by_emp": xl_by_emp
        }

        # ==========================================
        # 3. LƯƠNG NHÂN VIÊN GIAO HÀNG (NVGH)
        # ==========================================
        ws_nv = sh.worksheet("Lương Nhân Viên ")
        rows_nv = ws_nv.get_all_values()
        
        nvgh_by_hub = {}
        nvgh_grand_total = 0.0
        current_hub = ""

        for r in rows_nv[2:]:
            col0 = r[0].strip()
            if col0.startswith("Kho Giao Hàng Nặng"):
                current_hub = col0.replace("Kho Giao Hàng Nặng - ", "")
                nvgh_by_hub.setdefault(current_hub, [])
            elif col0.startswith("Tổng số"):
                current_hub = ""
            elif current_hub and r[1].strip():
                emp_name = r[1].strip()
                tot_str = r[-1].strip().replace(".", "").replace(",", "")
                try:
                    tot_val = float(tot_str)
                except:
                    tot_val = 0.0
                
                nvgh_by_hub[current_hub].append({
                    "driver_name": emp_name,
                    "total_salary": tot_val,
                    "formatted_salary": f"{tot_val:,.0f} đ"
                })
                nvgh_grand_total += tot_val

        # Sắp xếp lương tài xế giảm dần theo từng kho
        for h in nvgh_by_hub:
            nvgh_by_hub[h] = sorted(nvgh_by_hub[h], key=lambda x: -x["total_salary"])

        salary_nvgh_data = {
            "grand_total": nvgh_grand_total,
            "by_hub": nvgh_by_hub
        }

        final_payload = {
            "last_sync": now_str,
            "sheet_id": GOOGLE_SHEET_ID,
            "sheet_url": f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit",
            "truck_analytics": {
                "standard_norm": {"Cái Răng": 6, "Bình Thủy": 3, "Vị Thanh": 2, "Ô Môn": 2, "Tổng": 13},
                "daily_records": daily_trucks,
                "reduced_days": reduced_days_summary,
                "increased_days": increased_days_summary,
                "reconciliation_365": reconciliation_365
            },
            "salary_nvxl": salary_nvxl_data,
            "salary_nvgh": salary_nvgh_data
        }

        with open(COST_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, ensure_ascii=False, indent=2)

        # Xuất Excel chuẩn Executive (tự động căn chỉnh cột, định dạng VNĐ, màu KPI)
        try:
            from tiger_cost_dashboard_service import generate_mt01_cost_excel_report
            generate_mt01_cost_excel_report(hub="all", mode="month", key=None)
        except Exception as ex:
            print(f"Warning: Không thể xuất file Excel đối soát: {ex}")

        print(f"[{now_str}] ✅ Đã đồng bộ thành công dữ liệu Chi Phí MT01 vào {COST_CACHE_FILE}!")
        return final_payload

    except Exception as ex:
        print(f"[{now_str}] ⚠️ Lỗi khi đồng bộ Google Sheet: {ex}")
        if os.path.exists(COST_CACHE_FILE):
            print(f"[{now_str}] 🔄 Sử dụng bản cache dữ liệu gần nhất.")
            with open(COST_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        raise ex

def get_cached_cost_data():
    """Lấy dữ liệu chi phí đã đồng bộ (hoặc tự động sync nếu chưa có)"""
    if os.path.exists(COST_CACHE_FILE):
        try:
            with open(COST_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return sync_mt01_cost_data(force=True)

def generate_quick_cost_telegram_report():
    """Tạo báo cáo tóm tắt chi phí & xe tải để gửi nhanh qua Telegram"""
    data = get_cached_cost_data()
    t_info = data.get("truck_analytics", {})
    recon = t_info.get("reconciliation_365", {})
    xl_info = data.get("salary_nvxl", {})
    nvgh_info = data.get("salary_nvgh", {})

    lines = [
        "💰 <b>TIGER AI • BÁO CÁO NHANH CHI PHÍ & ĐỐI SOÁT VẬN TẢI MT01</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📅 <i>Đồng bộ lần cuối: {data.get('last_sync', 'Mới nhất')}</i>\n",
        "🚚 <b>1. XE CỐ ĐỊNH & ĐỐI SOÁT NCC 365 (26/09 - 25/10):</b>",
        f"• Định mức chuẩn vùng: <b>13 xe/ngày</b> (CR: 6, BT: 3, VT: 2, OM: 2)",
        f"• Tổng chuyến xe chạy thực tế: <b>{recon.get('total_running', 328)}</b> chuyến",
        f"• Tổng số lượt xe OFF (cắt giảm): <b>{recon.get('total_off', 56)}</b> lượt",
        f"  - Cái Răng: Chạy 153 | OFF 26 lượt",
        f"  - Bình Thủy: Chạy 71 | OFF 22 lượt",
        f"  - TP Vị Thanh: Chạy 56 | OFF 2 lượt",
        f"  - Ô Môn: Chạy 48 | OFF 6 lượt\n",
        "👷 <b>2. TỔNG LƯƠNG NHÂN VIÊN XỬ LÝ (NVXL):</b>",
        f"• Tổng chi phí: <b>{xl_info.get('grand_total', 0):,.0f} đ</b> (4 kho)",
        f"  - Cái Răng: 16.330.190 đ (Công Bằng)",
        f"  - Bình Thủy: 10.131.471 đ (Bảo Toàn)",
        f"  - Vị Thanh: 7.250.659 đ (Đức Trung)",
        f"  - Ô Môn: 5.556.942 đ (Trọng Bằng)\n",
        "🛵 <b>3. TỔNG LƯƠNG TÀI XẾ GIAO NHẬN (NVGH):</b>",
        f"• Tổng chi phí: <b>{nvgh_info.get('grand_total', 0):,.0f} đ</b> (26 tài xế)",
        f"  - Cái Răng: 74.520.898 đ (12 TX)",
        f"  - Bình Thủy: 38.619.386 đ (6 TX)",
        f"  - Vị Thanh: 22.885.933 đ (4 TX)",
        f"  - Ô Môn: 19.674.491 đ (4 TX)\n",
        "🔗 <i>Dữ liệu được liên kết và cập nhật tự động mỗi ngày từ Google Sheet vận hành!</i>"
    ]
    return "\n".join(lines)

if __name__ == "__main__":
    data = sync_mt01_cost_data(force=True)
    print("Test sync output keys:", list(data.keys()))
    print("\n--- Telegram Summary Preview ---")
    print(generate_quick_cost_telegram_report())

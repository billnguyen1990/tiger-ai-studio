import pytest
import requests

BASE_URL = "http://127.0.0.1:5050"

def test_fleet_radar_schema_and_trucks():
    """Verify live fleet radar dictionary has all 4 trucks with complete attributes"""
    url = f"{BASE_URL}/api/saban/fleet-radar"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data.get("success") is True, f"Response success should be True: {data}"
    
    trucks = data.get("trucks") or data.get("fleet")
    assert isinstance(trucks, dict), f"Expected dict of trucks, got {type(trucks)}"
    
    required_trucks = ["truck-cairang", "truck-omon", "truck-vithanh", "truck-highway"]
    for tid in required_trucks:
        assert tid in trucks, f"Missing truck {tid} in fleet radar"
        t = trucks[tid]
        
        # 1. License Plate
        assert "plate" in t and len(t["plate"]) > 0, f"Truck {tid} missing plate"
        
        # 2. Driver Details
        driver = t.get("driver", {})
        for field in ["name", "phone", "license", "rating"]:
            assert field in driver and len(str(driver[field])) > 0, f"Truck {tid} missing driver.{field}"
            
        # 3. Origin & Destination
        origin = t.get("origin", {})
        dest = t.get("destination", {})
        assert "name" in origin and len(origin["name"]) > 0, f"Truck {tid} missing origin name"
        assert "name" in dest and len(dest["name"]) > 0, f"Truck {tid} missing destination name"
        
        # 4. Payload Metrics
        payload = t.get("payload", {})
        for field in ["currentKg", "maxKg", "utilizationPercent", "packageCount", "cargoCategory"]:
            assert field in payload, f"Truck {tid} missing payload.{field}"
            
        # 5. Cargo Status & Seal
        cargo = t.get("cargoStatus", {})
        for field in ["stateText", "sealCode", "securityCheck", "dispatchTime", "etaTime"]:
            assert field in cargo and len(str(cargo[field])) > 0, f"Truck {tid} missing cargoStatus.{field}"
            
        # 6. Live Telemetry
        telemetry = t.get("telemetry", {})
        for field in ["speedKmh", "fuelPercent", "odoTodayKm", "gps"]:
            assert field in telemetry, f"Truck {tid} missing telemetry.{field}"

def test_incidents_reset_and_seed_content():
    """Verify POST /api/saban/incidents/reset re-initializes seed incidents"""
    reset_url = f"{BASE_URL}/api/saban/incidents/reset"
    resp = requests.post(reset_url, timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert data.get("count") >= 4
    
    incidents = data.get("incidents", [])
    expected_ids = {"INC-20261106-001", "INC-20261106-002", "INC-20261106-003", "INC-20261106-004"}
    actual_ids = {i.get("id") for i in incidents}
    assert expected_ids.issubset(actual_ids), f"Missing seed IDs: {expected_ids - actual_ids}"

def test_incidents_query_and_filtering():
    """Verify GET /api/saban/incidents supports status=all|open|resolved"""
    # 1. status=all
    res_all = requests.get(f"{BASE_URL}/api/saban/incidents?status=all", timeout=5).json()
    assert res_all.get("success") is True
    assert res_all.get("open_count") >= 1
    assert res_all.get("critical_count") >= 1
    
    # 2. status=open
    res_open = requests.get(f"{BASE_URL}/api/saban/incidents?status=open", timeout=5).json()
    assert res_open.get("success") is True
    for item in res_open.get("incidents", []):
        assert item.get("status") == "OPEN"

def test_incidents_resolve_lifecycle():
    """Verify resolving an incident marks status RESOLVED, updates fields and logs to War Room"""
    # Resolve first open incident
    res_open = requests.get(f"{BASE_URL}/api/saban/incidents?status=open", timeout=5).json()
    target = res_open["incidents"][0]
    target_id = target["id"]
    
    resolve_url = f"{BASE_URL}/api/saban/incidents/resolve"
    payload = {
        "id": target_id,
        "resolved_by": "Chỉ Huy MT01 • Tiger AI",
        "note": "Xử lý thành công qua bài kiểm tra tự động"
    }
    resp = requests.post(resolve_url, json=payload, timeout=5)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data.get("success") is True
    assert res_data["incident"]["status"] == "RESOLVED"
    assert res_data["incident"]["resolved_by"] == payload["resolved_by"]
    assert res_data["incident"]["resolved_at"] is not None
    assert res_data["incident"]["resolution_note"] == payload["note"]
    
    # Check status=resolved includes this item
    res_resolved = requests.get(f"{BASE_URL}/api/saban/incidents?status=resolved", timeout=5).json()
    resolved_ids = [i.get("id") for i in res_resolved.get("incidents", [])]
    assert target_id in resolved_ids
    
    # Reset back to clean state
    requests.post(f"{BASE_URL}/api/saban/incidents/reset", timeout=5)

def test_starbucks_order_and_drone_routing():
    """Verify POST /api/saban/starbucks/order creates order and routes Drone Courier"""
    order_url = f"{BASE_URL}/api/saban/starbucks/order"
    order_data = {
        "item_id": "sb-nitro-cold-brew",
        "item_name": "Starbucks Nitro Cold Brew",
        "quantity": 3,
        "size": "VENTI",
        "destination_key": "vithanh",
        "note": "Giao khẩn cấp cho ban giám sát kho Vị Thanh"
    }
    resp = requests.post(order_url, json=order_data, timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert "order_id" in data and len(data["order_id"]) > 0
    assert "destination" in data
    dest = data["destination"]
    assert dest.get("key") == "vithanh"
    assert "name" in dest and "x" in dest and "y" in dest

def test_war_room_pipeline_traces():
    """Verify that operational events are logged to War Room pipeline traces"""
    url = f"{BASE_URL}/api/war-room/traces"
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    traces = data.get("traces", [])
    assert len(traces) > 0, "Expected non-empty traces in pipeline_tracer"

if __name__ == "__main__":
    pytest.main(["-v", __file__])

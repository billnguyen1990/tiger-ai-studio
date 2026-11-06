"""
End-to-End Playwright Test Suite for Sa Ban 3D Multi-Agent OS (MT01)
Features Covered:
  - Feature 1: Live Interactive Truck & Cargo Fleet Radar
  - Feature 2A: Starbucks Coffee & Boba Order with Quadcopter Drone Delivery
  - Feature 2B: Riverside Fishing Rod Minigame & Park Pedestrian Network
  - Feature 3: Real-Time Smart Incident & Anomaly HUD with 1-Click Auto-Heal

Author: Tiger AI (teamwork_test_writer)
Milestone: M3 (E2E Test Suite Authoring & Full Verification)
"""

import os
import sys
import time
import pytest
import requests
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("SABAN_URL", "http://127.0.0.1:5050")
SCREENSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saban_e2e_verified.png")


@pytest.fixture(scope="function")
def page():
    """Provides a fresh headless Chromium page with 1920x1080 viewport and zero JS error assertion"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page_obj = context.new_page()

        # Track uncaught JS page errors and console errors
        recorded_errors = []

        def on_page_error(err):
            recorded_errors.append(f"PAGEERROR: {err}")

        def on_console(msg):
            if msg.type == "error":
                recorded_errors.append(f"CONSOLE_ERROR: {msg.text}")

        page_obj.on("pageerror", on_page_error)
        page_obj.on("console", on_console)
        setattr(page_obj, "recorded_errors", recorded_errors)

        yield page_obj

        # Strict assertion: Zero uncaught JS errors
        errors = getattr(page_obj, "recorded_errors", [])
        assert len(errors) == 0, f"Uncaught JS/Console errors detected during test: {errors}"

        browser.close()


def test_feature_1_truck_fleet_radar(page):
    """
    Test 1 (Feature 1 Radar):
    - Navigates to /sa-ban
    - Clicks #truck-cairang
    - Waits for #truckRadarModal.open
    - Asserts plate '65C-188.92', driver name 'Đặng Hoàng Phúc', origin/destination,
      payload progress bar, seal ID, and telemetry values
    - Clicks #btnLocateTruckCamera to verify camera auto-focus
    - Verifies modal closes and focus highlight applies
    """
    page.goto(f"{BASE_URL}/sa-ban", wait_until="networkidle")

    # Locate and click truck-cairang
    truck_locator = page.locator("#truck-cairang")
    truck_locator.wait_for(state="visible", timeout=10000)
    truck_locator.click()

    # Wait for modal to open
    modal = page.locator("#truckRadarModal")
    page.wait_for_selector("#truckRadarModal.open", timeout=5000)

    # 1. License Plate
    plate = page.locator("#trPlate").inner_text().strip()
    assert plate == "65C-188.92", f"Expected plate '65C-188.92', got '{plate}'"

    # 2. Driver Profile
    driver_name = page.locator("#trDriverName").inner_text().strip()
    assert driver_name == "Đặng Hoàng Phúc", f"Expected driver 'Đặng Hoàng Phúc', got '{driver_name}'"

    # 3. Origin & Destination
    origin = page.locator("#trOriginName").inner_text().strip()
    dest = page.locator("#trDestName").inner_text().strip()
    assert len(origin) > 0, "Origin name should not be empty"
    assert len(dest) > 0, "Destination name should not be empty"
    assert "Cái Răng" in origin or "Kho" in origin, f"Origin should reference warehouse, got '{origin}'"

    # 4. Payload Progress Bar & Metrics
    util_text = page.locator("#trUtilPercent").inner_text().strip()
    assert "%" in util_text, f"Payload utilization should contain '%', got '{util_text}'"
    payload_fill = page.locator("#trPayloadFill")
    style_attr = payload_fill.get_attribute("style") or ""
    assert "width:" in style_attr and "0%" not in style_attr, f"Payload progress bar should be filled: {style_attr}"

    # 5. Seal Code
    seal = page.locator("#trSealCode").inner_text().strip()
    assert len(seal) > 0 and "GHN" in seal, f"Expected valid GHN seal code, got '{seal}'"

    # 6. Live Telemetry
    speed = page.locator("#trSpeed").inner_text().strip()
    fuel = page.locator("#trFuel").inner_text().strip()
    odo = page.locator("#trOdo").inner_text().strip()
    gps = page.locator("#trGps").inner_text().strip()

    assert "km/h" in speed, f"Speed should contain 'km/h', got '{speed}'"
    assert "%" in fuel, f"Fuel should contain '%', got '{fuel}'"
    assert "km" in odo, f"Odo should contain 'km', got '{odo}'"
    assert "°" in gps or "," in gps, f"GPS should have coordinates format, got '{gps}'"

    # 7. Camera Auto-Focus Button
    page.click("#btnLocateTruckCamera")

    # Assert modal closes
    page.wait_for_function(
        "() => !document.getElementById('truckRadarModal').classList.contains('open')",
        timeout=5000
    )

    # Assert camera-focused animation class applied to truck
    page.wait_for_selector("#truck-cairang.camera-focused", timeout=5000)

    # Verify zero JS errors recorded
    assert len(page.recorded_errors) == 0, f"JS errors: {page.recorded_errors}"


def test_feature_2a_starbucks_order_and_drone(page):
    """
    Test 2 (Feature 2A Starbucks):
    - Clicks Starbucks sign/chibi (.starbucks-zone-sign)
    - Waits for #starbucksOrderModal.open
    - Asserts 5 curated menu items
    - Selects destination 'cairang'
    - Clicks '🚀 XÁC NHẬN ĐẶT & GIAO NGAY'
    - Asserts modal closes, delivery quadcopter #sb-drone-courier launches,
      toast appears, and delivery speech bubble pops on target agent
    """
    page.goto(f"{BASE_URL}/sa-ban", wait_until="networkidle")

    # Click Starbucks Zone Sign
    sb_sign = page.locator(".starbucks-zone-sign")
    sb_sign.wait_for(state="visible", timeout=10000)
    sb_sign.click()

    # Wait for modal to open
    page.wait_for_selector("#starbucksOrderModal.open", timeout=5000)

    # Assert 5 menu items
    menu_items = page.locator("#sbMenuList .sb-menu-item").all()
    assert len(menu_items) == 5, f"Expected 5 menu items, found {len(menu_items)}"

    # Select destination cairang
    page.select_option("#sbDestinationSelect", "cairang")

    # Click Submit Order button
    page.click(".btn-sb-submit")

    # Assert modal closes
    page.wait_for_function(
        "() => !document.getElementById('starbucksOrderModal').classList.contains('open')",
        timeout=5000
    )

    # Assert delivery quadcopter #sb-drone-courier launches
    drone = page.wait_for_selector("#sb-drone-courier", timeout=5000)
    assert drone is not None, "Quadcopter drone courier actor should be attached to DOM"

    # Assert confirmation toast appears
    toast = page.wait_for_selector("#sabanToastContainer .saban-toast-pill", timeout=5000)
    toast_text = toast.inner_text()
    assert "Starbucks" in toast_text or "Quadcopter" in toast_text, f"Unexpected toast: {toast_text}"

    # Assert delivery speech bubble pops on target warehouse agent (Kho Cái Răng)
    bubble = page.wait_for_selector("#bubble-cairang.show", timeout=8000)
    bubble_text = bubble.inner_text()
    assert "Cảm ơn Sếp Lộc" in bubble_text or "Starbucks" in bubble_text, f"Unexpected speech bubble text: {bubble_text}"

    # Verify zero JS errors recorded
    assert len(page.recorded_errors) == 0, f"JS errors: {page.recorded_errors}"


def test_feature_2b_fishing_and_pedestrians(page):
    """
    Test 3 (Feature 2B Fishing & Pedestrians):
    - Locates fisherman at Bến 1 (#river-fisherman-1)
    - Clicks it to trigger 'Giật Cần!'
    - Asserts reeling animation, catch toast, and chat log entry
    - Asserts park pedestrians (#park-stroller, #park-dog-walker, #park-bench-relaxer) exist in #isoScene
    """
    page.goto(f"{BASE_URL}/sa-ban", wait_until="networkidle")

    # Locate fisherman at dock
    fisherman = page.locator("#river-fisherman-1")
    fisherman.wait_for(state="attached", timeout=10000)
    fisherman.click()

    # Assert reeling animation triggers (rod bend or fish jump)
    page.wait_for_selector("#jumpingFishFx.active, #waterSplashFx.active, #fishermanRodWrap.reeling-in", timeout=3000)

    # Assert catch toast notification appears
    page.wait_for_selector("#sabanToastContainer .saban-toast-pill", timeout=5000)

    # Assert chat log entry recorded in #chatBodyList
    page.wait_for_function(
        "() => document.getElementById('chatBodyList') && document.getElementById('chatBodyList').innerText.includes('[GIẬT CẦN THÀNH CÔNG]')",
        timeout=5000
    )

    # Assert park pedestrians exist in #isoScene
    stroller = page.locator("#isoScene #park-stroller")
    dog_walker = page.locator("#isoScene #park-dog-walker")
    bench_relaxer = page.locator("#isoScene #park-bench-relaxer")

    assert stroller.count() == 1, "Expected 1 #park-stroller in #isoScene"
    assert dog_walker.count() == 1, "Expected 1 #park-dog-walker in #isoScene"
    assert bench_relaxer.count() == 1, "Expected 1 #park-bench-relaxer in #isoScene"

    # Verify zero JS errors recorded
    assert len(page.recorded_errors) == 0, f"JS errors: {page.recorded_errors}"


def test_feature_3_incident_hud_and_1click_resolve(page):
    """
    Test 4 (Feature 3 Incident HUD):
    - Ensures clean seed incident state via API reset
    - Asserts #incidentTickerHud is rendered below header
    - Asserts active incident title, location, severity pill
    - Clicks #btnIncidentResolve ('⚡ XỬ LÝ 1-CLICK')
    - Asserts button flashes '✓ ĐÃ XỬ LÝ XONG'
    - Verifies auto-heal log appears in chat
    - Asserts incident counter decrements or shows 100% operational status
    - Captures verified screenshot artifact to tiger_studio/saban_e2e_verified.png
    """
    # Reset incidents to known 4-item seed state
    try:
        requests.post(f"{BASE_URL}/api/saban/incidents/reset", timeout=5)
    except Exception as e:
        print(f"Warning: Failed to reset incidents: {e}")

    page.goto(f"{BASE_URL}/sa-ban", wait_until="networkidle")

    # Assert #incidentTickerHud is rendered and visible
    hud = page.locator("#incidentTickerHud")
    hud.wait_for(state="visible", timeout=10000)

    # Wait for initial incident fetch to populate ticker
    page.wait_for_function(
        "() => document.getElementById('tickerLocTag') && document.getElementById('tickerLocTag').innerText.length > 0",
        timeout=5000
    )

    # Check incident metadata
    loc_text = page.locator("#tickerLocTag").inner_text().strip()
    sev_text = page.locator("#tickerSevPill").inner_text().strip()
    desc_text = page.locator("#tickerDescText").inner_text().strip()
    badge_before = page.locator("#tickerBadge").inner_text().strip()

    assert "📍" in loc_text, f"Location tag should have pin icon, got '{loc_text}'"
    assert sev_text in ["CRITICAL", "WARNING", "INFO"], f"Unexpected severity pill: '{sev_text}'"
    assert len(desc_text) > 0, "Incident description should not be empty"
    assert "SỰ CỐ CẦN XỬ LÝ" in badge_before, f"Expected active incidents badge, got '{badge_before}'"

    # Click 1-Click Resolve button
    btn_resolve = page.locator("#btnIncidentResolve")
    btn_resolve.click()

    # Assert button flashes '✓ ĐÃ XỬ LÝ XONG'
    page.wait_for_selector("#btnIncidentResolve.resolved-flash", timeout=5000)
    btn_flash_text = page.locator("#btnIncidentResolve").inner_text()
    assert "ĐÃ XỬ LÝ XONG" in btn_flash_text, f"Button should flash resolved status, got '{btn_flash_text}'"

    # Verify auto-heal log appears in chat
    page.wait_for_function(
        "() => document.getElementById('chatBodyList') && document.getElementById('chatBodyList').innerText.includes('[1-CLICK AUTO-HEAL]')",
        timeout=5000
    )

    # Wait for incident counter update (after 900ms server reload)
    page.wait_for_timeout(1500)
    badge_after = page.locator("#tickerBadge").inner_text().strip()
    assert ("(3)" in badge_after) or ("100%" in badge_after), f"Counter should decrement, got '{badge_after}'"

    # Capture full-page screenshot artifact
    page.screenshot(path=SCREENSHOT_PATH, full_page=True)
    assert os.path.exists(SCREENSHOT_PATH), f"Screenshot artifact missing at {SCREENSHOT_PATH}"
    print(f"\n[Artifact Generated] Verified full-page screenshot saved to: {SCREENSHOT_PATH}")

    # Verify zero JS errors recorded
    assert len(page.recorded_errors) == 0, f"JS errors: {page.recorded_errors}"


if __name__ == "__main__":
    print("=" * 70)
    print("🚀 EXECUTING PLAYWRIGHT E2E TEST SUITE FOR SA BAN 3D MT01")
    print(f"Target URL: {BASE_URL}/sa-ban")
    print("=" * 70)

    exit_code = pytest.main(["-v", "-s", __file__])
    print("=" * 70)
    if exit_code == 0:
        print("✅ ALL E2E PLAYWRIGHT TESTS PASSED (100% SUCCESS RATE, 0 ERRORS)")
    else:
        print(f"❌ TEST RUN FAILED WITH EXIT CODE: {exit_code}")
    print("=" * 70)
    sys.exit(exit_code)

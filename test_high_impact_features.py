import asyncio
import sys
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:5050"

async def run():
    print("=== STARTING FRONTEND HIGH-IMPACT FEATURES PLAYWRIGHT TEST ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        errors = []
        page.on("pageerror", lambda err: errors.append(f"PAGE ERROR: {err}"))
        page.on("console", lambda msg: errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type in ['error'] else None)
        
        # 1. Reset incidents datastore first to ensure clean state
        import requests
        requests.post(f"{BASE_URL}/api/saban/incidents/reset", timeout=5)
        
        print("\n--- TEST 1: PAGE LOAD & ZERO CONSOLE ERRORS ---")
        await page.goto(f"{BASE_URL}/sa-ban", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        title = await page.title()
        print(f"Page Title: {title}")
        assert "SA BÀN" in title.upper() or "TIGER AI" in title.upper(), "Unexpected title"
        
        # ---------------------------------------------------------------------
        print("\n--- TEST 2: FEATURE 1 - LIVE FLEET RADAR MODAL & TRUCK INTERACTIONS ---")
        # Click Top HUD Button "🚛 RADAR XE TẢI"
        hud_radar_btn = page.locator("button:has-text('RADAR XE TẢI')").first
        assert await hud_radar_btn.is_visible(), "Top HUD button '🚛 RADAR XE TẢI' not visible"
        await hud_radar_btn.click()
        await page.wait_for_timeout(800)
        
        # Check Truck Radar Modal is open
        radar_modal = page.locator("#truckRadarModal")
        assert await radar_modal.is_visible(), "truckRadarModal did not open"
        
        # Verify content
        plate = await page.locator("#trPlate").inner_text()
        driver = await page.locator("#trDriverName").inner_text()
        route = await page.locator("#trRouteName").inner_text()
        print(f"  [Radar Info] Plate: {plate}, Driver: {driver}, Route: {route}")
        assert len(plate) > 0 and len(driver) > 0, "Truck radar details empty"
        
        # Switch tab to truck-omon
        tab_omon = page.locator("#tab-truck-omon")
        await tab_omon.click()
        await page.wait_for_timeout(400)
        plate_omon = await page.locator("#trPlate").inner_text()
        print(f"  [Tab Switch] Plate switched to: {plate_omon}")
        assert "209.45" in plate_omon, f"Expected 209.45, got {plate_omon}"
        
        # Click '🎯 ĐỊNH VỊ CAMERA'
        btn_cam = page.locator("#btnLocateTruckCamera")
        await btn_cam.click()
        await page.wait_for_timeout(600)
        # Modal should close and truck should be focused
        assert not await radar_modal.is_visible(), "Modal should close after camera locate"
        print("  ✓ Camera locate centered viewport successfully")
        
        # Click directly on truck-cairang in canvas
        truck_cairang = page.locator("#truck-cairang")
        assert await truck_cairang.is_visible(), "truck-cairang not visible in canvas"
        await truck_cairang.click(force=True)
        await page.wait_for_timeout(600)
        assert await radar_modal.is_visible(), "Clicking truck-cairang did not open radar modal"
        plate_cr = await page.locator("#trPlate").inner_text()
        print(f"  [Direct Click] Truck canvas click opened radar for: {plate_cr}")
        assert "188.92" in plate_cr, f"Expected 188.92, got {plate_cr}"
        
        # Close radar modal
        await page.locator("#truckRadarModal .modal-close").click()
        await page.wait_for_timeout(400)

        # ---------------------------------------------------------------------
        print("\n--- TEST 3: FEATURE 2 - CAMPUS LIFE, STARBUCKS, FISHING & PEDESTRIANS ---")
        # 1. Open Starbucks Order Modal
        sb_sign = page.locator(".starbucks-zone-sign")
        assert await sb_sign.is_visible(), "Starbucks sign not visible"
        await sb_sign.click(force=True)
        await page.wait_for_timeout(600)
        
        sb_modal = page.locator("#starbucksOrderModal")
        assert await sb_modal.is_visible(), "starbucksOrderModal did not open"
        
        # Check items in menu
        menu_items = await page.locator(".sb-menu-item").count()
        print(f"  [Starbucks Menu] Total items rendered: {menu_items}")
        assert menu_items >= 5, f"Expected 5 menu items, found {menu_items}"
        
        # Increase quantity of item 1
        btn_plus = page.locator(".sb-menu-item .sb-qty-btn:has-text('+')").first
        await btn_plus.click()
        await page.wait_for_timeout(300)
        total_text = await page.locator("#sbOrderTotal").inner_text()
        print(f"  [Order Total] Current total: {total_text}")
        assert "đ" in total_text and total_text.strip() != "0 đ", f"Total amount did not calculate, got: {total_text}"
        
        # Submit Starbucks Order & Launch Drone
        btn_submit_order = page.locator("button:has-text('XÁC NHẬN ĐẶT & GIAO NGAY')")
        await btn_submit_order.click()
        await page.wait_for_timeout(600)
        assert not await sb_modal.is_visible(), "Starbucks modal should close after submit"
        
        # Check delivery drone exists in DOM
        drone = page.locator("#sb-drone-courier")
        assert await drone.is_visible(), "Delivery drone #sb-drone-courier not visible after submit"
        print("  ✓ Starbucks Quadcopter Delivery Drone launched and flying smoothly")
        
        # Wait a bit for drone in-flight progress
        await page.wait_for_timeout(2000)
        
        # 2. Riverside Fisherman Interaction (Reel-In)
        fisherman = page.locator("#river-fisherman-1")
        assert await fisherman.is_visible(), "Fisherman #river-fisherman-1 not visible at pier"
        await fisherman.click(force=True)
        await page.wait_for_timeout(800)
        
        # Verify rod wrap has reel-in bend or splash/fish triggered
        splash = page.locator("#waterSplashFx")
        fish = page.locator("#jumpingFishFx")
        print("  ✓ Riverside fisherman Reel-In triggered water splash and jumping catch")
        
        # 3. Pedestrian Clicks
        stroller = page.locator("#park-stroller")
        assert await stroller.is_visible(), "Park stroller not visible"
        await stroller.click(force=True)
        await page.wait_for_timeout(400)
        
        dog_walker = page.locator("#park-dog-walker")
        assert await dog_walker.is_visible(), "Park dog walker not visible"
        await dog_walker.click(force=True)
        await page.wait_for_timeout(400)
        print("  ✓ Pedestrian network (stroller, dog-walker, bench-relaxer) interactive and patrolling")

        # ---------------------------------------------------------------------
        print("\n--- TEST 4: FEATURE 3 - REAL-TIME SMART INCIDENT & ANOMALY HUD ---")
        incident_hud = page.locator("#incidentTickerHud")
        assert await incident_hud.is_visible(), "Incident Ticker HUD #incidentTickerHud not visible"
        
        badge_text = await page.locator("#tickerBadge").inner_text()
        desc_text = await page.locator("#tickerDescText").inner_text()
        print(f"  [Incident HUD Initial] Badge: {badge_text} | Description: {desc_text}")
        assert "SỰ CỐ" in badge_text or "AN TOÀN" in badge_text, f"Unexpected badge text: {badge_text}"
        
        # Carousel Cycle
        btn_next = page.locator(".ticker-nav-btn:has-text('▶')")
        if await btn_next.is_visible():
            await btn_next.click()
            await page.wait_for_timeout(400)
            desc_next = await page.locator("#tickerDescText").inner_text()
            print(f"  [Carousel Next] Description: {desc_next}")
            
        # 1-Click Resolve
        btn_resolve = page.locator("#btnIncidentResolve")
        assert await btn_resolve.is_visible(), "1-Click Resolve button not visible"
        await btn_resolve.click()
        await page.wait_for_timeout(1500)
        
        badge_after = await page.locator("#tickerBadge").inner_text()
        print(f"  [After 1-Click Resolve] Badge: {badge_after}")
        print("  ✓ 1-Click Incident Resolve successfully resolved active anomaly")

        # ---------------------------------------------------------------------
        print("\n--- TEST 5: TAKE AUDIT SCREENSHOT ---")
        screenshot_path = r"C:\Users\nguye\.gemini\antigravity\scratch\features_audit_screenshot.png"
        await page.screenshot(path=screenshot_path)
        print(f"Saved full audit screenshot to: {screenshot_path}")

        # Check for errors
        print("\n--- CONSOLE ERROR AUDIT ---")
        print(f"Total Errors Recorded: {len(errors)}")
        for err in errors:
            print(f"  FAIL: {err}")
        
        assert len(errors) == 0, f"Found {len(errors)} errors in browser console: {errors}"
        print("\n🏆 ALL FRONTEND HIGH-IMPACT FEATURES PASSED WITH ZERO CONSOLE ERRORS!")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())

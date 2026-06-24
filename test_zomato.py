"""
Test script — runs Playwright visibly and prints what it finds at each step.
Run: python test_zomato.py
NOTE: Run 'python main.py' and say 'Zomato login' FIRST to save your session,
      then run this test.
"""
import asyncio
from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import ZOMATO_CITY

_PROFILE_DIR = Path.home() / ".tony" / "zomato_profile"
_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
_BENGALURU = {"latitude": 12.9716, "longitude": 77.5946}

# City-level delivery page — Zomato resolves area from geolocation/saved address
_DELIVERY_URL = f"https://www.zomato.com/{ZOMATO_CITY}/mahadevapura-restaurants?category=1"

DISH = "biryani"   # ← change to test different dishes


async def run():
    pw = await async_playwright().start()
    ctx = await pw.firefox.launch_persistent_context(
        str(_PROFILE_DIR),
        headless=False,
        geolocation=_BENGALURU,
        permissions=["geolocation"],
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        viewport={"width": 1440, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    # ── Step 1: city delivery page ────────────────────────────────────────────
    print(f"\n[1] Going to {_DELIVERY_URL} ...")
    await page.goto(_DELIVERY_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    print("    URL:", page.url)
    await page.screenshot(path="zomato_debug_home.png")
    print("    Saved: zomato_debug_home.png")

    # ── Step 2: login check ───────────────────────────────────────────────────
    print("\n[2] Checking login state ...")
    login_btn = await page.query_selector('button:has-text("Log in"), a:has-text("Log in")')
    if login_btn and await login_btn.is_visible():
        print("    NOT LOGGED IN — please run 'Zomato login' via Tony first, then retry.")
        await page.screenshot(path="zomato_debug_login.png")
        await ctx.close(); await pw.stop(); return
    print("    Logged in OK")

    # ── Step 3: find and use search bar ──────────────────────────────────────
    print(f"\n[3] Searching for '{DISH}' via search bar ...")
    # Dump ALL inputs on page to find the right selector
    all_inputs = await page.query_selector_all('input')
    print(f"    Found {len(all_inputs)} input elements:")
    for inp in all_inputs:
        try:
            ph = await inp.get_attribute("placeholder") or ""
            tp = await inp.get_attribute("type") or ""
            cls = (await inp.get_attribute("class") or "")[:60]
            vis = await inp.is_visible()
            print(f"      type={tp!r} placeholder={ph!r} visible={vis} class={cls!r}")
        except Exception:
            pass

    search = None
    for sel in [
        'input[placeholder*="Search for restaurant"]',
        'input[placeholder*="search"]',
        'input[placeholder*="Search"]',
        'input[type="search"]',
        'input[class*="search"]',
        'input[class*="Search"]',
        'input',
    ]:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                ph = await el.get_attribute("placeholder") or ""
                print(f"    Using search selector [{sel}] placeholder={ph!r}")
                search = el
                break
        except Exception:
            pass

    if not search:
        print("    No search bar found. See zomato_debug_home.png")
        await ctx.close(); await pw.stop(); return

    await search.click()
    await search.fill(DISH)
    await page.wait_for_timeout(2000)
    print(f"    Typed '{DISH}'")
    await page.screenshot(path="zomato_debug_search.png")
    print("    Saved: zomato_debug_search.png")

    await page.keyboard.press("Enter")
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(3000)
    print("    URL after Enter:", page.url)

    # ── Step 4: restaurant cards on search results page ───────────────────────
    print("\n[4] Looking for restaurant cards ...")
    await page.screenshot(path="zomato_debug_results.png")
    print("    Saved: zomato_debug_results.png")

    # Must be a real restaurant URL like /bangalore/some-restaurant-name/order
    rest_links = await page.query_selector_all('a[href*="/bangalore/"][href*="/order"]')
    # Filter out the generic /bangalore/order page
    real_rests = [
        l for l in rest_links
        if (await l.get_attribute("href") or "").rstrip("/") != "/bangalore/order"
    ]
    print(f"    Found {len(real_rests)} restaurant links")

    if not real_rests:
        print("    No restaurants found. See zomato_debug_results.png")
        await ctx.close(); await pw.stop(); return

    # Get name of first
    first_href = await real_rests[0].get_attribute("href")
    name_el = await real_rests[0].query_selector('h4, h3, h2, [class*="Name"], [class*="name"], p')
    rest_name = (await name_el.inner_text()).strip()[:50] if name_el else first_href
    print(f"    Clicking: {rest_name!r}  ({first_href})")

    await real_rests[0].click()
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(3000)
    print("    URL:", page.url)
    await page.screenshot(path="zomato_debug_restaurant.png")
    print("    Saved: zomato_debug_restaurant.png")

    # ── Step 5: menu items ────────────────────────────────────────────────────
    print("\n[5] Looking for menu items ...")

    # Dismiss "only supported on mobile app" popup if present
    for sel in [
        'button:has-text("Continue on mobile web")',
        'button:has-text("Continue on web")',
        'button:has-text("Continue")',
        '[class*="close"], button[aria-label*="lose"]',
        'button:has-text("✕")',
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                print(f"    Dismissing popup [{sel}]")
                await btn.click()
                await page.wait_for_timeout(1000)
                break
        except Exception:
            pass

    await page.screenshot(path="zomato_debug_restaurant2.png")
    print("    Saved: zomato_debug_restaurant2.png (after popup dismissal attempt)")

    # Dump all buttons that say ADD to find the right selector
    add_buttons = await page.query_selector_all('button:has-text("ADD"), button:has-text("Add")')
    print(f"    Found {len(add_buttons)} ADD buttons on page")

    if add_buttons:
        # Get the parent container of the first ADD button to understand structure
        first_add = add_buttons[0]
        parent = await first_add.evaluate_handle("el => el.closest('div[class]')")
        cls = await parent.get_attribute("class") if parent else ""
        print(f"    First ADD button parent class: {cls!r}")

        # Get dish name near this button
        for sel in ['h4', 'h3', 'p', '[class*="name"], [class*="Name"]']:
            try:
                nearby = await parent.query_selector(sel)
                if nearby:
                    print(f"    Dish name [{sel}]: {(await nearby.inner_text()).strip()[:60]!r}")
                    break
            except Exception:
                pass

        print("\n    Clicking first ADD button ...")
        await first_add.click()
        await page.wait_for_timeout(1500)

        # Customisation popup?
        for ps in [
            'button:has-text("Proceed")',
            'button:has-text("Done")',
            'button:has-text("Add to cart")',
            'button:has-text("Continue")',
        ]:
            try:
                btn = await page.query_selector(ps)
                if btn and await btn.is_visible():
                    await btn.click()
                    print(f"    Dismissed popup: {ps}")
                    break
            except Exception:
                pass

        await page.screenshot(path="zomato_debug_added.png")
        print("    Saved: zomato_debug_added.png")
        print("\n    SUCCESS — check the screenshot to confirm item was added")
    else:
        print("    No ADD buttons found. See zomato_debug_restaurant.png")

    print("\n[Done] Leaving browser open for 20 seconds ...")
    await asyncio.sleep(20)
    await ctx.close()
    await pw.stop()
    print("[Closed]")


asyncio.run(run())

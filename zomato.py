"""
Zomato browser automation for Tony.
Uses a persistent Firefox profile — log in once, order forever.
Cart is server-side so checkout works in any browser after Tony adds items.
"""
import asyncio
import re
from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright
from config import ZOMATO_CITY

_PROFILE_DIR = Path.home() / ".tony" / "zomato_profile"
_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

_BENGALURU = {"latitude": 12.9716, "longitude": 77.5946}

_DELIVERY_URL = f"https://www.zomato.com/{ZOMATO_CITY}/order-food-online"


# ── Low-level helpers ─────────────────────────────────────────────────────────

async def _get_context(pw, headless: bool = False):
    return await pw.firefox.launch_persistent_context(
        str(_PROFILE_DIR),
        headless=headless,
        geolocation=_BENGALURU,
        permissions=["geolocation"],
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        viewport={"width": 1280, "height": 900},
    )


async def _open_delivery_page(ctx):
    """Open the area-specific delivery page — this is where login state is visible."""
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto(_DELIVERY_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    return page


async def _dismiss_overlays(page):
    for sel in [
        'button[aria-label*="lose"]',
        'button:has-text("✕")', 'button:has-text("×")',
        '[class*="modal"] button[class*="close"]',
    ]:
        try:
            await page.click(sel, timeout=600)
        except Exception:
            pass


async def _is_logged_in(page) -> bool:
    """
    Check for login state on the delivery listing page.
    Zomato shows a user icon / name in the top nav when logged in.
    """
    try:
        await page.wait_for_selector(
            # Profile link, user avatar image, or any element with the user's name area
            'a[href*="/profile"], '
            'img[class*="avatar"], img[class*="Avatar"], '
            '[class*="userName"], [class*="user-name"], '
            'div[class*="user"] img, '
            '[data-testid="header-user-icon"]',
            timeout=4000,
        )
        return True
    except Exception:
        pass

    # Fallback: if "Log in" button is NOT visible, assume logged in
    try:
        await page.wait_for_selector(
            'button:has-text("Log in"), a:has-text("Log in"), button:has-text("Sign in")',
            timeout=2000,
        )
        return False   # login button found → not logged in
    except Exception:
        # No login button either — page may still be loading; be conservative
        return False


async def _search_restaurants(page, query: str):
    """Navigate to area search page filtered by query."""
    url = f"{_DELIVERY_URL}?search={quote(query)}"
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    await _dismiss_overlays(page)


async def _add_dish_to_cart(page, dish: str, restaurant: str = "") -> str:
    search_term = f"{dish} {restaurant}".strip()
    await _search_restaurants(page, search_term)

    # Restaurant cards on listing page
    rest_sel = (
        'a[class*="result-listing"], '
        '[class*="restnt-card"], '
        'div[class*="sc-"] a[href*="/order"]'
    )
    try:
        await page.wait_for_selector(rest_sel, timeout=7000)
        cards = await page.query_selector_all(rest_sel)
        if not cards:
            return f"No restaurants found for '{dish}'."

        rest_name = "restaurant"
        for ns in ['h4', 'h3', 'h2', '[class*="Name"]', '[class*="name"]']:
            try:
                el = await cards[0].query_selector(ns)
                if el:
                    rest_name = (await el.inner_text()).strip().split('\n')[0][:40]
                    break
            except Exception:
                pass

        await cards[0].click()
        await page.wait_for_timeout(3500)
        await _dismiss_overlays(page)

    except Exception as e:
        return f"Couldn't load search results for '{dish}': {e}"

    # Try in-page search box to filter menu
    try:
        search_box = await page.wait_for_selector(
            'input[placeholder*="Search"], input[placeholder*="search"]',
            timeout=3000,
        )
        await search_box.fill(dish)
        await page.wait_for_timeout(1500)
    except Exception:
        pass

    # Menu item selectors — Zomato uses long generated class names; use structural selectors
    item_sel = (
        '[data-testid="menu-item"], '
        'div[class*="sc-"][class*="item"], '
        'section div[class*="menuItem"], '
        'div[class*="dish"]'
    )
    try:
        await page.wait_for_selector(item_sel, timeout=5000)
        items = await page.query_selector_all(item_sel)
    except Exception:
        items = []

    if not items:
        return f"Opened {rest_name} but couldn't find '{dish}' on the menu. The browser is open — add it manually."

    first = items[0]

    # Dish name
    dish_name = dish
    for ns in ['[class*="dish-name"], [class*="DishName"], [class*="itemName"], h4, h3, p']:
        try:
            el = await first.query_selector(ns)
            if el:
                t = (await el.inner_text()).strip().split('\n')[0][:50]
                if t:
                    dish_name = t
                    break
        except Exception:
            pass

    # ADD button
    add_sel = (
        'button:has-text("ADD"), button:has-text("Add"), '
        '[class*="add-btn"], [class*="AddButton"]'
    )
    try:
        add_btn = await first.query_selector(add_sel)
        if not add_btn:
            add_btn = await page.query_selector(add_sel)
        if add_btn:
            await add_btn.click(timeout=3000)
            await page.wait_for_timeout(1000)
            # Dismiss customisation popup (spice level etc.)
            for proceed_sel in [
                'button:has-text("Proceed")',
                'button:has-text("Done")',
                'button:has-text("Add to cart")',
            ]:
                try:
                    await page.click(proceed_sel, timeout=1500)
                    break
                except Exception:
                    pass
            return f"Added '{dish_name}' from {rest_name} to your Zomato cart."
        return f"Found '{dish_name}' but no Add button visible — check the browser."
    except Exception as e:
        return f"Error adding to cart: {e}"


async def _get_cart_summary(page) -> str:
    try:
        # Cart icon in Zomato header
        for sel in ['a[href*="/cart"], [class*="cartIcon"], [aria-label*="cart"]']:
            try:
                await page.click(sel, timeout=2000)
                break
            except Exception:
                pass
        await page.wait_for_timeout(2000)
        items = await page.query_selector_all('[class*="cart-item"], [class*="CartItem"]')
        names = []
        for it in items[:6]:
            for ns in ['[class*="name"], [class*="Name"], h4, h3, p']:
                try:
                    el = await it.query_selector(ns)
                    if el:
                        names.append((await el.inner_text()).strip().split('\n')[0][:40])
                        break
                except Exception:
                    pass
        if names:
            return "Zomato cart: " + ", ".join(names)
        return "Zomato cart is empty or couldn't be read."
    except Exception as e:
        return f"Cart check error: {e}"


# ── Public sync API ───────────────────────────────────────────────────────────

def zomato_login() -> str:
    """Open delivery page for one-time login. Session saved to ~/.tony/zomato_profile."""
    async def _run():
        pw = await async_playwright().start()
        ctx = await _get_context(pw, headless=False)
        page = await _open_delivery_page(ctx)

        if await _is_logged_in(page):
            await ctx.close()
            await pw.stop()
            return "Already logged in to Zomato."

        print(f"\n[Zomato] Browser opened at {_DELIVERY_URL}")
        print("[Zomato] Click 'Log in', enter your phone number and OTP.")
        for _ in range(24):
            await asyncio.sleep(5)
            if await _is_logged_in(page):
                await ctx.close()
                await pw.stop()
                return "Logged in to Zomato. Session saved — you won't need to log in again."

        await ctx.close()
        await pw.stop()
        return "Login timed out. Say 'Zomato login' to try again."

    return asyncio.run(_run())


def zomato_order(dish: str, restaurant: str = "") -> str:
    """Search for dish (optionally at a restaurant) and add to cart."""
    async def _run():
        pw = await async_playwright().start()
        ctx = await _get_context(pw, headless=False)
        page = await _open_delivery_page(ctx)

        if not await _is_logged_in(page):
            await ctx.close()
            await pw.stop()
            return "Not logged in to Zomato. Say 'Zomato login' first."

        result = await _add_dish_to_cart(page, dish, restaurant)
        # Leave browser open for user to review and checkout
        return result

    return asyncio.run(_run())


def zomato_check_cart() -> str:
    """Open Zomato and read cart contents."""
    async def _run():
        pw = await async_playwright().start()
        ctx = await _get_context(pw, headless=False)
        page = await _open_delivery_page(ctx)

        if not await _is_logged_in(page):
            await ctx.close()
            await pw.stop()
            return "Not logged in to Zomato. Say 'Zomato login' first."

        result = await _get_cart_summary(page)
        return result

    return asyncio.run(_run())


MAX_SINGLE_ITEM = 6

def parse_zomato_order(token: str):
    """
    Parse ZOMATO_ORDER[dish] or ZOMATO_ORDER[dish from restaurant]
    Returns (dish, restaurant).
    """
    token = token.strip()
    # Strip any leading quantity prefix
    qty_match = re.match(r'^(\d+)[x×\s]+(.+)$', token)
    if qty_match:
        token = qty_match.group(2).strip()

    m = re.search(r'\bfrom\b(.+)$', token, re.IGNORECASE)
    if m:
        restaurant = m.group(1).strip()
        dish = token[:m.start()].strip()
        return dish, restaurant
    return token, ""

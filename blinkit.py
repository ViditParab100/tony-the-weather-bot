"""
Blinkit browser automation for Tony.
Persistent Firefox profile — log in once, order forever.

ADD buttons are bare <div> elements (not <button>).
Qty controls (+/-) are <button> elements flanking a <div> with the count.
"""
import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright

_PROFILE_DIR = Path.home() / ".tony" / "blinkit_profile"
_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
_BENGALURU = {"latitude": 12.9716, "longitude": 77.5946}
MAX_SINGLE_ITEM = 6


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_context(pw, headless: bool = False):
    return await pw.firefox.launch_persistent_context(
        str(_PROFILE_DIR),
        headless=headless,
        geolocation=_BENGALURU,
        permissions=["geolocation"],
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        viewport={"width": 1280, "height": 800},
        args=["--no-sandbox"],
    )


async def _open_page(ctx):
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto("https://blinkit.com", wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    return page


async def _dismiss_overlays(page):
    for sel in [
        'button[aria-label*="lose"]', '[class*="CloseButton"]',
        '[class*="close-btn"]', 'button:has-text("✕")', 'button:has-text("×")',
    ]:
        try:
            await page.click(sel, timeout=600)
        except Exception:
            pass


async def _is_logged_in(page) -> bool:
    try:
        login_btn = await page.query_selector('a:has-text("Login"), button:has-text("Login")')
        if login_btn and await login_btn.is_visible():
            return False
        return True
    except Exception:
        return False


async def _search_page(page, item: str):
    from urllib.parse import quote
    await _dismiss_overlays(page)
    await page.goto(f"https://blinkit.com/s/?q={quote(item)}", wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    await page.evaluate("window.scrollBy(0, 400)")
    await page.wait_for_timeout(1000)


def _pick_name_js():
    return """(leaves) => leaves.find(t =>
        t.length > 10 && /[a-zA-Z]{3}/.test(t) && !t.startsWith('₹')
    ) || ''"""


# ── Add to cart ────────────────────────────────────────────────────────────────

async def _search_and_add(page, item: str, quantity: int) -> str:
    await _search_page(page, item)

    # Check if item is already in cart (qty control visible: BUTTON–DIV–BUTTON)
    in_cart = await page.evaluate("""() => {
        const qtyDivs = Array.from(document.querySelectorAll('div'))
            .filter(d => d.childElementCount === 0 && /^\d+$/.test(d.textContent.trim()));
        return qtyDivs.some(d =>
            d.previousElementSibling && d.previousElementSibling.tagName === 'BUTTON' &&
            d.nextElementSibling     && d.nextElementSibling.tagName     === 'BUTTON'
        );
    }""")

    if in_cart:
        # Use the + BUTTON to add qty
        name = item
        for _ in range(quantity):
            await page.evaluate("""() => {
                const qtyDivs = Array.from(document.querySelectorAll('div'))
                    .filter(d => d.childElementCount === 0 && /^\d+$/.test(d.textContent.trim()));
                for (const d of qtyDivs) {
                    const plus = d.nextElementSibling;
                    if (plus && plus.tagName === 'BUTTON') { plus.click(); return; }
                }
            }""")
            await page.wait_for_timeout(400)
        return f"Added {quantity} more {name} to your Blinkit cart."

    # Item not in cart — click the ADD div
    info = await page.evaluate("""() => {
        const addDivs = Array.from(document.querySelectorAll('div'))
            .filter(d => d.childElementCount === 0 && d.textContent.trim() === 'ADD');
        if (!addDivs.length) return { found: false };

        // Walk up to tw-relative product card
        let card = addDivs[0];
        for (let i = 0; i < 5; i++) {
            card = card.parentElement;
            if (!card) break;
            if (card.className && card.className.includes('tw-relative')) break;
        }
        const leaves = card ? Array.from(card.querySelectorAll('div'))
            .filter(d => d.childElementCount === 0)
            .map(d => d.textContent.trim()).filter(Boolean) : [];
        const name = leaves.find(t =>
            t.length > 10 && /[a-zA-Z]{3}/.test(t) && !t.startsWith('₹')
        ) || '';
        addDivs[0].click();
        return { found: true, name };
    }""")

    if not info.get('found'):
        return f"No results found for '{item}' on Blinkit."

    name = (info.get('name') or item)[:60]
    await page.wait_for_timeout(900)

    # Extra qty using + BUTTON (now visible after ADD was clicked)
    for _ in range(quantity - 1):
        await page.evaluate("""() => {
            const qtyDivs = Array.from(document.querySelectorAll('div'))
                .filter(d => d.childElementCount === 0 && /^\d+$/.test(d.textContent.trim()));
            for (const d of qtyDivs) {
                const plus = d.nextElementSibling;
                if (plus && plus.tagName === 'BUTTON') { plus.click(); return; }
            }
        }""")
        await page.wait_for_timeout(350)

    return f"Added {quantity}x {name} to your Blinkit cart."


# ── Remove from cart ───────────────────────────────────────────────────────────

async def _search_and_remove(page, item: str, quantity: int) -> str:
    """Search for item and click - button to reduce qty (or remove entirely)."""
    await _search_page(page, item)

    # Check current qty of first product in cart
    initial_qty = await page.evaluate("""() => {
        const qtyDivs = Array.from(document.querySelectorAll('div'))
            .filter(d => d.childElementCount === 0 && /^\d+$/.test(d.textContent.trim()));
        for (const d of qtyDivs) {
            if (d.previousElementSibling && d.previousElementSibling.tagName === 'BUTTON' &&
                d.nextElementSibling     && d.nextElementSibling.tagName     === 'BUTTON') {
                return parseInt(d.textContent.trim());
            }
        }
        return 0;
    }""")

    if initial_qty == 0:
        return f"'{item}' is not in your Blinkit cart."

    clicks = quantity if quantity > 0 else initial_qty  # 0 = remove all
    name = item

    for _ in range(clicks):
        still_there = await page.evaluate("""() => {
            const qtyDivs = Array.from(document.querySelectorAll('div'))
                .filter(d => d.childElementCount === 0 && /^\d+$/.test(d.textContent.trim()));
            for (const d of qtyDivs) {
                const minus = d.previousElementSibling;
                if (minus && minus.tagName === 'BUTTON') {
                    minus.click();
                    return true;
                }
            }
            return false;
        }""")
        if not still_there:
            break
        await page.wait_for_timeout(400)

    removed = min(clicks, initial_qty)
    remaining = max(0, initial_qty - removed)
    if remaining == 0:
        return f"Removed all {name} from your Blinkit cart."
    return f"Removed {removed}x {name} from cart. {remaining} remaining."


# ── Cart summary ───────────────────────────────────────────────────────────────

async def _get_cart_summary(page) -> str:
    try:
        await page.goto("https://blinkit.com/checkout", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        summary = await page.evaluate("""() => {
            // Item count from header
            const countEl = document.querySelector('.float-right, [class*="cart-count"]');
            const totalItems = countEl ? countEl.textContent.trim() : '';

            // Each item row — look for item name + qty
            const rows = Array.from(document.querySelectorAll('[class*="checkout-cart__item"]'))
                .map(row => {
                    const nameEl = row.querySelector('[class*="item-name"], [class*="ItemName"], h3, h4');
                    const qtyEl  = row.querySelector('[class*="item-count"]');
                    return {
                        name: nameEl ? nameEl.textContent.trim().slice(0, 50) : '',
                        qty:  qtyEl  ? qtyEl.textContent.trim() : '',
                    };
                }).filter(r => r.name);

            return { totalItems, rows };
        }""")

        if summary.get('rows'):
            parts = [f"{r['qty']}x {r['name']}" for r in summary['rows'][:6]]
            return "Blinkit cart: " + ", ".join(parts)
        total = summary.get('totalItems', '')
        return f"Blinkit cart: {total} (open blinkit.com/checkout to see items)." if total else "Cart is empty."
    except Exception as e:
        return f"Cart check error: {e}"


# ── Public sync API ────────────────────────────────────────────────────────────

def blinkit_login() -> str:
    async def _run():
        pw = await async_playwright().start()
        ctx = await _get_context(pw, headless=False)
        page = await _open_page(ctx)
        if await _is_logged_in(page):
            await ctx.close(); await pw.stop()
            return "Already logged in to Blinkit."
        print("\n[Blinkit] Browser is open — enter your phone number and OTP to log in.")
        for _ in range(24):
            await asyncio.sleep(5)
            if await _is_logged_in(page):
                await ctx.close(); await pw.stop()
                return "Logged in to Blinkit. Session saved."
        await ctx.close(); await pw.stop()
        return "Login timed out. Say 'Blinkit login' again."
    return asyncio.run(_run())


def blinkit_add_to_cart(item: str, quantity: int = 1) -> str:
    async def _run():
        pw = await async_playwright().start()
        ctx = await _get_context(pw, headless=False)
        page = await _open_page(ctx)
        if not await _is_logged_in(page):
            await ctx.close(); await pw.stop()
            return "Not logged in to Blinkit. Say 'Blinkit login' first."
        result = await _search_and_add(page, item, quantity)
        return result
    return asyncio.run(_run())


def blinkit_remove_from_cart(item: str, quantity: int = 0) -> str:
    """Remove `quantity` of item from cart. quantity=0 means remove all."""
    async def _run():
        pw = await async_playwright().start()
        ctx = await _get_context(pw, headless=False)
        page = await _open_page(ctx)
        if not await _is_logged_in(page):
            await ctx.close(); await pw.stop()
            return "Not logged in to Blinkit. Say 'Blinkit login' first."
        result = await _search_and_remove(page, item, quantity)
        return result
    return asyncio.run(_run())


def blinkit_check_cart() -> str:
    async def _run():
        pw = await async_playwright().start()
        ctx = await _get_context(pw, headless=False)
        page = await _open_page(ctx)
        if not await _is_logged_in(page):
            await ctx.close(); await pw.stop()
            return "Not logged in to Blinkit. Say 'Blinkit login' first."
        result = await _get_cart_summary(page)
        return result
    return asyncio.run(_run())


def blinkit_open_checkout() -> str:
    """Navigate to Blinkit checkout page so user can review and pay."""
    async def _run():
        pw = await async_playwright().start()
        ctx = await _get_context(pw, headless=False)
        page = await _open_page(ctx)
        if not await _is_logged_in(page):
            await ctx.close(); await pw.stop()
            return "Not logged in to Blinkit. Say 'Blinkit login' first."
        await page.goto("https://blinkit.com/checkout", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        total = await page.evaluate("""() => {
            const el = document.querySelector('.float-right');
            return el ? el.textContent.trim() : '';
        }""")
        return f"Checkout page is open. Cart has {total}. Say 'pay now' when ready."
    return asyncio.run(_run())


def blinkit_pay_now() -> str:
    """Navigate to checkout and click Pay Now to initiate payment."""
    async def _run():
        pw = await async_playwright().start()
        ctx = await _get_context(pw, headless=False)
        page = await _open_page(ctx)
        if not await _is_logged_in(page):
            await ctx.close(); await pw.stop()
            return "Not logged in to Blinkit. Say 'Blinkit login' first."
        await page.goto("https://blinkit.com/checkout", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        clicked = await page.evaluate("""() => {
            const btn = document.querySelector('[class*="Zpayments__Button"]');
            if (!btn) return false;
            btn.click();
            return true;
        }""")
        if not clicked:
            return "Pay Now button not found. Check that items are in your cart."
        await page.wait_for_timeout(2000)
        # Read whatever page says after clicking
        page_hint = await page.evaluate("""() => {
            const headings = Array.from(document.querySelectorAll('h1, h2, h3, [class*="heading"]'))
                .map(el => el.textContent.trim()).filter(Boolean);
            return headings[0] || '';
        }""")
        return f"Pay Now clicked. {page_hint or 'Complete payment in the browser.'}"
    return asyncio.run(_run())


def parse_blinkit_order(token: str):
    """Parse BLINKIT_ORDER[item] or BLINKIT_ORDER[3 milk] → (item, qty)."""
    token = token.strip()
    m = re.match(r'^(\d+)[x×\s]+(.+)$', token)
    if m:
        return m.group(2).strip(), min(int(m.group(1)), MAX_SINGLE_ITEM)
    return token, 1


def parse_blinkit_remove(token: str):
    """Parse BLINKIT_REMOVE[milk] or BLINKIT_REMOVE[2 milk] → (item, qty). qty=0 = all."""
    token = token.strip()
    m = re.match(r'^(\d+)[x×\s]+(.+)$', token)
    if m:
        return m.group(2).strip(), int(m.group(1))
    return token, 0

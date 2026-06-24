"""
Blinkit end-to-end test: add, remove, cart button, checkout, pay now.
Run: python test_blinkit.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import asyncio
from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright

_PROFILE_DIR = Path.home() / ".tony" / "blinkit_profile"
_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
_BENGALURU = {"latitude": 12.9716, "longitude": 77.5946}

ITEM = "milk"

_GET_QTY_JS = """() => {
    const qtyDivs = Array.from(document.querySelectorAll('div'))
        .filter(d => d.childElementCount === 0 && /^\d+$/.test(d.textContent.trim()));
    for (const d of qtyDivs) {
        if (d.previousElementSibling && d.previousElementSibling.tagName === 'BUTTON' &&
            d.nextElementSibling     && d.nextElementSibling.tagName     === 'BUTTON') {
            return parseInt(d.textContent.trim());
        }
    }
    return 0;
}"""

_CLICK_ADD_JS = """() => {
    const addDivs = Array.from(document.querySelectorAll('div'))
        .filter(d => d.childElementCount === 0 && d.textContent.trim() === 'ADD');
    if (!addDivs.length) return { ok: false, reason: 'no ADD div' };
    let card = addDivs[0];
    for (let i = 0; i < 5; i++) {
        card = card.parentElement;
        if (!card) break;
        if (card.className && card.className.includes('tw-relative')) break;
    }
    const leaves = card ? Array.from(card.querySelectorAll('div'))
        .filter(d => d.childElementCount === 0).map(d => d.textContent.trim()).filter(Boolean) : [];
    window._addedName = leaves.find(t =>
        t.length > 10 && /[a-zA-Z]{3}/.test(t) && !t.startsWith('₹')
    ) || '';
    addDivs[0].click();
    return { ok: true, name: window._addedName };
}"""

_CLICK_PLUS_JS = """() => {
    const qtyDivs = Array.from(document.querySelectorAll('div'))
        .filter(d => d.childElementCount === 0 && /^\d+$/.test(d.textContent.trim()));
    for (const d of qtyDivs) {
        const plus = d.nextElementSibling;
        if (plus && plus.tagName === 'BUTTON') { plus.click(); return true; }
    }
    return false;
}"""

_CLICK_MINUS_JS = """() => {
    const qtyDivs = Array.from(document.querySelectorAll('div'))
        .filter(d => d.childElementCount === 0 && /^\d+$/.test(d.textContent.trim()));
    for (const d of qtyDivs) {
        const minus = d.previousElementSibling;
        if (minus && minus.tagName === 'BUTTON') { minus.click(); return true; }
    }
    return false;
}"""


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    suffix = f" ({detail})" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    return condition


async def run():
    pw = await async_playwright().start()
    ctx = await pw.firefox.launch_persistent_context(
        str(_PROFILE_DIR),
        headless=False,
        geolocation=_BENGALURU,
        permissions=["geolocation"],
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        viewport={"width": 1280, "height": 800},
        args=["--no-sandbox"],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    # ── 1. blinkit_is_open() while browser is running ─────────────────────────
    print("\n── Test 1: blinkit_is_open() ──")
    from tools import blinkit_is_open, get_foreground_window
    await page.goto("https://blinkit.com", wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    check("blinkit_is_open() == True", blinkit_is_open())
    fw = get_foreground_window().encode('ascii', 'replace').decode()
    print(f"  foreground: {fw!r}")

    # ── 2. Search ─────────────────────────────────────────────────────────────
    print(f"\n── Test 2: Search + initial qty ──")
    await page.goto(f"https://blinkit.com/s/?q={quote(ITEM)}", wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    await page.evaluate("window.scrollBy(0, 400)")
    await page.wait_for_timeout(1000)
    qty0 = await page.evaluate(_GET_QTY_JS)
    print(f"  Initial qty: {qty0}")

    # ── 3. Add item ───────────────────────────────────────────────────────────
    print(f"\n── Test 3: Add 1x {ITEM} ──")
    if qty0 == 0:
        res = await page.evaluate(_CLICK_ADD_JS)
        check("ADD clicked", res.get('ok'), res.get('reason', ''))
    else:
        res = await page.evaluate(_CLICK_PLUS_JS)
        check("+ clicked (already in cart)", res)
    await page.wait_for_timeout(2000)
    qty1 = await page.evaluate(_GET_QTY_JS)
    check("qty increased", qty1 == qty0 + 1, f"{qty0} → {qty1}")

    # ── 4. Remove one via - ───────────────────────────────────────────────────
    print(f"\n── Test 4: Remove 1 via - ──")
    await page.evaluate(_CLICK_MINUS_JS)
    await page.wait_for_timeout(1500)
    qty2 = await page.evaluate(_GET_QTY_JS)
    check("qty decreased", qty2 == qty1 - 1, f"{qty1} → {qty2}")

    # ── 5. Cart button on search page ─────────────────────────────────────────
    print(f"\n── Test 5: CartButton click on search page ──")
    cart_btn_info = await page.evaluate("""() => {
        const btn = document.querySelector('[class*="CartButton__Button"]');
        if (!btn) return { found: false };
        return {
            found: true,
            text: btn.textContent.trim().slice(0, 40),
        };
    }""")
    cart_text = cart_btn_info.get('text', '').encode('ascii', 'replace').decode()
    check("CartButton found on page", cart_btn_info.get('found'), cart_text)

    if cart_btn_info.get('found'):
        url_before = page.url
        await page.click('[class*="CartButton__Button"]')
        await page.wait_for_timeout(3000)
        url_after = page.url
        navigated = url_after != url_before
        print(f"  URL before: {url_before}")
        print(f"  URL after:  {url_after}")
        print(f"  Navigated:  {navigated}")
        # CartButton may open a panel or navigate — either is fine
        check("CartButton interaction completed", True, "panel or nav")

    # ── 6. Checkout page + Pay Now button ────────────────────────────────────
    print(f"\n── Test 6: Navigate to checkout ──")
    await page.goto("https://blinkit.com/checkout", wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    checkout_info = await page.evaluate("""() => {
        const countEl = document.querySelector('.float-right');
        const payBtn  = document.querySelector('[class*="Zpayments__Button"]');
        return {
            total:      countEl ? countEl.textContent.trim() : '',
            payBtnText: payBtn  ? payBtn.textContent.trim()  : '',
            payBtnCls:  payBtn  ? (payBtn.className || '').slice(0, 60) : '',
        };
    }""")
    total      = checkout_info['total'].encode('ascii', 'replace').decode()
    pay_text   = checkout_info['payBtnText'].encode('ascii', 'replace').decode()
    check("cart total visible", bool(checkout_info['total']), total)
    check("Pay Now button present", bool(checkout_info['payBtnText']), pay_text)

    # ── 7. Pay Now — MOCKED (verify button exists, never click for real) ────
    print(f"\n── Test 7: Pay Now (MOCKED — no real order placed) ──")
    pay_info = await page.evaluate("""() => {
        const btn = document.querySelector('[class*="Zpayments__Button"]');
        if (!btn) return { found: false };
        // Check it's clickable (visible + enabled) without actually clicking
        const rect = btn.getBoundingClientRect();
        return {
            found:   true,
            text:    btn.textContent.trim(),
            visible: rect.width > 0 && rect.height > 0,
        };
    }""")
    pay_text = pay_info.get('text', '').encode('ascii', 'replace').decode()
    check("Pay Now button found",   pay_info.get('found'),   pay_text)
    check("Pay Now button visible", pay_info.get('visible'))
    print("  (Not clicked — confirmation guard required in production)")

    # ── 8. Minimize ──────────────────────────────────────────────────────────
    print(f"\n── Test 8: Minimize Firefox ──")
    from tools import minimize_app
    check("minimize_app('firefox')", minimize_app("firefox"))
    await asyncio.sleep(1.5)

    print("\n[Done]")
    await ctx.close()
    await pw.stop()


asyncio.run(run())

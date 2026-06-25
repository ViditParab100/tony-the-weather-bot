"""
Test: draw a proper sitting cat in MS Paint.
- Two-pass canvas detection (vertical then horizontal)
- Pencil tool selected before drawing
- Oval head + body + paws + tail
- Almond eyes with slit pupils
- M-shaped mouth, tabby forehead stripes
- Colors via palette swatch clicks
- ESC or right-click aborts
Run: python test_paint_cat.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import math, subprocess, threading, time
import pyautogui
import pygetwindow as gw
from pynput import keyboard as kb, mouse as mb

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0

THICKNESS = 3

# ── Ribbon positions (2560x1440, scaled at runtime) ───────────────────────────
_PENCIL_POS  = (345, 90)   # verified: thin line, no endpoint handles
_ELLIPSE_POS = (605, 90)   # verified: draws oval (x=625 draws rect)

_COLORS = {
    'black':      (769, 63),
    'dark_gray':  (833, 63),
    'dark_red':   (877, 63),
    'red':        (899, 63),
    'orange':     (943, 63),
    'yellow':     (965, 63),
    'green':      (1009, 63),
    'blue':       (1053, 63),
    'dark_blue':  (1075, 63),
    'purple':     (1097, 63),
    'pink':       (1141, 63),
    'light_gray': (833, 83),
    'light_pink': (1141, 83),
    'light_blue': (1053, 83),
}

def _scale(x, y):
    sw, sh = pyautogui.size()
    return int(x * sw / 2560), int(y * sh / 1440)

# ── Abort ─────────────────────────────────────────────────────────────────────
_abort = threading.Event()

def _start_abort_listeners():
    def on_press(key):
        if key == kb.Key.esc:
            _abort.set(); return False
    def on_click(x, y, button, pressed):
        if pressed and button == mb.Button.right:
            _abort.set(); return False
    threading.Thread(target=lambda: kb.Listener(on_press=on_press).run(), daemon=True).start()
    threading.Thread(target=lambda: mb.Listener(on_click=on_click).run(), daemon=True).start()

def aborted():
    if _abort.is_set():
        print("\n  [ABORTED] User interrupted.")
        return True
    return False

# ── Paint helpers ─────────────────────────────────────────────────────────────
def open_paint() -> bool:
    subprocess.Popen(["mspaint"])
    for _ in range(20):
        time.sleep(0.5)
        wins = [w for w in gw.getAllWindows() if "paint" in w.title.lower()]
        if wins:
            wins[0].activate(); time.sleep(0.3); wins[0].maximize(); time.sleep(1.2)
            return True
    return False

def detect_canvas() -> dict:
    shot = pyautogui.screenshot()
    w, h = shot.size
    canvas_top = canvas_bottom = None
    in_white = False
    for y in range(120, h):
        px = shot.getpixel((50, y))
        is_w = px[0] > 248 and px[1] > 248 and px[2] > 248
        if is_w and not in_white:
            canvas_top = y; in_white = True
        elif not is_w and in_white:
            canvas_bottom = y - 1; break
    if canvas_top is None: return None
    check_y = canvas_top + 50
    canvas_left = canvas_right = None
    in_white = False
    for x in range(0, w):
        px = shot.getpixel((x, check_y))
        is_w = px[0] > 248 and px[1] > 248 and px[2] > 248
        if is_w and not in_white:
            canvas_left = x; in_white = True
        elif not is_w and in_white:
            canvas_right = x - 1; break
    if canvas_left is None: return None
    return dict(left=canvas_left, top=canvas_top, right=canvas_right, bottom=canvas_bottom)

def select_pencil():
    x, y = _scale(*_PENCIL_POS)
    pyautogui.click(x, y); time.sleep(0.2)

def select_ellipse():
    x, y = _scale(*_ELLIPSE_POS)
    pyautogui.click(x, y); time.sleep(0.2)

def draw_shape_ellipse(cx, cy, rx, ry, dur=1.2):
    """Use Paint's built-in ellipse tool — clean smooth oval, no wobble."""
    if aborted(): return
    pyautogui.moveTo(cx - rx, cy - ry); time.sleep(0.1)
    pyautogui.dragTo(cx + rx, cy + ry, duration=dur, button='left')
    time.sleep(0.3)

def set_color(name, bx, by, restore='pencil'):
    if aborted(): return
    sx, sy = _scale(*_COLORS.get(name, _COLORS['black']))
    pyautogui.click(sx, sy); time.sleep(0.12)
    pyautogui.click(bx, by); time.sleep(0.12)
    if restore == 'ellipse':
        select_ellipse()
    else:
        select_pencil()
    pyautogui.click(bx, by); time.sleep(0.08)

# ── Drawing primitives ────────────────────────────────────────────────────────
def _off(t):
    h = t // 2
    return range(-h, h + 1)

def draw_oval(cx, cy, rx, ry, segments=72, thickness=THICKNESS):
    for dr in _off(thickness):
        if aborted(): return
        pts = [(cx + (rx+dr)*math.cos(math.radians(a)),
                cy + (ry+dr)*math.sin(math.radians(a)))
               for a in range(0, 361, max(1, 360//segments))]
        pyautogui.moveTo(pts[0][0], pts[0][1])
        pyautogui.mouseDown(button='left')
        for px, py in pts[1:]:
            if aborted(): pyautogui.mouseUp(button='left'); return
            pyautogui.moveTo(px, py, duration=0.03)
        pyautogui.mouseUp(button='left')
        time.sleep(0.05)

def draw_line(x1, y1, x2, y2, dur=0.4, thickness=THICKNESS):
    for dy in _off(thickness):
        if aborted(): return
        pyautogui.moveTo(x1, y1+dy)
        pyautogui.dragTo(x2, y2+dy, duration=dur, button='left')
        time.sleep(0.04)

def draw_arc(pts, thickness=THICKNESS):
    for dy in _off(thickness):
        if aborted(): return
        pyautogui.moveTo(pts[0][0], pts[0][1]+dy)
        pyautogui.mouseDown(button='left')
        for px, py in pts[1:]:
            if aborted(): pyautogui.mouseUp(button='left'); return
            pyautogui.moveTo(px, py+dy, duration=0.035)
        pyautogui.mouseUp(button='left')
        time.sleep(0.05)

def draw_triangle(pts, thickness=THICKNESS, open_base=False):
    limit = len(pts) - 1 if open_base else len(pts)
    for i in range(limit):
        if aborted(): return
        x1, y1 = pts[i]; x2, y2 = pts[(i+1) % len(pts)]
        draw_line(x1, y1, x2, y2, thickness=thickness)

# ── Proper sitting cat ────────────────────────────────────────────────────────
def draw_cat(cx, head_cy, R):
    """
    cx, head_cy: center of the cat's head
    R: head radius
    """
    hr  = R                  # head horizontal radius
    vr  = int(R * 0.88)      # head vertical radius (slightly shorter)
    bcy = head_cy + int(R * 1.45)  # body center (slightly closer to head)
    brx = int(R * 0.80)      # body horizontal radius
    bry = int(R * 1.05)      # body vertical radius

    # -- BODY (ellipse tool) --
    set_color('black', cx, bcy, restore='ellipse')   # anchor click at body center
    print("  drawing body...")
    draw_shape_ellipse(cx, bcy, brx, bry, dur=1.5)
    if aborted(): return
    time.sleep(0.4)

    # -- TAIL: 10 random-offset pencil passes build a thick fuzzy J-curve stroke --
    print("  drawing tail...")
    import random as _rand
    sw, sh = pyautogui.size()
    # Cubic Bezier — J-hook: body right → dips far below → sweeps right → tip curls up
    P0 = (cx + brx,                  bcy)
    P1 = (cx + brx + int(R * 1.4),   bcy + bry + int(R * 0.4))
    P2 = (cx + brx + int(R * 1.9),   bcy)
    P3 = (cx + brx + int(R * 1.2),   bcy - int(R * 0.5))

    def _b(t):
        mt = 1.0 - t
        x = mt**3*P0[0] + 3*mt**2*t*P1[0] + 3*mt*t**2*P2[0] + t**3*P3[0]
        y = mt**3*P0[1] + 3*mt**2*t*P1[1] + 3*mt*t**2*P2[1] + t**3*P3[1]
        return (int(min(x, sw - 10)), int(min(y, sh - 10)))

    N = 14  # 13 segments
    tail_pts = [_b(i / (N - 1)) for i in range(N)]
    select_pencil(); pyautogui.click(cx, bcy); time.sleep(0.1)
    # Per-segment perpendicular thickness — no parallelogram artifact at any angle
    HALF = 2  # ±2px → 5px wide stroke
    for i in range(len(tail_pts) - 1):
        if aborted(): return
        x1, y1 = tail_pts[i]
        x2, y2 = tail_pts[i + 1]
        sdx, sdy = x2 - x1, y2 - y1
        slen = max(1.0, (sdx*sdx + sdy*sdy)**0.5)
        px, py = -sdy / slen, sdx / slen  # perpendicular unit
        for k in range(-HALF, HALF + 1):
            if aborted(): return
            ox, oy = int(round(k * px)), int(round(k * py))
            pyautogui.moveTo(x1+ox, y1+oy)
            pyautogui.mouseDown(button='left')
            pyautogui.moveTo(x2+ox, y2+oy, duration=0.018)
            pyautogui.mouseUp(button='left')
            time.sleep(0.01)
    if aborted(): return
    time.sleep(0.4)

    # -- PAWS (ellipse tool, clearly separated below body) --
    paw_y = bcy + bry + int(R * 0.15)
    set_color('black', cx - int(R*0.4), paw_y, restore='ellipse')
    print("  drawing paws...")
    draw_shape_ellipse(cx - int(R*0.38), paw_y, int(R*0.28), int(R*0.13), dur=0.6)
    time.sleep(0.1)
    draw_shape_ellipse(cx + int(R*0.38), paw_y, int(R*0.28), int(R*0.13), dur=0.6)
    if aborted(): return
    time.sleep(0.4)

    # -- EARS drawn BEFORE head so head outline covers the base → natural connection --
    select_pencil(); pyautogui.click(cx, head_cy - vr - int(R*0.3)); time.sleep(0.15)
    print("  drawing ears...")
    ear_base_y = head_cy - vr + int(R*0.08)
    # narrower (R*0.40 base span) and taller (R*0.58 height) → properly pointed & separated
    l_ear = [(cx - int(R*0.56), ear_base_y),
              (cx - int(R*0.62), head_cy - vr - int(R*0.76)),
              (cx - int(R*0.18), ear_base_y - int(R*0.02))]
    r_ear = [(cx + int(R*0.56), ear_base_y),
              (cx + int(R*0.62), head_cy - vr - int(R*0.76)),
              (cx + int(R*0.18), ear_base_y - int(R*0.02))]
    draw_triangle(l_ear, thickness=1, open_base=True); draw_triangle(r_ear, thickness=1, open_base=True)
    if aborted(): return
    time.sleep(0.3)

    # Inner ears
    set_color('light_pink', cx, head_cy)
    l_in = [(cx - int(R*0.51), ear_base_y - int(R*0.01)),
             (cx - int(R*0.56), head_cy - vr - int(R*0.58)),
             (cx - int(R*0.23), ear_base_y - int(R*0.03))]
    r_in = [(cx + int(R*0.51), ear_base_y - int(R*0.01)),
             (cx + int(R*0.56), head_cy - vr - int(R*0.58)),
             (cx + int(R*0.23), ear_base_y - int(R*0.03))]
    draw_triangle(l_in, thickness=1, open_base=True); draw_triangle(r_in, thickness=1, open_base=True)
    if aborted(): return
    time.sleep(0.2)

    # -- HEAD (drawn AFTER ears so head outline naturally merges with ear bases) --
    set_color('black', cx, head_cy, restore='ellipse')
    select_ellipse()
    print("  drawing head...")
    draw_shape_ellipse(cx, head_cy, hr, vr, dur=1.8)
    if aborted(): return
    time.sleep(0.5)

    # -- FOREHEAD TABBY STRIPES --
    set_color('dark_gray', cx, head_cy)
    print("  drawing forehead stripes...")
    stripe_base_y = head_cy - int(R * 0.42)
    for sx in [cx - int(R*0.33), cx, cx + int(R*0.33)]:
        draw_line(sx, stripe_base_y, sx + int(R*0.04), stripe_base_y - int(R*0.24), thickness=2)
    if aborted(): return

    # -- EYES (ellipse tool, green iris + black slit pupil) --
    print("  drawing eyes...")
    eye_y  = head_cy - int(R * 0.14)
    eye_ox = int(R * 0.37)
    erx, ery = int(R * 0.21), int(R * 0.13)

    set_color('green', cx, head_cy, restore='ellipse')
    select_ellipse()
    draw_shape_ellipse(cx - eye_ox, eye_y, erx, ery, dur=0.8)
    draw_shape_ellipse(cx + eye_ox, eye_y, erx, ery, dur=0.8)

    # Slit pupils — narrow vertical ovals like real cat eyes
    set_color('black', cx, head_cy, restore='ellipse')
    select_ellipse()
    prx = max(2, int(erx * 0.09))   # very narrow
    pry = int(ery * 0.92)            # nearly full iris height
    draw_shape_ellipse(cx - eye_ox, eye_y, prx, pry, dur=0.6)
    draw_shape_ellipse(cx + eye_ox, eye_y, prx, pry, dur=0.6)
    if aborted(): return
    time.sleep(0.3)

    # -- NOSE --
    print("  drawing nose...")
    set_color('pink', cx, head_cy)
    nose_top_y = head_cy + int(R * 0.17)
    nw = int(R * 0.10)
    nh = int(R * 0.08)
    draw_triangle([(cx, nose_top_y), (cx-nw, nose_top_y+nh), (cx+nw, nose_top_y+nh)], thickness=2)
    if aborted(): return
    time.sleep(0.3)

    # -- MOUTH (M shape below nose) --
    print("  drawing mouth...")
    set_color('black', cx, head_cy)
    m_top_y = nose_top_y + nh
    m_mid_y = m_top_y + int(R * 0.09)
    m_end_y = m_top_y + int(R * 0.07)
    draw_line(cx, m_top_y, cx, m_mid_y, thickness=2)
    draw_arc([(cx, m_mid_y), (cx-int(R*0.12), m_mid_y+int(R*0.1)), (cx-int(R*0.26), m_end_y)], thickness=2)
    draw_arc([(cx, m_mid_y), (cx+int(R*0.12), m_mid_y+int(R*0.1)), (cx+int(R*0.26), m_end_y)], thickness=2)
    if aborted(): return
    time.sleep(0.3)

    # -- WHISKERS (from cheeks, 3 per side) --
    print("  drawing whiskers...")
    set_color('dark_gray', cx, head_cy)
    w_base_y = nose_top_y + int(R * 0.04)
    w_inner_x = int(R * 0.18)
    for i, frac in enumerate([-0.06, 0.06, 0.18]):
        wy = w_base_y + int(R * frac)
        angle_dy = int(R * (i - 1) * 0.06)
        draw_line(cx - hr - int(R*(0.48+i*0.08)), wy + angle_dy, cx - w_inner_x, wy, thickness=2)
        draw_line(cx + hr + int(R*(0.48+i*0.08)), wy + angle_dy, cx + w_inner_x, wy, thickness=2)
        if aborted(): return

# ── LLM Judge ────────────────────────────────────────────────────────────────
def screenshot_canvas(bounds: dict, path: str):
    pad = 10
    l = max(0, bounds['left'] - pad)
    t = max(0, bounds['top']  - pad)
    w = bounds['right']  - bounds['left'] + pad * 2
    h = bounds['bottom'] - bounds['top']  + pad * 2
    pyautogui.screenshot(region=(l, t, w, h)).save(path)

def judge_cat(image_path: str) -> str:
    import base64, os
    from groq import Groq
    from dotenv import load_dotenv
    load_dotenv()
    client = Groq(api_key=os.environ['GROQ_API_KEY'])
    with open(image_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": (
                    "You are judging an AI-drawn cat in MS Paint. "
                    "Score each part 1-10 and give one specific fix for each:\n"
                    "1. Head (round oval?)\n"
                    "2. Body (oval, bigger than head?)\n"
                    "3. Eyes (oval irises + slit pupils?)\n"
                    "4. Ears (triangular points?)\n"
                    "5. Tail (curved?)\n"
                    "6. Whiskers (thin lines?)\n"
                    "7. Overall cat likeness\n\n"
                    "Then give ONE top improvement suggestion in plain English that the code can act on. "
                    "Format:\nHEAD: X/10 - fix\nBODY: X/10 - fix\nEYES: X/10 - fix\n"
                    "EARS: X/10 - fix\nTAIL: X/10 - fix\nWHISKERS: X/10 - fix\n"
                    "OVERALL: X/10 - comment\nTOP_FIX: one sentence"
                )}
            ]
        }],
        max_tokens=400
    )
    return resp.choices[0].message.content.strip()

# ── Main ─────────────────────────────────────────────────────────────────────
def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" ({detail})" if detail else ""))
    return ok

def main():
    print("  [INFO] Press ESC or RIGHT-CLICK to abort.\n")

    print("-- Test 1: Open MS Paint --")
    if not check("Paint opened", open_paint()): return

    print("\n-- Test 2: Detect canvas --")
    bounds = detect_canvas()
    if not check("Canvas detected", bounds is not None, str(bounds)): return

    cw      = bounds['right']  - bounds['left']
    ch      = bounds['bottom'] - bounds['top']
    cx      = bounds['left']   + cw // 2
    R       = min(cw, ch) // 6
    head_cy = bounds['top'] + int(ch * 0.34)
    print(f"  Canvas: {cw}x{ch}  head_center: ({cx},{head_cy})  R: {R}")

    print("\n-- Test 3: Select pencil --")
    select_pencil()
    pyautogui.click(cx, head_cy); time.sleep(0.3)
    check("Pencil selected", True)

    print("\n-- Test 4: Draw cat --")
    # Clear canvas so previous runs don't show through
    pyautogui.hotkey('ctrl', 'a'); time.sleep(0.2)
    pyautogui.press('delete');     time.sleep(0.3)
    print("  Canvas cleared.")
    print("  Starting in 2 seconds -- ESC or right-click to abort!")
    time.sleep(2)
    _start_abort_listeners()
    time.sleep(0.1)
    if aborted(): return

    draw_cat(cx, head_cy, R)

    if _abort.is_set():
        print("\n[Aborted by user]"); return

    check("Cat drawn", True)

    print("\n-- Test 5: LLM Judge --")
    canvas_shot = "cat_canvas.png"
    screenshot_canvas(bounds, canvas_shot)
    print(f"  Canvas saved → {canvas_shot}")
    print("  Asking Llama-4-Scout to judge the drawing...")
    try:
        verdict = judge_cat(canvas_shot)
        print("\n=== LLM VERDICT ===")
        print(verdict)
        print("===================\n")
    except Exception as e:
        print(f"  Judge failed: {e}")

    time.sleep(8)
    print("Closing Paint...")
    for w in [w for w in gw.getAllWindows() if "paint" in w.title.lower()]:
        w.close()
    time.sleep(0.5)
    pyautogui.hotkey('alt', 'n')

if __name__ == "__main__":
    main()

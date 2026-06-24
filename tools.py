import re
import requests
import webbrowser
import subprocess
from ddgs import DDGS

# ── Weather (wttr.in — no API key needed) ─────────────────────────────────────

def get_weather(location: str) -> str | None:
    try:
        url = f"https://wttr.in/{requests.utils.quote(location)}?format=j1"
        data = requests.get(url, timeout=6).json()
        cur = data['current_condition'][0]
        today = data['weather'][0]
        hourly = today['hourly']
        desc = cur['weatherDesc'][0]['value']
        temp = cur['temp_C']
        feels = cur['FeelsLikeC']
        hi = today['maxtempC']
        lo = today['mintempC']
        rain_pct = max(int(h['chanceofrain']) for h in hourly)
        umbrella = " Carry an umbrella." if rain_pct >= 40 else ""
        return (f"{temp}°C (feels {feels}°C), {desc}. "
                f"High {hi}°C / Low {lo}°C. Rain chance {rain_pct}%.{umbrella}")
    except Exception as e:
        print(f"Weather API error: {e}")
        return None

# ── Safety guardrails ─────────────────────────────────────────────────────────

# Shell chars that could turn an app name into a command injection
_SHELL_INJECTION = re.compile(r'[&|;<>`$]')

# Path fragments that should never be touched
_DANGEROUS_PATHS = re.compile(
    r'(system32|syswow64|windows\\|\\windows|program files|'
    r'appdata\\roaming|boot|bcd|ntldr|bootmgr)',
    re.IGNORECASE
)

# Destructive shell commands that must never run
_DANGEROUS_CMDS = re.compile(
    r'\b(del|erase|rd|rmdir|format|cipher|bcdedit|diskpart|'
    r'reg\s+delete|net\s+user|shutdown|taskkill\s+/f\s+/im\s+system)\b',
    re.IGNORECASE
)

# System processes that must never be killed
_PROTECTED_PROCESSES = {
    "system", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "svchost.exe", "dwm.exe",
    "explorer.exe", "taskhost.exe", "taskhostw.exe", "audiodg.exe",
}

def _safe_app_name(name: str) -> str | None:
    """Return name if safe, None if it looks like an injection attempt."""
    if _SHELL_INJECTION.search(name):
        print(f"[BLOCKED] Shell injection in app name: {name!r}")
        return None
    if _DANGEROUS_PATHS.search(name):
        print(f"[BLOCKED] Dangerous path in app name: {name!r}")
        return None
    if _DANGEROUS_CMDS.search(name):
        print(f"[BLOCKED] Dangerous command in app name: {name!r}")
        return None
    return name

# News search gets actual headlines (scores, match results).
# Weather/forecast queries must use text search — weather sites have structured
# data in their page descriptions; news returns sports headlines instead.
_NEWS_TRIGGERS  = {"score", "match", "game", "result", "live", "news", "latest",
                   "winner", "final", "standings", "table", "fixture"}
_TEXT_OVERRIDES = {"weather", "forecast", "temperature", "humidity", "rain",
                   "climate", "wind", "precipitation", "celsius", "fahrenheit"}

# Temporal keywords → DuckDuckGo timelimit value
# 'd' = past day, 'w' = past week, 'm' = past month
_TIMELIMIT_MAP = {
    "yesterday":  "d",
    "last night": "d",
    "this week":  "w",
    "last week":  "w",
    "past week":  "w",
    "recently":   "w",
    "recent":     "w",
    "past":       "w",
    "last month": "m",
    "past month": "m",
    "this month": "m",
}

def _timelimit_for(query: str, is_text_search: bool) -> str | None:
    # Never restrict weather/forecast queries — they're always fresh
    if is_text_search:
        return None
    q = query.lower()
    for phrase, limit in _TIMELIMIT_MAP.items():
        if phrase in q:
            return limit
    return None

_WEATHER_WORDS = {"weather", "forecast", "temperature", "rain", "humidity",
                  "wind", "umbrella", "celsius", "fahrenheit", "hot", "cold", "sunny", "cloudy"}

def search_web(query):
    # Route weather queries to wttr.in — DuckDuckGo can't read JS-rendered weather pages
    words = set(query.lower().split())
    if words & _WEATHER_WORDS:
        # Extract location: remove weather keywords, keep the rest
        loc_words = [w for w in query.split() if w.lower() not in _WEATHER_WORDS
                     and w.lower() not in {"today", "tomorrow", "forecast", "the", "in", "for", "what", "is"}]
        location = " ".join(loc_words).strip() or "Bengaluru"
        print(f"[Weather API] location={location!r}")
        result = get_weather(location)
        if result:
            return result

    try:
        with DDGS() as ddgs:
            is_text = bool(words & _TEXT_OVERRIDES)
            use_news = bool(words & _NEWS_TRIGGERS) and not is_text
            timelimit = _timelimit_for(query, is_text_search=is_text or not use_news)
            if timelimit:
                print(f"[Search] timelimit={timelimit!r} for: {query}")
            if use_news:
                results = list(ddgs.news(query, max_results=4, timelimit=timelimit))
                items = [f"- {r['title']}: {r.get('body', '')[:120]}" for r in results]
            else:
                results = list(ddgs.text(query, max_results=3, timelimit=timelimit))
                items = [f"- {r['title']}: {r.get('body', '')[:120]}" for r in results]
            return "\n".join(items)[:500]
    except Exception as e:
        print(f"Search error: {e}")
        return "Search failed."

def close_tab():
    """Close the active browser tab with Ctrl+W."""
    import pyautogui
    pyautogui.hotkey('ctrl', 'w')

# ── Code execution ────────────────────────────────────────────────────────────

import sys, tempfile, os

_TEMP_CODE_PATH = os.path.join(tempfile.gettempdir(), "tony_code.py")

_CODE_BLACKLIST = re.compile(
    r'\b(os\.system|subprocess|shutil\.rmtree|rmdir|del |format\(|'
    r'__import__|eval|exec|open\s*\(.*["\']w["\'])\b',
    re.IGNORECASE
)

def save_code(code: str) -> str:
    """Write code to temp file, return path."""
    with open(_TEMP_CODE_PATH, "w", encoding="utf-8") as f:
        f.write(code)
    return _TEMP_CODE_PATH

def run_code(path: str = None) -> str:
    """Execute saved code, return stdout/stderr (truncated)."""
    path = path or _TEMP_CODE_PATH
    if not os.path.exists(path):
        return "No code to run yet."
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if _CODE_BLACKLIST.search(src):
        return "Blocked: code contains unsafe operations."
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=10
        )
        out = (result.stdout + result.stderr).strip()
        return out[:400] if out else "Code ran with no output."
    except subprocess.TimeoutExpired:
        return "Code timed out after 10 seconds."
    except Exception as e:
        return f"Error: {e}"

def open_in_vscode(path: str = None):
    """Open the temp code file in VS Code."""
    path = path or _TEMP_CODE_PATH
    subprocess.Popen(["code", path], shell=True)

def open_url(url):
    if not url.startswith(("http://", "https://", "www.")):
        url = "https://www.google.com/search?q=" + url.replace(" ", "+")
    webbrowser.open(url)

_APPS = {
    "word": "winword",
    "microsoft word": "winword",
    "excel": "excel",
    "microsoft excel": "excel",
    "powerpoint": "powerpnt",
    "microsoft powerpoint": "powerpnt",
    "paint": "mspaint",
    "ms paint": "mspaint",
    "notepad": "notepad",
    "calculator": "calc",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "file explorer": "explorer",
    "explorer": "explorer",
    "task manager": "taskmgr",
    "settings": "start ms-settings:",
    "control panel": "control",
    "spotify": "spotify",
    "vs code": "code",
    "vscode": "code",
    "terminal": "cmd",
    "command prompt": "cmd",
}

_PROCESSES = {
    "word": "WINWORD.EXE",
    "microsoft word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "microsoft excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "microsoft powerpoint": "POWERPNT.EXE",
    "paint": "mspaint.exe",
    "ms paint": "mspaint.exe",
    "notepad": "notepad.exe",
    "calculator": "CalculatorApp.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "file explorer": "explorer.exe",
    "spotify": "Spotify.exe",
    "vs code": "Code.exe",
    "vscode": "Code.exe",
    "terminal": "cmd.exe",
    "command prompt": "cmd.exe",
}

def open_app(app_name):
    if not _safe_app_name(app_name):
        return False
    cmd = _APPS.get(app_name.lower().strip(), app_name)
    launch = cmd if cmd.startswith("start") else f'start "" {cmd}'
    try:
        result = subprocess.run(launch, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            print(f"App launch error: {result.stderr.strip() or result.stdout.strip()}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return True
    except Exception as e:
        print(f"App open error: {e}")
        return False

def close_app(app_name):
    process = _PROCESSES.get(app_name.lower().strip(), app_name)
    if process.lower() in _PROTECTED_PROCESSES:
        print(f"[BLOCKED] Refusing to kill protected process: {process}")
        return False
    result = subprocess.run(
        f"taskkill /f /im {process}", shell=True, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Close app error: {result.stderr.strip()}")
    return result.returncode == 0

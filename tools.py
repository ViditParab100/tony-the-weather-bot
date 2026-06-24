import re
import webbrowser
import subprocess
from ddgs import DDGS

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

def search_web(query):
    try:
        with DDGS() as ddgs:
            words = set(query.lower().split())
            use_news = bool(words & _NEWS_TRIGGERS) and not bool(words & _TEXT_OVERRIDES)
            if use_news:
                results = list(ddgs.news(query, max_results=4))
                items = [f"- {r['title']}: {r.get('body', '')[:120]}" for r in results]
            else:
                results = list(ddgs.text(query, max_results=3))
                items = [f"- {r['title']}: {r.get('body', '')[:120]}" for r in results]
            return "\n".join(items)[:500]
    except Exception as e:
        print(f"Search error: {e}")
        return "Search failed."

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

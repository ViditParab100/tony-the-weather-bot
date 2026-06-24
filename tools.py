import webbrowser
import subprocess
from ddgs import DDGS

# For these query types, news headlines contain actual data (scores, match results)
# whereas text search only returns website meta-descriptions
_NEWS_TRIGGERS = {"score", "match", "game", "result", "live", "news", "latest",
                  "today", "winner", "final", "standings", "table", "fixture"}

def search_web(query):
    try:
        with DDGS() as ddgs:
            words = set(query.lower().split())
            if words & _NEWS_TRIGGERS:
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
    cmd = _APPS.get(app_name.lower().strip(), app_name)
    # Use Windows shell 'start' so it resolves apps via registry App Paths
    # (e.g. winword, excel, powerpnt are not in PATH but are in App Paths).
    # Commands that already start with 'start' (ms-settings:) are left as-is.
    launch = cmd if cmd.startswith("start") else f'start "" {cmd}'
    try:
        result = subprocess.run(launch, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            print(f"App launch error: {result.stderr.strip() or result.stdout.strip()}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return True   # app launched and kept running — that's success
    except Exception as e:
        print(f"App open error: {e}")
        return False

def close_app(app_name):
    process = _PROCESSES.get(app_name.lower().strip(), app_name)
    result = subprocess.run(
        f"taskkill /f /im {process}", shell=True, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Close app error: {result.stderr.strip()}")
    return result.returncode == 0

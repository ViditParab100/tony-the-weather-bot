import webbrowser
import subprocess
from ddgs import DDGS

def search_web(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            return "\n".join([f"- {r['title']}: {r.get('body', '')}" for r in results])
    except:
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

# Maps friendly name → Windows process filename for taskkill
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
    try:
        subprocess.Popen(cmd, shell=True)
        return True
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

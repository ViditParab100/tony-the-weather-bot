import webbrowser
from ddgs import DDGS

def search_web(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=2))
            return "\n".join([f"- {r['title']}" for r in results])
    except: return "Search failed."

def open_url(url):
    webbrowser.open(url)
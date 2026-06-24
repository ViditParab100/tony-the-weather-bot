"""
Text-mode Tony — bypasses mic and TTS for fast manual/automated testing.
Run:  python test_tony.py
      python test_tony.py --batch queries.txt
"""
import sys
from brain import get_response, summarize_search
from tools import search_web, open_url, open_app, close_app
from main import clean_for_speech, process_response

def run_query(text):
    print(f"\n[You]: {text}")
    agent_text = process_response(text)
    spoken = clean_for_speech(agent_text)
    print(f"[Tony]: {spoken}")
    return spoken

def batch_test(path):
    with open(path) as f:
        queries = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    passed = failed = 0
    for line in queries:
        # Format: "query | expected_substring"
        if "|" in line:
            query, expected = [p.strip() for p in line.split("|", 1)]
            result = run_query(query)
            ok = expected.lower() in result.lower()
            status = "PASS" if ok else "FAIL"
            if not ok:
                print(f"  >> expected to contain: '{expected}'")
            print(f"  [{status}]")
            if ok: passed += 1
            else: failed += 1
        else:
            run_query(line)
    if passed or failed:
        print(f"\n{passed} passed, {failed} failed")

if __name__ == "__main__":
    if "--batch" in sys.argv:
        idx = sys.argv.index("--batch")
        batch_test(sys.argv[idx + 1])
    else:
        print("Tony text-mode (Ctrl+C to quit)\n")
        while True:
            try:
                q = input("You: ").strip()
                if q:
                    run_query(q)
            except KeyboardInterrupt:
                break

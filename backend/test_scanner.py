"""Test all vision models with 60s timeout."""
import json
import sys
import os
import time
import signal

sys.path.insert(0, os.path.dirname(__file__))
from app.services.ollama_vision import check_ollama_status, extract_invoice

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError()

status = check_ollama_status()
vision_models = status.get("vision_models", [])
print(f"Vision models: {vision_models}\n")

image_path = sys.argv[1] if len(sys.argv) > 1 else "PHOTO.jpg"
with open(image_path, "rb") as f:
    image_bytes = f.read()
print(f"Image: {image_path} ({len(image_bytes)} bytes)\n")

TIMEOUT = 60
results = []

for model in vision_models:
    print(f"{'='*60}")
    print(f"Testing: {model} (max {TIMEOUT}s)")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TIMEOUT)
    
    start = time.time()
    try:
        result = extract_invoice(image_bytes, model)
        elapsed = time.time() - start
        signal.alarm(0)
        
        if result:
            print(f"✅ SUCCESS in {elapsed:.1f}s")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            results.append({"model": model, "time": elapsed, "status": "OK", "data": result})
        else:
            print(f"❌ FAILED after {elapsed:.1f}s — no data")
            results.append({"model": model, "time": elapsed, "status": "FAIL"})
    except TimeoutError:
        signal.alarm(0)
        print(f"⏰ TIMEOUT after {TIMEOUT}s — skipped")
        results.append({"model": model, "time": TIMEOUT, "status": "TIMEOUT"})
    except Exception as e:
        signal.alarm(0)
        elapsed = time.time() - start
        print(f"💥 ERROR after {elapsed:.1f}s: {e}")
        results.append({"model": model, "time": elapsed, "status": "ERROR", "error": str(e)})
    print()

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"{'Model':<25} {'Time':>8} {'Status':<8} {'Vendor':<15} {'Total':>8} {'Date':<12} {'Description'}")
print("-" * 110)
for r in results:
    d = r.get("data", {})
    print(f"{r['model']:<25} {r['time']:>7.1f}s {r['status']:<8} {d.get('vendor','—'):<15} {d.get('total_amount','—'):>8} {d.get('date','—'):<12} {d.get('description','—')[:40]}")

Вот одноразовый скрипт (bash + python), который:

согласно списка responseId из `incident-report-08.01.25.md`
тянет логи docker compose logs app
для каждого responseId ищет ближайшие gemini.request.start и HTTP Request
считает дельту в секундах
Запусти в терминале сервера:

```
cd /opt/photochanger/app
python3 - <<'PY'
import re
import subprocess
from datetime import datetime

response_ids = [
    "3IVfaf_oKtvQz7IPlJbBSQ",
    "4oFfabnJI9bRz7IP98qTkAw",
    "5HhfaZvMA-Osz7IPvI3K0QY",
    "AXRfaanzHZaDz7IPvYXJqQI",
    "AZFfafWoNoLrz7IPwNT0sAs",
    "f4FfaYj7G5Prz7IPzavk0QE",
    "JW1faaLAO5biz7IP5fi64A0",
    "JY9fae6GBaDqz7IPudTm0Qo",
    "LJBfaYW8GIbOz7IPyJnhqAY",
    "mpFfafH8CKHUz7IP6KLN-Qs",
    "nJRfafL-PKDUz7IP4-yksQU",
    "nZNfafeTNuOsz7IPvI3K0QY",
    "OI9fadimI_fQz7IPjq6ngAg",
    "onBfaZKOArnUz7IPw7fbuAU",
    "QZBfabyBG9bRz7IP98qTkAw",
    "rHRfae3KNrrUz7IPx8LPsAo",
    "SGpfaf_vJbrUz7IPx8LPsAo",
    "uGNfaZHlL43jz7IPk4iY-AY",
    "VZBfabrzFYjmz7IPu4TLqA8",
    "WoRfaeapEvjVz7IP2c7I0Qo",
    "Xnhfaa7ZDZbiz7IP5fi64A0",
    "YIhfabDrDMHQz7IP54XFiQg",
]

log_text = subprocess.check_output(
    ["docker", "compose", "logs", "app"],
    text=True,
    errors="ignore",
)

lines = log_text.splitlines()
ts_re = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[.,]\d+)")
def parse_ts(s):
    return datetime.fromisoformat(s.replace(",", "."))

results = {}

for i, line in enumerate(lines):
    if "responseId" not in line:
        continue
    m = re.search(r'"responseId": "([^"]+)"', line)
    if not m:
        continue
    rid = m.group(1)
    if rid not in response_ids:
        continue

    start_ts = None
    end_ts = None
    for j in range(i, max(-1, i-60), -1):
        if start_ts is None and "gemini.request.start" in lines[j]:
            tsm = ts_re.search(lines[j])
            if tsm:
                start_ts = parse_ts(tsm.group(1))
        if end_ts is None and "HTTP Request: POST https://generativelanguage.googleapis.com" in lines[j]:
            tsm = ts_re.search(lines[j])
            if tsm:
                end_ts = parse_ts(tsm.group(1))
        if start_ts and end_ts:
            break
    results[rid] = (start_ts, end_ts)

print("responseId, start_ts, end_ts, provider_latency_seconds")
for rid in response_ids:
    start_ts, end_ts = results.get(rid, (None, None))
    if start_ts and end_ts:
        delta = (end_ts - start_ts).total_seconds()
        print(f"{rid}, {start_ts}, {end_ts}, {delta:.3f}")
    else:
        print(f"{rid}, ?, ?, ?")
PY
```
# -*- coding: utf-8 -*-
"""地区字段嗅探：完整 dump settings?scope=main + sign_up 页面 HTML，正则搜地区线索。

用法：python tools\\geo_field_probe.py
"""
from __future__ import annotations

import json
import re
import sys
import uuid

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://chat.deepseek.com"

PAT = re.compile(r"region|mainland|country|geo|locale|area|timezone", re.I)


def main() -> None:
    s = requests.Session()
    s.trust_env = False
    h = {"user-agent": UA, "accept": "*/*", "accept-language": "en-US,en;q=0.9"}
    s.get(BASE + "/sign_up", headers=h, proxies=PROXY, timeout=30)

    did = str(uuid.uuid4())
    r = s.get(f"{BASE}/api/v0/client/settings?did={did}&scope=main",
              headers=h, proxies=PROXY, timeout=30)
    print("=== settings?scope=main HTTP", r.status_code, "len", len(r.text), "===")
    try:
        j = r.json()
        blob = json.dumps(j, ensure_ascii=False, indent=1)
        # 只打印命中地区关键词的行 + 上下各 2 行
        lines = blob.splitlines()
        hits = [i for i, ln in enumerate(lines) if PAT.search(ln)]
        if hits:
            seen = set()
            for i in hits:
                for k in range(max(0, i - 2), min(len(lines), i + 3)):
                    if k not in seen:
                        seen.add(k)
                        print(f"{k:5d}| {lines[k]}")
        else:
            print("(scope=main 响应无地区关键词；所有顶层键如下)")
        print("\n--- 顶层结构 ---")
        print(json.dumps({k: (list(v.keys()) if isinstance(v, dict) else type(v).__name__)
                          for k, v in j.items()}, ensure_ascii=False, indent=1))
        d = j.get("data", {})
        print("--- data keys ---", list(d.keys()))
        bd = d.get("biz_data", {})
        print("--- biz_data keys ---", list(bd.keys()))
        st = bd.get("settings", {})
        print("--- settings 全部键 ---")
        print(json.dumps(list(st.keys()), ensure_ascii=False, indent=1))
        # 全量落盘备查
        with open("work/settings_main.json", "w", encoding="utf-8") as f:
            f.write(blob)
        print("\n[已写入 work/settings_main.json]")
    except Exception as e:
        print("parse fail:", e, r.text[:800])

    # sign_up HTML 里的地区线索
    r2 = s.get(BASE + "/sign_up", headers=h, proxies=PROXY, timeout=30)
    html = r2.text
    print("\n=== sign_up HTML len", len(html), "===")
    for m in PAT.finditer(html):
        a, b2 = max(0, m.start() - 120), min(len(html), m.end() + 120)
        print("  …", html[a:b2].replace("\n", " "), "…")
    # SSR 注入状态
    for kw in ("__INITIAL", "window.__", "__APP", "mainland", "is_mainland", "region"):
        idx = html.find(kw)
        print(f"  [{kw}] idx={idx}", "" if idx < 0 else html[max(0, idx - 60):idx + 160].replace("\n", " "))


if __name__ == "__main__":
    main()

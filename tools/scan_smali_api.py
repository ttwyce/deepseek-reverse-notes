# -*- coding: utf-8 -*-
"""扫描全量 smali，提取 /api/v0/* 接口路径与对应 HTTP 方法。

改进版：对每个方法内的 (行号, 事件) 序列按行号排序，为每个 path 事件
选取**行号距离最近**的 rg5 事件（而不是方法内第一个），并跳过
clinit（那是白名单常量集合，不是请求构造点）。

用法: python tools\\scan_smali_api.py [smali_root]
输出: work\\api_methods.txt
"""
import os
import re
import sys
from collections import defaultdict

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"F:\dshh\deepseeka\work\smali\dex1"
OUT = r"F:\dshh\deepseeka\work\api_methods.txt"

METHOD_FIELDS = {
    "b": "GET",
    "c": "POST",
    "d": "PUT",
    "e": "PATCH",
    "f": "DELETE",
    "g": "HEAD",
    "h": "OPTIONS",
}

RE_PATH = re.compile(r'const-string(?:/jumbo)?\s+[vp]\d+,\s*"(/api/v0/[^"]*)"')
RE_RG5 = re.compile(r"sget-object\s+[vp]\d+,\s*Lrg5;->([a-h]):Lrg5;")
# 备用：rg5 常量可能经 iget/静态初始化间接触发，兜底抓 "GET"/"POST" 字面量
RE_VERB = re.compile(r'const-string(?:/jumbo)?\s+[vp]\d+,\s*"(GET|POST|PUT|PATCH|DELETE)"')
RE_KI5 = re.compile(r"Lki5;->")
RE_PD3G = re.compile(r"Lpd3;->G\(")


def scan_file(path):
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    cur_method = None
    events = []      # [(line_no, kind, value)]  kind in {path, rg5, verb}
    flags = {"ki5": False, "pd3g": False}

    def flush():
        nonlocal events, flags
        if events:
            paths = [(ln, v) for ln, k, v in events if k == "path"]
            rg5s = [(ln, v) for ln, k, v in events if k == "rg5"]
            verbs = [(ln, v) for ln, k, v in events if k == "verb"]
            for ln, api in paths:
                pick = None
                if rg5s:
                    # 取行号距离最近的 rg5 事件
                    ln2, letter = min(rg5s, key=lambda t: abs(t[0] - ln))
                    pick = METHOD_FIELDS.get(letter, "?" + letter)
                elif verbs:
                    ln2, v = min(verbs, key=lambda t: abs(t[0] - ln))
                    pick = v
                out.append((api, pick, path, cur_method, ln, flags["ki5"], flags["pd3g"]))
        events = []
        flags = {"ki5": False, "pd3g": False}

    for idx, raw in enumerate(lines, 1):
        line = raw.strip()
        if line.startswith(".method"):
            flush()
            cur_method = line[len(".method"):].strip()
            continue
        if line.startswith(".end method"):
            flush()
            cur_method = None
            continue
        if cur_method is None:
            continue
        mp = RE_PATH.search(line)
        if mp:
            events.append((idx, "path", mp.group(1)))
        mr = RE_RG5.search(line)
        if mr:
            events.append((idx, "rg5", mr.group(1)))
        mv = RE_VERB.search(line)
        if mv:
            events.append((idx, "verb", mv.group(1)))
        if RE_KI5.search(line):
            flags["ki5"] = True
        if RE_PD3G.search(line):
            flags["pd3g"] = True
    flush()
    return out


def main():
    results = defaultdict(list)
    files = 0
    for dirpath, _dirnames, filenames in os.walk(ROOT):
        for fn in filenames:
            if not fn.endswith(".smali"):
                continue
            files += 1
            full = os.path.join(dirpath, fn)
            try:
                for rec in scan_file(full):
                    results[rec[0]].append(rec)
            except Exception as exc:  # noqa: BLE001
                print("ERR", full, exc)

    rows = []
    for api in sorted(results):
        recs = results[api]
        # 过滤 clinit（白名单常量集合）
        real = [r for r in recs if r[3] and "<clinit>" not in r[3]]
        pool = real if real else recs
        votes = [r[1] if r[1] else "?" for r in pool]
        best = max(set(votes), key=votes.count)
        # 只保留能连到 Ktor 执行链（ki5）的记录作为依据行
        executed = [r for r in pool if r[5]]
        ref = executed[0] if executed else pool[0]
        loc = "%s:%d" % (os.path.basename(ref[2]).replace(".smali", ""), ref[4])
        sm = (ref[3] or "?").replace(".method", "").strip()
        if len(sm) > 55:
            sm = sm[:52] + "..."
        rows.append((api, best, sm, loc, len(pool), ref[6]))

    lines_out = [
        "# /api/v0/* 接口路径 → HTTP 方法（全量 smali 扫描，取路径行最近的 rg5 引用）",
        "# %d 个 smali 文件，%d 条唯一路径" % (files, len(results)),
        "",
        "| 接口路径 | 方法 | smali 方法 | 位置 | 命中数 | 带 body |",
        "|---|---|---|---|---|---|",
    ]
    for api, best, sm, loc, n, pd3g in rows:
        lines_out.append(
            "| `%s` | %s | `%s` | `%s` | %d | %s |"
            % (api, best, sm, loc, n, "是" if pd3g else "")
        )
    text = "\n".join(lines_out)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(text)
    print("\n写入:", OUT)


if __name__ == "__main__":
    main()

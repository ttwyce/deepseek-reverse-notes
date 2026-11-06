# -*- coding: utf-8 -*-
"""用注册返回的 token 验证登录态（GET /api/v0/users/current）。"""
from __future__ import annotations

import json
import sys

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from deepseek_pow import API, HEADERS
from enc_login_test import base_headers

PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

st = json.load(open(r"F:\dshh\deepseeka\work\reg_state.json", encoding="utf-8"))
res = json.load(open(r"F:\dshh\deepseeka\work\reg_result.json", encoding="utf-8"))
dev = st["device_id"]
token = res["data"]["biz_data"]["user"]["token"]

s = requests.Session()
s.trust_env = False
s.proxies = PROXY

h = dict(HEADERS)
h.update(base_headers(dev))
h["Authorization"] = "Bearer " + token

r = s.get(API + "/api/v0/users/current", headers=h, timeout=30)
print("[users/current] HTTP", r.status_code)
print(r.text[:800])

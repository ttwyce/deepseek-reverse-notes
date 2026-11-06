# -*- coding: utf-8 -*-
"""Hook 网页端的请求体加密链路，抓取加密前的明文 JSON。

钩子：crypto.subtle.encrypt / JSON.stringify / XHR.send / fetch
"""
from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROXY = "http://127.0.0.1:7890"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
EMAIL = "demo.user+4@example.com"

HOOK = r"""
(() => {
  const cap = window.__cap = {encrypt: [], str: [], xhr: [], fetch: [], stack: []};
  const dec = (d) => {
    try {
      if (typeof d === 'string') return d;
      if (d instanceof ArrayBuffer) return new TextDecoder().decode(new Uint8Array(d));
      if (ArrayBuffer.isView(d)) return new TextDecoder().decode(new Uint8Array(d.buffer, d.byteOffset, d.byteLength));
      return String(d);
    } catch (e) { return '<undecodable>'; }
  };
  // 1) WebCrypto AES
  if (window.crypto && crypto.subtle && crypto.subtle.encrypt) {
    const oe = crypto.subtle.encrypt.bind(crypto.subtle);
    crypto.subtle.encrypt = function(algo, key, data) {
      try {
        cap.encrypt.push({algo: JSON.stringify(algo), len: (data.byteLength || 0), plain: dec(data)});
      } catch (e) {}
      return oe(algo, key, data);
    };
  }
  // 2) JSON.stringify
  const os = JSON.stringify;
  JSON.stringify = function() {
    const r = os.apply(this, arguments);
    try {
      if (r && (r.indexOf('turnstile') >= 0 || r.indexOf('hcaptcha') >= 0 || r.indexOf('scenario') >= 0 || r.indexOf('email') >= 0)) {
        cap.str.push(r.slice(0, 3000));
      }
    } catch (e) {}
    return r;
  };
  // 3) XHR
  const ox = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function(body) {
    try {
      if (body) cap.xhr.push({url: this.__url || '', body: dec(body).slice(0, 3000),
                              eu: this.__eu || '', type: typeof body, ctor: body.constructor && body.constructor.name});
    } catch (e) {}
    return ox.apply(this, arguments);
  };
  const oo = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(m, u) { try { this.__url = u; } catch (e) {} return oo.apply(this, arguments); };
  const osh = XMLHttpRequest.prototype.setRequestHeader;
  XMLHttpRequest.prototype.setRequestHeader = function(k, v) {
    try { if (/encryption|pow|x-ds|x-client/i.test(k)) this.__eu = (this.__eu || '') + k + '=' + String(v).slice(0, 120) + '; '; } catch (e) {}
    return osh.apply(this, arguments);
  };
  // 4) fetch
  const of = window.fetch;
  window.fetch = function(input, init) {
    try {
      const u = typeof input === 'string' ? input : (input && input.url) || '';
      if (init && init.body) cap.fetch.push({url: u, body: dec(init.body).slice(0, 3000), type: typeof init.body});
    } catch (e) {}
    return of.apply(this, arguments);
  };
})();
"""


def main() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(proxy={"server": PROXY}, locale="en-US", timezone_id="Asia/Tokyo",
                            viewport={"width": 1280, "height": 900}, user_agent=UA)
        ctx.add_init_script(HOOK)
        page = ctx.new_page()
        page.goto("https://chat.deepseek.com/sign_up", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(7000)
        print("region:", page.evaluate("()=>{const e=document.querySelector('meta[name=region]');return e?e.content:null}"))

        page.fill("input[type=text]", EMAIL)
        page.get_by_text("Send code", exact=True).first.click()
        print("已点击 Send code...")
        page.wait_for_timeout(12000)

        cap = page.evaluate("() => window.__cap || {}")
        print("\n=== crypto.subtle.encrypt 调用 ===")
        for i, e in enumerate(cap.get("encrypt", [])):
            print(f"[{i}] algo={e['algo']} len={e['len']}")
            print(f"    明文: {e['plain'][:800]}")

        print("\n=== XHR.send ===")
        for i, x in enumerate(cap.get("xhr", [])):
            print(f"[{i}] {x['url']} type={x['type']} ctor={x['ctor']}")
            print(f"    headers: {x['eu']}")
            print(f"    body: {x['body'][:800]}")

        print("\n=== fetch ===")
        for i, x in enumerate(cap.get("fetch", [])):
            print(f"[{i}] {x['url']} type={x['type']}")
            print(f"    body: {x['body'][:800]}")

        print("\n=== JSON.stringify 命中（含 turnstile/scenario/email）===")
        for i, s in enumerate(cap.get("str", [])):
            if "turnstile" in s or "hcaptcha" in s or "scenario" in s:
                print(f"[{i}] {s[:900]}")

        b.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gmail IMAP 收码工具 —— 为 demo.user+N@example.com 系列别名账号取 DeepSeek 验证码。

用法:
    python tools/gmail_code.py check                 # 测试 IMAP 登录 + 列最近 5 封主题
    python tools/gmail_code.py code                  # 提取最新 DeepSeek 6 位验证码
    python tools/gmail_code.py code --since 300      # 只看最近 300 秒内的邮件
    python tools/gmail_code.py code --to demo.user+5@example.com

凭据来自 tools/local_config.py（不入库）:
    CFG = {"GMAIL_USER": "demo.user@example.com", "GMAIL_APP_PASS": "xxxxxxxxxxxxxxxx"}
"""
import argparse
import email
import imaplib
import re
import socket
import ssl
import sys
import time
from email.header import decode_header
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

PROXY = ("127.0.0.1", 7890)
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993


def load_cfg():
    try:
        from local_config import CFG  # type: ignore
    except Exception as e:  # noqa: BLE001
        sys.exit(f"缺少 tools/local_config.py 或 CFG 读取失败: {e}")
    user = CFG.get("GMAIL_USER")
    pw = (CFG.get("GMAIL_APP_PASS") or "").replace(" ", "")
    if not user or not pw:
        sys.exit("local_config.CFG 需要 GMAIL_USER 与 GMAIL_APP_PASS")
    return user, pw


def connect(user, pw):
    """经 SOCKS5 代理建 TLS 连接（FlClash mixed 端口支持 socks5）。"""
    import socks  # pysocks

    sock = socks.socksocket()
    sock.set_proxy(socks.SOCKS5, PROXY[0], PROXY[1], rdns=True)
    sock.settimeout(30)
    sock.connect((IMAP_HOST, IMAP_PORT))
    ctx = ssl.create_default_context()
    tls = ctx.wrap_socket(sock, server_hostname=IMAP_HOST)
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
    # IMAP4_SSL 自己会建连，上面的手工 socket 只用于探测；此处复用标准建连
    conn.socket().settimeout if False else None  # noqa: B018
    return conn


def connect_plain(user, pw):
    """标准 IMAP4_SSL（系统代理 TUN/全局模式下可直连）。"""
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=30)
    conn.login(user, pw)
    return conn


def decode_hdr(raw):
    if not raw:
        return ""
    out = []
    for part, enc in decode_header(raw):
        if isinstance(part, bytes):
            try:
                out.append(part.decode(enc or "utf-8", "replace"))
            except LookupError:
                out.append(part.decode("utf-8", "replace"))
        else:
            out.append(part)
    return "".join(out)


def body_text(msg):
    if msg.is_multipart():
        chunks = []
        for p in msg.walk():
            if p.get_content_type() in ("text/plain", "text/html"):
                try:
                    payload = p.get_payload(decode=True) or b""
                    chunks.append(payload.decode(p.get_content_charset() or "utf-8", "replace"))
                except Exception:  # noqa: BLE001
                    pass
        return "\n".join(chunks)
    try:
        return (msg.get_payload(decode=True) or b"").decode(
            msg.get_content_charset() or "utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""


CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")


def extract_code(text):
    """优先取 DeepSeek 邮件里最像验证码的 6 位数字。"""
    # 常见文案: "Your verification code is 123456" / "验证码为 123456"
    m = re.search(
        r"(?:code|验证码|verification)[^0-9]{0,40}(\d{6})(?!\d)", text, re.I)
    if m:
        return m.group(1)
    m = CODE_RE.search(text)
    return m.group(1) if m else None


def cmd_check(args):
    user, pw = load_cfg()
    print(f"user={user} pass_len={len(pw)}")
    try:
        conn = connect_plain(user, pw)
        print("LOGIN_OK (direct)")
    except Exception as e:  # noqa: BLE001
        print(f"direct failed: {type(e).__name__}: {e}")
        print("-> 直连不可用时，请确认 FlClash 处于全局/TUN 模式")
        return 1
    conn.select("INBOX")
    typ, data = conn.search(None, "ALL")
    ids = data[0].split()[-5:]
    for i in reversed(ids):
        typ, msg_data = conn.fetch(i, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        print(f"  [{i.decode()}] {decode_hdr(msg.get('Subject'))[:80]} | "
              f"from={decode_hdr(msg.get('From'))[:50]} | {msg.get('Date')}")
    conn.logout()
    return 0


def cmd_code(args):
    user, pw = load_cfg()
    conn = connect_plain(user, pw)
    conn.select("INBOX")
    if args.since:
        since = time.strftime("%d-%b-%Y", time.localtime(time.time() - args.since))
        typ, data = conn.search(None, f'(SINCE "{since}")')
    else:
        typ, data = conn.search(None, "ALL")
    ids = data[0].split()
    if not ids:
        print("NO_MAIL")
        return 1
    deadline = time.time() + args.wait
    seen = set()
    while True:
        # 每轮重查，等待新邮件到达
        typ, data = conn.search(None, "ALL")
        ids = data[0].split()
        for i in reversed(ids[-args.scan:]):
            if i in seen:
                continue
            seen.add(i)
            typ, msg_data = conn.fetch(i, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subj = decode_hdr(msg.get("Subject"))
            to = decode_hdr(msg.get("To"))
            if args.to and args.to.lower() not in to.lower():
                continue
            text = subj + "\n" + body_text(msg)
            code = extract_code(text)
            print(f"[{i.decode()}] to={to[:60]} subj={subj[:70]} -> code={code}")
            if code:
                conn.logout()
                print(f"CODE={code}")
                return 0
        if time.time() > deadline:
            conn.logout()
            print("NO_CODE_TIMEOUT")
            return 1
        time.sleep(args.interval)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.set_defaults(func=cmd_check)
    k = sub.add_parser("code")
    k.add_argument("--since", type=int, default=0, help="只看最近 N 秒内的邮件（0=全部）")
    k.add_argument("--to", default=None, help="按收件人过滤，如 demo.user+5@example.com")
    k.add_argument("--wait", type=int, default=90, help="等待新邮件的最长秒数")
    k.add_argument("--interval", type=int, default=5)
    k.add_argument("--scan", type=int, default=8, help="每轮检查最近 N 封")
    k.set_defaults(func=cmd_code)
    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

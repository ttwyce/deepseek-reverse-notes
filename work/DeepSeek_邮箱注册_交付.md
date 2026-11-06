# DeepSeek 邮箱注册 · 纯协议打通交付（2026-10-27）

> **编码说明**：本文档在早期提交中因 GBK/UTF-8 编码错误受损，已按字节层面尽最大可能还原，个别处按保留的命令/接口信息重建；文中 `…` 表示原字符已不可恢复。
> 账号、设备标识、密码等敏感值已脱敏为示例值。

## 结论

**邮箱注册全链路已纯协议打通**，无需浏览器、无需 Turnstile、无需人工过人机验证。

- 注册账号：`demo.user+4@example.com`
- user id：`00000000-0000-4000-8000-000000000001`
- token：`<已脱敏，见本地 work/reg_result.json>`
- 有效性：`GET /api/v0/users/current` 返回 `biz_code=0` 与完整用户信息，`is_mainland=false`
- 产物文件：`work\reg_state.json`（设备号）· `work\reg_result.json`（注册响应）

## 唯一硬前提：非大陆 IP

服务端按**真实连接 IP** 渲染 HTML 的 `meta` 并把结果写进 token 校验链：

```html
<meta name="ip" content="13.230.77.79"><meta name="region" content="JP">
```

前端据此判定 `is_mainland`，进而决定走数美还是 hCaptcha。**大陆 IP 请求 `register` 一律丢 `biz_code=6 REGISTER_FROM_MAINLAND`**，与 `region` / `locale` / 时区 / UA 头全都无关——这些字段一个都不影响判定。

本机走 `127.0.0.1:7890`（FlClash，全局模式）出口为日本东京 AWS（`13.230.77.79`），注册页文案从 `Only phone number registration is supported in your region.` 变为 `Only email registration is supported in your region.`，登记流程随即放行。

> 注意：默认 Clash 规则模式下 `deepseek.com` 命中 `geosite:cn` 走 DIRECT，必须切全局或改写规则，否则代理形同虚设。境外 IP 首访会先过 AWS WAF（`Server: CloudFront`、HTTP 202、`Human Verification` 页），浏览器会自动过 challenge；纯协议侧直接请求 API 不受此影响。

## 全流程（5 步）

```powershell
cd <项目根>

# 1+2+3. 换数美设备号 → 自动解点选拿 rid → 发验证码
.\.venv\Scripts\python.exe tools\reg_flow.py send

# 4. 从邮箱抄 6 位码
# 5. 提交注册
.\.venv\Scripts\python.exe tools\reg_flow.py verify 478725
```

`send` 会把 device_id / smid / rid / 发送时间写入 `work\reg_state.json`，`verify` 读取同一 device_id 复用——**两步必须用同一个 device_id**。

### 步骤细节

| 步骤 | 接口 | 关键点 |
|---|---|---|
| 设备号 | `POST https://fp-it-acc.portal101.cn/deviceprofile/v4` | 数美 deviceprofile，判定 `code==1100`，取 `detail.deviceId` 长度 88；最终 device_id = `"B" + deviceId`，共 89 字符 |
| 人机 | 数美点选 | `tools\shumei_solver.solve(batch=4, rounds=3)`，实测一次通过、耗时 2.7~3.1 秒，产出 `rid` |
| 发码 | `POST /api/v0/users/create_email_verification_code` | 明文 JSON 即可；body 见下 |
| 收码 | 人工 / IMAP | Gmail IMAP 需应用专用密码，见文末「IMAP 取码要点」 |
| 注册 | `POST /api/v0/users/register` | 明文 JSON 即可；需 PoW 头；body 见下 |

### 发码请求

```python
payload = {
    "email": "demo.user+4@example.com",
    "locale": "en_US",
    "device_id": dev,                                  # 89 字符，必填
    "scenario": "register",                            # 必填，缺则 422
    "shumei_verification": {"region": "CN", "rid": rid},
    "shumei_device_id": smid,                          # 88 字符
    "hcaptcha_token": "",
    "turnstile_token": "",
}
# 成功: {"code":0,"data":{"biz_code":0,"biz_data":{"send_window_secs":60}}}
```

### 注册请求

```python
outer = {
    "payload": {
        "email": "demo.user+4@example.com",
        "email_verification_code": "478725",
        "password": "<密码>",
    },
    "region": "JP", "locale": "en_US", "os": "android", "device_id": dev,
}
# 需带 X-DS-Guest-Pow-Response（target_path = /api/v0/users/register）
# 成功: data.biz_code=0, data.biz_data.user.{id,token,email,...}
```

## 错误码对照（实测）

| biz_code | biz_msg | 含义与处置 |
|---|---|---|
| 0 | — | 成功 |
| 1 | `EMAIL_REQUEST_TOO_FREQUENT` | 60 秒发码限流，`send_window_secs` 给出窗口 |
| 2 | `RECAPTCHA_VERIFY_FAILED` | 缺有效人机凭证。**未带真实数美 rid 时必然出现**；带上 rid 即消除 |
| 6 | `REGISTER_FROM_MAINLAND` | 大陆 IP，换境外 IP |
| 7 | `EMAIL_EXPIRED` | 验证码记录不存在/已过期（多发一封会覆盖前封） |
| 8 | `EMAIL_VERIFY_FAILED` | 码与邮箱不匹配（通常是拿到了被覆盖的旧码） |
| 11 | `RISK_DEVICE_DETECTED` | 设备与账号绑定不符 |

## 踩坑与证伪记录

1. **Turnstile 是死路，且根本不参与发码**
   - 前端 `turnstileEnabled: !isMainlandChina` 只调用 setup，从不调用 render；全站无 `pz`（取 token）调用点。
   - 抓到的真实发码明文里 `turnstile_token` 就是空串 `""`，也没有 `hcaptcha_token` / `shumei_verification` 字段——**DeepSeek 官方页面自己发的请求也会被 `biz_code=2` 拒绝**。
   - 手动 `turnstile.render('#my-ts',{sitekey:'0x4AAAAAAA1jQEh8YFk064tz'})` 能返回 widget id，但在数据中心 IP 下 Cloudflare 静默不插 iframe（`/pat/` 返回 401），token 恒空；有头 Chrome 同样失败。
2. **`check_email_code` 不能用来验证注册码**：它对有效注册码也返回 `EMAIL_EXPIRED(7)`，语义只适用于忘记密码场景，误判会误导排查。此外它不在 PoW 白名单（`create_guest_challenge` 返回 `INVALID_TARGET_PATH`）。
3. **`biz_code=2` 与 body 里三个 token 字段无关**：矩阵实验（仅 device_id / 仅 turnstile / 仅 hcaptcha / 假数美 / 三个全带）全部同码；真正的凭证是**有效数美 rid**。
4. **不带 `device_id` 直接 422**（`{"detail":[{"loc":"body.device_id"}]}`），早期不带该字段的测试结论全部作废。
5. **PoW 一次性**：同一个 `X-DS-Guest-Pow-Response` 复用第二个请求会得到 `40301 Invalid PoW Response`，每个请求都要重新 `create_guest_challenge` + 求解。
6. **验证码互相覆盖**：同一邮箱 60 秒后重发会作废前一封，务必只保留最后一封。

## 相关工具

| 文件 | 作用 |
|---|---|
| `tools\reg_flow.py` | 主流程（`send` / `verify` / `show`） |
| `tools\check_code.py` | `check_email_code` 诊断（注意上面的语义陷阱） |
| `tools\verify_token.py` | 用 token 调 `users/current` 验证登录态 |
| `tools\shumei_solver.py` | 数美点选自动求 rid |
| `tools\sm_fp_client.py` | 数美 deviceprofile 纯协议换设备号 |
| `tools\deepseek_pow.py` | DeepSeekHashV1 PoW 求解 |

---

## 全自动注册流水线（2026-10-27 追加）

`tools/reg_auto.py` 把 5 步串成一条命令，验证码由 Gmail IMAP 自动取回。

```powershell
cd <项目根>
.\.venv\Scripts\python.exe tools\reg_auto.py --email demo.user+5@example.com --password YOUR_PASSWORD
```

四个阶段的实测耗时（2026-10-27 09:0x，日本 IP）：

| 阶段 | 动作 | 主接口 | 实测 |
|---|---|---|---|
| 1 | 换设备号 → 点选 → 发码 | `fp-it-acc.portal101.cn/deviceprofile/v4`、`shumei solver`、`POST /api/v0/users/create_email_verification_code` | ~3 s，`biz_code=0`，`send_window_secs=60` |
| 2 | IMAP 取 6 位码 | `imap.gmail.com:993` SSL | 5~30 s |
| 3 | 提交注册 | `POST /api/v0/users/register` + PoW | <1 s，`data.biz_code=0` |
| 4 | 校验登录态 | `GET /api/v0/users/current` | `biz_code=0`，`is_mainland=false` |

批量注册结果（2026-10-27）：

| 邮箱 | user id | 状态 |
|---|---|---|
| `demo.user+4@example.com` | `00000000-0000-4000-8000-000000000001` | 有效 |
| `demo.user+5@example.com` | `00000000-0000-4000-8000-000000000002` | 有效 |
| `demo.user+6@example.com` | `00000000-0000-4000-8000-000000000003` | 有效 |

token / device_id 全部落在 `work/reg_results.json`（已 gitignore，不入库）。

### IMAP 取码要点

- Gmail 主账号 `demo.user@example.com` 开启两步验证后生成 16 位应用专用密码，写入 `tools/local_config.py` 的 `GMAIL_APP_PASS`（去空格）。
- 走 FlClash 全局 / TUN 模式时 `imap.gmail.com:993` 可直连，实测 `LOGIN_OK`；socks 代理下需注意超时设置。
- **关键**：`imaplib` 的 SELECT 复用会话，每次取值前需 `conn.noop()` 触发 EXISTS，否则 `search` 结果一直为空（表现为收不到邮件而超时）。
- DeepSeek 验证码邮件主题为 `Your verification code for DeepSeek`，正文含 6 位数字；按 `To` 头精确匹配 `demo.user+N@example.com` 即可支持同一主账号下的无限别名。

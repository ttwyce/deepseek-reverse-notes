# -*- coding: utf-8 -*-
"""更新逆向报告：修正 PoW 表述、追加网页端协议与错误码全表。"""
import io
import re

P = r"F:\dshh\deepseeka\work\DeepSeek_2.7.1_逆向报告.md"
src = io.open(P, encoding="utf-8").read()

# 1) 修正 §6 中残留的 SHA3-256 表述
old = "PoW 的哈希算法（SHA3-256/rate136/域0x06）与求解结构"
new = "PoW 的哈希算法（**改造版 Keccak：rate136/域0x06/只跑 23 轮且跳过 RC[0]**，非标准 SHA3-256）与求解结构"
if old in src:
    src = src.replace(old, new)

# 2) 追加网页端协议章节
extra = u"""

---

## 7. 网页端（Web）协议对照

网页端是纯协议复刻的最佳参照：它不发 `x-hif-*`，但会发一组**设备头**，且同一套 `/api/v0/*` 后端。

### 7.1 静态资源与版本

| 项 | 值 |
|---|---|
| 主 JS | `https://fe-static.deepseek.com/chat/static/main.<hash>.js`（本次 1,609,382 B） |
| vendor JS | `default-vendors.<hash>.js`（1,033,287 B） |
| 埋点 SDK | `lf3-data.volccdn.com/obj/data-static/log-sdk/collect/5.0/collect-rangers-v5.2.11.js`（火山） |
| 构建配置 | `{appVersion:"2.7.0", commitId:"26090614", channel:"queue", clientPlatform:"web"}` |

### 7.2 通用请求头（模块 6594 + 配置）

```js
a = ({brand, platform, version, locale, timezoneOffsetSeconds}) => ({
  "x-client-bundle-id": HP(brand),      // HP: brand==="dseek" ? "com.deepseek.chat.nov" : "com.deepseek.chat"
  "x-client-platform": platform,        // "web"
  "x-client-version": version,          // "2.7.0"
  "x-client-locale": locale,
  "x-client-timezone-offset": timezoneOffsetSeconds });   // 60 * dayjs().utcOffset()，东八区 28800
```

### 7.3 设备头（模块 55652）

```js
// deviceId 必须是 UUID v4，持久化在 localStorage，键前缀 "deepseek-device-id:"
r = e => /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(e);
s = e => ({"x-device-id": e.deviceId, "x-device-model": e.deviceModel});   // deviceModel 恒为 ""
```

- 这两个头由 `onBeforeRequest` 钩子注入**每一个 `/api/` 开头的同源请求**：`e.headers = {...e.headers, ...s(snapshot)}`。
- 设备快照：`{info:{deviceId, deviceModel:""}, persistence:"persistent"}`。

### 7.4 登录请求体（`ed("/login", ...)`）

```js
// 邮箱分支
{ email, mobile:"", area_code:"", password, device_id, os, ...(mfaDevice && {credential_id}) }
// 手机分支
{ email:"", mobile:ea(mobile), area_code:ea(areaCode), password, device_id, os, ... }
```

**实测校正（服务端与网页 JS 版本不一致）**：当前服务端 `os:"web"` 分支是 `extra=forbid` 的固定 schema，合法字段集 = `{email, password, device_id, os, credential_id}`；
- 多传 `mobile` / `area_code` → `422 {"detail":[{"loc":"body"}]}`；
- 缺 `credential_id` → 同样 `422 body`；
- `credential_id:""` + `x-device-id`/`x-device-model` 全套头 → **schema 通过**（返回业务码）。

### 7.5 错误码全表（网页端枚举，服务端通用）

`LOGIN_ERROR_CODE`：`OK=0`、`PASSWORD_OR_USER_NAME_IS_WRONG=2`、`USER_IS_BANNED=10`、**`RISK_DEVICE_DETECTED=11`**、`MOBILE_RESTRICTED=12`、`SIGNATURE_REQUIRED=13`、`OTP_REQUIRED=14`。

| 枚举 | 取值 |
|---|---|
| `GET_TOKEN_ERROR_CODE` | OK=0, USER_IS_BANNED=10 |
| `LOGIN_BY_MOBILE_SMS_ERROR_CODE` | OK=0, LOGIN_TO_EXISTING_ACCOUNT=1, ACCOUNT_BANNED=3, ONLY_SUPPORT_REGISTER_FROM_MAINLAND=6, SMS_EXPIRED=7, SMS_VERIFY_FAILED=8, MOBILE_VERIFY_TOO_MANY_ATTEMPTS=9, RISK_DEVICE_DETECTED=11, TEMP_DISABLED_IN_THIS_CHANNEL=98 |
| `REGISTER_ERROR_CODE` | OK=0, EMAIL_EXISTS=1, INVALID_PASSWORD=4, EMAIL_VERIFY_TOO_MANY_ATTEMPTS=5, REGISTER_FROM_MAINLAND=6, EMAIL_EXPIRED=7, EMAIL_VERIFY_FAILED=8, ACCOUNT_BANNED=10 |
| `EMAIL_RESET_PASSWORD_ERROR_CODE` | OK=0, EMAIL_NOT_EXIST=2, INVALID_PASSWORD=4, EMAIL_EXPIRED=7, EMAIL_VERIFY_FAILED=8, ACCOUNT_BANNED=10 |
| `CREATE_SMS_VERIFICATION_CODE_ERROR_CODE` | SMS_SEND_TOO_FREQUENT=1, RECAPTCHA_VERIFY_FAILED=2, NO_MOBILE_NUMBER=3, INVALID_TICKET=4, REBIND_TO_SAME_NUMBER=5, INVALID_MOBILE_NUMBER=6, TEMP_DISABLED=98, CLOUD_ERROR=99 |
| `OAUTH_GOOGLE_CALLBACK_ERROR_MESSAGE_CODE` | SWAP_CODE_INVALID=2, ACCOUNT_BANNED=3, EMAIL_ACCOUNT_ALREADY_HAS_OAUTH_ACCOUNT=5, OAUTH_ACCOUNT_ALREADY_BOUND_EMAIL=6, RISK_DEVICE_DETECTED=11, REGISTER_FROM_MAINLAND=12, TEMP_DISABLED=98, UNEXCEPTED_ERROR=99 |
| `OAUTH_APPLE_LOGIN_BIZ_CODE` | OK=0, NEED_BIND_MOBILE=1, TOKEN_VERIFY_FAILED=2, ACCOUNT_BANNED=3, EMAIL_ACCOUNT_ALREADY_HAS_APPLE_ACCOUNT=8, APPLE_ACCOUNT_ALREADY_BOUND_OTHER_EMAIL=9, USER_IS_BANNED=10, RISK_DEVICE_DETECTED=11 |
| 全局 | `INVALID_POW_RESPONSE=40301`、`CHALLENGE_REQUIRED=40303`、`CHALLENGE_FAILED=40304`、`TOO_MANY_REQUESTS=40029`、`Missing Token=40002`、`REQUEST_DECRYPT_FAILED=40006` |

**`RISK_DEVICE_DETECTED=11` 是终态拒绝**：网页端 `case LOGIN_ERROR_CODE.RISK_DEVICE_DETECTED: b("deviceRisk")` 只弹 `exectionEnvironmentExecptionToast`（"检测到异常环境"）并上报埋点，**没有任何验证码/申诉/重试分支**；手机验证码登录、注册、Google/Apple 登录、换绑手机号遇 11 时同样只弹该 toast。

### 7.6 人机验证与 GuestPow 分流（网页端）

- `captchaEnabled = isMainlandChina ? "shumei" : (hasHcaptcha && "hcaptcha")`；开关 `getFrozenFeature("chat_hcaptcha", false)`。
- 数美产物：`shumei_verification:{rid, region}` + `shumei_device_id`（客户端 IP）；hCaptcha 产物：`hcaptcha_token`。
- GuestPow 白名单（网页端 `eA`，注意前缀混用）：`/v0/users/register`、`/v0/users/register_by_mobile`、`/v0/users/login_by_mobile_sms`、`/api/v0/users/create_sms_verification_code`、`/api/v0/users/create_email_verification_code`。
- 挑战接口 `getChallengeUrl: "/api/v0/users/create_guest_challenge"`，body `{target_path}`，取 `data.biz_data.guest_challenge`；Pow 响应 `btoa(JSON.stringify(...))`。
- `create_email_verification_code` 的 `scenario` ∈ `register` / `bind_email` / `reset_password`（服务端实测仅 `register` 与 `reset_password` 被接受）。

### 7.7 纯协议登录实测记录（<your-email>）

| 结论 | 证据 |
|---|---|
| 请求体加密正确 | `os=android` + RSA-OAEP(SHA-256)/AES-128-CBC + `x-request-encryption-key` → 服务端解密成功（422 报缺字段而非 40006） |
| 服务端不强制加密 | 明文 JSON 同样返回业务码 |
| 凭据正确 | 错密码 → `biz_code 2 PASSWORD_OR_USER_NAME_IS_WRONG`；正确密码 → `biz_code 11` |
| 登录前无 PoW 通道 | `create_pow_challenge` 需 token（40002）；`create_guest_challenge` 对 login 返回 `INVALID_TARGET_PATH` |
| 11 与 UA/TLS/IP/头/device_id 形态无关 | 浏览器 UA、curl_cffi `impersonate=chrome`、直连/代理、`x-hif-*`、`x-device-id`(UUIDv4)、32hex/UUID device_id 全部仍 11 |
| 账号维度限流 | 高频尝试后 `40029 TOO_MANY_REQUESTS`，冷却需数十分钟 |
"""
if "## 7. 网页端（Web）协议对照" not in src:
    src = src.rstrip() + extra

io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("lines:", src.count("\n") + 1)
print("has_sec7:", "## 7. 网页端（Web）协议对照" in src)
print("pow_fixed:", "改造版 Keccak" in src)

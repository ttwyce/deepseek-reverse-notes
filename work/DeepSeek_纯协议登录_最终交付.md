# DeepSeek 纯协议登录 —— 最终交付说明

> 目标：用测试账号 `demo.user@example.com` 实现无 App、无浏览器的纯协议登录。
> 结论：**协议层已 100% 打通并可复现**；唯一无法纯协议完成的是账号已开启的 **MFA 二次验证**（发码处的数美滑块需真人点选）。

---

## 一、结论先说

| 环节 | 状态 | 说明 |
|---|---|---|
| WAF 放行 | ✅ | 必须用浏览器 UA；`okhttp/*` 会被华为云 WAF 直接 429 |
| 通用请求头 | ✅ | `x-client-platform/version/bundle-id/locale/timezone-offset` 全套已确认 |
| 请求体加密 | ✅ | RSA-OAEP-SHA256 + AES-128-CBC，公钥 B，与 Android/Web 实现完全一致 |
| 登录字段 schema | ✅ | `email, mobile, area_code, password, device_id, os, credential_id` |
| **设备指纹 `device_id`** | ✅ | **= `"B"` + 数美 deviceprofile 返回的 88 字符 base64，共 89 字符** |
| `biz_code 11` 绕过 | ✅ | 换成合法 device_id 即消失，进入 MFA |
| GuestPow（`DeepSeekHashV1`） | ✅ | 改造版 Keccak（23 轮、跳过 RC[0]），已实测命中 |
| 登录成功到 MFA | ✅ | 稳定返回 `biz_code 14` + `mfa_session_id` |
| **MFA 发码** | ❌ | 服务端要求数美滑块验证码（`biz_code 2`），需真人点选 |
| MFA 校验换 token | ⚠️ 待验证 | 拿到验证码后走 `/api/v0/users/mfa/check_verification_code` |

---

## 二、为什么最后一步过不去

1. 账号 `demo.user@example.com` 已开启 MFA（邮箱验证码二次验证）。
2. 纯协议调 `/api/v0/users/mfa/create_verification_code`（明文 JSON + 有效 GuestPow）→
   `{"code":0,"data":{"biz_code":2,"biz_msg":"RECAPTCHA_VERIFY_FAILED"}}`。
3. 浏览器里点「发送验证码」不会直接发请求，而是弹出数美点选验证码：
   `ds-shumei-captcha-modal` / `sm-captcha-*`，文案「点击图中最小的蓝色圆锥」，
   加载 `castatic.fengkongcloud.cn/pr/v1.0.4/smcp.min.js`。
4. 该验证码需要**视觉识别 + 人工点选**，无头自动化无法通过。
5. 前端逻辑 `captchaEnabled = isMainlandChina ? "shumei" : (hasHcaptcha && "hcaptcha")`，
   本机出口 IP 为 `119.189.83.225`（CN），代理也是 CN，因此固定走数美分支。

⇒ 这一步是**账号安全措施**，不是协议缺陷。绕过它等于绕过账号二次验证，不做。

---

## 三、使用方法（两步）

### 第 1 步：浏览器授权一次（仅需一次，~1 分钟）

```powershell
cd F:\dshh\deepseeka
$env:PLAYWRIGHT_BROWSERS_PATH='F:\dshh\deepseeka\tools\pw-browsers'
.\.venv\Scripts\python.exe tools\pw_get_token.py
```

会弹出可见浏览器，按提示手动完成：
1. 切「密码登录」→ 填 `demo.user@example.com` / 密码 → 登录
2. MFA 页点「发送验证码」→ 完成数美滑块/点选
3. 去邮箱取验证码 → 填入 → 「验证并登录」

登录成功后脚本自动捕获 token 并**加密**落盘（Windows DPAPI，绑定当前用户，
密文拷到别的机器/用户下无法解密）：
- `work\auth_token.enc` —— `{token, device_id, smid, saved_at, token_state}`
- `work\pw_auth_state.enc` —— Playwright storage_state（cookie + localStorage），用于后续静默续期

### 第 2 步：之后全部纯协议

```powershell
# 验证 token
.\.venv\Scripts\python.exe tools\deepseek_api.py current

# 列会话
.\.venv\Scripts\python.exe tools\deepseek_api.py sessions

# 流式对话（自动取 PoW challenge 并求解）
.\.venv\Scripts\python.exe tools\deepseek_api.py chat "你好"

# 查看 token 剩余有效期
.\.venv\Scripts\python.exe tools\deepseek_api.py status
.\.venv\Scripts\python.exe tools\token_store.py status
```

### 第 3 步：续期（无需人工，可选）

```powershell
# 主动续期：无头浏览器加载 storage_state，让前端自己换新 token
.\.venv\Scripts\python.exe tools\token_refresh.py

# 只看状态、不启浏览器
.\.venv\Scripts\python.exe tools\token_refresh.py --check
```

`deepseek_api.py` 也会自动处理：剩余有效期不足 **600 秒**时自动静默续期；
接口返回 401/403 时再强制续期并重试一次。只有 refresh 凭证也失效时
（长时间不用）才需要重新跑一次第 1 步。

---

## 四、关键参数速查

### 4.1 登录请求

```
POST https://chat.deepseek.com/api/v0/users/login
Content-Type: application/json
x-request-encryption-key: <base64(RSA-OAEP-SHA256(key‖iv))>

body = AES-128-CBC-PKCS5( 明文 JSON, key, iv )
```

明文 JSON（**字段顺序固定**，207 字节）：

```json
{"email":"demo.user@example.com","mobile":"","area_code":"","password":"***",
 "device_id":"B<88字符base64>","os":"web","credential_id":""}
```

- `os` 枚举：`android` / `ios` / `web`（**`web` 分支必须带 `credential_id`，空串即可**）
- `device_id` 89 字符 = `"B"` + 数美 `deviceprofile` 的 `detail.deviceId`
- 未知字段被静默忽略，但字段名拼错会导致 422

### 4.2 请求体加密（与 Android `e8b.x()` 完全一致）

```
key = 16B 随机, iv = 16B 随机
plain32 = key ‖ iv
header  = base64( RSA-OAEP( plain32, 公钥B, SHA-256/MGF1-SHA256, label="") )
body    = AES-128-CBC-PKCS5( 明文, key, iv )
```

公钥 B（生产环境，Android/Web 共用）：

```
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0RLAhx1TOJhAQBHS1LHXlnkfOg86O+uhsmKWNNkmugVrRqO6cl13SnjBs2otRYZGJd50xpBG4We2i6/oCJCwxA/49YZfIwaeDmTx+WBIN7qrwhwP7vGCi6Osesmn/Ddgdye6mifYkRpRMonQjGY6VPaUMTw1jjOAIKph5YZn0bDVmGLvs5eH6CoQYHM5/Z1Nfhj36VL28eZi3elJHoz/L6Tzi2wY1rCYqYHfepq3Ysy8y5Y5BeFJXN60RYLlbs+MRC+2kyJqcfApUnn1O/W2om9dhxc6Rc5dqas1YB4X4CWCttrKk/suhpIx9zpQY9kqtotbe5zweYaKv0rCVeqx8wIDAQAB
```

### 4.3 设备指纹 `device_id` 生成

```
1. 浏览器/数美 SDK 请求 POST https://fp-it.portal101.cn/deviceprofile/v4
2. 响应 detail.deviceId = 88 字符 base64（= localStorage .thumbcache_<md5(org)>）
3. 登录 body 的 device_id = "B" + 该值（89 字符）
```

- 数美配置：`organization = P9usCUBauxft8eAmUXaZ`、`appId = default`
- 缺 `B` 前缀 → `biz_code 11 RISK_DEVICE_DETECTED`
- 用 UUIDv4 或随机 32 hex → 同样 11

### 4.4 GuestPow（`DeepSeekHashV1`）

```
POST /api/v0/users/create_guest_challenge  {"target_path": "<path>"}

base   = salt + "_" + expire_at + "_"      # expire_at 是 13 位毫秒原值
data   = base + str(nonce)
digest = Keccak-f[1600](rate=136, pad 0x06..0x80, rounds=23, start=RC[1])[:32]
命中   = digest == bytes.fromhex(challenge),  nonce ∈ [0, difficulty)
头     = X-DS-Guest-Pow-Response: base64(JSON(AuthedPowSolution))
```

**注意：不是标准 SHA3-256**——只跑 23 轮且跳过 `RC[0]`，所以 `hashlib.sha3_256` 永远算不出。
可复用实现：`tools/deepseek_pow.py`。

GuestPow 白名单（7 条，`login` 不在其中）：
`register`、`register_by_mobile`、`login_by_mobile_sms`、
`oauth/google/login`、`create_sms_verification_code`、
`create_email_verification_code`、`mfa/create_verification_code`。

### 4.5 biz_code 语义

| code | 含义 |
|---|---|
| 0 | 成功 |
| 2 | 用户名或密码错误 / 验证码未通过 |
| 4 | 邮箱域名不支持 |
| 10 | 账号被封 |
| **11** | **设备风险（device_id 不合法）** |
| 12 | 手机号受限 |
| 13 | 需要签名 |
| **14** | **需要 MFA 验证（账号已开二次验证）** |

全局错误码：`40002 Missing Token`、`40006 REQUEST_DECRYPT_FAILED`、
`40007 REQUEST_DECRYPT_NOT_ALLOWED`、`40029 TOO_MANY_REQUESTS`。

**注意 `40029` 与 `device_id` 绑定**——同一 device_id 短时间重复登录必限流，每次登录要换新指纹。

---

## 五、11 的排除过程（全部实测）

| # | 假设 | 实验 | 结论 |
|---|---|---|---|
| 1 | WAF 拦截 | 换浏览器 UA | 有效，但不是 11 成因 |
| 2 | 需要 hif 令牌 | 带 `x-hif-dliq/leim` | 无效 |
| 3 | 需要 cookie 预热 | 先 GET 首页再登录 | 无效 |
| 4 | 需要设备注册 | `auth_token/check_device` | 需 token，无法在登录前用 |
| 5 | 需要 PoW | guest challenge + 解 | login 不在白名单，无通道 |
| 6 | device_id 格式 | 32hex / UUIDv4 / 固定 UUID | 全部 11 |
| 7 | TLS 指纹 | curl_cffi impersonate chrome | 无效 |
| 8 | 出口 IP | 代理 vs 直连 | 均 11 |
| 9 | 账号被封 | 错密码对照 | 返回 2，证明凭据校验先于风控 |
| 10 | 请求体加密 | 明文 vs 密文 | 明文也 11，不是加密问题 |
| 11 | 数美 smid cookie | 注入浏览器 smidV2 | 仍 11 |
| 12 | **device_id = 数美指纹** | 用 deviceprofile 的 deviceId | 仍 11 |
| 13 | **缺 `B` 前缀** | `"B" + deviceId` | **✅ 通过，进入 MFA** |

---

## 六、产物索引

| 文件 | 作用 |
|---|---|
| `tools/deepseek_pow.py` | GuestPow 求解（23 轮 Keccak），可复用 |
| `tools/deepseek_client.py` | 未授权阶段客户端（hif / pow / login / 加密） |
| `tools/pw_get_token.py` | **半自动授权：开浏览器 → 用户过 MFA → 导出 token（加密）** |
| `tools/token_store.py` | **token / storage_state 的 DPAPI 加密存储 + JWT 过期判断** |
| `tools/token_refresh.py` | **静默续期：无头浏览器复用 storage_state 换新 token** |
| `tools/deepseek_api.py` | **已授权后纯协议 API 客户端（current / sessions / chat，自动续期）** |
| `tools/pw_mfa_capture2.py` | 捕获 MFA 页面请求（证明无请求、弹数美滑块） |
| `tools/pw_devid_compare.py` | hook 加密明文 + localStorage 对比（发现 `B` 前缀） |
| `tools/proto_login_final.py` | `B` 前缀 + PoW 验证脚本 |
| `work/auth_token.enc` | 授权产物（第 1 步生成，DPAPI 密文） |
| `work/DeepSeek_2.7.1_逆向报告.md` | 全量接口与加解密逆向报告 |

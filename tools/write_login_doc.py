# -*- coding: utf-8 -*-
"""生成《DeepSeek 纯协议登录 交付说明》文档。"""
import io

P = r"F:\dshh\deepseeka\work\DeepSeek_纯协议登录_交付说明.md"

DOC = u"""# DeepSeek 纯协议登录：协议全打通 + 唯一卡点定位

测试账号 `<your-email>`。目标：不依赖 App/浏览器，用 HTTP 请求完成登录并拿到 token。

---

## 一、结论先说

| 环节 | 状态 |
|---|---|
| 网络可达（绕过华为云 WAF） | **已解决**：浏览器 UA + 直连（走代理 IP 会 429 `Server: CW`） |
| 请求体加密（RSA-OAEP + AES-128-CBC） | **已复刻**，服务端解密成功（返回字段校验错而非 `REQUEST_DECRYPT_FAILED`） |
| PoW `DeepSeekHashV1` | **完全破解**，实测命中（`nonce=14`/`16`），服务端接受 `X-DS-Guest-Pow-Response` |
| `x-hif-dliq` / `x-hif-leim` 令牌 | **已解决**：两个 GET 接口白拿，TTL 600s，无需认证 |
| 登录请求 schema | **已确定**：`{email, password, device_id, os, credential_id}` |
| 凭据正确性 | **已验证**：错密码返回 `biz_code 2`，说明密码校验在风控之前 |
| **登录放行** | **卡在 `biz_code 11 RISK_DEVICE_DETECTED`** |

**11 是终态拒绝**：网页端源码 `case LOGIN_ERROR_CODE.RISK_DEVICE_DETECTED: b("deviceRisk")` 只弹"检测到异常环境"toast，**官方客户端没有任何验证码/申诉/重试分支**；手机验证码登录、注册、Google/Apple 登录遇 11 时同样只弹 toast。

---

## 二、可直接使用的实现

### 2.1 客户端模块 `tools/deepseek_client.py`

```bash
.venv\\Scripts\\python.exe tools/deepseek_client.py hif          # 取 hif 令牌（200，TTL 600）
.venv\\Scripts\\python.exe tools/deepseek_client.py pow          # 取 guest challenge 并求解
.venv\\Scripts\\python.exe tools/deepseek_client.py login --email <your-email> --password *** --os android
.venv\\Scripts\\python.exe tools/deepseek_client.py settings     # 免登录可访问的接口
```

已封装：通用头（`x-client-*` / `x-device-id` / `x-device-model` / `x-hif-*`）、请求体加密、PoW 求解、错误码映射。

### 2.2 PoW 求解 `tools/deepseek_pow.py`

**关键：不是标准 SHA3-256。**

```
base   = salt + "_" + expire_at + "_"     # expire_at 用 13 位毫秒原值
data   = base + str(nonce)
digest = Keccak-f[1600](rate=136, padding 0x06..0x80, rounds=23, start=RC[1])[:32]
命中：digest == bytes.fromhex(challenge)，nonce ∈ [0, difficulty)
```

`librscrypto.so` 所有调用点传 `w1=#0x17`（23 轮）且从 `RC[1]` 起算，因此只跑 23 轮并跳过 `RC[0]` —— 这就是 `hashlib.sha3_256` 永远算不出的原因。

### 2.3 请求体加密

```
1. 随机 16B AES key + 16B IV
2. RSA-OAEP(SHA-256, MGF1-SHA256, label="") 加密 (key||iv) 的 32 字节 → Base64 → 头 x-request-encryption-key
3. AES-128-CBC/PKCS5 加密 JSON body → 裸字节作为请求体
```

公钥（`o69.a`，来自 `p0a.smali`，登录链路实际使用）：

```
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0RLAhx1TOJhAQBHS1LHXlnkfOg86O+uhsmKW
NNkmugVrRqO6cl13SnjBs2otRYZGJd50xpBG4We2i6/oCJCwxA/49YZfIwaeDmTx+WBIN7qrwhwP7vGCi
6Osesmn/Ddgdye6mifYkRpRMonQjGY6VPaUMTw1jjOAIKph5YZn0bDVmGLvs5eH6CoQYHM5/Z1Nfhj36VL
28eZi3elJHoz/L6Tzi2wY1rCYqYHfepq3Ysy8y5Y5BeFJXN60RYLlbs+MRC+2kyJqcfApUnn1O/W2om9dh
xc6Rc5dqas1YB4X4CWCttrKk/suhpIx9zpQY9kqtotbe5zweYaKv0rCVeqx8wIDAQAB
```

---

## 三、登录接口的完整契约

```
POST https://chat.deepseek.com/api/v0/users/login
Content-Type: application/json
```

| 字段 | 说明 |
|---|---|
| `email` | 必填 |
| `password` | 必填 |
| `device_id` | 必填。网页端为 **UUID v4**；App 端默认走数美 smid |
| `os` | 必填。**枚举仅 `android` / `ios` / `web`**（其余 422 `body.os`） |
| `credential_id` | `os=web` 时**必填**（可为空串）；MFA 可信设备凭证 |

额外字段（`email_verification_code` / `turnstile_token` / `hcaptcha_token` / `shumei_*` / `mfa_*`）会被**静默忽略**，不能用于解除 11。

响应：`{code, msg, data:{biz_code, biz_msg, biz_data}}`，登录业务码：

| biz_code | 含义 |
|---|---|
| 0 | OK（`biz_data` 含 token） |
| 2 | `PASSWORD_OR_USER_NAME_IS_WRONG` |
| 10 | `USER_IS_BANNED` |
| **11** | **`RISK_DEVICE_DETECTED`** |
| 12 | `MOBILE_RESTRICTED` |
| 13 | `SIGNATURE_REQUIRED`（MFA） |
| 14 | `OTP_REQUIRED` |

---

## 四、11 的排除过程（都已实测，全部无效）

| 假设 | 实验 | 结果 |
|---|---|---|
| UA 指纹 | okhttp / Dalvik / Chrome / 官方 App UA | 仅 okhttp 被 WAF 429，其余到业务层仍 11 |
| TLS 指纹 | `curl_cffi impersonate=chrome / chrome124` | 仍 11 |
| 出口 IP | 直连家宽 / 代理 | 均 11（代理会额外触发 WAF 429） |
| 设备头 | 补 `x-device-id`(UUIDv4) + `x-device-model:""` | 仍 11 |
| device_id 形态 | 32 hex / UUIDv4 / 固定 UUID | 均 11 |
| hif 令牌 | 带 `x-hif-dliq` / `x-hif-leim` | 仍 11 |
| cookie 预热 | 先 GET 首页拿 `HWWAFSESTIME/HWWAFSESID/ds_session_id` | 仍 11 |
| 启动序列预热 | `ip_to_country_code` → `client/settings` → `check_client_update` → `users/current` | 仍 11 |
| 客户端版本 | `x-client-version` = 2.7.1 / 2.7.5 / 2.8.5 / 2.9.5 / 3.0.0 | 全部 40029（限流），无版本判定差异 |
| PoW | guest challenge 求解后带 `X-DS-Guest-Pow-Response` | login 不在 GuestPow 白名单，无法用于登录 |
| 请求体加密 | 加密 / 明文 | 均 11（服务端不强制加密） |
| 密码正确性 | 错密码 vs 正确密码 | 2 vs 11 → **密码正确，风控在后** |

---

## 五、11 的最可能成因（静态证据）

1. **设备标识链路默认走数美**：`by2.smali` 的 `<clinit>` 把 `Lby2;->c` 置 `true`，`dy2.smali:4055-4165` 的 `q()`（`should_use_sm_device_id`）默认返回 true；`o2a.smali:447-500` 在启用时取数美 smid，否则返回空串。数美配置：organization `P9usCUBauxft8eAmUXaZ`、`appId="default"`、`/deviceprofile/v4`、`/v3/cloudconf`、端点 `fp-it.fengkongcloud.com`。
2. **随机 UUID 的 `device_id` 不具备任何设备指纹**，服务端无法与历史设备关联 → 判为新设备/异常环境。
3. **11 无自救通道**：官方客户端对该码只有 toast，说明它是"服务端环境判定"，客户端无法用验证码解除。

---

## 六、三条可行路径（按可行性排序）

### 路径 A：真实浏览器环境（推荐，能真正拿到 token）

用 Playwright 打开 `https://chat.deepseek.com/sign_in`，让官方前端自己生成 `x-device-id`、跑完人机验证并完成登录，然后从 `localStorage`/`document.cookie` 取 token。风控看到的是完整真实环境，`11` 不会出现。

- 成本：需下载 Chromium（可装到本工作目录，设 `PLAYWRIGHT_BROWSERS_PATH`）。
- 产出：token 可直接给后续 ChatAPI 纯协议调用用（**只有登录这一步需要浏览器，之后全部可纯协议**）。

### 路径 B：提供一次性凭证（最省事）

在任意浏览器手动登录一次，导出该次请求的 `Authorization`（`Bearer ...`）或 `localStorage` 中的 token。之后所有 `/api/v0/*`（含 ChatAPI、SSE）都可纯协议调用，token 有效期通常较长。

### 路径 C：手机号验证码登录（需账号已绑手机）

`users/login_by_mobile_sms` 与 `users/create_sms_verification_code` **都在 GuestPow 白名单内**，PoW 已可解。但需要：账号已绑定的手机号 + 能接收短信（需要你提供）。

---

## 七、附：GuestPow 白名单（能纯协议走通的接口）

```
/v0/users/register
/v0/users/register_by_mobile
/v0/users/login_by_mobile_sms
/api/v0/users/create_sms_verification_code
/api/v0/users/create_email_verification_code
```

`login` **不在其中**，因此密码登录无法借助 PoW 提升可信度。

邮箱验证码路径实测：`scenario` 合法值仅 `register` / `reset_password`；`<your-email>` 被判 `EMAIL_DOMAIN_NOT_SUPPORTED`（biz_code 4），而 gmail/outlook/qq/163/126/foxmail/yahoo/proton/icloud/example.com 均通过域名校验但要求 reCAPTCHA（biz_code 2 `RECAPTCHA_VERIFY_FAILED`）——即**邮箱验证码路径必须过 reCAPTCHA**，纯协议不可行。

---

## 八、产物索引

| 文件 | 内容 |
|---|---|
| `tools/deepseek_client.py` | 客户端模块（头、加密、PoW、登录、错误码） |
| `tools/deepseek_pow.py` | PoW 求解（23 轮 Keccak） |
| `tools/email_domain_probe.py` | 邮箱域名白名单探测 |
| `tools/login_schema_probe.py` | 登录 schema / os 枚举探测 |
| `tools/login_wait.py` | 冷却后单次尝试（结果写 `work/login_wait.log`） |
| `work/DeepSeek_2.7.1_逆向报告.md` | 全量接口 + 加解密 + 网页端协议对照（§7） |
| `work/api_methods.txt` | 80 条接口 → HTTP 方法映射 |
| `work/models_dump.txt` | 222 个请求/响应模型字段 |
"""

io.open(P, "w", encoding="utf-8", newline="\n").write(DOC)
print("written", P, len(DOC), "chars")

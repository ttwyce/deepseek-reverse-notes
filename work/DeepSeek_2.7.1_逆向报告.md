# DeepSeek Android v2.7.1 网络接口与加解密机制逆向报告

- 样本：`input\DeepSeek_2.7.1_apks.apk`（26,879,926 B，sha256 `efc2a589…14fa7`）
- 包名：`com.deepseek.chat`；versionName `2.7.1`；DEX：classes.dex 12.66 MB / classes2 44 KB / classes3 265 KB / classes4 2.78 MB
- 分析方式：静态（jadx 1.5.1 全量反编译 + **baksmali 3.0.10 全量 smali** + dex 字符串表 + capstone ARM64 反汇编），未运行 App
- 说明：jadx 报 `Method dump skipped` 的方法不等于拿不到——dex→smali 是逐指令无损的，所有 Java 层逻辑都可用 `work\smali\dex1`（12,345 个 .smali）复核
- 混淆：R8 全量重命名，业务类全部落在 `defpackage.xxx`（如 `hp3`、`r69`、`q69`、`e8b`、`mr1`、`k01`、`sq2`），原始包名仅以 kotlinx.serialization descriptor 字符串形式保留

---

## 1. 网络栈与主机

| 项 | 结论 |
|---|---|
| HTTP 客户端 | Ktor（`zf5`=HttpClientConfig，`vf5`=HttpClient，`gh5`=HttpRequestBuilder，`ki5`=call 构建器） |
| API 基址 | `https://chat.deepseek.com`（源码中只出现该 host；`/api/v0/*` 拼在其后） |
| 官方附属域 | `cdn.deepseek.com`（policies、`client-resource/mobile_report_inject.js`）、`static.deepseek.com`（faq）、`download.deepseek.com`（app 下载页） |
| 风控探测域 | `https://hif-dliq.deepseek.com/query`、`https://hif-leim.deepseek.com/query`（GET，超时 3000 ms，响应 `biz_data.value` 为字符串） |
| 重试 | `oy7`：最多 10 次 |
| 插件链 | `HttpTimeout`（`kjb.b`，`ft3.a`）、`DefaultRequest`（`sr3.b`）、ContentNegotiation(json)、自定义 `ChallengePlugin`（`mr1`）、`RequestBodyEncryption`（`r69`/`q69`）、APM span（`r0a`） |

### 调用模板（所有接口统一）

```java
gh5 b = new gh5();
bfb.b(b.a, "/api/v0/users/login");   // 只设 path，host 由 client 补全
b.b = rg5.c;                          // 方法：rg5.b=GET c=POST d=PUT e=PATCH f=DELETE g=HEAD h=OPTIONS
pd3.G(b, fc3.a);                      // application/json + setBody（有 body 时）
new ki5(b, vf5Var).c(scope);          // 执行
```

### 通用请求头（`defpackage/x06.java:69-77`、`s3.java:129`、`nw9.java`）

| Header | 值 / 来源 |
|---|---|
| `Referer` | `https://chat.deepseek.com` |
| `x-client-platform` | `android` |
| `x-client-version` | `2.7.1` |
| `x-client-locale` | `tw5.R(R.string.locale, ctx)`（如 `zh_CN`） |
| `x-client-bundle-id` | `com.deepseek.chat` |
| `User-Agent` | 运行时注入（`nw9` case 1） |
| `Authorization` | `Bearer <token>`（`yy8.java:302`） |
| `x-settings-token` | 仅 `/api/v0/client/settings`、`/client/settings/report` |
| `x-ds-compression` | 仅 telemetry：`gzip` |
| `x-request-encryption-key` | 请求体加密时：Base64(RSA-OAEP(随机 key‖iv)) |
| `X-DS-PoW-Response` | PoW 答案（`mr1.c`） |
| `X-DS-Guest-Pow-Response` | 游客 PoW 答案 |
| `X-DS-Challenge-Response` | 挑战响应 |
| `X-Debug-Recaptcha-Challenge` | 仅 debug 构建 |
| `x-ds-trace-id` | 由 APM 拦截器写入并回读（`mb.java:9`、`tw5.java:325`） |
| `x-hif-dliq` / `x-hif-leim` | 请求头，值来自 hif 令牌通道（见 §3.5），非空才添加 |
| `x-hif-ttl` | **响应头**（客户端只读不发），令牌有效期秒数 |

---

## 2. 接口清单（80 条）

> HTTP 方法已用全量 smali 逐条回填（脚本 `tools/scan_smali_api.py`，取路径字符串行最近的 `rg5` 方法常量引用），完整表见 **`work/api_methods.txt`**（含 smali 文件:行号与是否带 JSON body）。下方各表「方法」列即该扫描结果。

### 2.1 认证 / 账号（`users/*`）

| 路径 | 方法 | 说明 |
|---|---|---|
| `users/login` | POST | 邮箱或手机号+密码登录（**加密体**、**GuestPow**） |
| `users/register` | POST | 邮箱注册（**加密体**、**GuestPow**） |
| `users/register_by_mobile` | POST | 手机号注册（**加密体**、**GuestPow**） |
| `users/login_by_mobile_sms` | POST | 短信验证码登录（**加密体**、**GuestPow**） |
| `users/one_tap_login` | POST | 运营商一键登录（`fly_verify.token/op_token`） |
| `users/create_sms_verification_code` | POST | 发短信码（**加密体**、**GuestPow**） |
| `users/check_sms_code` | POST | 校验短信码（**加密体**） |
| `users/create_email_verification_code` | POST | 发邮件码（**加密体**、**GuestPow**） |
| `users/check_email_code` | POST | 校验邮件码（**加密体**） |
| `users/mobile_reset_password` | POST | 手机重置密码（**加密体**） |
| `users/email_reset_password` | POST | 邮箱重置密码（**加密体**） |
| `users/rebind_mobile/start` / `finish` / `verify_disabled_old_mobile` | POST | 换绑手机（finish 为**加密体**） |
| `users/oauth/wechat/mobile_verification` | POST | 微信登录补手机验证（**加密体**） |
| `users/oauth/wechat/login` / `bind` / `unbind` | POST/GET | 微信登录、绑定、解绑 |
| `users/oauth/google/login` / `authorize` | POST/GET | Google 登录（**GuestPow**） |
| `users/oauth/get_token` | POST | 三方换 token |
| `users/create_guest_challenge` | POST | 取游客 PoW 挑战 |
| `users/mfa/create_verification_code` | POST | MFA 发码（**GuestPow**） |
| `users/mfa/check_verification_code` | POST | MFA 校验码 |
| `users/mfa/verify_signature` | POST | MFA 签名验证 |
| `users/mfa/trusted_device/register` / `verify` | POST | 可信设备公钥注册 / 验证 |
| `users/auth_token/list` | GET | 会话列表 |
| `users/auth_token/revoke` | POST | 撤销某 token |
| `users/auth_token/check_device` | POST | 设备校验（可返回 `rotate.token`） |
| `users/current` | GET | 当前用户信息 |
| `users/logout` / `logout_all_sessions` / `unregister` | GET | 登出/全登出/注销 |
| `users/settings` | GET | 读设置（`biz_data.training_allowed`，即「数据用于优化体验」开关） |
| `users/update_settings` | POST | 改设置（`{"training_allowed": bool}`；响应 `biz_data` 为 null，须回读校验） |
| `users/get_birthday` | GET | 取生日 |
| `users/set_birthday` | POST | 设生日 |
| `ip_to_country_code` | GET | IP→地区 |

### 2.2 对话（`chat/*`）

| 路径 | 方法 | 说明 |
|---|---|---|
| `chat/completion` | POST | **主对话接口（SSE 流）** |
| `chat/continue` | POST | 继续生成（SSE） |
| `chat/regenerate` | POST | 重新生成（SSE） |
| `chat/edit_message` | POST | 编辑重发（SSE） |
| `chat/resume_stream` | POST | 断线续流 |
| `chat/stop_stream` | POST | 停止生成 |
| `chat/history_messages` | POST | 历史消息分页 |
| `chat/message_feedback` | POST | 点赞/踩 |
| `chat/create_pow_challenge` | POST | 取对话 PoW 挑战 |
| `chat/tts/` | POST | 语音合成（流） |
| `chat/tts/voice` | POST | 选音色 |
| `chat/tts/voices` | GET | 音色列表 |

### 2.3 会话 / 文件 / 索引 / 通话 / 分享 / 客户端

| 路径 | 方法 |
|---|---|
| `chat_session/create` / `delete` / `delete_all` / `fetch_page` / `update_title` / `update_pinned` / `batch_update_pinned` | POST |
| `file/upload_file` / `fetch_files` / `fork_file_task` | POST |
| `index/prepare` | GET |
| `index/query` | GET |
| `asr/ws` | POST（WebSocket 升级） |
| `call/config` | GET |
| `call/start`（SSE）/ `call/update` / `call/stop` / `call/rating` | POST |
| `share/create` / `delete` / `fork` / `list` / `content` | POST/GET |
| `client/settings` / `client/settings/report` / `client/span` | GET/POST |
| `check_client_update` / `telemetry` | POST |

> SSE 接口集合硬编码于 `jp3.java`：`chat/completion`、`chat/edit_message`、`chat/regenerate`、`chat/continue`、`call/start`。

### 2.4 隐私开关「数据用于优化体验」（`training_allowed`）—— 已实测双向验证

Web 设置里的 **Improve the model for everyone**（中文「数据用于优化体验 / 允许将内容用于训练与优化服务」），埋点 `switchAllowTraining`，文案键 `allowTrainingSwitchLabel` / `allowTrainingDescription`。

| 操作 | 方法 | 路径 | 载荷 |
|---|---|---|---|
| 读 | GET | `/api/v0/users/settings` | 响应 `data.biz_data.training_allowed`（bool） |
| 写 | POST | `/api/v0/users/update_settings` | 请求体 `{"training_allowed": true/false}` |

结论（逐项核实，非推断）：

1. **写成功不回显状态**：`{"code":0,"msg":"","data":{"biz_code":0,"biz_msg":"","biz_data":null}}`，必须回读 `users/settings`。Web 端同样只做本地缓存乐观更新（`mutate` + `revalidate:false`）。
2. **请求头只需 `Authorization: Bearer <token>` + 标准 `x-client-*` 头**，已登录接口不要求 GuestPoW / `X-DS-PoW-Response`。
3. **不需要 `x-settings-token`**：Web 拦截器（`const b="x-settings-token"`，`hook` 仅挂在 `E()`→`/api/v0/client/settings` 与 `d()`→`/api/v0/client/settings/report`）；与 §1 表格中「仅 client/settings」一致。
4. **body 明文 JSON，不加密**：Web 的请求体加密钩子只对白名单 pathname 生效——`eN={chat:new Set([...ej,"oauth/apple/mobile_verification","miniprogram/mobile_verification"].map(e=>"/api/v0/users/"+e))}`；`update_settings` 在整个 bundle 中仅出现 1 次（明文 `post({json:e})`）。
5. **Android 端同路径**：`api_methods.txt` 记录 `users/settings`（`k01:379`）、`users/update_settings`（`x9b:873`），dex 字符串表含 `training_allowed`，方法 POST、需鉴权。

实测记录（自有账号，先读 → 写 → 回读 → 还原）：

```
GET  users/settings                      -> 200  training_allowed=false
POST users/update_settings {true}        -> 200  biz_data=null
GET  users/settings                      -> 200  training_allowed=true     ← 写入生效
POST users/update_settings {false}       -> 200  biz_data=null
GET  users/settings                      -> 200  training_allowed=false    ← 已还原
```

封装：`tools/deepseek_client.py` 的 `DeepSeekClient.from_token_file()` / `get_training_allowed()` / `set_training_allowed(bool, verify=True)`；CLI 为 `python tools/deepseek_client.py training [--set true|false] [--token-file PATH]`。

---

## 3. 加解密机制

### 3.1 请求体加密（RSA-OAEP-256 + AES-128-CBC）—— 登录/注册核心

**触发白名单**（`defpackage/r69.java`，12 条，命中才加密）：
```
/api/v0/users/create_sms_verification_code   /api/v0/users/create_email_verification_code
/api/v0/users/login_by_mobile_sms            /api/v0/users/login
/api/v0/users/register_by_mobile             /api/v0/users/register
/api/v0/users/check_sms_code                 /api/v0/users/check_email_code
/api/v0/users/mobile_reset_password          /api/v0/users/email_reset_password
/api/v0/users/rebind_mobile/finish           /api/v0/users/oauth/wechat/mobile_verification
```

**实现**（`q69.java` 钩子 → `e8b.java:x(byte[])`）：

1. `SecureRandom` 取 16 B = AES key，16 B = IV，拼成 32 B `key‖iv`
2. `RSA/ECB/OAEPPadding` + `OAEPParameterSpec("SHA-256","MGF1",MGF1ParameterSpec.SHA256)` 加密该 32 B → Base64 → header `x-request-encryption-key`
3. 明文 JSON 用 `AES/CBC/PKCS5Padding`（key/iv 同上）加密 → 密文**直接作为请求体字节**（Content-Type 不再是 json）
4. 请求体替换在 Ktor `HttpRequestPipeline` 的 Transform 阶段（`new tv0(cipherBytes, contentType)`）

**Python 复现**：

```python
import os, base64, json
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PUB_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAo2wegFXo1m3LGL5mWHXe
3s2+tuxutbxwRQRO3RJO6Xjengngpkqtq0CfkZVdQyMRIR+9nU5xr26swsEbnwG9
keuW4ZF8iAPfTobFT5Dxo0Pkya2Q6i+3jBnnC+MdWlSWuW2pJIX0O+78kmB6ZtXx
nf/KmUBa9s6ufFcisgnH1tdpbjwRvzcUz4+zDIneEL7fZlB+nzo258F/oYfqECPR
RJRLgDzFYfDd5K22K3grhSTpIvdaYAUe4gyIz/DHLuo+fIeEeGeTcy2hp4pqaT6c
tlh7iHDbcSXvy5wqmVwI4M8atyLcl0/osb7JErbu/nuTc8okGCKzt3D8RTwHa/Z2
BQIDAQAB
-----END PUBLIC KEY-----"""

def encrypt_body(payload: dict):
    key, iv = os.urandom(16), os.urandom(16)
    pub = serialization.load_pem_public_key(PUB_PEM)
    kek = pub.encrypt(key + iv, padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(), label=None))
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    data = json.dumps(payload, separators=(",", ":")).encode()
    pad = 16 - len(data) % 16
    body = enc.update(data + bytes([pad]) * pad) + enc.finalize()
    return base64.b64encode(kek).decode(), body
```

**两个 RSA 公钥**：

- 主 API（`bb.java:45`）—— 上文 PEM。
- 备用（`p0a.java:53`，疑用于 hif/telemetry 通道）：
```
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0RLAhx1TOJhAQBHS1LHXlnkfOg86O+uhsmKWNNkmugVrRqO6cl13SnjBs2otRYZGJd50xpBG4We2i6/oCJCwxA/49YZfIwaeDmTx+WBIN7qrwhwP7vGCi6Osesmn/Ddgdye6mifYkRpRMonQjGY6VPaUMTw1jjOAIKph5YZn0bDVmGLvs5eH6CoQYHM5/Z1Nfhj36VL28eZi3elJHoz/L6Tzi2wY1rCYqYHfepq3Ysy8y5Y5BeFJXN60RYLlbs+MRC+2kyJqcfApUnn1O/W2om9dhxc6Rc5dqas1YB4X4CWCttrKk/suhpIx9zpQY9kqtotbe5zweYaKv0rCVeqx8wIDAQAB
```

### 3.2 PoW 工作量证明（`DeepSeekHashV1`）

- Java 侧：`com/deepseek/crypto/PowCalculator.java` → `System.loadLibrary("rscrypto")` → `native long nativeCalculateDeepSeekHashV1Pow(String, String, long)`
- 原生实现：`lib/arm64-v8a/librscrypto.so`（336,568 B，**唯一导出** `Java_com_deepseek_crypto_PowCalculator_nativeCalculateDeepSeekHashV1Pow@0x18e40`）
- 该 .so 为 **Rust 编译产物**，依赖 `rust-sha3(sha3c)` + `keccak-0.2.0-pre.0` + `jni-0.21.1`；文件内无 SHA-2/SHA-512/FNV/Murmur/BLAKE 常量
- **核心结论：`DeepSeekHashV1` = 改造版 Keccak 迭代求解（不是标准 SHA3-256）**
  - `0x1a7e8` = Keccak-f[1600] 排列，`cmp x1,#0x19` 越界报 `A round_count greater than KECCAK_F_ROUND_COUNT is not supported!`
  - **关键差异：所有调用点都传 `w1=#0x17`（23），且轮循环从 `RC[1]` 起算 ⇒ 实际只跑 23 轮并跳过 `RC[0]`。因此 `hashlib.sha3_256` 永远算不出正确值——这是早期所有暴力尝试失败的唯一原因。**
  - rate = **136 B**（`0x88`，尾部 `umull 0xf0f0f0f1` 取模），输出 **32 B**（`cmp len,#0x20`），padding 域分隔字节 **0x06**、末字节 `|= 0x80`（SHA-3 风格，非 SHAKE 的 0x1F）
  - 主循环：`for nonce in 0..difficulty`，nonce 转**十进制字符串**追加到已 absorb 的前缀后 finalize，得到 32 B digest，与服务端目标逐字节比较（32 次 `ldrb`+`cmp`+`b.ne`），命中即返回 nonce；`difficulty < 1` 或循环耗尽返回 **-1**
  - 每次迭代复用 state 副本（前缀只 absorb 一次），所以复杂度是 O(difficulty) 次 Keccak-f；服务端下发 `difficulty=20`，即期望约 2^20 次尝试

#### 参数绑定（smali + 反汇编双重实证）

`0x18e40` 的取参顺序：`stp x0,x2,[sp,#8]` / `str x3,[sp,#0x18]` → 第一次转换 **jstring1**（`(x19,x20,x22)`=ptr,len,cap），第二次转换 **jstring2**（`(x23,x24,w1)`），最终

```
x0 = x24 (str2 的 ptr)   w1 = len(str2)   x2 = x20 (str1 的 ptr)   w3 = len(str1)   x4 = difficulty
bl 0x19bc0
```

`0x19bc0` 内 **x0/w1 走 hex 解码**（奇数长度失败、`0-9a-fA-F` 解析），**x2/w3 作为 base 前缀直接 absorb 且 ≤135 B**。因此：

| 位置 | 语义 | 来源字段 |
|---|---|---|
| `str2`（hex 解码 → **32 B 目标**） | `challenge` | `ServerChatChallenge.challenge` |
| `str1`（base 前缀，≤135 B） | **`salt + "_" + expire_at + "_"`** | `me0.smali` 三个分支一致：`StringBuilder.append(c).append("_").append(f).append("_")`，`c`=salt、`f`=expire_at |
| `difficulty` | nonce 上界 | `ServerChatChallenge.difficulty` |

`Lor9`（`ServerChatChallenge`）字段映射经 serializer `mr9.smali` 逐个 index 确认：`a`=algorithm、`b`=challenge、`c`=salt、`d`=signature、`e`=difficulty、`f`=expire_at、`g`=expire_after、`h`=target_path。

**`algorithm` 取值 = 字符串 `"DeepSeekHashV1"`**（`oe0.smali:879`、`fg2.smali:1058`：`uw5.b(algorithm, "DeepSeekHashV1")`）。相等时反射调用 native `calculateDeepSeekHashV1Pow`，否则退到 `Lr3`（索引 2）的备用实现。

#### 答案封装与请求头

`AuthedPowSolution`（`se0`）字段：`a`=algorithm、`b`=challenge、`c`=salt、`d`=signature、`e`=answer(long)、`f`=target_path、`g`=本地过期时刻。

组装（`fg2.smali:1182-1238`）：

```java
long expireAt = SystemClock.elapsedRealtime() + (challenge.g /*expire_after*/ - 20000);
new AuthedPowSolution(algorithm, challenge, salt, signature, nonce, "/api/v0/chat/completion", expireAt);
```

编码（`fg2.smali:854-883`）：`Json.encodeToString(AuthedPowSolution.serializer(), solution)` → **`dk0.a(json)` 即 Base64** → 放进 `X-DS-PoW-Response`。过期判定 `se0.a()`：`elapsedRealtime() > g`。

头注入点 `mr1.smali:2298-2352`（ChallengePlugin 执行体）：

```java
if (debugRecaptcha != null) headers.set("X-Debug-Recaptcha-Challenge", debugRecaptcha);
if (challengeResp  != null) headers.set("X-DS-Challenge-Response", challengeResp);
if (powResp        != null) headers.set("X-DS-PoW-Response", powResp);
```

#### Python 复现

```python
import json, base64

def deepseek_hash(data: bytes) -> bytes:
    """Keccak-f[1600]，只跑 23 轮且从 RC[1] 开始（DeepSeekHashV1 的关键差异）。"""
    a = [0] * 25
    padded = bytearray(data)
    padlen = 136 - (len(data) % 136)
    padded += b"\x86" if padlen == 1 else b"\x06" + b"\x00" * (padlen - 2) + b"\x80"
    for i in range(0, len(padded), 136):
        for j, byte in enumerate(padded[i:i + 136]):
            a[j // 8] ^= byte << ((j % 8) * 8)
        a = _keccak_f(a, rounds=23, start=1)        # ← 23 轮、跳过 RC[0]
    return b"".join(l.to_bytes(8, "little") for l in a)[:32]

def solve(challenge_hex: str, salt: str, expire_at: int, difficulty: int) -> int:
    target = bytes.fromhex(challenge_hex)           # 32 B
    prefix = f"{salt}_{expire_at}_".encode()        # <=135 B
    for nonce in range(max(difficulty, 1)):
        if deepseek_hash(prefix + str(nonce).encode()) == target:
            return nonce
    return -1

answer = solve(ch["challenge"], ch["salt"], ch["expire_at"], ch["difficulty"])
pow_resp = base64.b64encode(json.dumps({
    "algorithm": "DeepSeekHashV1", "challenge": ch["challenge"], "salt": ch["salt"],
    "signature": ch["signature"], "answer": answer, "target_path": ch["target_path"],
}, separators=(",", ":")).encode()).decode()
```

完整可运行实现（含 `_keccak_f` 的 23 轮版本、guest challenge 申请、头构造）见 `tools/deepseek_pow.py`。

**实测命中记录**：`salt=408c87d6f327d6257cbc, expire_at=1792936998058` → `nonce=14`；`salt=1f68a1ff14a82106434c, expire_at=1792937297882` → `nonce=16`。带该头请求 `users/create_email_verification_code` 时服务端不再报 PoW 错误（422 只提示缺 `turnstile_token`/`scenario`），**证明 PoW 校验已通过**。

**PoW 需要的接口**（GuestPow 白名单，`hp3.java`）：`users/register`、`users/register_by_mobile`、`users/login_by_mobile_sms`、`users/oauth/google/login`、`users/create_sms_verification_code`、`users/create_email_verification_code`、`users/mfa/create_verification_code`（走 `X-DS-Guest-Pow-Response`，挑战来自 `users/create_guest_challenge`）。

> 残留不确定：`answer` 在 JSON 里是数字还是字符串（`se0.e` 为 `long`，序列化器按 long 写出）；`salt`/`expire_at` 拼接的确切分隔符已由 `me0` 实证为 `"_"`。

### 3.3 其他加密 / 隐私相关组件

| 组件 | 作用 |
|---|---|
| `libEncryptorP.so` | **字节跳动 AppLog 日志加密**（`com/bytedance/applog/encryptor/EncryptorUtil`、`ttEncrypt([BI)[B]`），火山 APM 上报用，与主 API 无关 |
| `libWCDB.so` | 内置完整 OpenSSL（AES-128/192/256 CBC/CTR/GCM/ECB/XTS、HMAC-SHA1/256/512），用于**本地数据库加密**（聊天记录落盘） |
| `libmmkv.so` | KV 存储（`KVAppUserInfo` 等），MMKV 自带加密选项 |
| `libsmsdk.so` | 数美（ishumei）风控 SDK，设备指纹 |
| `libliteavsdk.so` | 腾讯 TRTC/直播（音视频通话），含 `JNI_OnLoad` + 369 个 JNI 导出 |
| telemetry | `POST /api/v0/telemetry`，body 走 3.1 同款混合加密 + `x-ds-compression: gzip` |

### 3.4 人机验证与风控

- 数美 `ShumeiVerification{region, rid}` + `shumei_device_id`（域名 `fengkongcloud.com`：castatic / fp-it-tracker / captcha / api-device-eur）
- hCaptcha（`hcaptcha_token`，`js.hcaptcha.com`）
- Cloudflare Turnstile（`turnstile_token`，仅部分接口）
- 运营商一键登录（`cmpassport.com`、`wosms.cn`、`crbt.i139.cn`，字段 `fly_verify.token/op_token`）
- 自有探测：`hif-dliq` / `hif-leim` 的 `/query`（GET，3 s 超时），配 `kv_remote_settings_hif_max_retry_interval_secs` 远程重试间隔

---

### 3.5 hif 令牌通道（`x-hif-dliq` / `x-hif-leim` 的真实来源）

**结论：这两个头不是本地算出来的，而是两个远端 `/query` 接口返回的 `biz_data.value` 字符串，按 `x-hif-ttl` 响应头给的秒数定期刷新。**

请求构造（`defpackage/k01.smali`，`L700-960`）：

```java
gh5 b = new gh5();
bfb.b(b.a, "https://hif-dliq.deepseek.com/query");   // 另一处是 hif-leim
ni5 t = new ni5();
t.c(3000L); t.b(3000L); t.d(3000L);                  // connect/read/socket 均 3s
b.d(timeoutKey, t);
b.b = rg5.b;                                         // GET，无 body、无参数
new ki5(b, client).c(cont);
```

响应处理（`ab0.smali:4214` / `wa0.smali:8476`）：

```java
Integer ttl = lia.L(response.headers["x-hif-ttl"]);  // 解析响应头
if (ttl != null) o19.a = ttl.intValue();
// hs9.c 是响应体 JsonElement，用 lb5(HifQueryBizData{value:String}) 反序列化
mb5 token = new mb5(lb5.a, o19.a);                   // (令牌值, TTL 秒)
```

令牌管理器 `ib5`（`implements yc6`，即 Ktor 拦截器）：

| 字段 | 含义 | 写入点 |
|---|---|---|
| `ib5.a` | dliq 令牌 | 静态方法 `ib5.a(...)`：取到 `mb5` 后 `a = mb5.a`；若 `mb5.b > 0` 则 `delay(ttl*1000)` 后重试刷新 |
| `ib5.b` | leim 令牌 | 静态方法 `ib5.b(...)`，逻辑同上 |
| `ib5.c` | `k99` 缓存/配置句柄 | 构造时读 MMKV 键 `kv_settings_hif_max_retry_interval_secs` / `hif_max_retry_interval_secs` / `kv_remote_settings_hif_max_retry_interval_secs` / `kv_remote_settings_id_hif_max_retry_interval_secs`，缺省值取 `by2.M` |

注入（`ak.smali:908-964`，DefaultRequest lambda）：

```java
yy8.i(req, "x-device-model", Build.MODEL);
if (ib5.a != null) yy8.i(req, "x-hif-dliq",  ib5.a);
if (ib5.b != null) yy8.i(req, "x-hif-leim", ib5.b);
```

默认 TTL 初值 `0x258` = **600 秒**（`jsc.smali:4122`）。同一 DefaultRequest lambda 里的完整静态头序列：`Referer` → `x-client-platform` → `x-client-version` → `x-client-locale` → `x-client-bundle-id` → `x-client-timezone-offset`（`ZoneRules.getOffset().getTotalSeconds()`）→ `x-device-model` → `x-hif-dliq` → `x-hif-leim`。

**`x-ds-sse-heartbeat-timeout-secs` 同样是响应头**（`g0.smali:1805`、`vk0.smali:1050`）：客户端从 SSE 响应头读秒数，缺省 **10 秒**（`const-wide/16 v17, 0xa`），作为流心跳超时。

---

## 4. SSE 流式协议

- Content-Type：`text/event-stream`（`ic3.java:18`）
- 帧根：`SseMessageRoot{ response }`（`tba.java`），`response` 为动态 JSON
- 增量指令：`DeltaCommand{ p（path，必填）, o（op，必填）, v（value，可选） }`（`zu3.java`）
- op 取值（`sq2.java` 分派链 + dex 字符串）：**`APPEND`、`REPLACE`、`MERGE`**；另有 `snapshot` / `append` / `mutate` / `update` 出现在同一模块
- 语义：服务端下发 JSON-Patch 风格指令，客户端把它折叠成 `AppStaticMessage.fragments` 列表
- 片段类型（`StaticChatMessageFragment.*`）：`ThinkFragment`、`ResponseFragment`、`SearchFragment`、`ToolOpenFragment`、`ToolFindFragment`、`ReadLinkFragment`、`TipFragment`、`RequestFragment`、`UnknownFragment`
- 事件类型（`ChatCompletion*EventData`）：`ready`（request/response_message_id）、`title`、`toast`（finish_reason）、`close`、`update_session`、`check_client_update`、`update_parent_message`、`auto_tts_capability`
- 心跳：header `x-ds-sse-heartbeat-timeout-secs`（值由服务端下发）

---

## 5. 登录/注册请求字段速查

| 接口 | 请求体字段 |
|---|---|
| `users/login`（邮箱） | `email, password, device_id, credential_id?` |
| `users/login`（手机） | `mobile, area_code?, password, device_id, credential_id?` |
| `users/login_by_mobile_sms` | `mobile_number, sms_verification_code, area_code, device_id` |
| `users/register`（邮箱） | `region, locale, device_id, payload{email, email_verification_code, password}` |
| `users/create_sms_verification_code` | `mobile_number, ticket, locale, shumei_verification{region,rid}, hcaptcha_token, device_id, scenario` |
| `users/create_email_verification_code` | `email, locale, shumei_verification, hcaptcha_token, turnstile_token?, device_id, scenario` |
| `users/check_sms_code` | `area_code, mobile_number, ticket, sms_verification_code, scenario` |
| `users/mfa/create_verification_code` | `mfa_session_id, shumei_device_id, shumei_verification?, hcaptcha_token?, turnstile_token?` |
| `users/mfa/verify_signature` | `mfa_session_id, mfa_signature` |
| `users/mfa/trusted_device/register` | `mfa_ticket, mfa_public_key, mfa_algorithm` |
| `users/oauth/wechat/login` | `device_id, code, channel` |
| `users/oauth/google/login` | `device_id, id_token, shumei_verification, hcaptcha_token` |
| `users/one_tap_login` | `fly_verify{token, op_token}` |
| `chat/completion` | `chat_session_id, parent_message_id, prompt, ref_file_ids?, thinking_enabled?, search_enabled?, audio_id?, preempt, model_type?, action?` |
| `chat/regenerate` | `chat_session_id, child_message_id, thinking_enabled, search_enabled, user_options?{verbosity, search}` |
| `chat/edit_message` | `chat_session_id, message_id, prompt, ref_file_ids?, thinking_enabled, search_enabled, client_stream_id?, action?` |
| `chat/resume_stream` | `chat_session_id, message_id, interaction_type` |
| `chat/stop_stream` | `chat_session_id, message_id` |

响应外壳：`ServerBodyResponse{code,msg,data}` ⊃ `ServerResponseBizDataWrapper{biz_code,biz_msg,biz_data}`。

---

## 6. 结论与待确认

**已完全确定**：全部 80 条接口路径与所属模块、请求体混合加密算法与两把 RSA 公钥、12 条加密白名单、7 条 GuestPow 白名单、PoW 的哈希算法（**改造版 Keccak：rate136/域0x06/只跑 23 轮且跳过 RC[0]**，非标准 SHA3-256）与求解结构、通用请求头、SSE 增补协议（APPEND/REPLACE/MERGE）、222 个请求/响应模型的字段名与顺序。

**已用 smali 补齐**（原 jadx `Method dump skipped` 的部分）：
- `x-hif-dliq` / `x-hif-leim` 的完整生成与注入链路（见 §3.5），以及 `x-hif-ttl`、`x-ds-sse-heartbeat-timeout-secs` 均为**响应头**而非请求头
- DefaultRequest 拦截器的完整静态头序列与顺序
- **PoW 全部参数绑定**（见 §3.2 参数绑定小节）：`challenge` 为 hex 串并解出 32 B 目标、`base = salt + "_" + expire_at + "_"`、`difficulty` 为 nonce 上界、`algorithm == "DeepSeekHashV1"`、答案 = `Base64(JSON(AuthedPowSolution))`
- **接口 → HTTP 方法**：全量 smali 扫描出 70+ 条明确方法，落盘 `work/api_methods.txt`

**仍待确认**（静态已到边界）：
1. `answer` 在 `AuthedPowSolution` JSON 中的类型（long 数字 vs 字符串）——需一次真实响应比对
2. `libsmsdk.so`（数美设备指纹）、`pairip` 保护壳是否影响运行时行为
3. 少数接口（`chat/completion`、`index/query`、`client/settings/report` 等）方法常量由外层 builder 传入，扫描结果标 `?`，按上下文推断为 POST

**产物索引**：
- 全量模型字段：`work\models_dump.txt`（222 个类）
- 反编译源码：`work\jadx_out\sources`（14,101 个 .java）
- dex 字符串表：`work\dex_strings.txt`（71,763 条去重）
- 工具链：`tools\scan_java.py`、`disas.py`、`elf_sym.py`、`dump_str.py`、`g.py`、`dump_models.py`

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

### 7.7 纯协议登录实测记录（demo.user@example.com）

| 结论 | 证据 |
|---|---|
| 请求体加密正确 | `os=android` + RSA-OAEP(SHA-256)/AES-128-CBC + `x-request-encryption-key` → 服务端解密成功（422 报缺字段而非 40006） |
| 服务端不强制加密 | 明文 JSON 同样返回业务码 |
| 凭据正确 | 错密码 → `biz_code 2 PASSWORD_OR_USER_NAME_IS_WRONG`；正确密码 → `biz_code 11` |
| 登录前无 PoW 通道 | `create_pow_challenge` 需 token（40002）；`create_guest_challenge` 对 login 返回 `INVALID_TARGET_PATH` |
| 11 与 UA/TLS/IP/头/device_id 形态无关 | 浏览器 UA、curl_cffi `impersonate=chrome`、直连/代理、`x-hif-*`、`x-device-id`(UUIDv4)、32hex/UUID device_id 全部仍 11 |
| 账号维度限流 | 高频尝试后 `40029 TOO_MANY_REQUESTS`，冷却需数十分钟 |

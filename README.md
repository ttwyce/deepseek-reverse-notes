# DeepSeek 逆向工程：数美点选求解器 + 纯协议登录

> ## ⚠️ 风险提示与使用限制（请先阅读）
>
> 本项目是**个人安全研究笔记**，不是任何服务的官方客户端或产品，与 DeepSeek、数美（Shumei）等公司无任何隶属或授权关系。使用前请完整阅读 [DISCLAIMER.md](DISCLAIMER.md)。
>
> - **法律与合规风险**：逆向工程、协议复刻与自动化访问的合法性因司法辖区而异。使用者须自行确认其行为符合所在地适用法律（著作权、计算机信息系统安全、数据与个人信息保护、反不正当竞争等）以及服务方的服务条款。**违反服务条款可能导致账号被永久封禁，并可能承担民事或刑事责任。**
> - **明确禁止用途**：批量注册、养号、账号买卖、撞库、密码喷洒、账号接管、绕过风控/配额/付费牟利、爬取他人数据、拒绝服务或任何干扰服务可用性的行为。
> - **无担保**：全部代码按「现状」（AS IS）提供，作者不保证可用性、正确性、稳定性与安全性，亦不对任何使用后果承担责任。
> - **无真实凭据**：仓库内全部账号、邮箱、密码、token、user id、设备指纹均为占位符或示例值；请勿在 Issue / PR 中提交真实凭据。
> - **无第三方转储**：DeepSeek / 数美的前端 bundle、APK 字符串转储、原始 captcha SDK、第三方指纹 SDK 均**已从仓库移除且不再分发**（版权归各自权利人所有），仓库仅保留原创分析代码与自建测试向量。
>
> 授权范围：**作者原创**代码与文档以 [MIT License](LICENSE) 授权；该许可不覆盖任何第三方材料，也不构成对任何第三方商标的使用许可。

对 DeepSeek（Android v2.7.1 / Web）的协议层逆向成果，包含：

- **数美（Shumei）spatial_select 点选验证码纯 Python 求解器** —— 不依赖浏览器，10/10 通过，平均 3.8 秒
- **DeepSeek 纯协议登录全链路** —— PoW 求解 → 请求体加密 → 邮箱 MFA → 受信设备 ES256 免 MFA
- **数美 SDK 离线反混淆工具链** —— 字符串表还原，可复用于其他版本

---

## 一、核心能力

| 能力 | 脚本 | 耗时 | 说明 |
|---|---|---|---|
| 数美点选验证码求解 | `tools/shumei_solver.py` | 3.8 s | 纯 HTTP + OpenCV 风格图像处理 |
| 受信设备免 MFA 登录 | `tools/sm_trusted_login.py` | ~2 s | 零邮件、零验证码 |
| 邮箱 MFA 登录（首次授权） | `tools/sm_full_login.py` + `tools/sm_mfa_check.py` | ~3 s + 等邮件 | 需人工提供 6 位验证码 |
| GuestPoW 求解 | `tools/deepseek_pow.py` | <1 s | 非标准 Keccak |
| 已授权 API 调用 | `tools/deepseek_api.py` | — | `current` / `sessions` / `chat` |
| 隐私开关「数据用于优化体验」 | `tools/deepseek_client.py training` | ~1 s | `users/settings` 读 + `users/update_settings` 写，写完回读校验 |
| **境外邮箱注册（全自动）** | `tools/reg_auto.py` | ~8 s + 等邮件 | 需非大陆 IP；数美自动解 + Gmail IMAP 自动取码 |
| 境外邮箱注册（人工抄码） | `tools/reg_flow.py` | ~3 s + 等邮件 | 同上，验证码由人工输入 |
| Gmail 收码 | `tools/gmail_code.py` | ~2 s | IMAP over SSL，支持 `demo.user+N@example.com` 别名 |

---

## 二、数美 spatial_select 逆向结论

### 协议

```
GET  /ca/v1/register     → 拿题（不带任何指纹即可）
GET  /ca/v2/fverify      → 提交答案（JSONP，全部字段在 query）
POST /ca/v1/log          → 埋点（明文 JSON）
```

- `organization = P9usCUBauxft8eAmUXaZ`，`appId = default`，`model = spatial_select`
- 题目图片是静态 JPG（600×300），直接 `GET https://castatic.fengkongcloud.cn<detail.bg>` 下载
- register 返回：`{bg, bg_height, bg_width, k, l, order, rid}`

### 答案加密：DES-ECB + ZeroPadding + Base64

```python
encrypt(value, salt) = base64( DES_ECB(key=salt(8字节ASCII), data=utf8(value) 补 \0 到 8 倍数) )
```

已用 **195/195** 组向量与 SDK 逐字节比对通过。

verify 请求字段：

| 字段 | 明文 | salt |
|---|---|---|
| `pe` | 点击坐标数组 | `e1024477` |
| `yc` | 鼠标轨迹（同 selectData） | `803d9d10` |
| `xt` | `endTime - startTime` | `e6c8d743` |
| `qf` / `qs` | 显示宽 / 高（294 / 147） | `d809f47c` / `210a5a6d` |
| `vf` / `ri` / `cx` / `is` | appId / channel / lang / 环境标志 | `3ae79dfa` / `fa1b1f22` / `10c0600a` / `53cda785` |
| `pr` / `vn` / `kh` | console / bot 检测 / 常量 | `f2858cfa` / `df29aa2d` / `9728245c` |

### 三大约束（决定架构）

1. **verify 一次性** —— 同一 `rid` 首次提交后即失效，后续一律 `REJECT`。必须一次命中。
2. **同一 captchaUuid 不能连续 register** —— 会被判定为脚本，后续 verify 全部拒绝。
3. **题目是「颜色 + 形状」双限定** —— 「最小的黄色六棱柱」= 所有黄色六棱柱中面积最小的那个。

因此求解器采用 **「多 uuid 并发拿题 + 串行提交 + 失败换新题」**，把单次 ~35% 的识别率通过重试提到 100%。

### 图像识别

- 数美只用 **4 种颜色**：红 hue≈0、黄≈38、绿≈125、蓝≈208
- 逐像素归到最近色 hub（含 360° 环绕），再对每色单独做 `closing(5) + opening(3)` 连通域
- **先分色再连通**是关键：不同颜色的粘连会天然断开，同色亮面暗面不会被撕裂
- 取同色面积最小者的 bbox 中心作为点击坐标

---

## 三、DeepSeek 纯协议登录

### 完整链路

```
PoW 求解（DeepSeekHashV1，23 轮 Keccak，跳过 RC[0]）
  └─ 请求体 AES-128-CBC 加密 + RSA-OAEP 包裹 key||iv
       └─ POST /api/v0/users/login（body.device_id = "B" + 数美 deviceId）
            ├─ biz_code 13 → ES256 受信设备签名 → POST /mfa/verify_signature → token
            └─ biz_code 14 → 邮箱 MFA → POST /mfa/check_verification_code → token
```

### 受信设备（免 MFA）关键点

| 位置 | 必须用 | 用错的后果 |
|---|---|---|
| `body.device_id` | `B<smid>`（89 字符） | `biz_code 11 RISK_DEVICE_DETECTED` |
| `header x-device-id` | 注册时的 UUID v4 | `biz_code 4`，降级要求 OTP |

- 公钥 = **SPKI DER 的 base64**
- 签名输入 = `challenge\n(sessionId|registerTicket)\ncredentialId\naction`
- 签名输出 = **ECDSA P-256 SHA-256 的 64 字节 r||s**，再标准 base64

### MFA 接口例外

`mfa/create_verification_code` 与 `mfa/check_verification_code` **不在加密白名单**，加密请求返回 `40007 REQUEST_DECRYPT_NOT_ALLOWED`，必须明文 JSON。

---

## 四、隐私开关：「数据用于优化体验」

对应 Web 设置里的 **Improve the model for everyone / 允许将内容用于训练与优化服务**（埋点 `switchAllowTraining`）。

| 操作 | 方法 | 路径 | 载荷 |
|---|---|---|---|
| 读状态 | GET | `/api/v0/users/settings` | 响应 `data.biz_data.training_allowed`（bool） |
| 改状态 | POST | `/api/v0/users/update_settings` | 请求体 `{"training_allowed": true/false}` |

关键结论（已实测：读 → 写 → 回读 → 还原）：

- **写入成功响应不回显状态**：`{"code":0,"data":{"biz_code":0,"biz_data":null}}`，必须回读 `users/settings` 校验。Web 端同样靠乐观更新本地缓存，不依赖响应体。
- **请求头只要 `Authorization: Bearer <token>` + 标准 `x-client-*` 头**；已登录接口不做 GuestPoW。
- **不需要 `x-settings-token`**：该头只由 `/api/v0/client/settings` 与 `/client/settings/report` 的拦截器注入，`users/settings` 不走它。
- **body 明文 JSON，不加密**：Web 的请求体加密拦截器只对白名单路径生效（`eN={chat:new Set([...ej,"oauth/apple/mobile_verification","miniprogram/mobile_verification"].map(e=>"/api/v0/users/"+e))}`），`update_settings` 不在其中。

```powershell
.venv\Scripts\python.exe tools\deepseek_client.py training              # 读，输出 {"training_allowed": false}
.venv\Scripts\python.exe tools\deepseek_client.py training --set true   # 打开（回读校验，applied=true 才算成功）
.venv\Scripts\python.exe tools\deepseek_client.py training --set false  # 关闭
```

> 检查开关状态时请用 `--token-file` 指定对应账号的登录态（默认 `work/auth_token.json`），避免误改他人账号。

---

## 五、目录结构

```
tools/
  shumei_solver.py        数美求解器（对外 solve()）
  sm_crypto.py            DES-ECB + ZeroPadding + base64
  sm_cv4.py               4 色 hub 分色连通域识别
  sm_verify_probe.py      register / build_body / verify / jsonp_get 底层
  sm_solve.py             单次尝试版（--retry 换题）
  sm_strtab.py            数美 SDK 字符串表还原（浏览器内执行 header）
  sm_deob.py              字符串表回填，产出可读 SDK
  sm_dict.py / sm_fn.py / sm_grep.py / sm_slice.py / sm_pretty.py   反混淆辅助
  sm_hue_stat.py          色相分布统计
  sm_dataset.py           形状数据集收集
  sm_full_login.py        登录 → 解数美 → MFA 发码
  sm_mfa_check.py         MFA 验证码 → token
  sm_save_token.py        token DPAPI 加密落盘
  sm_trusted_device.py    受信设备注册（ES256）
  sm_trusted_login.py     受信设备免 MFA 登录
  sm_check_device.py      三组对照诊断
  deepseek_pow.py         GuestPoW 求解（23 轮 Keccak）
  deepseek_client.py      客户端（未授权阶段 + 隐私开关 training）
  deepseek_api.py         已授权客户端
  token_store.py          token 存储（DPAPI）
  reg_flow.py             境外邮箱注册（send / verify / show）
  reg_auto.py             境外邮箱注册全自动流水线（发码 → IMAP 取码 → register → 校验）
  gmail_code.py           Gmail IMAP 取 6 位验证码（check / code）
  check_code.py           check_email_code 诊断（仅适用忘记密码语义）
  verify_token.py         token 有效性校验（users/current）

work/
  数美求解器_交付.md                       数美协议与求解器完整交付说明
  DeepSeek_2.7.1_逆向报告.md               APK 静态逆向报告
  DeepSeek_纯协议登录_最终交付.md          登录链路结论与排除实验
  DeepSeek_邮箱注册_交付.md                邮箱注册全链路、错误码表与踩坑证伪
  api_methods.txt                         80 条接口路径 ↔ HTTP 方法
  sm/                                    （第三方原始 SDK / 转储已移除，不再分发）
  sm/captcha-sdk.deob.js                  反混淆后可读版
  sm/strtab.json                          2620 条字符串表
  sm/vectors.json                         195 组 DES 测试向量
```

---

## 六、快速开始

```powershell
# 环境（全部装在当前目录，不污染系统）
python -m venv .venv
$env:PIP_CACHE_DIR = "$PWD\.cache\pip"
.venv\Scripts\pip install requests cryptography pillow numpy scipy playwright

# 数美求解器自测
.venv\Scripts\python.exe tools\shumei_solver.py --n 5

# 受信设备注册（一次性）
.venv\Scripts\python.exe tools\sm_trusted_device.py

# 免 MFA 登录
.venv\Scripts\python.exe tools\sm_trusted_login.py

# 验证 token
.venv\Scripts\python.exe tools\deepseek_api.py current

# 读 / 改「数据用于优化体验」开关（默认读 work/auth_token.json 的登录态）
.venv\Scripts\python.exe tools\deepseek_client.py training
.venv\Scripts\python.exe tools\deepseek_client.py training --set false
```

---

## 七、数美 SDK 反混淆方法（可复用于其他版本）

SDK 是 obfuscator.io 产物：

- `_0x127b()` 返回字符串数组，`_0x3634(i)` 就是 `arr[i - 431]`（**无解密运算**）
- 外层有一个旋转 IIFE，按校验和循环 `push(shift())` 直到匹配

流程：

1. `tools/sm_strtab.py` —— 在浏览器里只执行「header（数组函数 + 解码函数 + 旋转 IIFE）」，导出全表
2. `tools/sm_deob.py` —— 收集 566 个解码器别名，替换 5293 处调用，得到可读 SDK

> 数美会随 SDK 小版本（v1.0.4-148…210）更换 DES key 与参数名，换版本需重跑上述两步。

---

## 八、免责声明与法律提示

> 本章为摘要，**完整条款以 [DISCLAIMER.md](DISCLAIMER.md) 为准**。

1. **性质**：本项目为个人安全研究与协议学习笔记，非官方客户端、非受支持产品，与 DeepSeek、数美（Shumei）、火山引擎等公司无隶属、合作、授权或背书关系。
2. **合法性自负**：逆向工程与自动化访问的合法性因司法辖区而异。使用者须自行确认符合所在地全部适用法律及目标平台的服务条款；使用者对自身行为承担全部法律与合同责任，作者不承担任何责任。
3. **禁止用途**：批量注册、养号、账号买卖、撞库、密码喷洒、账号接管、越权访问他人账号、绕过风控/配额/付费限制牟利、爬取他人数据或个人信息、拒绝服务与任何干扰服务可用性的行为。
4. **仅限自有账号**：任何自动化操作仅限使用者**自己拥有并有权操作**的账号；请勿代他人操作，勿共享 token。
5. **无担保与责任限制**：内容按「现状」提供，不附带任何明示或默示担保；作者不对任何直接、间接、附带或后果性损害（含账号损失、数据丢失、利润损失、第三方索赔）承担责任。
6. **凭据**：仓库内全部账号、邮箱、密码、token、user id 与设备指纹均为占位符或示例值，不含任何真实凭据或个人数据。发现残留请提 Issue，作者将尽快删除。
7. **权利人通知**：任何权利人若认为本仓库内容侵犯其合法权益，可提出通知，作者将在合理时间内删除或修改相关内容。

---

## 九、第三方材料与版权

1. 本仓库**不包含、不再分发**任何第三方原始文件或转储，下列内容已被有意排除（`.gitignore` 亦已屏蔽，避免再次误入库）：

   | 已移除内容 | 说明 | 权利人 |
   |---|---|---|
   | `work/web_main.js` | DeepSeek Web 前端 bundle | DeepSeek |
   | `work/web_vendors.js` | DeepSeek Web 依赖 bundle | DeepSeek 及其第三方依赖作者 |
   | `work/web_index.html` | DeepSeek Web 入口 HTML | DeepSeek |
   | `work/fp.min.js` | 第三方设备指纹 SDK | 其原始作者 |
   | `work/sm/captcha-sdk.min.js` | 数美 captcha SDK 原始压缩文件 | 数美（Shumei） |
   | `work/dex_strings.txt` | DeepSeek APK dex 字符串转储 | DeepSeek |

2. 如研究需要上述材料，请**自行从合法渠道获取**并遵守其许可条款；本仓库只描述方法，不提供其副本。
3. 仓库保留的 `work/sm/captcha-sdk.deob.js`、`work/sm/strtab.json`、`work/sm/vectors.json` 等为**分析产物**（符号还原片段与自建测试数据），仅用于说明去混淆与加密流程；如权利人提出异议，作者将按要求删除。
4. DeepSeek、Shumei、Volcengine 等名称与商标归各自权利人所有，本仓库仅在描述性意义上指明研究对象，不构成任何授权、关联或背书。
5. `LICENSE` 中的 MIT 条款**仅覆盖作者原创代码与文档**，不覆盖任何第三方材料。

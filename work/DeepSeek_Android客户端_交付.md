# DeepSeek Android 客户端模拟 —— 交付文档

> 目标：模拟真实 Android 设备，纯协议完成「创建对话 / 发消息 / 取消息 / 深度思考开关 / 联网搜索开关 / 停止生成 / 删除对话」，并做好防封。
>
> 实现：`tools\ds_android_client.py`（不依赖浏览器，只用已授权 token）。

---

## 一、能力清单

| 能力 | 方法 | 接口 | 实测 |
|---|---|---|---|
| 创建对话 | `create_session()` | `POST /api/v0/chat_session/create` | ✅ 200 |
| 发送消息（流式） | `completion(sid, prompt, thinking, search)` | `POST /api/v0/chat/completion` | ✅ 200 SSE |
| 深度思考开关 | `thinking=True` → `thinking_enabled: true` | 同上 | ✅ 思考链与回答正确分离 |
| 联网搜索开关 | `search=True` → `search_enabled: true` | 同上 | ✅ 返回 `[citation:N]` |
| 获取消息 | `history(sid)` | `GET /api/v0/chat/history_messages` | ✅ 200 |
| 会话列表 | `sessions(count)` | `GET /api/v0/chat_session/fetch_page` | ✅ 200 |
| 停止生成 | `stop_stream(sid, message_id)` | `POST /api/v0/chat/stop_stream` | ✅ 200，消息标记 `INCOMPLETE` |
| 删除对话 | `delete_session(sid)` | `POST /api/v0/chat_session/delete` | ✅ 200 |

---

## 二、设备形态与依据

### 2.1 真实 App 的请求头（`work\smali\dex1\ak.smali:642-965`）

```
x-client-platform: android
x-client-version: 2.7.1
x-client-locale: <string resource 0x7f0f017a>
x-client-bundle-id: com.deepseek.chat
x-client-timezone-offset: <ZoneOffset.getTotalSeconds()>   → 28800
x-device-model: Build.MODEL
x-hif-dliq / x-hif-leim   （非空才加，APM 用）
```
App **不发** `Origin` / `Referer`；`Lafb;->a` 里存的是 `chat.deepseek.com`（Host，不是 Referer）。

### 2.2 UA 取舍（关键决策）

App 自身用 OkHttp 默认 UA `okhttp/4.12.0`，但实测被华为云 WAF 硬拦：

| 组 | UA | 请求头 | 结果 |
|---|---|---|---|
| A | `okhttp/4.12.0` | 完整 Android 头 | **429** `Error - Request Blocked` |
| B | `Chrome/156` 桌面 | 完整 Android 头 | 200 |
| C | `okhttp/4.12.0` | 无 x-client | **429** |
| D | `Chrome/156` 桌面 | 无 x-client | 200 |
| E | curl_cffi(chrome 指纹) + okhttp UA | 完整 Android 头 | **429** |
| F | curl_cffi(chrome 指纹) + Chrome UA | 完整 Android 头 | 200 |
| **G** | **Android 手机 UA** | 无 x-client | **200** |
| **H** | **Android 手机 UA** | 完整 Android 头 | **200（采用）** |
| I | Android 平板 UA | 无 x-client | 200 |

**结论**：
- WAF **只看 UA 是否含 `Mozilla`**，与 TLS 指纹无关。
- `curl_cffi` 没有 okhttp 指纹（`impersonate="okhttp4_12"` → `ImpersonateError`），Python 侧无法复刻 App 的 UA+TLS 组合。
- WAF cookie 不是放行凭证：同一 session 带 cookie 换 okhttp UA 仍 429，换回 Chrome 又 200。

**采用形态 H**：`Mozilla/5.0 (Linux; Android {ver}; {model}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Mobile Safari/537.36`
—— UA 是 Android 手机浏览器，与 `x-client-platform: android`、`x-device-model` **自洽**，既过 WAF 又不出现「okhttp UA 配 android 头」的矛盾指纹。

### 2.3 设备档案（持久化，固定不变）

`work\device_profile.json`，首次运行随机选机型后**永不改变**（避免设备指纹漂移）：

```json
{
  "device_model": "Pixel 7",
  "android_version": "14",
  "brand": "google",
  "chrome_major": "156",
  "timezone_offset": 28800,
  "locale": "zh_CN",
  "uuid_device_id": "1bdff51e-3305-46e8-a579-b091b8b7ee7d",
  "created_at": 1792978445
}
```

机型池：SM-G991B/13、SM-S9180/14、Pixel 7/14、2201123C/13、M2012K11AC/12、V2118A/12、PGT-AN10/13、PGZ110/13。

---

## 三、接口与请求体

| 接口 | Method | Body / Query |
|---|---|---|
| `/api/v0/chat_session/create` | POST | `{"character_id": null}` |
| `/api/v0/chat_session/fetch_page` | GET | `?count=20` |
| `/api/v0/chat/completion` | POST | `{chat_session_id, parent_message_id: null, prompt, ref_file_ids: [], thinking_enabled, search_enabled}` |
| `/api/v0/chat/history_messages` | GET | `?chat_session_id=<sid>` |
| `/api/v0/chat/stop_stream` | POST | `{chat_session_id, message_id}` |
| `/api/v0/chat_session/delete` | POST | `{chat_session_id}` |

### 响应结构

- `create` → `data.biz_data.chat_session.id`（**注意多一层 `chat_session`**）
- `history` → `data.biz_data.chat_session` + `data.biz_data.chat_messages[]`（`title` 由服务端自动生成）
- `fetch_page` → `data.biz_data.chat_sessions[]`
- `delete` / `stop_stream` → `{"code":0,"data":{"biz_code":0,"biz_data":null}}`

### stop_stream 的 message_id 来源

APK 模型 `ChatStopStreamRequest`（`defpackage\mr2.java`）字段为 `chat_session_id, message_id`。
`message_id` 取 completion 流的**首个事件** `{"request_message_id":1,"response_message_id":2,...}` 中的 `response_message_id`。

---

## 四、SSE 事件协议（核心）

```
event: ready
data: {"request_message_id":1,"response_message_id":2,"model_type":"default"}
event: update_session
data: {"updated_at":1792979154.037356}
data: {"v":{"response":{"message_id":2,"status":"WIP",...}}}          ← 完整消息快照
data: {"p":"response/fragments/-1/content","o":"APPEND","v":"想要"}    ← 建立片段
data: {"v":"写"}  data: {"v":"一篇"}  ...                              ← 只有 v = 上一个 p 的增量
data: {"p":"response/fragments/-1/elapsed_secs","o":"SET","v":0.79}
data: {"p":"response/fragments","o":"APPEND","v":[{"id":3,"type":"RESPONSE","content":"2",...}]}
data: {"p":"response","o":"BATCH","v":[{"p":"accumulated_token_usage","v":63},{"p":"quasi_status","v":"FINISHED"}]}
data: {"p":"response/status","o":"SET","v":"FINISHED"}
data: {"content":"一加一等于二"}                                        ← 标题事件
data: [DONE]
```

**解析规则**：

1. 带 `p` 的事件切换「当前路径」；**只带 `v`** 的事件延续上一个 `p`（增量）。
2. `p` 以 `/content` 结尾 → `v` 是增量字符串。
3. `p == "response/fragments"` → `v` 是**完整** fragment 列表，每项 `{id, type: "THINKING"|"RESPONSE", content}`。
4. **fragment 的 `content` 只携带该段首片段**，其余内容经 `response/fragments/-1/content` 增量下发。
5. 首个 `RESPONSE` fragment 出现前，`-1/content` 增量属思考；之后属回答。
6. 最终文本 = `frag_content + 后续增量`；若增量本身以 `frag_content` 开头则直接用增量（`_merge()`）。
7. **消息快照事件（无 `p`，形如 `{"v":{"response":{"fragments":[...]}}}`）也是 fragment 的来源**，且首个 `RESPONSE` fragment 常常**只出现在这里**（不会再有 `p == "response/fragments"` 事件）。必须同样据此切换 phase，否则单片段回答（如「2」「苹果、香蕉、橙子」）会被整段误归入 thinking，表现为 `text` 为空。
8. 收到 `{"p":"response/status","o":"SET","v":"FINISHED"}` 即可主动 break —— 服务端之后还会发标题事件并长时间不关连接，不 break 会让单轮多等数十秒。

**三次解析错误（教训）**：
- 把 `p` 含 `content` 的都当回答 → thinking 混进 text。
- 按 `type` 分类但用覆盖写入 → 同 id 多次 APPEND 只留最后一段。
- 二选一（frag 或增量）→ 只剩首片段（如 `'按'`）。**必须拼接。**

---

## 五、防封策略

| 措施 | 实现 |
|---|---|
| 设备指纹固定 | `work\device_profile.json` 持久化，`x-device-id` 永不变 |
| 形态自洽 | Android 手机 UA + `x-client-platform: android` + 同机型 `x-device-model` |
| 先访问首页 | `warmup()` GET `chat.deepseek.com/` 拿 WAF cookie（真实浏览器行为） |
| 人类节奏 | `_pace()` 每次请求前随机 1.2~3.5s，**绝不并发** |
| 429 退避 | `[0, 3, 8, 20]` 秒指数退避，不硬刚 |
| 连接复用 | 单 `requests.Session`，复用 TCP 与 cookie |
| PoW 必解 | 每次 completion 前取 challenge 并求解 `DeepSeekHashV1` |
| 不加 Web 头 | 不发 `Origin` / `Referer`（App 不发，加了反而暴露） |
| 不碰加密白名单外接口 | MFA 等接口只收明文（见下） |

**已验证的反例**：`okhttp/*` UA 直接 429；带 WAF cookie 也不能豁免。

---

## 六、使用示例

```bash
# 全流程自检
python tools\ds_android_client.py test

# 普通对话
python tools\ds_android_client.py chat "你好"

# 深度思考
python tools\ds_android_client.py chat "9.11 和 9.9 哪个大？" --thinking

# 联网搜索
python tools\ds_android_client.py chat "今天山东聊城的天气怎么样？" --search

# 两者同时
python tools\ds_android_client.py chat "分析下今天的新闻" --thinking --search

# 其它
python tools\ds_android_client.py sessions
python tools\ds_android_client.py history <session_id>
python tools\ds_android_client.py delete <session_id>
python tools\ds_android_client.py current
```

### 作为库使用

```python
from ds_android_client import AndroidClient

c = AndroidClient()
sid = c.create_session()
out = c.completion(sid, "你好", thinking=True, search=False)
print(out["thinking"])   # 思考链
print(out["text"])       # 最终回答
print(out["response_message_id"])   # 可用于 stop_stream
c.delete_session(sid)
```

---

## 七、实测记录

| 场景 | 结果 |
|---|---|
| `test` 全流程 | current 200 / create 200 / completion 200（30 事件）/ history 200 / sessions 200 / delete 200 |
| `--search`「今天山东聊城的天气怎么样？」 | 200，72 事件，回答含 `[citation:1][citation:4][citation:5]`，内容「聊城是小雨或阵雨，8℃~16℃」 |
| `--thinking`「9.11 和 9.9 哪个大？」 | 200，172 事件，`thinking` 完整思考链，`text` = 「按小数比较 9.9 大 / 按版本号比较 9.11 大」 |
| `stop_stream` 中途停止 | 200，3.76s 终止（原任务 2000 字），历史消息 `status=INCOMPLETE` |
| **连续压测（同会话 8 轮）** | **8/8 成功，0 次 429**，总 345.9s |
| **连续压测（同会话 6 轮，修复后）** | **6/6 成功，0 次 429**，总 174.8s，`text` 全部完整，`history` 12 条，`delete` code=0 |

### 单轮耗时说明

实测 14.9s ~ 66.6s 波动，且与回答长度无关（短回答也可能 60s+）。原因在**服务端排队**（免费账号高峰），非客户端逻辑；客户端侧固定开销约为 PoW 求解（难度 20，1~3s）+ 随机间隔 1.2~3.5s + 一次首页 warmup。


---

## 八、文件清单

| 文件 | 说明 |
|---|---|
| `tools\ds_android_client.py` | 主客户端（设备档案、请求头、PoW、SSE 解析、六项能力） |
| `tools\ds_test_stop.py` | stop_stream 验证脚本 |
| `tools\ds_probe_headers.py` | UA/WAF 对照探测（A~I 九组） |
| `tools\deepseek_pow.py` | PoW 求解（Keccak-f 23 轮，跳过 RC[0]） |
| `tools\token_store.py` | token 的 DPAPI 加密落盘 |
| `tools\sm_trusted_login.py` | 免 MFA 登录（ES256 受信设备） |
| `work\device_profile.json` | 设备档案（持久化） |
| `work\models_dump.txt` | 222 个 kotlinx 模型（含 `ChatStopStreamRequest`） |
| `work\api_methods.txt` | 80 条接口表 |

---

## 九、已知限制

1. **UA 无法 100% 等同 App**：App 用 `okhttp/4.12.0` + BoringSSL TLS 指纹，Python 无法复刻（WAF 硬拦 + curl_cffi 无 okhttp 指纹）。当前方案是「Android 手机浏览器」，属于合理且自洽的形态。
2. **`stop_stream` 需 message_id**：必须先读流首事件。若在 completion 的封装接口里调用，需先拿到 `response_message_id`。
3. **`search_enabled` 字段名未在 dex 中直接出现**（只有 KV 键 `kv_settings_conversation_search_enabled`），但实测生效；若某版本失效，需重新从 APK 提取 completion 请求体模型。

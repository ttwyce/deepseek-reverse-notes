# 免责声明 / 风险提示 / Legal Notice

> 本文件适用于本仓库（`deepseek-reverse-notes`）的全部内容。
> 使用、复制、克隆、运行本仓库任何代码或参考任何文档之前，请完整阅读本文件。
> 中文为正文，英文对照见下半部分。**中文与英文如有歧义，以中文为准。**

---

## 一、项目性质

1. 本仓库是**个人网络安全学习与技术研究笔记**，记录对 DeepSeek 客户端与数美（Shumei）验证码 SDK 的协议层研究过程。
2. 本仓库**不是**任何服务的官方客户端、官方 SDK、官方文档或受支持的产品，与 DeepSeek（杭州深度求索人工智能基础技术研究有限公司）、数美（北京数美时代科技有限公司）、火山引擎（Volcengine）及其关联公司**没有任何隶属、合作、授权或背书关系**。
3. 仓库中的全部代码按「现状」（AS IS）提供，用于学习与研究，**不承诺可用性、正确性、稳定性或安全性**。

## 二、法律与合规责任（请务必自行判断）

1. **合法性因司法辖区而异**。逆向工程、抓包分析、协议复刻与自动化（机器人）操作，在不同国家和地区可能合法，也可能构成违法。使用者须**自行确认**其使用行为符合所在地适用的全部法律与行政法规，包括但不限于：
   - 著作权及相关邻接权法律；
   - 计算机信息系统安全 / 网络犯罪相关法律（如《中华人民共和国刑法》第 285、286 条，《中华人民共和国网络安全法》，《中华人民共和国数据安全法》）；
   - 个人信息保护相关法律；
   - 反不正当竞争法。
2. **服务条款（ToS）**：自动化访问、协议复刻、验证码自动化通常**明确违反**服务方的用户协议与反自动化条款。使用者应自行评估并承担账号被封禁、内容被删除、订阅被终止等后果。
3. 使用者因使用本仓库内容而产生的**任何**直接或间接后果（包括但不限于法律追责、行政处理、民事赔偿、账号与资产损失），**由使用者自行承担**，作者不承担任何责任。

## 三、明确禁止的用途

无论所在地法律如何规定，以下用途均**明确禁止**，作者不为其提供任何支持或辩护：

- 批量注册账号、养号、账号买卖、租售；
- 撞库、密码喷洒、账号接管（ATO）、越权访问他人账号；
- 绕过风控、验证码、配额或付费限制以牟利；
- 爬取他人数据、抓取个人信息，或对本项目涉及的平台实施任何形式的滥用；
- 拒绝服务攻击、干扰服务可用性、对服务端施加异常负载；
- 规避地域限制进行违法活动，或用于任何违反当地法律的目的。

## 四、凭据与个人数据

1. 本仓库内的所有账号、邮箱地址、密码、token、user id、设备指纹均已被替换为**占位符或示例值**（如 `demo.user@example.com`、`YOUR_PASSWORD`、全零 UUID），不含任何真实凭据或个人数据。
2. 请勿在 Issue、Pull Request、Commit 或任何公开渠道中提交真实凭据、token、Cookie 或他人个人信息。
3. 如果你发现本仓库仍残留任何真实凭据或个人数据，请通过 Issue 告知，作者会在第一时间删除。

## 五、第三方知识产权

1. DeepSeek、数美（Shumei）、Volcengine、obfuscator.io、core-js 等名称、商标、服务标记、界面与代码，**归各自权利人所有**。本仓库使用这些名称仅用于**描述性、指示性说明**（指明研究对象），不构成商标使用授权，也不表示任何关联或背书。
2. 本仓库**不包含、不再分发**下列第三方原始文件或转储，它们被有意排除在版本库之外：
   - DeepSeek Web 前端 JavaScript bundle（`main.js` / `default-vendors.js`）与其 HTML 入口页；
   - DeepSeek Android APK 的 dex 字符串转储；
   - 数美 captcha SDK 原始压缩文件（`captcha-sdk.min.js`）；
   - 第三方设备指纹 SDK（`fp.min.js`）。
   如研究需要，请**自行从合法渠道获取**并遵守其许可条款；本仓库仅提供分析脚本与自建测试数据。
3. 仓库保留的 `work/sm/captcha-sdk.deob.js`、`work/sm/strtab.json` 等属于**分析产物**（符号还原结果与自建索引），仅用于说明去混淆方法；如权利人认为其构成侵权，请联系删除。
4. 任何权利人若认为本仓库内容侵犯其合法权益，可通过 Issue 或仓库所有者主页所列联系方式提出，作者将**在合理时间内删除或修改**相关内容。

## 六、无担保与责任限制

在法律允许的最大范围内：

1. 本仓库内容按「现状」提供，**不附带任何明示或默示的担保**，包括但不限于适销性、特定用途适用性、不侵权、无错误或无中断运行的担保。
2. 作者**不对任何损害承担责任**，包括但不限于直接、间接、附带、特殊、惩罚性或后果性损害，以及利润损失、数据丢失、业务中断、账号损失或第三方索赔，无论其基于合同、侵权（含过失）、严格责任或其他理论，即使已被告知该等损害的可能性。
3. 使用者对自身运行环境、数据备份与合规审查负全部责任。

## 七、许可范围

- 本仓库中**作者原创**的代码与文档以 [MIT License](LICENSE) 授权。
- MIT 许可**不覆盖**任何第三方材料（见第五节），也不构成对任何第三方商标或服务的使用许可。
- 若本文件与 `LICENSE` 冲突，**以本文件中更严格的限制为准**。

## 八、适用法律与争议解决

本文件不创设任何合同关系。若因本仓库内容产生争议，适用仓库所有者所在地法律；但因使用者自身违法行为所产生的责任，不受此条影响，与作者无关。

---

# Disclaimer / Legal Notice (English)

> This applies to the entire repository `deepseek-reverse-notes`.
> Read it fully before using, copying, cloning or running anything here.
> The Chinese text above is authoritative; this English version is a courtesy translation.

## 1. Nature of the project

This is a **personal security-research notebook** documenting protocol-level study of the
DeepSeek client and the Shumei captcha SDK. It is **not** an official client, official SDK,
official documentation or supported product of any service, and it is **not affiliated with,
endorsed by, or authorised by** DeepSeek, Shumei (数美), Volcengine, or any of their affiliates.
All code is provided **AS IS**, for study only, with no guarantee of usability, correctness,
stability or security.

## 2. Legal and compliance responsibility

1. **Legality varies by jurisdiction.** Reverse engineering, traffic analysis, protocol
   re-implementation and automation may be lawful in some countries and unlawful in others.
   You must independently verify that your use complies with all applicable laws, including
   copyright law, computer-misuse / cybercrime law, data-protection law and unfair-competition law.
2. **Terms of Service.** Automated access, protocol re-implementation and captcha automation
   typically **violate** the target service's terms. You accept the consequences, including
   account suspension or termination.
3. **You bear all consequences** of using this material. The author accepts no liability
   whatsoever for legal action, administrative penalties, damages, account loss or any other
   outcome arising from your use.

## 3. Prohibited uses

Regardless of local law, the following are **expressly prohibited**: bulk account registration,
account trading, credential stuffing, password spraying, account takeover, unauthorised access,
circumventing risk controls / captchas / quotas / paywalls for profit, scraping other people's
data or personal information, denial-of-service or any interference with service availability,
and any use that violates applicable law.

## 4. Credentials and personal data

All accounts, e-mail addresses, passwords, tokens, user IDs and device fingerprints in this
repository have been replaced with **placeholders or example values**. It contains no real
credentials or personal data. Do not submit real credentials, tokens, cookies or third-party
personal data via Issues, Pull Requests or Commits. If any real credential or personal data is
found, please report it and it will be removed promptly.

## 5. Third-party intellectual property

Names, trademarks, service marks, interfaces and code of DeepSeek, Shumei, Volcengine,
obfuscator.io and core-js belong to their respective owners. Such names are used here only
descriptively, to identify the subject of study. This repository **does not contain and does not
redistribute** any original third-party bundle, APK string dump or SDK binary; those files have
been deliberately excluded. Obtain any such material yourself from lawful sources and comply
with its licence. Analysis artefacts that remain (e.g. symbol-restored fragments and self-built
string indices) exist solely to illustrate the deobfuscation method; rights holders may request
their removal, and the author will comply within a reasonable time.

## 6. No warranty; limitation of liability

To the maximum extent permitted by law, the content is provided **without any warranty** of any
kind, express or implied, including merchantability, fitness for a particular purpose,
non-infringement, accuracy, or uninterrupted operation. The author shall **not be liable** for
any direct, indirect, incidental, special, punitive or consequential damages, including lost
profits, lost data, business interruption, account loss or third-party claims, whether in
contract, tort (including negligence), strict liability or otherwise, even if advised of the
possibility of such damages.

## 7. Licence scope

Original code and documentation authored by the repository owner are licensed under the
[MIT License](LICENSE). The MIT licence does **not** cover any third-party material and grants
no rights to any third-party trademark or service. Where this notice and `LICENSE` conflict,
**the stricter restriction in this notice prevails**.

## 8. Governing law

This notice creates no contractual relationship. Disputes concerning this repository are
governed by the law of the repository owner's place of residence; liability for your own
unlawful conduct is unaffected by this clause and remains entirely yours.

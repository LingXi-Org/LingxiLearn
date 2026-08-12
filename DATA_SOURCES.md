# 数据来源与合规说明

## 教学抓包（合成，非真实流量）

`packs/computer-networks/missions/*/artifacts/*.pcap`

由 `scripts/build_artifacts.py` 从 `server/lingxilearn/tools/net/synth.py` 逐字节生成，
**不含任何真实用户流量**，因此没有需要脱敏的内容，也没有可泄露的隐私。

生成而非录制是有意的：

- ground truth 精确已知，判分是算术而不是意见；
- 帧号在每次重新生成后保持稳定，因此提示里可以放心引用帧号；
- 仓库里存的是生成器而不是二进制，ground truth 是可评审的。

产物是**真正的 pcap 文件**，校验和正确，可以直接用 Wireshark 打开核对——这一点是刻意的：
学生应当有能力审计我们。

| 文件 | 场景 | 地址空间 |
|---|---|---|
| `web-slow.pcap` | 一次含 DNS 延迟、服务器处理时间与一次丢包重传的网页加载 | RFC 1918 私网 + RFC 5737 文档地址（`203.0.113.0/24`） |
| `dns-nxdomain.pcap` | 域名不存在（RCODE=3） | 同上 |

域名使用 `course.example.edu`（RFC 2606 保留的文档域名）。
所有 IP 均取自 RFC 5737 / RFC 1918 保留段，不指向任何真实主机。

许可：CC0-1.0，可随仓库自由分发。

重新生成与校验：

```bash
python scripts/build_artifacts.py --check
```

## 协议参考资料

`packs/computer-networks/knowledge/`

| 文件 | 来源 | 用途 |
|---|---|---|
| `rfc9293-tcp.md` | [RFC 9293 — Transmission Control Protocol](https://www.rfc-editor.org/rfc/rfc9293.html) | 握手、序号与累计确认、重传超时、重复确认与快重传、发送窗口 |
| `rfc1035-dns.md` | [RFC 1035 — Domain Names](https://www.rfc-editor.org/rfc/rfc1035.html) | 报文格式、事务 ID 配对、RCODE、A 记录、解析时延 |
| `lingxilearn-notes.md` | LingxiLearn 原创（CC BY 4.0） | 归因方法论：先定边界再算时间 |

RFC 文档版权归 IETF Trust 所有，此处为教学用途的**摘录与转述**，
每个小节标题即引用锚点，教练给出的技术结论必须能指回其中一条。
若需完整原文，请以上方链接的官方版本为准。

## 学习记录

- 持久化用户数据必须通过 LingxiIdentity OIDC Bearer JWT；服务端以验证后的
  `Principal.subject` 和 issuer 建立唯一 Identity User 映射，客户端不能传入 learner ID。
- 本地只有显式 `LINGXILEARN_INSECURE_DEV_AUTH=true` 时才使用固定开发 subject；不接受
  客户端自报 subject、header 或 learner ID。
- 存储内容：学习者画像、会话状态、作答证据、掌握度、误区聚合、偏好、追加式学习事件、报告和 SSE 投影日志。
- 本地开发默认写入 `var/lingxilearn.sqlite3`；容器部署写入 PostgreSQL 卷。
- 旧的匿名 guest 记录不会自动映射到新 Identity 用户，仍保留但不通过受保护 API 暴露。
- 演示与评测使用的学习者档案全部是**合成的**（`scripts/smoke.py`、`lingxilearn.eval`），
  评测报告中的"学习增益"一栏已明确标注为流程验证，**不代表真实学生的学习效果**。

## 学生上传的抓包

当前版本的两个任务使用课程包内置工件，**没有开放上传入口**。
若后续开放，已经就位的约束是：

- 大小上限 `LINGXILEARN_MAX_ARTIFACT_BYTES`（默认 10 MB）；
- 仅接受经典 pcap，格式校验失败给出明确的中文错误；
- 解析完全离线——`net.pcap.*` 只读文件，**不会发出任何网络包，也不做任何主动探测**。

## 模型调用

| 引擎 | 数据外发 |
|---|---|
| `scripted`（默认） | **无**。不联网 |
| `openai` | 步骤标题、目标、课程作者写的问题与提示、证据摘要、掌握度数值 |
| `coze` | 同上 |

送往模型的是**教学上下文**，不包含学习者身份。原始抓包字节、完整工具输出与
数据库记录都不外发。判分、误区识别与证据引用始终在本地完成，模型不参与。

## 边界声明

> LingxiLearn 用于学习辅导与形成性反馈，**不替代教师、学校、考试或任何专业教育机构的最终评价**。

该声明同时固定显示在产品首页与学习报告页底部。

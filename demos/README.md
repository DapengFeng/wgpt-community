# Continuity lab / 连续性实验室

**Keep the work. Recover the connection.** Explore three ideas behind wgpt: translating replies, recovering an interrupted request, and keeping tool execution with the coding client.

**让工作留下来，让连接接得上。** 探索 wgpt 的三个设计理念：转换回复、恢复中断请求，以及将工具执行留在编程客户端。

**Offline scenario demo.** These independently authored examples run locally with synthetic data. They do not run the wgpt product, connect to AI websites or APIs, use accounts, or reproduce real conversations. Messages, playback timing and outcomes are illustrative, not live recordings or benchmarks.

**离线场景演示。** 这些独立编写的示例使用合成数据在本地运行，不运行 wgpt 产品、不连接 AI 网站或 API、不使用账号、不复用真实对话。消息、播放时序与结果均为示意，并非实站录像或性能测试。

## Try it / 体验演示

Open [index.html](index.html) from your local checkout in a modern browser. GitHub's file viewer displays source rather than running the page. If your browser restricts local-file scripts, serve just the demo directory locally; from the community repository root, run the following and visit **http://127.0.0.1:8765/**. Stop it with Ctrl+C when finished. Choose another unused port if 8765 is occupied.

从本地仓库中用现代浏览器打开 [index.html](index.html)。GitHub 的文件查看器只显示源码，不运行页面。若浏览器限制本地文件脚本，可仅为演示目录启动本地服务：在 community 仓库根目录执行以下命令，再访问 **http://127.0.0.1:8765/**。结束后按 Ctrl+C 停止；若 8765 已占用，换用其他空闲端口。

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory demos
```

Select a story, then use **Play**, **Next step**, **Pause** or **Reset**. Playback never starts automatically. Everything is included locally: no package installation, API key, provider account or wgpt installation is needed. The optional HTTP server serves static files on loopback only; it is not a model endpoint. Markdown links can be read in your editor or in GitHub's repository view.

选择一个故事，再使用 **Play（播放）**、**Next step（下一步）**、**Pause（暂停）** 或 **Reset（重置）**。页面不会自动播放。全部内容均在本地，无需安装依赖包、API key、provider 账号或 wgpt。可选 HTTP 服务仅在回环地址提供静态文件，不是模型接口。Markdown 链接可在编辑器或 GitHub 仓库视图中阅读。

## Three stories / 三个故事

1. **Translate a reply.** Follow one authored text fragment into illustrative Responses and Messages delta events. Inspect how both carry the same text. These excerpts omit the rest of each protocol's lifecycle; they are not an SDK endpoint or a full compatibility implementation.

   **转换回复协议。** 观察同一段预设文本如何转换为 Responses 和 Messages 的示意 delta 事件，查看两者如何携带相同文本。这些片段省略了协议的其他生命周期事件，不是 SDK 端点或完整兼容实现。

2. **Reconnect, don't resubmit.** Advance through identity recording, a simulated submission, disconnection, receipt retention and receiving the original result. The submission counter stays at **1** throughout recovery. Records live only in page memory; refreshing resets the illustration, so this is not a crash-persistence implementation.

   **恢复连接，避免重复提交。** 依次体验身份记录、模拟提交、断流、保留回执和接收原结果。恢复期间提交计数始终为 **1**。记录仅保存在页面内存中，刷新即重置示意，因此它不是崩溃持久化实现。

3. **Keep tools with the client.** A synthetic `add` function call waits at the client permission boundary, receives a scripted approved result with the same `call_id`, and continues to an authored final answer. The bridge is the carrier; the client owns permission and execution. No command, file operation or tool is executed by the demo.

   **工具执行留在客户端。** 合成的 `add` 函数调用在客户端权限边界等待，再接收带有相同 `call_id` 的预设已批准结果，并继续至预设的最终回答。bridge 负责传递，客户端负责权限及执行。本演示不执行任何命令、文件操作或工具。

## Build with us / 一起改进

If these problems interest you, help improve recovery invariants, protocol fixtures, failure diagnostics or accessibility. Start with the [contribution guide](../CONTRIBUTING.md). Product development stays in the private repository after onboarding; this directory contains only independently authored public teaching material.

如果这些问题吸引你，欢迎完善恢复约束、协议夹具、失败诊断或无障碍体验。从[贡献指南](../CONTRIBUTING.md)开始接入。产品开发仍在接入后的私有仓库中进行；本目录仅包含独立编写的公开教学材料。

<a id="scope-and-sources"></a>

## Scope and sources / 范围与依据

Reviewed on **2026-10-13**: [OpenAI ROW terms](https://openai.com/policies/row-terms-of-use/) and [European terms](https://openai.com/policies/eu-terms-of-use/) restrict automated output extraction; [Qwen's agreement](https://qwen.ai/termsservice) restricts bot access and automated extraction; [DeepSeek's terms](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html) restrict automated capture/copying under their service-security provisions. Those rules informed the choice to demonstrate local, authored data instead of automating a provider website. Applicable versions and regions must be checked for any future live demonstration.

于 **2026-10-13** 核验：[OpenAI ROW 条款](https://openai.com/policies/row-terms-of-use/)及[欧洲条款](https://openai.com/policies/eu-terms-of-use/)限制自动提取输出；[Qwen 协议](https://qwen.ai/termsservice)限制机器人访问及自动提取；[DeepSeek 条款](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html)在服务安全规定中限制自动抓取／复制。因此，本演示采用本地编写的数据，而非自动操作 provider 网站。未来任何实站演示均须重新核对适用版本及地区。

wgpt is independent and is not endorsed by any provider. These examples do not establish website compatibility, release readiness or permission to automate third-party services. Project naming and trademarks require separate review, including the [OpenAI brand guidelines](https://openai.com/brand/); the existing project name is not evidence of clearance. Offline execution reduces the service-use concerns addressed here but is not a worldwide legal guarantee.

wgpt 是独立项目，未获任何 provider 背书。这些示例不能证明网站兼容性、发布就绪状态或第三方服务自动化许可。项目命名与商标仍须单独核验，包括 [OpenAI 品牌指南](https://openai.com/brand/)；沿用现有项目名不代表已获授权。离线运行减少了本文涉及的服务使用风险，但不是全球法律合规保证。

Keep any additions within this boundary: original synthetic examples, no private source or client instructions, no actual transcripts, captures, account screenshots, credentials, provider logos, internal endpoint URLs or live provider requests. Keep the offline/synthetic label inside shareable visuals. The preview [overview.svg](overview.svg) is original vector artwork, not a screenshot of the product. Public sources are linked for readers; the running demo loads no remote assets or analytics and applies `connect-src 'none'`.

新增内容应保持相同边界：原创合成示例，不含私有源码或客户端指令、真实会话、捕获、账号截图、凭据、provider 标志、内部接口 URL 或实站请求。可单独分享的视觉材料中也要保留离线／合成标识。预览 [overview.svg](overview.svg) 为原创矢量图，并非产品截图。公开依据以链接供读者查阅；运行中的演示不加载远程资源或统计脚本，并设置 `connect-src 'none'`。

## Maintain one demo / 维护同一份演示

`demo.js` owns the authored scenarios and their deterministic in-memory progression; the DOM view consumes that same state. `index.html` and `style.css` own presentation. The existing `tests/` directory owns verification, including Node's built-in test runner invoked by the Python suite. Node.js 18 or newer is needed for development tests, not for visitors. Run the same entry used by community CI:

`demo.js` 统一维护预设场景及其确定性的内存状态推进，DOM 视图使用同一状态。`index.html` 与 `style.css` 负责展示。验证归现有 `tests/` 目录，其中由 Python 测试套件调用 Node 内置测试运行器。开发测试需要 Node.js 18 或更新版本，访客体验无需 Node。执行与 community CI 相同的入口：

```bash
python3 -m unittest discover -s tests
```

The tests cover scenario progression, controller behavior with a minimal DOM/clock double, and local-resource boundaries. They do not replace visual, keyboard or accessibility checks in a real browser, and do not exercise a provider website.

测试覆盖场景推进、使用最小 DOM／时钟替身的控制器行为，以及本地资源边界。它们不能替代真实浏览器中的视觉、键盘或无障碍检查，也不验证 provider 网站。

# Continuity lab / 连续性实验室

**Keep the work. Recover the connection.** Explore three ideas behind wgpt: translating replies, recovering an interrupted request, and keeping tool execution with the coding client.

**让工作留下来，让连接接得上。** 探索 wgpt 的三个设计理念：转换回复、恢复中断请求，以及将工具执行留在编程客户端。

**Watch here, without deploying anything.** The GIFs below record the existing offline HTML demo, advancing its synthetic scenarios with **Next step**. Frame hold times are edited for readability. They do not run the wgpt product, connect to AI websites or APIs, use accounts, or reproduce real conversations. Messages and outcomes are illustrative; these are not live product/provider recordings or benchmarks.

**直接观看，无需部署。** 下方 GIF 录制自现有离线 HTML 演示，通过 **Next step（下一步）** 推进合成场景。各帧停留时间经过调整，方便阅读。演示不运行 wgpt 产品、不连接 AI 网站或 API、不使用账号、不复用真实对话。消息与结果均为示意；这些不是产品／provider 实站录像或性能测试。

GIFs may start automatically and play once without looping; their pictured controls are part of the recording. For reduced-motion viewing, open the [static overview](overview.svg). Each story below also has a written explanation. Viewing requires only this GitHub page; the optional interactive version and recording tools are described later.

GIF 可能自动开始，播放一次后停止，不循环；画面中的控件也是录像的一部分。需要减少动态内容时，可打开[静态概览](overview.svg)。下方每个故事也有文字说明。观看只需打开此 GitHub 页面；可选交互版本及录制工具的说明放在后文。

## Three stories / 三个故事

1. **Translate a reply.** Follow one authored text fragment into illustrative Responses and Messages delta events. Inspect how both carry the same text. These excerpts omit the rest of each protocol's lifecycle; they are not an SDK endpoint or a full compatibility implementation.

   **转换回复协议。** 观察同一段预设文本如何转换为 Responses 和 Messages 的示意 delta 事件，查看两者如何携带相同文本。这些片段省略了协议的其他生命周期事件，不是 SDK 端点或完整兼容实现。

   ![Offline simulation: one reply becomes two protocol events. / 离线模拟：同一回复转换为两种协议事件。](recordings/protocol.gif)

2. **Reconnect, don't resubmit.** Advance through identity recording, a simulated submission, disconnection, receipt retention and receiving the original result. The submission counter stays at **1** throughout recovery. Records live only in page memory; refreshing resets the illustration, so this is not a crash-persistence implementation.

   **恢复连接，避免重复提交。** 依次体验身份记录、模拟提交、断流、保留回执和接收原结果。恢复期间提交计数始终为 **1**。记录仅保存在页面内存中，刷新即重置示意，因此它不是崩溃持久化实现。

   ![Offline simulation: the same request resumes while simulated submissions stay at one. / 离线模拟：恢复同一请求，模拟提交计数保持为一。](recordings/recovery.gif)

3. **Keep tools with the client.** A synthetic `add` function call waits at the client permission boundary, receives a scripted approved result with the same `call_id`, and continues to an authored final answer. The bridge is the carrier; the client owns permission and execution. No command, file operation or tool is executed by the demo.

   **工具执行留在客户端。** 合成的 `add` 函数调用在客户端权限边界等待，再接收带有相同 `call_id` 的预设已批准结果，并继续至预设的最终回答。bridge 负责传递，客户端负责权限及执行。本演示不执行任何命令、文件操作或工具。

   ![Offline simulation: client approval precedes a correlated scripted tool result. / 离线模拟：客户端批准后接收关联的预设工具结果。](recordings/tools.gif)

## Optional interactive version / 可选交互版本

To pause or advance each step yourself, open [index.html](index.html) from a local checkout in a modern browser. GitHub's file viewer displays HTML source rather than running the page. If your browser restricts local-file scripts, serve just the demo directory locally; from the community repository root, run the following and visit **http://127.0.0.1:8765/**. Stop it with Ctrl+C when finished. Choose another unused port if 8765 is occupied. None of these steps is required to watch the GIFs above.

如需自行暂停或逐步推进，可从本地仓库中用现代浏览器打开 [index.html](index.html)。GitHub 的文件查看器只显示 HTML 源码，不运行页面。若浏览器限制本地文件脚本，可仅为演示目录启动本地服务：在 community 仓库根目录执行以下命令，再访问 **http://127.0.0.1:8765/**。结束后按 Ctrl+C 停止；若 8765 已占用，换用其他空闲端口。观看上方 GIF 不需要这些步骤。

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory demos
```

Select a story, then use **Play**, **Next step**, **Pause** or **Reset**. The interactive page never starts playback automatically. Its assets are included locally: no package installation, API key, provider account or wgpt installation is needed. The optional HTTP server serves static files on loopback only; it is not a model endpoint. Markdown links can be read in your editor or in GitHub's repository view.

选择一个故事，再使用 **Play（播放）**、**Next step（下一步）**、**Pause（暂停）** 或 **Reset（重置）**。交互页面不会自动播放。其资源全部包含在本地，无需安装依赖包、API key、provider 账号或 wgpt。可选 HTTP 服务仅在回环地址提供静态文件，不是模型接口。Markdown 链接可在编辑器或 GitHub 仓库视图中阅读。

## Build with us / 一起改进

If these problems interest you, help improve recovery invariants, protocol fixtures, failure diagnostics or accessibility. Start with the [contribution guide](../CONTRIBUTING.md). Product development stays in the private repository after onboarding; this directory contains only independently authored public teaching material.

如果这些问题吸引你，欢迎完善恢复约束、协议夹具、失败诊断或无障碍体验。从[贡献指南](../CONTRIBUTING.md)开始接入。产品开发仍在接入后的私有仓库中进行；本目录仅包含独立编写的公开教学材料。

<a id="scope-and-sources"></a>

## Scope and sources / 范围与依据

Reviewed on **2026-10-13**: [OpenAI ROW terms](https://openai.com/policies/row-terms-of-use/) and [European terms](https://openai.com/policies/eu-terms-of-use/) restrict automated output extraction; [Qwen's agreement](https://qwen.ai/termsservice) restricts bot access and automated extraction; [DeepSeek's terms](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html) restrict automated capture/copying under their service-security provisions. Those rules informed the choice to demonstrate local, authored data instead of automating a provider website. Applicable versions and regions must be checked for any future live demonstration.

于 **2026-10-13** 核验：[OpenAI ROW 条款](https://openai.com/policies/row-terms-of-use/)及[欧洲条款](https://openai.com/policies/eu-terms-of-use/)限制自动提取输出；[Qwen 协议](https://qwen.ai/termsservice)限制机器人访问及自动提取；[DeepSeek 条款](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html)在服务安全规定中限制自动抓取／复制。因此，本演示采用本地编写的数据，而非自动操作 provider 网站。未来任何实站演示均须重新核对适用版本及地区。

wgpt is independent and is not endorsed by any provider. These examples do not establish website compatibility, release readiness or permission to automate third-party services. Project naming and trademarks require separate review, including the [OpenAI brand guidelines](https://openai.com/brand/); the existing project name is not evidence of clearance. Offline execution reduces the service-use concerns addressed here but is not a worldwide legal guarantee.

wgpt 是独立项目，未获任何 provider 背书。这些示例不能证明网站兼容性、发布就绪状态或第三方服务自动化许可。项目命名与商标仍须单独核验，包括 [OpenAI 品牌指南](https://openai.com/brand/)；沿用现有项目名不代表已获授权。离线运行减少了本文涉及的服务使用风险，但不是全球法律合规保证。

Keep any additions within this boundary: original synthetic examples, no private source or client instructions, no actual transcripts, provider captures, account screenshots, credentials, provider logos, internal endpoint URLs or live provider requests. Keep the offline/synthetic label inside every recorded frame. The preview [overview.svg](overview.svg) is original vector artwork; the GIFs capture only this teaching page. Neither is a screenshot of the wgpt product. Public sources are linked for readers; the running HTML demo loads no remote assets or analytics and applies `connect-src 'none'`.

新增内容应保持相同边界：原创合成示例，不含私有源码或客户端指令、真实会话、provider 实站捕获、账号截图、凭据、provider 标志、内部接口 URL 或实站请求。每个录制帧都应保留离线／合成标识。预览 [overview.svg](overview.svg) 为原创矢量图；GIF 仅录制此教学页面，两者均非 wgpt 产品截图。公开依据以链接供读者查阅；运行中的 HTML 演示不加载远程资源或统计脚本，并设置 `connect-src 'none'`。

## Maintain one demo / 维护同一份演示

`demo.js` owns the authored scenarios and their deterministic in-memory progression; the DOM view consumes that same state. `index.html` and `style.css` own presentation. The existing `tests/` directory owns verification, including Node's built-in test runner invoked by the Python suite. Node.js 18 or newer is needed for development tests, not for visitors. Run the same entry used by community CI:

`demo.js` 统一维护预设场景及其确定性的内存状态推进，DOM 视图使用同一状态。`index.html` 与 `style.css` 负责展示。验证归现有 `tests/` 目录，其中由 Python 测试套件调用 Node 内置测试运行器。开发测试需要 Node.js 18 或更新版本，访客体验无需 Node。执行与 community CI 相同的入口：

```bash
python3 -m unittest discover -s tests
```

The tests cover scenario progression, controller behavior with a minimal DOM/clock double, local-resource boundaries, and recording/source hashes and state sequences in `recordings/manifest.json`. They do not replace visual, keyboard or accessibility checks in a real browser, and do not exercise a provider website.

测试覆盖场景推进、使用最小 DOM／时钟替身的控制器行为、本地资源边界，以及 `recordings/manifest.json` 中的录像／源码哈希与状态序列。它们不能替代真实浏览器中的视觉、键盘或无障碍检查，也不验证 provider 网站。

Maintainers can regenerate the three GIFs with [scripts/record_demos.py](../scripts/record_demos.py). On Debian/Ubuntu, the recorder needs `python3-gi`, `gir1.2-webkit2-4.1`, `python3-pil`, `xvfb` and `fonts-noto-cjk`. From the community repository root, run the command below. These dependencies are only for recording, not viewing.

维护者可使用 [scripts/record_demos.py](../scripts/record_demos.py)重新生成三个 GIF。在 Debian/Ubuntu 上，录制器需要 `python3-gi`、`gir1.2-webkit2-4.1`、`python3-pil`、`xvfb` 和 `fonts-noto-cjk`。在 community 仓库根目录运行下方命令。这些依赖仅用于录制，观看无需安装。

```bash
xvfb-run -a -s '-screen 0 1280x1200x24' /usr/bin/python3 scripts/record_demos.py
```

The recorder renders the existing local HTML in isolated WebKit, advances **Next step**, and writes `demos/recordings/protocol.gif`, `demos/recordings/recovery.gif` and `demos/recordings/tools.gif` with edited hold times and no loop. Regenerate recordings when scenario or presentation changes, then inspect the frames for readable English/Chinese text, complete states and counters, and the visible offline/synthetic label. A recorded fixture demonstrates only this local simulation, not product or provider acceptance.

录制器在隔离的 WebKit 中渲染现有本地 HTML，通过 **Next step（下一步）** 推进，并将调整停留时间、不循环的动画写入 `demos/recordings/protocol.gif`、`demos/recordings/recovery.gif` 及 `demos/recordings/tools.gif`。场景或展示发生变化后应重新录制，再检查各帧英中文本的可读性、状态及计数是否完整，以及离线／合成标识是否可见。录制夹具只能展示此本地模拟，不代表产品或 provider 验收通过。

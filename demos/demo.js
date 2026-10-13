/* Independently authored offline scenarios; no wgpt runtime or provider data. */
(function (root) {
  "use strict";
  const scenarios = {
    protocol: {
      title: "A reply, two client protocols.",
      titleZh: "一段回复，两种客户端协议。",
      description: "Follow an authored text fragment into two illustrative stream events.",
      translation: "观察一段预设文本如何转换为两种示意流事件。",
      steps: [
        { title: "Accept a synthetic request", zh: "接受合成请求", state: "accepted", data: { request_id: "demo-protocol", prompt: "Say hello.", source: "authored fixture" } },
        { title: "Submit once to the local simulation", zh: "向本地模拟器提交一次", state: "submitted", submit: true, data: { fixture: "Hello from the offline lab.", provider_calls: 0 } },
        { title: "Map the text to client events", zh: "将文本映射为客户端事件", state: "streaming", data: { responses_event: { type: "response.output_text.delta", output_index: 0, content_index: 0, delta: "Hello from the offline lab." }, messages_event: { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "Hello from the offline lab." } } } },
        { title: "Mark the example complete", zh: "将本示例标记为完成", state: "completed", data: { request_id: "demo-protocol", status: "completed", text: "Hello from the offline lab.", note: "Illustrative excerpts, not complete protocol streams." } },
      ],
    },
    recovery: {
      title: "A disconnect is not a new request.",
      titleZh: "断开连接，不等于新的请求。",
      description: "Retain the request identity, then recover its prepared result without a second submission.",
      translation: "保留请求标识，再恢复预设结果，不进行第二次提交。",
      steps: [
        { title: "Record identity before submission", zh: "提交前记录身份", state: "accepted", data: { request_id: "demo-recovery", receipt: "created in memory", persistence: "simulation only" } },
        { title: "Submit once", zh: "提交一次", state: "submitted", submit: true, data: { request_id: "demo-recovery", local_simulated_submissions: 1, provider_calls: 0 } },
        { title: "Disconnect; retain ownership", zh: "模拟断流，保留请求", state: "retained", data: { request_id: "demo-recovery", client: "disconnected (simulated)", result: "not yet delivered", next_action: "receive this request" } },
        { title: "Receive the same request", zh: "接收同一个请求", state: "receiving", data: { request_id: "demo-recovery", operation: "receive", automatic_resubmission: false, recovered_text: "Your prepared result is ready." } },
        { title: "Deliver once; release ownership", zh: "交付结果，解除保留", state: "completed", data: { request_id: "demo-recovery", status: "completed", total_simulated_submissions: 1, result: "Your prepared result is ready." } },
      ],
    },
    tools: {
      title: "The client owns the action.",
      titleZh: "由客户端掌握执行权限。",
      description: "A bridge carries a tool request. The client checks permission and supplies the result.",
      translation: "bridge 传递工具请求，由客户端检查权限并提供结果。",
      steps: [
        { title: "Accept a calculation request", zh: "接受计算请求", state: "accepted", data: { request_id: "demo-tools", prompt: "What is 2 + 3?", source: "authored fixture" } },
        { title: "Return a synthetic tool call", zh: "返回合成工具调用", state: "awaiting_tool", submit: true, data: { type: "function_call", call_id: "demo-call-add", name: "add", arguments: "{\"a\":2,\"b\":3}" } },
        { title: "Client permission boundary", zh: "客户端权限边界", state: "awaiting_approval", data: { actor: "client", call_id: "demo-call-add", permission: "pending in this illustration", actual_tool_execution: false } },
        { title: "Use an authored, approved result", zh: "载入预设的已批准结果", state: "tool_result", data: { actor: "simulated client", permission: "approved (scripted)", type: "function_call_output", call_id: "demo-call-add", output: "5", actual_tool_execution: false } },
        { title: "Continue with the correlated result", zh: "使用匹配的结果继续", state: "completed", submit: true, data: { request_id: "demo-tools", status: "completed", text: "2 + 3 = 5.", note: "Authored final reply; no model or tool ran." } },
      ],
    },
  };

  function createSession(id) {
    if (!Object.hasOwn(scenarios, id)) throw new Error("Unknown demo scenario");
    return { id, index: -1, submissionCount: 0, state: "idle", events: [] };
  }

  function advance(session) {
    const scenario = scenarios[session.id];
    if (!scenario) throw new Error("Unknown demo scenario");
    if (session.index + 1 >= scenario.steps.length) return snapshot(session);
    const step = scenario.steps[++session.index];
    if (step.submit) session.submissionCount += 1;
    session.state = step.state;
    session.events.push(JSON.parse(JSON.stringify(step.data)));
    return snapshot(session);
  }

  function snapshot(session) {
    return JSON.parse(JSON.stringify({
      ...session,
      requestId: `demo-${session.id}`,
      retained: ["retained", "receiving"].includes(session.state),
      done: session.index === scenarios[session.id].steps.length - 1,
      providerCalls: 0,
    }));
  }

  const api = { scenarios, createSession, advance, snapshot };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.WgptDemo = api;

  if (typeof document === "undefined") return;
  let session = createSession("protocol");
  let timer = null;
  const byId = (id) => document.getElementById(id);
  const play = byId("play");
  const next = byId("next");
  const reducedMotion = root.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function pause() {
    if (timer !== null) root.clearInterval(timer);
    timer = null;
    play.textContent = "Play / 播放";
  }

  function render() {
    const scenario = scenarios[session.id];
    const value = snapshot(session);
    byId("scenario-title").textContent = scenario.title;
    byId("scenario-title-zh").textContent = scenario.titleZh;
    byId("scenario-description").textContent = scenario.description;
    byId("scenario-translation").textContent = scenario.translation;
    byId("submissions").textContent = String(value.submissionCount);
    byId("request-id").textContent = value.requestId;
    byId("state").textContent = value.state;
    byId("event-output").textContent = value.events.length
      ? JSON.stringify(value.events.at(-1), null, 2)
      : '// Authored fixture · No network requests\n// Click Play or Next step to begin.\n\n{\n  "provider_calls": 0,\n  "actual_tool_execution": false,\n  "state": "idle"\n}';
    const timeline = byId("timeline");
    timeline.replaceChildren();
    scenario.steps.forEach((step, index) => {
      const item = document.createElement("li");
      item.textContent = step.title;
      if (index <= value.index) item.classList.add("done");
      if (index === value.index) {
        item.classList.add("current");
        item.setAttribute("aria-current", "step");
      }
      const translation = document.createElement("span");
      translation.lang = "zh-CN";
      translation.textContent = step.zh;
      item.append(translation);
      timeline.append(item);
    });
    document.querySelectorAll("[data-scenario]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.scenario === session.id));
    });
    byId("progress").textContent = value.done
      ? "Example complete · 示例完成"
      : `Step ${value.index + 1} / ${scenario.steps.length} · 第 ${value.index + 1} / ${scenario.steps.length} 步`;
    next.disabled = value.done;
    play.disabled = value.done;
    if (value.done) pause();
  }

  function step() { advance(session); render(); }
  next.addEventListener("click", () => { pause(); step(); });
  play.addEventListener("click", () => {
    if (timer !== null) { pause(); return; }
    step();
    if (!snapshot(session).done) {
      play.textContent = "Pause / 暂停";
      // Timers advance only authored local steps; there are no network effects.
      timer = root.setInterval(step, reducedMotion ? 3500 : 2200);
    }
  });
  byId("reset").addEventListener("click", () => { pause(); session = createSession(session.id); render(); });
  document.querySelectorAll("[data-scenario]").forEach((button) => {
    button.addEventListener("click", () => { pause(); session = createSession(button.dataset.scenario); render(); });
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  render();
})(typeof globalThis === "undefined" ? this : globalThis);

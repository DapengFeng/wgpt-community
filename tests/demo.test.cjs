"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const demo = require("../demos/demo.js");

function finish(id) {
  const session = demo.createSession(id);
  const states = [demo.snapshot(session)];
  for (let i = 0; i < 20 && !states.at(-1).done; i += 1) states.push(demo.advance(session));
  assert.equal(states.at(-1).done, true, "Scenarios must finish in bounded steps");
  return { session, states };
}

test("every scenario starts idle and exposes no provider calls", () => {
  for (const id of Object.keys(demo.scenarios)) {
    const { states } = finish(id);
    assert.equal(states[0].state, "idle");
    assert.equal(states[0].submissionCount, 0);
    assert.ok(states.every((state) => state.providerCalls === 0));
    assert.ok(states.every((state) => state.requestId === `demo-${id}`));
    assert.equal(states.at(-1).state, "completed");
  }
});

test("receive retains identity without a second simulated submission", () => {
  const { states } = finish("recovery");
  const retained = states.find((state) => state.state === "retained");
  const receiving = states.find((state) => state.state === "receiving");
  assert.equal(retained.retained, true);
  assert.equal(receiving.retained, true);
  assert.equal(receiving.submissionCount, 1);
  assert.equal(receiving.events.at(-1).operation, "receive");
  assert.equal(receiving.events.at(-1).automatic_resubmission, false);
  assert.equal(states.at(-1).submissionCount, 1);
  assert.equal(states.at(-1).retained, false);
  assert.ok(states.flatMap((state) => state.events).every((event) => event.request_id === "demo-recovery"));
});

test("protocol excerpts preserve the authored text in both formats", () => {
  const { states } = finish("protocol");
  const fragment = states.find((state) => state.state === "streaming").events.at(-1);
  const answer = states.at(-1).events.at(-1).text;
  assert.equal(fragment.responses_event.type, "response.output_text.delta");
  assert.equal(fragment.messages_event.delta.type, "text_delta");
  assert.equal(fragment.responses_event.delta, answer);
  assert.equal(fragment.messages_event.delta.text, answer);
});

test("tool results are correlated and follow the client permission boundary", () => {
  const { states } = finish("tools");
  const call = states.find((state) => state.state === "awaiting_tool");
  const permission = states.find((state) => state.state === "awaiting_approval");
  const result = states.find((state) => state.state === "tool_result");
  assert.ok(call.index < permission.index && permission.index < result.index);
  assert.equal(call.events.at(-1).call_id, result.events.at(-1).call_id);
  assert.equal(permission.events.at(-1).actor, "client");
  assert.equal(result.events.at(-1).actor, "simulated client");
  assert.equal(permission.events.at(-1).actual_tool_execution, false);
  assert.equal(result.events.at(-1).actual_tool_execution, false);
  assert.equal(states.at(-1).submissionCount, 2);
});

test("completed playback cannot submit again", () => {
  for (const id of Object.keys(demo.scenarios)) {
    const { session, states } = finish(id);
    for (let i = 0; i < 5; i += 1) assert.deepEqual(demo.advance(session), states.at(-1));
  }
});

test("reset and snapshots cannot contaminate another playback", () => {
  const first = demo.createSession("recovery");
  const copy = demo.advance(first);
  copy.events[0].request_id = "changed";
  assert.equal(demo.snapshot(first).events[0].request_id, "demo-recovery");
  const fresh = demo.createSession("recovery");
  assert.deepEqual(fresh.events, []);
  assert.equal(fresh.index, -1);
  assert.equal(fresh.submissionCount, 0);
});

test("unrecognized scenarios cannot load arbitrary content", () => {
  for (const id of ["unknown", "__proto__", "constructor", "https://example.invalid/"]) {
    assert.throws(() => demo.createSession(id), /Unknown demo scenario/);
  }
});

function mount() {
  class Element {
    constructor() {
      this.textContent = "";
      this.children = [];
      this.attributes = {};
      this.listeners = {};
      this.classList = { add() {} };
      this.dataset = {};
      this.disabled = false;
    }
    append(child) { this.children.push(child); }
    replaceChildren() { this.children = []; }
    setAttribute(key, value) { this.attributes[key] = value; }
    addEventListener(name, listener) { this.listeners[name] = listener; }
    click() { if (!this.disabled) this.listeners.click(); }
  }
  const html = fs.readFileSync(path.join(__dirname, "../demos/index.html"), "utf8");
  const elements = Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map((match) => [match[1], new Element()]));
  const buttons = [...html.matchAll(/\bdata-scenario="([^"]+)"/g)].map((match) => {
    const element = new Element();
    element.dataset.scenario = match[1];
    return element;
  });
  const timers = new Map();
  const document = {
    hidden: false, listeners: {},
    getElementById: (id) => elements[id],
    querySelectorAll: () => buttons,
    createElement: () => new Element(),
    addEventListener(name, listener) { this.listeners[name] = listener; },
  };
  let timerId = 0;
  // A minimal DOM/clock double tests controller behavior, not browser rendering.
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../demos/demo.js"), "utf8"), {
    document, matchMedia: () => ({ matches: true }),
    setInterval: (callback) => { timers.set(++timerId, callback); return timerId; },
    clearInterval: (id) => timers.delete(id),
  });
  return { elements, buttons, timers, document };
}

test("controls do not autoplay and stop the clock on reset, switch or backgrounding", () => {
  const { elements, buttons, timers, document } = mount();
  assert.equal(timers.size, 0);
  assert.equal(elements.state.textContent, "idle");
  assert.ok(elements["scenario-title-zh"].textContent);
  elements.play.click();
  assert.equal(timers.size, 1);
  elements.reset.click();
  assert.equal(timers.size, 0);
  assert.equal(elements.state.textContent, "idle");
  elements.play.click();
  buttons.find((button) => button.dataset.scenario === "recovery").click();
  assert.equal(timers.size, 0);
  assert.equal(elements["request-id"].textContent, "demo-recovery");
  elements.play.click();
  document.hidden = true;
  document.listeners.visibilitychange();
  assert.equal(timers.size, 0);
});

test("step controls render retained and completed evidence and disable completion replay", () => {
  const { elements, buttons } = mount();
  buttons.find((button) => button.dataset.scenario === "recovery").click();
  for (let i = 0; i < 3; i += 1) elements.next.click();
  assert.equal(elements.state.textContent, "retained");
  assert.equal(elements.submissions.textContent, "1");
  assert.match(elements["event-output"].textContent, /receive this request/);
  elements.next.click();
  elements.next.click();
  assert.equal(elements.state.textContent, "completed");
  assert.equal(elements.submissions.textContent, "1");
  assert.equal(elements.next.disabled, true);
  assert.equal(elements.play.disabled, true);
  assert.match(elements.progress.textContent, /示例完成/);
});

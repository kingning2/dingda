/**
 * 归约器：`browserFrame` 落哪一块，以及断线重连倚赖的几条重放性质。
 *
 * 职责：
 *   验「帧可以点名挂步骤块」这条：掉线恢复时搜索块还在 running，二维码必须靠 `stepId`
 *   钉在「扫码登录」块上，不能被搜索块抢走；登录帧无点名时优先挂进行中的 login 块；
 *   普通截图帧仍走原来的「第一个进行中的 browser_crawl」。
 *
 * 重放那组（`describe("重放")`）验的是服务端日志的两个前提：同一 step 只留最新一帧
 * 不丢上屏信息（`agent.runs` 的淘汰策略），以及正文是追加型 —— 冷接回必须清空重建，
 * 不能把整段日志叠在已经折过前缀的状态上。
 */

import { describe, expect, it } from "vitest";
import type { AgentEvent } from "@v2/contracts/agent-event";
import type { AgentWorkStepView } from "@v2/contracts/ai-work";
import {
  createAgentRunMessageState,
  reduceAgentEvent,
  type AgentRunMessageState,
} from "../src/run/reducer";

const RUNNING = { state: "running", label: "执行中", badge_class: "" };

/** 一个刚下发、还没截图的 browser_crawl 步骤块。 */
function browserStep(id: string, label: string): AgentWorkStepView {
  return {
    id,
    label,
    kind: "browser_crawl",
    status: RUNNING,
    page: { url: "", title: label, loading: true, screenshot_url: null, focus_label: null },
  };
}

/** 扫码登录步骤块（kind=login，与直播页卡分开）。 */
function loginStep(id: string, label: string): AgentWorkStepView {
  return {
    id,
    label,
    kind: "login",
    status: RUNNING,
    page: { url: "", title: label, loading: true, screenshot_url: null, focus_label: "用 App 扫码登录" },
  };
}

function callStep(step: AgentWorkStepView): AgentEvent {
  return { type: "toolCall", id: step.id, name: step.label, input: {}, step };
}

/** 搜索块 + 登录块，两个都在 running —— 恢复时的真实局面。 */
function blockedState() {
  let state = createAgentRunMessageState();
  state = reduceAgentEvent(state, callStep(browserStep("search-1", "搜索商品 · 闲鱼")));
  state = reduceAgentEvent(state, callStep(loginStep("login-1", "扫码登录 · 闲鱼")));
  return state;
}

function frameWith(stepId?: string): AgentEvent {
  return {
    type: "browserFrame",
    url: "dingda://login/xianyu",
    title: "扫码登录 · 闲鱼",
    hint: "账号已失效，请扫码后继续",
    screenshot_url: "data:image/png;base64,AAAA",
    stepId,
  };
}

describe("reduceAgentEvent browserFrame", () => {
  it("stepId 点名时落在指定块，不碰还在跑的那个", () => {
    const state = reduceAgentEvent(blockedState(), frameWith("login-1"));

    const search = state.steps.find((step) => step.id === "search-1");
    const login = state.steps.find((step) => step.id === "login-1");

    expect(login?.page?.screenshot_url).toBe("data:image/png;base64,AAAA");
    expect(login?.page?.focus_label).toBe("账号已失效，请扫码后继续");
    expect(login?.kind).toBe("login");
    // 搜索块还是空的 loading 卡：二维码没被它抢走
    expect(search?.page?.screenshot_url).toBeNull();
    expect(state.steps).toHaveLength(2);
    // 扫码等待不是浏览器直播阶段
    expect(state.phase).toBe("executing");
  });

  it("不点名时仍落在第一个进行中的 browser_crawl", () => {
    const state = reduceAgentEvent(blockedState(), frameWith());

    // 登录帧无 stepId 时优先挂进行中的 login 块，不再误挂搜索直播
    expect(state.steps.find((step) => step.id === "login-1")?.page?.screenshot_url).toBe(
      "data:image/png;base64,AAAA",
    );
    expect(state.steps.find((step) => step.id === "search-1")?.page?.screenshot_url).toBeNull();
    expect(state.phase).toBe("executing");
  });

  it("stepId 认不出来时退回原逻辑，不丢帧", () => {
    const state = reduceAgentEvent(blockedState(), frameWith("nope-1"));

    // 认不出 stepId → 登录帧优先挂 login 块
    expect(state.steps.find((step) => step.id === "login-1")?.page?.screenshot_url).toBe(
      "data:image/png;base64,AAAA",
    );
  });

  it("无步骤时登录帧合成 login 块而不是 browser-live", () => {
    const state = reduceAgentEvent(createAgentRunMessageState(), frameWith());
    expect(state.steps).toHaveLength(1);
    expect(state.steps[0]?.kind).toBe("login");
    expect(state.steps[0]?.id).toBe("login-pending");
    expect(state.phase).toBe("executing");
  });
});

describe("重放", () => {
  /** 钉死 id 的爬取步：帧都点名挂在它上面。 */
  const crawlStep: AgentWorkStepView = {
    id: "crawl-1",
    label: "搜索商品 · 闲鱼",
    kind: "browser_crawl",
    status: RUNNING,
    page: { url: "", title: "闲鱼", loading: true, screenshot_url: null, focus_label: null },
  };

  function crawlFrame(shot: string, focus: string): AgentEvent {
    return {
      type: "browserFrame",
      url: "https://x.test/s",
      title: "闲鱼",
      hint: focus,
      screenshot_url: shot,
      stepId: "crawl-1",
    };
  }

  /** 折一段日志；不给起点就是从 0 折（冷接回的读法）。 */
  function replay(events: AgentEvent[], from?: AgentRunMessageState): AgentRunMessageState {
    return events.reduce<AgentRunMessageState>(
      (state, event) => reduceAgentEvent(state, event),
      from ?? createAgentRunMessageState(),
    );
  }

  it("同一 step 的旧帧被淘汰时，折叠结果与逐帧全收逐字相同", () => {
    const call = callStep(crawlStep);
    const first = crawlFrame("data:1", "第一页");
    const second = crawlFrame("data:2", "第二页");

    // 服务端只留同一 step 的最新一帧（base64 太大，见 `agent.runs` 的淘汰策略），
    // 所以客户端接回时拿到的常常是「中间那些帧从来没存在过」的序列。
    expect(replay([call, first, second])).toEqual(replay([call, second]));
    expect(replay([call, second]).steps[0]?.page?.screenshot_url).toBe("data:2");
  });

  it("正文是追加型：整段日志叠在折过前缀的状态上会重复", () => {
    const log: AgentEvent[] = [
      { type: "textDelta", text: "前半" },
      { type: "textDelta", text: "后半" },
      { type: "runCompleted", exitCode: 0 },
    ];

    // 冷接回：从 0 重放，正文精确等于原文。
    expect(replay(log).content).toBe("前半后半");
    // 错误读法：把整段日志续在折过前缀的状态上 —— 前半出现两次。
    // 这正是「接回要清空那条助手消息，再从 0 重放」的理由。
    expect(replay(log, replay([log[0]!])).content).toBe("前半前半后半");
  });

  it("工具步骤按 id upsert，整段重放不会叠出第二个块", () => {
    const state = replay([callStep(crawlStep), callStep(crawlStep), crawlFrame("data:1", "页")]);
    expect(state.steps).toHaveLength(1);
    expect(state.timeline).toEqual([{ kind: "step", id: "crawl-1" }]);
  });
});

/**
 * The two things most likely to be got wrong in the settings modal: what an
 * "inherit" toggle actually sends, and whether a thinking budget is legal.
 *
 * Both are pure, so they are pinned here rather than through the DOM.
 */

import { describe, expect, it } from "vitest";

import {
  INHERITABLE,
  LLM_FIELDS,
  budgetError,
  draftToUpdate,
  endpointSummary,
  stagesToUpdate,
} from "../llmSettings";
import type { ApiLLMGroup, LLMStage } from "../types";
import type { EndpointDraft } from "@/components/settings/EndpointFields";

const draft = (over: Partial<EndpointDraft> = {}): EndpointDraft => ({
  enabled: true,
  provider: "openai-compatible",
  base_url: "http://localhost:9090/v1",
  model: "default-model",
  api_key: "",
  timeout_s: "30",
  max_tokens: "4096",
  thinking_budget: "0",
  ...over,
});

const group = (over: Partial<ApiLLMGroup> = {}): ApiLLMGroup => ({
  enabled: false,
  provider: "openai-compatible",
  base_url: "http://localhost:9090/v1",
  model: "default-model",
  api_key_set: false,
  timeout_s: 30,
  max_tokens: 4096,
  thinking_budget: 0,
  inherited: [...LLM_FIELDS],
  ...over,
});

const stages = (over: Partial<Record<LLMStage, ApiLLMGroup>> = {}) =>
  ({
    planner: group(),
    specialist: group(),
    synthesis: group(),
    conversation: group(),
    eval: group(),
    ...over,
  }) as Record<LLMStage, ApiLLMGroup>;

describe("budgetError", () => {
  it("accepts a budget below max tokens", () => {
    expect(budgetError("4096", "2048")).toBeNull();
  });

  it("rejects a budget that consumes the whole allowance", () => {
    // The model spends everything reasoning and returns empty content, which
    // reaches a caller as a silent "LLM unavailable" rather than an error.
    expect(budgetError("4096", "4096")).toMatch(/must be less than/);
    expect(budgetError("4096", "5000")).toMatch(/must be less than/);
  });

  it("keeps 0 legal at any max — it means send no cap", () => {
    expect(budgetError("4096", "0")).toBeNull();
    expect(budgetError("1", "0")).toBeNull();
  });

  it("rejects a negative budget", () => {
    expect(budgetError("4096", "-1")).toMatch(/negative/);
  });

  it("stays quiet on half-typed numbers", () => {
    expect(budgetError("", "")).toBeNull();
  });
});

describe("draftToUpdate", () => {
  it("omits an empty API key so the stored one survives", () => {
    // "" must not be sent: it is indistinguishable from clearing, and clearing
    // goes through `inherit`.
    expect(draftToUpdate(draft()).api_key).toBeUndefined();
  });

  it("sends a key the operator just typed", () => {
    expect(draftToUpdate(draft({ api_key: "sk-new" })).api_key).toBe("sk-new");
  });

  it("coerces numeric fields off the string form state", () => {
    const update = draftToUpdate(draft({ timeout_s: "12.5", max_tokens: "8192" }));
    expect(update.timeout_s).toBe(12.5);
    expect(update.max_tokens).toBe(8192);
  });
});

describe("stagesToUpdate", () => {
  it("sends nothing for a stage that was inheriting and still is", () => {
    const out = stagesToUpdate(
      {
        planner: { custom: false, fields: draft() },
        specialist: { custom: false, fields: draft() },
        synthesis: { custom: false, fields: draft() },
        conversation: { custom: false, fields: draft() },
        eval: { custom: false, fields: draft() },
      },
      stages(),
    );
    expect(out).toEqual({}, "an already-inheriting stage is noise in the .env");
  });

  it("sends values for a stage switched to custom", () => {
    const out = stagesToUpdate(
      {
        planner: { custom: false, fields: draft() },
        specialist: { custom: false, fields: draft() },
        synthesis: { custom: false, fields: draft() },
        conversation: { custom: false, fields: draft() },
        eval: { custom: true, fields: draft({ model: "judge", base_url: "http://gpu2:8000/v1" }) },
      },
      stages(),
    );
    expect(out.eval?.model).toBe("judge");
    expect(out.eval?.base_url).toBe("http://gpu2:8000/v1");
    expect(out.eval?.inherit).toBeUndefined();
  });

  it("CLEARS a stage switched back to inherit, never rewriting the default's values", () => {
    // The load-bearing case. Sending the primary group's current numbers would
    // pin the stage to a snapshot that silently stops tracking the default.
    const out = stagesToUpdate(
      {
        planner: { custom: false, fields: draft() },
        specialist: { custom: false, fields: draft() },
        synthesis: { custom: false, fields: draft() },
        conversation: { custom: false, fields: draft() },
        eval: { custom: false, fields: draft({ model: "judge" }) },
      },
      stages({ eval: group({ inherited: ["enabled"], model: "judge" }) }),
    );
    expect(out.eval).toEqual({ inherit: INHERITABLE });
    expect(out.eval?.model).toBeUndefined();
  });
});

describe("endpointSummary", () => {
  it("shows the model and host an inheriting stage will use", () => {
    expect(endpointSummary(draft({ model: "qwen38-27B-v2", base_url: "http://gpu:8000/v1" }))).toBe(
      "qwen38-27B-v2 @ gpu:8000",
    );
  });

  it("does not blank out while a URL is half-typed", () => {
    // "http://gp" parses fine (host "gp"), so it renders as a host.
    expect(endpointSummary(draft({ base_url: "http://gp" }))).toBe("default-model @ gp");
    // A genuinely unparseable fragment falls back to the raw text rather than
    // rendering an empty line mid-keystroke.
    expect(endpointSummary(draft({ base_url: "htt" }))).toBe("default-model @ htt");
  });
});

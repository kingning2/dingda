import type { AgentRuntimeModelView } from "@/contracts/agent-runtime";

/** 与 OpenDesign `parseCodexDebugModels` 对齐。 */
export function parseCodexDebugModels(stdout: string): AgentRuntimeModelView[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(stdout || "");
  } catch {
    return [];
  }

  if (!parsed || typeof parsed !== "object") return [];
  const models = Array.isArray(parsed)
    ? parsed
    : (parsed as { models?: unknown }).models;
  if (!Array.isArray(models)) return [];

  const out: AgentRuntimeModelView[] = [{ id: "default", label: "默认" }];
  const seen = new Set(out.map((item) => item.id));

  for (const raw of models) {
    if (!raw || typeof raw !== "object") continue;
    const entry = raw as {
      slug?: unknown;
      id?: unknown;
      display_name?: unknown;
      name?: unknown;
      visibility?: unknown;
    };
    if (entry.visibility === "hidden") continue;

    const id =
      typeof entry.slug === "string"
        ? entry.slug.trim()
        : typeof entry.id === "string"
          ? entry.id.trim()
          : "";
    if (!id || seen.has(id)) continue;
    seen.add(id);

    const label =
      typeof entry.display_name === "string" && entry.display_name.trim()
        ? entry.display_name.trim()
        : typeof entry.name === "string" && entry.name.trim()
          ? entry.name.trim()
          : id;
    out.push({ id, label });
  }

  return out;
}

export const CODEX_FALLBACK_MODELS: AgentRuntimeModelView[] = [
  { id: "default", label: "默认" },
  { id: "gpt-5.5", label: "gpt-5.5" },
  { id: "gpt-5.4", label: "gpt-5.4" },
  { id: "gpt-5.4-mini", label: "gpt-5.4-mini" },
  { id: "gpt-5.3-codex", label: "gpt-5.3-codex" },
  { id: "gpt-5.1", label: "gpt-5.1" },
  { id: "gpt-5.1-codex-mini", label: "gpt-5.1-codex-mini" },
  { id: "gpt-5-codex", label: "gpt-5-codex" },
  { id: "gpt-5", label: "gpt-5" },
  { id: "o3", label: "o3" },
  { id: "o4-mini", label: "o4-mini" },
];

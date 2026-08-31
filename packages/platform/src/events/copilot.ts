import { listenEvent } from "./index";

export const COPILOT_AGUI_EVENT = "app/copilot/agui";

/** AG-UI 事件子集（snake_case，与 contracts/schema/v1/copilot/agui_event.schema.json 对齐）。 */
export interface CopilotAguiEvent {
  type: string;
  run_id: string;
  thread_id: string;
  message_id?: string;
  role?: string;
  delta?: string;
  content?: string;
  tool_call_id?: string;
  tool_name?: string;
  args_delta?: string;
  message?: string;
  code?: string;
}

export function listenCopilotAgui(
  handler: (event: CopilotAguiEvent) => void,
): Promise<import("@tauri-apps/api/event").UnlistenFn> {
  return listenEvent<CopilotAguiEvent>(COPILOT_AGUI_EVENT, handler);
}

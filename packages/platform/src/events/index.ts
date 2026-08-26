/**
 * Tauri event listen helpers for desktop UI push updates.
 *
 * @author coisini
 * @created 2026-07-21
 */

import { listen, type UnlistenFn } from "@tauri-apps/api/event";

/**
 * Subscribe to a Tauri event topic and receive typed payloads.
 *
 * @author coisini
 * @created 2026-07-21
 *
 * @typeParam T - Payload type (usually a contracts event DTO)
 * @param topic - Event topic，例如 `channel/message` / `runtime/sidecar/restarted`
 * @param handler - Callback invoked for each event payload
 * @returns Promise resolving to an unlisten function
 */
export async function listenEvent<T>(
  topic: string,
  handler: (payload: T) => void,
): Promise<UnlistenFn> {
  return listen<T>(topic, (event) => {
    handler(event.payload);
  });
}

export * from "./runtime";
export * from "./plugin";
export * from "./channel";
export * from "./agent";


import { api } from "./api";
import type { UiEventType } from "./types";

/**
 * `POST /ui-event` (docs/06 §8), fire and forget: a lost interaction record must never
 * interrupt what the reviewer is doing.
 */
export function postUiEvent(
  type: UiEventType,
  payload: Record<string, unknown> = {},
  runId: string | null = null,
): void {
  void api.uiEvent({ run_id: runId, type, payload }).catch(() => undefined);
}

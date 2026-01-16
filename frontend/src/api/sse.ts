import type { ObservedStep } from "./types";

export type StepListener = (step: ObservedStep) => void;

export function subscribeToSteps(
  sessionId: string,
  onStep: StepListener,
): () => void {
  const es = new EventSource(`/api/sessions/${sessionId}/stream`);

  const handler = (evt: MessageEvent) => {
    try {
      const parsed = JSON.parse(evt.data) as ObservedStep;
      onStep(parsed);
    } catch {
      // ignore malformed events
    }
  };

  es.addEventListener("step", handler as EventListener);

  return () => {
    es.removeEventListener("step", handler as EventListener);
    es.close();
  };
}

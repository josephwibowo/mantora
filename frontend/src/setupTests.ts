import "@testing-library/jest-dom";

// Mock EventSource for SSE
class MockEventSource {
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSED = 2;
  readyState = 0;
  url = "";
  withCredentials = false;

  constructor(url: string) {
    this.url = url;
  }

  close() {
    this.readyState = this.CLOSED;
  }

  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() {
    return true;
  }
}

globalThis.EventSource = MockEventSource as unknown as typeof EventSource;

// Mock ResizeObserver for Layout/Charts
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

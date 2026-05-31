import type { BenchmarkRow, CalculationSnapshot, PlannerConfig, RunResult, Scenario, ScoreBreakdown } from "./types";

/** Direct backend URL — used when Vite proxy races startup or fails. */
const DIRECT_BACKEND = "http://127.0.0.1:8000";

function apiBases(): string[] {
  const configured = import.meta.env.VITE_API_URL?.replace(/\/$/, "");
  if (configured) return [configured];
  if (import.meta.env.DEV) return ["", DIRECT_BACKEND];
  return [DIRECT_BACKEND];
}

function urlFor(base: string, path: string): string {
  if (base === "") return path;
  return `${base}${path}`;
}

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function apiFetch(
  path: string,
  init?: RequestInit,
  retries = 6,
): Promise<Response> {
  const bases = apiBases();
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < retries; attempt++) {
    for (const base of bases) {
      try {
        const res = await fetch(urlFor(base, path), init);
        if (res.ok) return res;
        const body = await res.text();
        lastError = new Error(
          body ? `HTTP ${res.status}: ${body.slice(0, 200)}` : `HTTP ${res.status}`,
        );
      } catch (err) {
        lastError =
          err instanceof Error
            ? err
            : new Error(String(err));
        if (
          lastError.message.includes("Failed to fetch") ||
          lastError.message.includes("NetworkError")
        ) {
          lastError = new Error(
            "Cannot reach API. Start backend: cd backend && py -3.13 -m uvicorn main:app --port 8000",
          );
        }
      }
    }
    if (attempt < retries - 1) {
      await sleep(400 * (attempt + 1));
    }
  }

  throw lastError ?? new Error("API request failed");
}

export async function fetchConfig(): Promise<PlannerConfig> {
  const res = await apiFetch("/api/config");
  return res.json();
}

export async function fetchScenarios(): Promise<Scenario[]> {
  const res = await apiFetch("/api/scenarios");
  return res.json();
}

export async function fetchCalculations(
  scenarioId: string,
  t_s: number,
  score?: ScoreBreakdown | null,
): Promise<CalculationSnapshot> {
  if (score) {
    const res = await apiFetch("/api/calculations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario_id: scenarioId, t_s, score }),
    });
    return res.json();
  }
  const res = await apiFetch(
    `/api/calculations?scenario_id=${encodeURIComponent(scenarioId)}&t_s=${t_s}`,
  );
  return res.json();
}

export async function runScenario(
  scenarioId: string,
  useMock = false,
): Promise<RunResult> {
  const res = await apiFetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: scenarioId, use_mock: useMock }),
  });
  return res.json();
}

export function streamRun(
  scenarioId: string,
  useMock: boolean,
  handlers: {
    onReasoning: (chunk: string) => void;
    onScoreReasoning?: (chunk: string) => void;
    onStatus?: (phase: string, message?: string) => void;
    onComplete: (result: RunResult) => void;
    onError: (msg: string) => void;
  },
): () => void {
  const controller = new AbortController();
  const streamUrl = `${DIRECT_BACKEND}/api/run/stream`;
  const streamTimeoutMs = 120_000;
  let timedOut = false;

  const timeoutId = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, streamTimeoutMs);

  (async () => {
    try {
      const res = await fetch(streamUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_id: scenarioId, use_mock: useMock }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body ? `HTTP ${res.status}: ${body.slice(0, 200)}` : `HTTP ${res.status}`);
      }
      if (!res.body) throw new Error("Stream failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const lines = part.split("\n");
          let event = "message";
          let data = "";
          for (const line of lines) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            if (line.startsWith("data:")) data = line.slice(5).trim();
          }
          if (!data) continue;
          const payload = JSON.parse(data);
          if (event === "reasoning") handlers.onReasoning(payload.text ?? "");
          if (event === "score_reasoning") handlers.onScoreReasoning?.(payload.text ?? "");
          if (event === "status") {
            handlers.onStatus?.(payload.phase ?? "", payload.message as string | undefined);
          }
          if (event === "complete") handlers.onComplete(payload as RunResult);
          if (event === "error") handlers.onError(payload.message ?? "Error");
        }
      }
    } catch (e) {
      if (e instanceof Error && e.name === "AbortError") {
        if (timedOut) {
          handlers.onError("Mission run timed out after 2 minutes. Retry or use offline baseline.");
        }
        return;
      }
      handlers.onError(e instanceof Error ? e.message : String(e));
    } finally {
      window.clearTimeout(timeoutId);
    }
  })();

  return () => {
    window.clearTimeout(timeoutId);
    controller.abort();
  };
}

export async function runAll(useMock = false): Promise<BenchmarkRow[]> {
  const res = await apiFetch(`/api/run-all?use_mock=${useMock}`, { method: "POST" });
  return res.json();
}

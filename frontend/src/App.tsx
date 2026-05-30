import { useCallback, useEffect, useState } from "react";
import { fetchScenarios, runAll, streamRun } from "./api";
import { BenchmarkChart } from "./components/BenchmarkChart";
import { OrbitalViewport3D } from "./components/OrbitalViewport3D";
import { ReasoningPanel } from "./components/ReasoningPanel";
import { ScenarioList } from "./components/ScenarioList";
import { CalculationsPanel } from "./components/CalculationsPanel";
import { ScorePanel } from "./components/ScorePanel";
import type { BenchmarkRow, RunResult, Scenario, ScoreBreakdown } from "./types";
import styles from "./App.module.css";

function formatScoreOutcome(score: ScoreBreakdown): string {
  if (score.crashed) {
    return "\n\n--- Simulation outcome ---\nCrashed into Earth. Final score: 0.0 / 100.";
  }
  const parts = [
    `Final score: ${score.score.toFixed(1)} / 100.`,
    `3D miss ${score.miss_km.toFixed(2)} km at T+${score.closest_approach_time_s.toFixed(0)} s.`,
  ];
  if ((score.plane_offset_km ?? 0) > 0.01) {
    parts.push(`Cross-track plane offset ${score.plane_offset_km!.toFixed(2)} km.`);
  }
  parts.push(
    `Fuel ${score.fuel_used.toFixed(3)} km/s (${(score.fuel_ratio * 100).toFixed(0)}% of Lambert/Hohmann optimal).`,
  );
  if (score.fuel_penalty > 0) {
    parts.push(`Over-budget penalty −${(score.fuel_penalty * 100).toFixed(1)} pts.`);
  }
  return `\n\n--- Simulation outcome ---\n${parts.join(" ")}`;
}

export default function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runningAll, setRunningAll] = useState(false);
  const [reasoning, setReasoning] = useState("");
  const [status, setStatus] = useState("Idle");
  const [resultsByScenario, setResultsByScenario] = useState<Record<string, RunResult>>({});
  const [scrubT, setScrubT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [benchmark, setBenchmark] = useState<BenchmarkRow[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingScenarios, setLoadingScenarios] = useState(true);
  const useMock = !import.meta.env.VITE_ANTHROPIC_LIVE;

  const loadScenarios = useCallback(async () => {
    setLoadingScenarios(true);
    setLoadError(null);
    setStatus("Connecting to API…");
    try {
      const list = await fetchScenarios();
      setScenarios(list);
      setSelectedId((prev) => prev ?? list[0]?.id ?? null);
      setStatus(`Ready — ${list.length} scenarios`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setLoadError(msg);
      setStatus(`Error: ${msg}`);
    } finally {
      setLoadingScenarios(false);
    }
  }, []);

  useEffect(() => {
    void loadScenarios();
  }, [loadScenarios]);

  const handleSelectScenario = useCallback((id: string) => {
    setSelectedId(id);
    setScrubT(0);
    setPlaying(false);
    setReasoning("");
    setStatus("Ready — select Run plan");
  }, []);

  const handleRun = useCallback(() => {
    if (!selectedId) return;
    setRunning(true);
    setReasoning("");
    setScrubT(0);
    setPlaying(false);
    setStatus("Planning…");

    const cancel = streamRun(selectedId, useMock, {
      onReasoning: (chunk) => {
        setReasoning((prev) => prev + chunk);
      },
      onComplete: (data) => {
        setResultsByScenario((prev) => ({ ...prev, [data.scenario_id]: data }));
        setReasoning((prev) => prev + formatScoreOutcome(data.score));
        setRunning(false);
        setStatus("Complete");
        setPlaying(true);
        setScrubT(0);
      },
      onError: (msg) => {
        setStatus(`Error: ${msg}`);
        setRunning(false);
      },
    });

    return cancel;
  }, [selectedId, useMock]);

  const handleRunAll = async () => {
    setRunningAll(true);
    setStatus("Benchmarking all scenarios…");
    try {
      const rows = await runAll(useMock);
      setBenchmark(rows);
      setStatus(`Benchmark done (${rows.length} scenarios)`);
    } catch (e) {
      setStatus(String(e));
    } finally {
      setRunningAll(false);
    }
  };

  const selected = scenarios.find((s) => s.id === selectedId) ?? null;
  const result = selectedId ? resultsByScenario[selectedId] ?? null : null;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Orbital Planner</h1>
          <p className={styles.sub}>SWEccathon — AGI & real-world modeling</p>
        </div>
        <div className={styles.headerRight}>
          <p className={styles.mode}>
            {useMock ? "Mock planner (Hohmann)" : "Claude live"}
          </p>
          {loadError && (
            <button type="button" className={styles.retryBanner} onClick={() => void loadScenarios()}>
              Retry API connection
            </button>
          )}
        </div>
      </header>

      {loadError && (
        <div className={styles.errorBanner} role="alert">
          <strong>Backend not reachable.</strong> {loadError}
        </div>
      )}

      <main className={styles.grid}>
        <ScenarioList
          scenarios={scenarios}
          selectedId={selectedId}
          onSelect={handleSelectScenario}
          onRun={handleRun}
          running={running}
          onRunAll={handleRunAll}
          runningAll={runningAll}
          loading={loadingScenarios}
          onRetryLoad={() => void loadScenarios()}
        />

        <section className={styles.center}>
          <p className={styles.sectionLabel}>Orbital viewport</p>
          <OrbitalViewport3D
            scenario={selected}
            score={result?.score ?? null}
            burns={result?.plan.burns ?? []}
            scrubT={scrubT}
            playing={playing}
            onScrub={setScrubT}
            onPlayingChange={setPlaying}
          />
          <BenchmarkChart rows={benchmark} />
        </section>

        <aside className={styles.right}>
          <CalculationsPanel scenario={selected} scrubT={scrubT} result={result} />
          <ReasoningPanel text={reasoning} status={status} />
          <ScorePanel
            key={selectedId ?? "none"}
            score={result?.score ?? null}
            scenarioName={selected?.name}
            fuelBudget={selected?.fuel_budget_dv}
          />
        </aside>
      </main>
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchConfig, fetchScenarios, runAll, streamRun } from "./api";
import { BenchmarkChart } from "./components/BenchmarkChart";
import { OrbitalViewport3D } from "./components/OrbitalViewport3D";
import { ReasoningPanel } from "./components/ReasoningPanel";
import { ScenarioList } from "./components/ScenarioList";
import { CalculationsPanel } from "./components/CalculationsPanel";
import { ScorePanel } from "./components/ScorePanel";
import type { BenchmarkRow, RunResult, Scenario } from "./types";
import styles from "./App.module.css";

function reasoningFromResult(result: RunResult | null | undefined): string {
  if (!result) return "";
  if (result.reasoning_text) return result.reasoning_text;
  const turn1 = result.plan.reasoning || result.raw_response || "";
  const turn2 = result.score_narrative || "";
  if (turn1 && turn2) return `${turn1}\n\n${turn2}`;
  return turn1 || turn2;
}

export default function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runningAll, setRunningAll] = useState(false);
  const [reasoning, setReasoning] = useState("");
  const [resultsByScenario, setResultsByScenario] = useState<Record<string, RunResult>>({});
  const [scrubT, setScrubT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [benchmark, setBenchmark] = useState<BenchmarkRow[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingScenarios, setLoadingScenarios] = useState(true);
  const [useMock, setUseMock] = useState(false);
  const reasoningLiveRef = useRef("");

  const loadScenarios = useCallback(async () => {
    setLoadingScenarios(true);
    setLoadError(null);
    try {
      const [list, config] = await Promise.all([fetchScenarios(), fetchConfig()]);
      setScenarios(list);
      setUseMock(!config.ai_available);
      setSelectedId((prev) => prev ?? list[0]?.id ?? null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setLoadError(msg);
    } finally {
      setLoadingScenarios(false);
    }
  }, []);

  useEffect(() => {
    void loadScenarios();
  }, [loadScenarios]);

  useEffect(() => {
    if (running || !selectedId) return;
    const stored = reasoningFromResult(resultsByScenario[selectedId]);
    reasoningLiveRef.current = stored;
    setReasoning(stored);
  }, [selectedId, running, resultsByScenario]);

  const handleSelectScenario = useCallback((id: string) => {
    setSelectedId(id);
    setScrubT(0);
    setPlaying(false);
  }, []);

  const handleRun = useCallback(() => {
    if (!selectedId) return;
    setRunning(true);
    reasoningLiveRef.current = "";
    setReasoning("");
    setScrubT(0);
    setPlaying(false);

    let outcomeStarted = false;
    const cancel = streamRun(selectedId, useMock, {
      onReasoning: (chunk) => {
        setReasoning((prev) => {
          const next = prev + chunk;
          reasoningLiveRef.current = next;
          return next;
        });
      },
      onStatus: () => {},
      onScoreReasoning: (chunk) => {
        setReasoning((prev) => {
          const next = !outcomeStarted ? `${prev}\n\n${chunk}` : prev + chunk;
          if (!outcomeStarted) outcomeStarted = true;
          reasoningLiveRef.current = next;
          return next;
        });
      },
      onComplete: (data) => {
        let final = reasoningLiveRef.current;
        if (data.score_narrative && !outcomeStarted) {
          final = `${final}\n\n${data.score_narrative}`;
        }
        reasoningLiveRef.current = final;
        setReasoning(final);
        setResultsByScenario((r) => ({
          ...r,
          [data.scenario_id]: { ...data, reasoning_text: final },
        }));
        setRunning(false);
        setPlaying(true);
        setScrubT(0);
      },
      onError: () => {
        setRunning(false);
      },
    });

    return cancel;
  }, [selectedId, useMock]);

  const handleRunAll = async () => {
    setRunningAll(true);
    try {
      const rows = await runAll(useMock);
      setBenchmark(rows);
    } catch {
      /* benchmark errors surface via loadError on next fetch */
    } finally {
      setRunningAll(false);
    }
  };

  const selected = scenarios.find((s) => s.id === selectedId) ?? null;
  const result = selectedId ? resultsByScenario[selectedId] ?? null : null;
  const reasoningText = running ? reasoning : reasoning || reasoningFromResult(result);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Orbital Planner</h1>
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
          <ReasoningPanel text={reasoningText} />
          <ScorePanel
            score={result?.score ?? null}
            scenarioName={selected?.name}
            fuelBudget={selected?.fuel_budget_dv}
          />
        </aside>
      </main>
    </div>
  );
}

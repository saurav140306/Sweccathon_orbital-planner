import type { Scenario, Tier } from "../types";
import styles from "./ScenarioList.module.css";

const TIERS: Tier[] = ["easy", "medium", "hard", "expert"];

interface Props {
  scenarios: Scenario[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRun: () => void;
  running: boolean;
  onRunAll: () => void;
  runningAll: boolean;
  loading?: boolean;
  onRetryLoad?: () => void;
}

export function ScenarioList({
  scenarios,
  selectedId,
  onSelect,
  onRun,
  running,
  onRunAll,
  runningAll,
  loading = false,
  onRetryLoad,
}: Props) {
  const selected = scenarios.find((s) => s.id === selectedId) ?? null;

  return (
    <aside className={styles.aside}>
      <p className={styles.label}>Scenarios</p>
      {loading && <p className={styles.hint}>Loading…</p>}
      {!loading && scenarios.length === 0 && onRetryLoad && (
        <button type="button" className={styles.retryBtn} onClick={onRetryLoad}>
          Reload scenarios
        </button>
      )}
      <nav className={styles.nav}>
        {TIERS.map((tier) => {
          const group = scenarios.filter((s) => s.tier === tier);
          if (!group.length) return null;
          return (
            <div key={tier} className={styles.group}>
              <p className={styles.tier}>{tier}</p>
              <ul>
                {group.map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      className={selectedId === s.id ? styles.active : styles.item}
                      onClick={() => onSelect(s.id)}
                    >
                      {s.name}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </nav>

      {selected && (
        <div className={styles.card}>
          <p className={styles.label}>Parameters</p>
          <dl className={styles.kv}>
            <dt>Position</dt>
            <dd>
              [{selected.spacecraft.position[0].toFixed(0)},{" "}
              {selected.spacecraft.position[1].toFixed(0)}] km
            </dd>
            <dt>Velocity</dt>
            <dd>
              [{selected.spacecraft.velocity[0].toFixed(3)},{" "}
              {selected.spacecraft.velocity[1].toFixed(3)}] km/s
            </dd>
            <dt>Target</dt>
            <dd>
              {selected.target.kind ?? "satellite"} @ r=
              {(selected.target.orbit_radius_km ?? 0).toFixed(0)} km
              <br />
              t=0: [{selected.target.position[0].toFixed(0)},{" "}
              {selected.target.position[1].toFixed(0)}] ±{selected.target.tolerance_km} km
            </dd>
            <dt>Revolution</dt>
            <dd>
              {selected.target.revolution_period_s
                ? `${(selected.target.revolution_period_s / 60).toFixed(1)} min`
                : "circular"}
            </dd>
            <dt>Fuel budget</dt>
            <dd>{selected.fuel_budget_dv} km/s</dd>
            <dt>Time limit</dt>
            <dd>{selected.time_limit_s} s</dd>
          </dl>
        </div>
      )}

      <button type="button" className={styles.runBtn} onClick={onRun} disabled={!selectedId || running}>
        {running ? "Planning…" : "Run plan ▸"}
      </button>
      <button
        type="button"
        className={styles.runAllBtn}
        onClick={onRunAll}
        disabled={runningAll}
      >
        {runningAll ? "Benchmarking…" : "Run all scenarios"}
      </button>
    </aside>
  );
}

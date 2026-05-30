import { useEffect, useState } from "react";
import type { ScoreBreakdown } from "../types";
import styles from "./ScorePanel.module.css";

interface Props {
  score: ScoreBreakdown | null;
  scenarioName?: string;
  fuelBudget?: number;
}

function useCountUp(target: number, active: boolean) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!active) {
      setValue(0);
      return;
    }
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setValue(target);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const duration = 900;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - t) ** 3;
      setValue(target * eased);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, active]);
  return value;
}

export function ScorePanel({ score, scenarioName, fuelBudget = 2 }: Props) {
  const display = useCountUp(score?.score ?? 0, score != null);
  const fuelPct = score ? Math.min(100, (score.fuel_used / fuelBudget) * 100) : 0;
  const effPct = score ? Math.min(100, score.fuel_ratio * 100) : 0;

  if (!score) {
    return (
      <div className={styles.panel}>
        <p className={styles.label}>Score breakdown</p>
        {scenarioName && <p className={styles.scenarioName}>{scenarioName}</p>}
        <p className={styles.placeholder}>Run a plan to see scoring.</p>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <p className={styles.label}>Score breakdown</p>
      {scenarioName && <p className={styles.scenarioName}>{scenarioName}</p>}
      <p className={styles.bigScore}>{display.toFixed(1)}</p>
      <table className={styles.table}>
        <tbody>
          <tr>
            <td>Proximity</td>
            <td>{(score.hit_score * 100).toFixed(1)}%</td>
          </tr>
          <tr>
            <td>Miss distance</td>
            <td>{score.crashed ? "—" : `${score.miss_km.toFixed(2)} km`}</td>
          </tr>
          <tr>
            <td>Fuel used</td>
            <td>{score.fuel_used.toFixed(3)} km/s</td>
          </tr>
          <tr>
            <td>Optimal (Lambert)</td>
            <td>{score.optimal_dv.toFixed(3)} km/s</td>
          </tr>
          <tr>
            <td>Crashed</td>
            <td>{score.crashed ? "Yes" : "No"}</td>
          </tr>
        </tbody>
      </table>
      <div className={styles.barBlock}>
        <span>Fuel vs budget</span>
        <div className={styles.barTrack}>
          <div className={styles.barFill} style={{ width: `${fuelPct}%` }} />
        </div>
      </div>
      <div className={styles.barBlock}>
        <span>Efficiency vs optimal</span>
        <div className={styles.barTrack}>
          <div className={styles.barFillEff} style={{ width: `${effPct}%` }} />
        </div>
        <span className={styles.pct}>{effPct.toFixed(0)}%</span>
      </div>
    </div>
  );
}

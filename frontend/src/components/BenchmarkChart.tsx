import type { BenchmarkRow } from "../types";
import styles from "./BenchmarkChart.module.css";

interface Props {
  rows: BenchmarkRow[];
}

export function BenchmarkChart({ rows }: Props) {
  if (!rows.length) return null;
  const max = Math.max(...rows.map((r) => r.score), 1);

  return (
    <div className={styles.wrap}>
      <p className={styles.label}>Benchmark — score by scenario</p>
      <ul className={styles.list}>
        {rows.map((r) => (
          <li key={r.scenario_id} className={styles.row}>
            <span className={styles.name} title={r.name}>
              {r.scenario_id}
            </span>
            <div className={styles.track}>
              <div
                className={styles.bar}
                style={{ width: `${(r.score / max) * 100}%` }}
                data-tier={r.tier}
              />
            </div>
            <span className={styles.score}>{r.score.toFixed(1)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

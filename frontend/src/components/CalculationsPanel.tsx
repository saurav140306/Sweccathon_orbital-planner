import { useEffect, useState } from "react";
import type { CalculationSnapshot, RunResult, Scenario } from "../types";
import { fetchCalculations } from "../api";
import styles from "./CalculationsPanel.module.css";

interface Props {
  scenario: Scenario | null;
  scrubT: number;
  result: RunResult | null;
}

function fmt(n: number, digits = 2): string {
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function Row({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className={styles.row}>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>
        {value}
        {unit && <span className={styles.unit}>{unit}</span>}
      </span>
    </div>
  );
}

export function CalculationsPanel({ scenario, scrubT, result }: Props) {
  const [calc, setCalc] = useState<CalculationSnapshot | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!scenario) {
      setCalc(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchCalculations(scenario.id, scrubT)
      .then((snap) => {
        if (!cancelled) setCalc(snap);
      })
      .catch(() => {
        if (!cancelled) setCalc(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scenario, scrubT, result?.score.score]);

  if (!scenario) {
    return (
      <div className={styles.panel}>
        <p className={styles.heading}>Orbital calculations</p>
        <p className={styles.placeholder}>Select a scenario to see live physics.</p>
      </div>
    );
  }

  const t = calc?.target ?? {};
  const c = calc?.chaser ?? {};
  const g = calc?.gravity ?? {};
  const sc = calc?.score;
  const isMoon = String(t.kind ?? "") === "moon";

  return (
    <div className={styles.panel}>
      <p className={styles.heading}>Orbital calculations</p>
      <p className={styles.sub}>
        T+{scrubT.toFixed(0)} s {loading ? "· updating…" : ""}
      </p>

      <section className={styles.block}>
        <h3 className={styles.blockTitle}>Constants</h3>
        <div className={styles.formula}>μ = 398600 km³/s² · R⊕ = 6371 km</div>
        <Row label="Earth spin" value={fmt(calc?.earth_spin_deg ?? 0, 1)} unit="°" />
      </section>

      <section className={styles.block}>
        <h3 className={styles.blockTitle}>Target ({String(t.kind ?? "satellite")})</h3>
        <div className={styles.formula}>r = a(1 − e²) / (1 + e cos ν)</div>
        <div className={styles.formula}>ε = v²/2 − μ/r · h = r × v</div>
        <Row label="Orbit" value={String(t.orbit_type ?? "elliptical")} />
        <Row label="Semi-major a" value={fmt(Number(t.semi_major_axis_km ?? 0), 0)} unit="km" />
        <Row label="Eccentricity e" value={fmt(Number(t.eccentricity ?? 0), 3)} />
        <Row label="Peri / Apo" value={`${fmt(Number(t.periapsis_km ?? 0), 0)} / ${fmt(Number(t.apoapsis_km ?? 0), 0)}`} unit="km" />
        <Row label="Period" value={fmt(Number(t.period_min ?? 0), 1)} unit="min" />
        <Row label="Radius r" value={fmt(Number(t.radius_km ?? 0), 1)} unit="km" />
        <Row label="Speed |v|" value={fmt(Number(t.speed_km_s ?? 0), 3)} unit="km/s" />
        <Row label="True anomaly ν" value={fmt(Number(t.true_anomaly_deg ?? 0), 1)} unit="°" />
        <Row label="Specific ε" value={fmt(Number(t.specific_energy ?? 0), 2)} unit="km²/s²" />
        {isMoon && (
          <>
            <Row label="μ body (GM)" value={fmt(Number(t.mu_body_km3_s2 ?? 0), 1)} unit="km³/s²" />
            <Row label="Body radius" value={fmt(Number(t.body_radius_km ?? 0), 0)} unit="km" />
          </>
        )}
      </section>

      <section className={styles.block}>
        <h3 className={styles.blockTitle}>Chaser (coast ellipse)</h3>
        <Row label="Semi-major a" value={fmt(Number(c.semi_major_axis_km ?? 0), 0)} unit="km" />
        <Row label="Eccentricity e" value={fmt(Number(c.eccentricity ?? 0), 3)} />
        <Row label="Radius r" value={fmt(Number(c.radius_km ?? 0), 1)} unit="km" />
        <Row label="Speed |v|" value={fmt(Number(c.speed_km_s ?? 0), 3)} unit="km/s" />
        <Row label="ν" value={fmt(Number(c.true_anomaly_deg ?? 0), 1)} unit="°" />
        <p className={styles.note}>{String(c.free_orbit ?? "")}</p>
      </section>

      <section className={styles.block}>
        <h3 className={styles.blockTitle}>Gravity integration</h3>
        <div className={styles.formula}>{String(g.earth_formula ?? "a⊕ = −μ⊕ r / |r|³")}</div>
        {isMoon && (
          <>
            <div className={styles.formula}>{String(g.moon_formula ?? "a☾ = μ☾ (r_moon − r) / |r_moon − r|³")}</div>
            <Row label="|a⊕|" value={fmt(Number(g.earth_accel_km_s2 ?? 0), 5)} unit="km/s²" />
            <Row label="|a☾|" value={fmt(Number(g.moon_accel_km_s2 ?? 0), 5)} unit="km/s²" />
            <Row label="|a| total" value={fmt(Number(g.total_accel_km_s2 ?? 0), 5)} unit="km/s²" />
            <Row label="Separation" value={fmt(Number(g.moon_separation_km ?? 0), 0)} unit="km" />
            <p className={styles.note}>{String(g.model ?? "restricted 3-body")}</p>
          </>
        )}
        {!isMoon && (
          <div className={styles.formula}>Satellite target — no third-body gravity</div>
        )}
        <div className={styles.formula}>Burns: v → v + Δv (impulsive)</div>
        <p className={styles.note}>Trajectory propagated with RK4 · Δt = 10 s</p>
      </section>

      {(sc || result?.score) && (
        <section className={styles.blockHighlight}>
          <h3 className={styles.blockTitle}>Score</h3>
          <div className={styles.formula}>
            {String(sc?.hit_formula ?? "proximity = 1 / (1 + miss / miss_scale)")}
          </div>
          <div className={styles.formula}>
            {String(sc?.score_formula ?? "100×(0.5·proximity + 0.3·fuel + 0.2·budget) − penalty")}
          </div>
          <Row
            label="Proximity"
            value={`${fmt((result?.score?.hit_score ?? Number(sc?.hit_score ?? 0)) * 100, 1)}%`}
          />
          <Row
            label="Miss"
            value={fmt(result?.score?.miss_km ?? Number(sc?.miss_km ?? 0), 2)}
            unit="km"
          />
          <Row
            label="Fuel used"
            value={fmt(result?.score?.fuel_used ?? Number(sc?.fuel_used ?? 0), 3)}
            unit="km/s"
          />
          <Row
            label="vs optimal"
            value={`${fmt((result?.score?.fuel_ratio ?? Number(sc?.fuel_ratio ?? 0)) * 100, 0)}%`}
          />
          <p className={styles.bigScore}>
            {fmt(result?.score?.score ?? Number(sc?.final_score ?? 0), 1)}
          </p>
        </section>
      )}
    </div>
  );
}

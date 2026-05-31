import { useEffect, useRef, useState } from "react";
import type { Scenario } from "../types";
import { getTargetMotion } from "../orbitalMotion";
import {
  ChaserLegendIcon,
  EarthLegendIcon,
  OrbitLegendSwatch,
  TargetLegendIcon,
} from "./ViewportLegendIcons";
import styles from "./OrbitalCanvas.module.css";

interface Props {
  scenario: Scenario | null;
}

export function ViewportKey({ scenario }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  if (!scenario) return null;

  const motion = getTargetMotion(scenario.target);
  const isMoon = motion.kind === "moon";
  const targetKind = isMoon ? "moon" : "satellite";

  return (
    <div className={styles.keyDropdown} ref={rootRef}>
      <button
        type="button"
        className={styles.keyToggle}
        aria-expanded={open}
        aria-controls="viewport-key-panel"
        onClick={() => setOpen((v) => !v)}
      >
        <span className={styles.keyToggleIcons} aria-hidden>
          <ChaserLegendIcon size={14} />
          <TargetLegendIcon kind={targetKind} size={14} />
        </span>
        Key
      </button>

      {open && (
        <div id="viewport-key-panel" className={styles.keyPanel} role="region" aria-label="Viewport legend">
          <div className={styles.keyItemCompact}>
            <ChaserLegendIcon size={14} />
            <span>Chaser</span>
          </div>
          <div className={styles.keyItemCompact}>
            <TargetLegendIcon kind={targetKind} size={14} />
            <span>Target{isMoon ? " (moon)" : ""}</span>
          </div>
          <div className={styles.keyItemCompact}>
            <OrbitLegendSwatch kind="chaser" />
            <span>Chaser orbit</span>
          </div>
          <div className={styles.keyItemCompact}>
            <OrbitLegendSwatch kind={isMoon ? "moon" : "satellite"} />
            <span>Target orbit</span>
          </div>
          <div className={styles.keyItemCompact}>
            <EarthLegendIcon size={14} />
            <span>Earth</span>
          </div>
        </div>
      )}
    </div>
  );
}

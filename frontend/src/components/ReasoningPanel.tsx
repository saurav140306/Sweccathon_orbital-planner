import styles from "./ReasoningPanel.module.css";

interface Props {
  text: string;
  status: string;
  turn?: number;
}

export function ReasoningPanel({ text, status, turn = 1 }: Props) {
  const isComplete = /complete/i.test(status);

  return (
    <div className={styles.panel}>
      <div className={styles.headerRow}>
        <p className={styles.label}>Mesocosm reasoning</p>
        <span className={styles.turnBadge}>Turn {turn}</span>
      </div>
      <p className={isComplete ? styles.statusDone : styles.status}>{status}</p>
      <div className={styles.trace}>{text || "Waiting for agent turn…"}</div>
    </div>
  );
}

import styles from "./ReasoningPanel.module.css";

interface Props {
  text: string;
}

export function ReasoningPanel({ text }: Props) {
  return (
    <div className={styles.panel}>
      <p className={styles.label}>Mesocosm reasoning</p>
      <div className={styles.trace}>{text || "Waiting for agent turn…"}</div>
    </div>
  );
}

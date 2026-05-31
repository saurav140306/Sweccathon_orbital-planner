import { useId } from "react";
import styles from "./OrbitalCanvas.module.css";

interface IconProps {
  size?: number;
  className?: string;
}

/** Matches bird's-eye / 3D chaser: mint triangle + cream ring. */
export function ChaserLegendIcon({ size = 16, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className ?? styles.legendIcon}
      aria-hidden
    >
      <circle cx="12" cy="12" r="10" fill="rgba(93, 202, 165, 0.25)" />
      <circle
        cx="12"
        cy="12"
        r="8"
        fill="none"
        stroke="rgba(245, 240, 230, 0.7)"
        strokeWidth="1.5"
      />
      <path
        d="M12 5 L19 16 L5 16 Z"
        fill="#5dcaa5"
        stroke="#f5f0e6"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Matches bird's-eye moon: gray sphere, craters, spin marker. */
export function MoonLegendIcon({ size = 16, className }: IconProps) {
  const gradId = useId();
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className ?? styles.legendIcon}
      aria-hidden
    >
      <defs>
        <radialGradient id={gradId} cx="35%" cy="30%" r="65%">
          <stop offset="0%" stopColor="#ece8e0" />
          <stop offset="55%" stopColor="#c8c4bc" />
          <stop offset="100%" stopColor="#7a7872" />
        </radialGradient>
      </defs>
      <circle cx="12" cy="12" r="9" fill={`url(#${gradId})`} />
      <circle cx="9" cy="10" r="2" fill="rgba(55, 53, 50, 0.4)" />
      <circle cx="15" cy="14" r="1.6" fill="rgba(55, 53, 50, 0.35)" />
      <circle cx="11" cy="15" r="1.2" fill="rgba(55, 53, 50, 0.3)" />
      <line x1="12" y1="12" x2="19" y2="12" stroke="rgba(245, 240, 230, 0.55)" strokeWidth="1.2" />
      <circle
        cx="12"
        cy="12"
        r="10.5"
        fill="none"
        stroke="rgba(232, 228, 220, 0.35)"
        strokeWidth="1"
      />
    </svg>
  );
}

/** Matches bird's-eye satellite: bus + solar panels. */
export function SatelliteLegendIcon({ size = 16, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className ?? styles.legendIcon}
      aria-hidden
    >
      <circle cx="12" cy="12" r="9" fill="rgba(93, 202, 165, 0.2)" />
      <rect x="9" y="10" width="6" height="4" fill="#c9d4ce" stroke="#5dcaa5" strokeWidth="1.2" />
      <rect x="3" y="11" width="5" height="2" fill="#3a5a48" />
      <rect x="16" y="11" width="5" height="2" fill="#3a5a48" />
    </svg>
  );
}

export function EarthLegendIcon({ size = 16, className }: IconProps) {
  const gradId = useId();
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className ?? styles.legendIcon}
      aria-hidden
    >
      <defs>
        <radialGradient id={gradId} cx="35%" cy="30%" r="65%">
          <stop offset="0%" stopColor="#4a8a6a" />
          <stop offset="60%" stopColor="#2a5a42" />
          <stop offset="100%" stopColor="#1a4030" />
        </radialGradient>
      </defs>
      <circle cx="12" cy="12" r="9" fill={`url(#${gradId})`} stroke="rgba(232, 193, 112, 0.5)" strokeWidth="1" />
      <line x1="12" y1="3" x2="12" y2="21" stroke="#e8c170" strokeWidth="1.2" opacity="0.85" />
    </svg>
  );
}

type OrbitKind = "chaser" | "moon" | "satellite";

export function OrbitLegendSwatch({ kind, className }: { kind: OrbitKind; className?: string }) {
  const color =
    kind === "chaser" ? "#f5f0e6" : kind === "moon" ? "#c8c8be" : "#5dcaa5";
  return (
    <span
      className={className ?? styles.orbitSwatch}
      style={{ background: color }}
      aria-hidden
    />
  );
}

export function TargetLegendIcon({
  kind,
  size = 16,
  className,
}: IconProps & { kind: "moon" | "satellite" }) {
  return kind === "moon" ? (
    <MoonLegendIcon size={size} className={className} />
  ) : (
    <SatelliteLegendIcon size={size} className={className} />
  );
}

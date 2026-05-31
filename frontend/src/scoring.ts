/** Must match backend orbital_planner/reward.py */
export const SCORE_WEIGHTS = {
  proximity: 0.75,
  fuel: 0.10,
  budget: 0.15,
} as const;

export const BUDGET_USE_FACTOR = 0.65;
export const FUEL_PENALTY_CAP = 0.10;

export function scoreComponentPoints(
  score: {
    hit_score: number;
    fuel_ratio: number;
    fuel_used: number;
  },
  fuelBudget: number,
) {
  return {
    proximityPts: score.hit_score * SCORE_WEIGHTS.proximity * 100,
    fuelPts: Math.min(1, score.fuel_ratio) * SCORE_WEIGHTS.fuel * 100,
    budgetPts: Math.max(0, 1 - BUDGET_USE_FACTOR * score.fuel_used / fuelBudget) * SCORE_WEIGHTS.budget * 100,
  };
}

export function scoreFormulaText(): string {
  const p = SCORE_WEIGHTS.proximity * 100;
  const f = SCORE_WEIGHTS.fuel * 100;
  const b = SCORE_WEIGHTS.budget * 100;
  return `100×(${p}%·proximity + ${f}%·fuel + ${b}%·budget) − penalty (cap ${FUEL_PENALTY_CAP * 100})`;
}

// Trial rules, mirrored from apps/api/app/services/entitlements.py.
// The server is the authority — these constants only drive what the UI shows,
// so a tampered client gets a 402 instead of a file.

export const TRIAL_PLAN_CODE = "trial";

/** Clips a trial account can download: none. The analysis is free, the files are not. */
export const TRIAL_UNLOCKED_CLIPS = 0;

export type ActivePlan = {
  planCode: string;
  isTrial: boolean;
};

export function planFromCode(planCode: string | null | undefined): ActivePlan {
  const code = planCode ?? TRIAL_PLAN_CODE;
  return { planCode: code, isTrial: code === TRIAL_PLAN_CODE };
}

export function clipIsLocked(plan: ActivePlan, idx: number): boolean {
  return plan.isTrial && idx >= TRIAL_UNLOCKED_CLIPS;
}

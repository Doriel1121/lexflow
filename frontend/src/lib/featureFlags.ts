const enabledValues = new Set(["1", "true", "yes", "on"]);

function isEnabled(value: string | undefined): boolean {
  return enabledValues.has((value ?? "").trim().toLowerCase());
}

export const featureFlags = {
  legalWorkflows: isEnabled(import.meta.env.VITE_LEGAL_WORKFLOWS_ENABLED),
};

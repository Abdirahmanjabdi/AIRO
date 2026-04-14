function readBool(value: string | undefined, fallback = false): boolean {
  if (value == null) {
    return fallback;
  }

  return value.trim().toLowerCase() === "true";
}

export const frontendEnv = {
  adminEnabled: readBool(import.meta.env.VITE_ENABLE_ADMIN, false),
};

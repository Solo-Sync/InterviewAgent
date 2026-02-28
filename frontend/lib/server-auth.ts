export const SESSION_COOKIE_NAME = "interview_agent_session"

export function backendOrigin() {
  return process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000"
}

export function authCookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge,
  }
}

export function candidateIdFromEmail(email: string) {
  const normalized = email.trim().toLowerCase()
  const slug = normalized.replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "")
  return `candidate_${slug || "user"}`
}

export function displayNameFromEmail(email: string) {
  const localPart = email.trim().split("@")[0] || "candidate"
  const words = localPart
    .split(/[._-]+/)
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
  return words.join(" ") || "Candidate"
}

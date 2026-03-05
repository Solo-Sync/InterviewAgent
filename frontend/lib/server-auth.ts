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

import type { UserRole } from "@/lib/types"

export type AuthenticatedUser = {
  role: Exclude<UserRole, null>
  email: string
  candidateId: string | null
  displayName: string | null
}

type LoginResponse = {
  user: AuthenticatedUser
}

export async function signIn(role: "admin" | "candidate", email: string, password: string) {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ role, email, password }),
  })

  const payload = (await response.json().catch(() => null)) as { error?: string; user?: AuthenticatedUser } | null
  if (!response.ok || !payload?.user) {
    throw new Error(payload?.error ?? `Login failed: ${response.status}`)
  }

  return (payload as LoginResponse).user
}

export async function signOut() {
  await fetch("/api/auth/logout", {
    method: "POST",
  })
}

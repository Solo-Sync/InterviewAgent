import type { UserRole } from "@/lib/types"

export type AuthenticatedUser = {
  role: Exclude<UserRole, null>
  identifier: string
  candidateId: string | null
  displayName: string | null
}

type LoginResponse = {
  user: AuthenticatedUser
}

type SignInInput =
  | { role: "admin"; email: string; password: string }
  | { role: "candidate"; username: string; password: string }

export async function signIn(input: SignInInput) {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  })

  const payload = (await response.json().catch(() => null)) as { error?: string; user?: AuthenticatedUser } | null
  if (!response.ok || !payload?.user) {
    throw new Error(payload?.error ?? `Login failed: ${response.status}`)
  }

  return (payload as LoginResponse).user
}

export async function registerCandidate(username: string, password: string) {
  const response = await fetch("/api/auth/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
  })

  const payload = (await response.json().catch(() => null)) as { error?: string; user?: AuthenticatedUser } | null
  if (!response.ok || !payload?.user) {
    throw new Error(payload?.error ?? `Registration failed: ${response.status}`)
  }

  return (payload as LoginResponse).user
}

export async function signOut() {
  await fetch("/api/auth/logout", {
    method: "POST",
  })
}

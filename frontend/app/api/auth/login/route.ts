import { NextResponse } from "next/server"
import { authCookieOptions, backendOrigin, SESSION_COOKIE_NAME } from "@/lib/server-auth"

type LoginBody = {
  role?: "admin" | "candidate"
  email?: string
  username?: string
  password?: string
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as LoginBody | null
  const role = body?.role
  const password = body?.password ?? ""

  if (!role) {
    return NextResponse.json({ error: "role is required" }, { status: 400 })
  }

  if (role === "candidate") {
    const username = body.username?.trim() ?? ""
    if (!username) {
      return NextResponse.json({ error: "username is required" }, { status: 400 })
    }
    return forwardCandidateLogin(username, password)
  }

  const email = body.email?.trim() ?? ""
  if (!email) {
    return NextResponse.json({ error: "email is required" }, { status: 400 })
  }

  return forwardAdminLogin(role, email, password)
}

async function forwardCandidateLogin(username: string, password: string) {
  const upstream = await fetch(`${backendOrigin()}/api/v1/auth/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      role: "candidate",
      username,
      password,
    }),
    cache: "no-store",
  })

  return buildAuthResponse(upstream, username)
}

async function forwardAdminLogin(role: "admin", email: string, password: string) {
  const upstream = await fetch(`${backendOrigin()}/api/v1/auth/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      role,
      email,
      password,
    }),
    cache: "no-store",
  })

  return buildAuthResponse(upstream, email)
}

async function buildAuthResponse(upstream: Response, identifier: string) {
  const payload = (await upstream.json().catch(() => null)) as
    | {
        ok?: boolean
        data?: {
          access_token: string
          expires_in: number
          role: "admin" | "candidate" | "annotator"
          candidate_id?: string | null
          display_name?: string | null
        }
        error?: { message?: string }
      }
    | null

  if (!upstream.ok || !payload?.ok || !payload.data) {
    return NextResponse.json(
      { error: payload?.error?.message ?? "Authentication failed" },
      { status: upstream.status || 502 }
    )
  }

  const response = NextResponse.json({
    user: {
      role: payload.data.role,
      identifier,
      candidateId: payload.data.candidate_id ?? null,
      displayName: payload.data.display_name ?? null,
    },
  })
  response.cookies.set(
    SESSION_COOKIE_NAME,
    payload.data.access_token,
    authCookieOptions(payload.data.expires_in)
  )
  return response
}

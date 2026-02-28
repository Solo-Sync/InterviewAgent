import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import {
  authCookieOptions,
  backendOrigin,
  candidateIdFromEmail,
  displayNameFromEmail,
  SESSION_COOKIE_NAME,
} from "@/lib/server-auth"

type LoginBody = {
  role?: "admin" | "candidate"
  email?: string
  password?: string
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as LoginBody | null
  const role = body?.role
  const email = body?.email?.trim() ?? ""
  const password = body?.password ?? ""

  if (!role || !email) {
    return NextResponse.json({ error: "role and email are required" }, { status: 400 })
  }

  const authRequest =
    role === "candidate"
      ? {
          role,
          email,
          password,
          candidate_id: candidateIdFromEmail(email),
          display_name: displayNameFromEmail(email),
        }
      : {
          role,
          email,
          password,
        }

  const upstream = await fetch(`${backendOrigin()}/api/v1/auth/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(authRequest),
    cache: "no-store",
  })

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

  const cookieStore = await cookies()
  cookieStore.set(
    SESSION_COOKIE_NAME,
    payload.data.access_token,
    authCookieOptions(payload.data.expires_in)
  )

  return NextResponse.json({
    user: {
      role: payload.data.role,
      email,
      candidateId: payload.data.candidate_id ?? null,
      displayName: payload.data.display_name ?? null,
    },
  })
}

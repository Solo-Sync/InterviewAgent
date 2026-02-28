import { cookies } from "next/headers"
import { backendOrigin, SESSION_COOKIE_NAME } from "@/lib/server-auth"

type Params = {
  params: Promise<{
    path: string[]
  }>
}

async function proxy(request: Request, { params }: Params) {
  const { path } = await params
  const target = new URL(`/api/v1/${path.join("/")}`, backendOrigin())
  target.search = new URL(request.url).search

  const cookieStore = await cookies()
  const accessToken = cookieStore.get(SESSION_COOKIE_NAME)?.value
  const headers = new Headers(request.headers)
  headers.delete("host")
  headers.delete("cookie")
  headers.delete("content-length")

  if (accessToken && !headers.has("authorization")) {
    headers.set("authorization", `Bearer ${accessToken}`)
  }

  const body =
    request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer()

  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body,
    cache: "no-store",
    redirect: "manual",
  })

  const responseHeaders = new Headers(upstream.headers)
  responseHeaders.delete("content-encoding")
  responseHeaders.delete("transfer-encoding")

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  })
}

export const GET = proxy
export const POST = proxy
export const PUT = proxy
export const PATCH = proxy
export const DELETE = proxy
export const OPTIONS = proxy
export const HEAD = proxy

type ApiError = {
  code: string
  message: string
  detail?: Record<string, unknown> | null
}

type ApiEnvelope<T> = {
  ok: boolean
  data: T
  error?: ApiError | null
  trace_id: string
}

export type BackendNextAction = {
  type: string
  text: string | null
  level: string | null
  payload: Record<string, unknown> | null
}

export type SessionCreatePayload = {
  session: {
    session_id: string
  }
  next_action: BackendNextAction
}

export type TurnCreatePayload = {
  turn: {
    turn_id: string
    turn_index: number
  }
  next_action: BackendNextAction
}

export type SessionEndPayload = {
  report: {
    overall: {
      plan: number
      monitor: number
      evaluate: number
      adapt: number
    }
  }
}

export type HealthPayload = {
  service: string
  version: string
  llm_ready: boolean
  asr_ready: boolean
}

export type QuestionSetListPayload = {
  items: Array<{
    question_set_id: string
    title: string
    description?: string | null
  }>
}

export type RubricListPayload = {
  items: Array<{
    rubric_id: string
    title: string
    description?: string | null
  }>
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  })

  const payload = (await response.json().catch(() => null)) as ApiEnvelope<T> | null
  if (!response.ok || !payload?.ok) {
    const message = payload?.error?.message ?? `Request failed: ${response.status}`
    throw new Error(message)
  }

  return payload.data
}

export async function createInterviewSession(displayName = "Web Candidate") {
  return request<SessionCreatePayload>("/api/v1/sessions", {
    method: "POST",
    body: JSON.stringify({
      candidate: {
        candidate_id: `candidate_${Date.now()}`,
        display_name: displayName,
      },
      mode: "text",
      question_set_id: "qs_fermi_v1",
      scoring_policy_id: "scoring_default_v1",
      scaffold_policy_id: "scaffold_default_v1",
    }),
  })
}

export async function submitInterviewTurn(sessionId: string, answerText: string) {
  return request<TurnCreatePayload>(`/api/v1/sessions/${sessionId}/turns`, {
    method: "POST",
    body: JSON.stringify({
      input: {
        type: "text",
        text: answerText,
      },
    }),
  })
}

export async function finishInterviewSession(sessionId: string, reason: "completed" | "aborted" = "completed") {
  return request<SessionEndPayload>(`/api/v1/sessions/${sessionId}/end`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  })
}

export async function fetchHealth() {
  return request<HealthPayload>("/api/v1/health")
}

export async function listQuestionSets() {
  return request<QuestionSetListPayload>("/api/v1/admin/question_sets")
}

export async function listRubrics() {
  return request<RubricListPayload>("/api/v1/admin/rubrics")
}

export type UserRole = "admin" | "candidate" | "annotator" | null

export interface AuthSession {
  role: Exclude<UserRole, null>
  identifier: string
  candidateId: string | null
  displayName: string | null
}

export type CandidateStatus = "pending" | "in-progress" | "completed" | "invalid"

export interface ScoreDimensions {
  plan: number
  monitor: number
  evaluate: number
  adapt: number
}

export interface SessionCandidate {
  candidate_id: string
  display_name: string | null
}

export interface InterviewSessionRecord {
  session_id: string
  candidate: SessionCandidate | null
  mode: string
  state: string
  question_set_id: string
  scoring_policy_id: string
  scaffold_policy_id: string
  created_at: string
}

export interface InterviewTurnRecord {
  turn_id: string
  turn_index: number
  input: {
    type: string
    text: string | null
    audio_url?: string | null
    audio_id?: string | null
  }
  next_action?: {
    type: string
    text: string | null
    level: string | null
    payload: Record<string, unknown> | null
  } | null
  created_at: string
}

export interface SessionReport {
  overall: ScoreDimensions
  timeline: Array<{
    turn_index: number
    scores: ScoreDimensions
  }>
  notes?: string[] | null
}

export interface Candidate {
  id: string
  name: string
  email: string
  role: string
  status: CandidateStatus
  score: number | null
  avatar: string
}

export interface ChatMessage {
  id: string
  sender: "system" | "user"
  text: string
  timestamp: string
}

export interface AdminSessionSummary {
  session: InterviewSessionRecord
  turn_count: number
  report: SessionReport | null
  review_status: Exclude<CandidateStatus, "pending">
  prompt_injection_count: number
  invalid_reason: string | null
}

export interface AdminSessionDetail {
  session: InterviewSessionRecord
  turns: InterviewTurnRecord[]
  report: SessionReport | null
  opening_prompt: string | null
  review_status: Exclude<CandidateStatus, "pending">
  prompt_injection_count: number
  invalid_reason: string | null
}

export type InterviewState = "idle" | "recording" | "processing"

export type AppView =
  | "login"
  | "admin-dashboard"
  | "admin-review"
  | "candidate-onboarding"
  | "candidate-interview"

export type UserRole = "admin" | "candidate" | null

export type CandidateStatus = "pending" | "in-progress" | "completed"

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

export type InterviewState = "idle" | "recording" | "processing"

export type AppView =
  | "login"
  | "admin-dashboard"
  | "admin-review"
  | "candidate-onboarding"
  | "candidate-interview"

"use client"

import { useEffect, useMemo, useState } from "react"
import { ArrowLeft, BrainCircuit, Bot, User, FileText, Clock3 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { getAdminSession } from "@/lib/api"
import type {
  AdminSessionDetail,
  AdminSessionSummary,
  ChatMessage,
  ScoreDimensions,
} from "@/lib/types"

interface AdminReviewProps {
  sessionSummary: AdminSessionSummary
  onBack: () => void
}

function scorePercent(value: number) {
  return `${Math.round(value * 100)} / 100`
}

function averageScore(score: ScoreDimensions) {
  return Math.round(((score.plan + score.monitor + score.evaluate + score.adapt) / 4) * 100)
}

function sessionLabel(summary: AdminSessionSummary) {
  return (
    summary.session.candidate?.display_name ||
    summary.session.candidate?.candidate_id ||
    summary.session.session_id
  )
}

function initials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("")
}

function buildTranscript(detail: AdminSessionDetail): ChatMessage[] {
  const messages: ChatMessage[] = []
  const makeTimestamp = (iso: string) =>
    new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })

  if (detail.opening_prompt) {
    messages.push({
      id: "opening-prompt",
      sender: "system",
      text: detail.opening_prompt,
      timestamp: makeTimestamp(detail.session.created_at),
    })
  }

  detail.turns.forEach((turn) => {
    if (turn.input.text) {
      messages.push({
        id: `${turn.turn_id}-user`,
        sender: "user",
        text: turn.input.text,
        timestamp: makeTimestamp(turn.created_at),
      })
    }

    if (turn.next_action?.text) {
      messages.push({
        id: `${turn.turn_id}-system`,
        sender: "system",
        text: turn.next_action.text,
        timestamp: makeTimestamp(turn.created_at),
      })
    }
  })

  return messages
}

export function AdminReview({ sessionSummary, onBack }: AdminReviewProps) {
  const [detail, setDetail] = useState<AdminSessionDetail | null>(null)
  const [errorText, setErrorText] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setErrorText(null)

    void (async () => {
      try {
        const payload = await getAdminSession(sessionSummary.session.session_id)
        if (cancelled) return
        setDetail(payload)
      } catch (error) {
        if (cancelled) return
        setErrorText(error instanceof Error ? error.message : "Failed to load session detail")
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [sessionSummary.session.session_id])

  const transcript = useMemo(() => (detail ? buildTranscript(detail) : []), [detail])
  const report = detail?.report ?? sessionSummary.report
  const reviewStatus = detail?.review_status ?? sessionSummary.review_status
  const promptInjectionCount = detail?.prompt_injection_count ?? sessionSummary.prompt_injection_count
  const invalidReason = detail?.invalid_reason ?? sessionSummary.invalid_reason
  const candidateName = sessionLabel(sessionSummary)
  const candidateId = sessionSummary.session.candidate?.candidate_id ?? "unknown"
  const createdAt = new Date(sessionSummary.session.created_at).toLocaleString()

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-30 border-b border-border bg-card">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 lg:px-8">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={onBack} aria-label="Back to dashboard">
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <Separator orientation="vertical" className="h-6" />
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <BrainCircuit className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-foreground">{candidateName}</h1>
              <p className="text-xs text-muted-foreground">{candidateId}</p>
            </div>
          </div>
          <Badge
            variant="outline"
            className={
              reviewStatus === "invalid"
                ? "border-rose-200 bg-rose-50 text-rose-700"
                : report
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-amber-200 bg-amber-50 text-amber-700"
            }
          >
            {reviewStatus === "invalid" ? "Invalid" : report ? "Completed" : "In Progress"}
          </Badge>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col lg:flex-row">
        <div className="flex flex-1 flex-col border-b border-border lg:border-b-0 lg:border-r">
          <div className="border-b border-border bg-card px-6 py-4">
            <h2 className="text-sm font-semibold text-foreground">Interview Transcript</h2>
            <p className="text-xs text-muted-foreground">Real turn history from the backend</p>
          </div>
          <ScrollArea className="flex-1 p-6" style={{ maxHeight: "calc(100vh - 180px)" }}>
            {isLoading ? (
              <div className="text-sm text-muted-foreground">Loading transcript...</div>
            ) : errorText ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                {errorText}
              </div>
            ) : transcript.length === 0 ? (
              <div className="text-sm text-muted-foreground">No turns have been submitted yet.</div>
            ) : (
              <div className="flex flex-col gap-4">
                {transcript.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex gap-3 ${msg.sender === "user" ? "flex-row-reverse" : "flex-row"}`}
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-card">
                      {msg.sender === "system" ? (
                        <Bot className="h-4 w-4 text-primary" />
                      ) : (
                        <User className="h-4 w-4 text-muted-foreground" />
                      )}
                    </div>
                    <div
                      className={`max-w-[80%] rounded-lg px-4 py-3 ${
                        msg.sender === "system"
                          ? "border border-primary/20 bg-card text-foreground"
                          : "bg-primary/10 text-foreground"
                      }`}
                    >
                      <p className="text-sm leading-relaxed">{msg.text}</p>
                      <p className="mt-1.5 text-xs text-muted-foreground">{msg.timestamp}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>

        <div className="flex w-full flex-col lg:w-[420px]">
          <div className="border-b border-border bg-card px-6 py-4">
            <h2 className="text-sm font-semibold text-foreground">Session Overview</h2>
            <p className="text-xs text-muted-foreground">Read-only data from session and report APIs</p>
          </div>
          <div className="flex flex-1 flex-col gap-6 p-6">
            <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
              <Avatar className="h-10 w-10 border border-border">
                <AvatarFallback className="bg-primary/10 text-sm font-medium text-primary">
                  {initials(candidateName)}
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="font-medium text-foreground">{candidateName}</p>
                <p className="text-xs text-muted-foreground">{candidateId}</p>
              </div>
            </div>

            <div className="grid gap-3">
              <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
                <FileText className="h-4 w-4 text-primary" />
                <div>
                  <p className="text-sm font-medium text-foreground">{sessionSummary.session.question_set_id}</p>
                  <p className="text-xs text-muted-foreground">Question set</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
                <Clock3 className="h-4 w-4 text-primary" />
                <div>
                  <p className="text-sm font-medium text-foreground">{createdAt}</p>
                  <p className="text-xs text-muted-foreground">Created at</p>
                </div>
              </div>
            </div>

            {reviewStatus === "invalid" ? (
              <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
                <p className="font-medium">This interview was marked Invalid.</p>
                <p className="mt-1">
                  Prompt injection detections: {promptInjectionCount}
                  {invalidReason ? ` | Reason: ${invalidReason}` : ""}
                </p>
              </div>
            ) : report ? (
              <>
                <div className="rounded-lg border border-border bg-card p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">Overall Score</span>
                    <span className="rounded-md bg-primary/10 px-2.5 py-1 text-sm font-bold text-primary">
                      {averageScore(report.overall)}/100
                    </span>
                  </div>
                </div>

                <div className="grid gap-3">
                  {(
                    [
                      ["Plan", report.overall.plan],
                      ["Monitor", report.overall.monitor],
                      ["Evaluate", report.overall.evaluate],
                      ["Adapt", report.overall.adapt],
                    ] as const
                  ).map(([label, value]) => (
                    <div key={label} className="rounded-lg border border-border bg-card p-4">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-foreground">{label}</span>
                        <span className="text-sm text-muted-foreground">{scorePercent(value)}</span>
                      </div>
                    </div>
                  ))}
                </div>

              </>
            ) : (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                This interview is still running. Final scoring will appear after the candidate ends the session.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

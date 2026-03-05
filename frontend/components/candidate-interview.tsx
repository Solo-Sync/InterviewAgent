"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { BrainCircuit, Clock, Bot, User, Send } from "lucide-react"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  createInterviewSession,
  finishInterviewSession,
  submitInterviewTurn,
} from "@/lib/api"
import type { ChatMessage, InterviewState } from "@/lib/types"

interface CandidateInterviewProps {
  onLogout: () => void
  candidateId: string
  displayName: string | null
}

function formatScoreLabel(score: { plan: number; monitor: number; evaluate: number; adapt: number }) {
  const avg = (score.plan + score.monitor + score.evaluate + score.adapt) / 4
  return `${Math.round(avg * 100)} / 100`
}

export function CandidateInterview({ onLogout, candidateId, displayName }: CandidateInterviewProps) {
  const [timeLeft, setTimeLeft] = useState(1800)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [interviewState, setInterviewState] = useState<InterviewState>("processing")
  const [interviewComplete, setInterviewComplete] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [turnCount, setTurnCount] = useState(0)
  const [errorText, setErrorText] = useState<string | null>(null)
  const [draftAnswer, setDraftAnswer] = useState("")
  const hasBootstrappedRef = useRef(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const progressPercent = interviewComplete ? 100 : Math.min(92, turnCount * 12)

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
  }

  const makeTimestamp = () =>
    new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })

  useEffect(() => {
    if (!sessionId || timeLeft <= 0 || interviewComplete) return
    const interval = setInterval(() => {
      setTimeLeft((t) => Math.max(0, t - 1))
    }, 1000)
    return () => clearInterval(interval)
  }, [interviewComplete, sessionId, timeLeft])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const initializeInterview = useCallback(async () => {
    if (sessionId) return
    setInterviewState("processing")
    setErrorText(null)

    try {
      const candidateName = displayName?.trim() || "Web Candidate"
      const payload = await createInterviewSession(candidateId, candidateName)
      setSessionId(payload.session.session_id)
      setMessages([
        {
          id: "system-intro",
          sender: "system",
          text: "Text mode is enabled. Type each answer below and send it to continue.",
          timestamp: makeTimestamp(),
        },
        {
          id: "system-first",
          sender: "system",
          text: payload.next_action.text ?? "请先说说你会如何拆解这个问题。",
          timestamp: makeTimestamp(),
        },
      ])
      setInterviewState("idle")
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to start interview session"
      setErrorText(message)
      setMessages([
        {
          id: "system-start-error",
          sender: "system",
          text: `无法连接后端：${message}`,
          timestamp: makeTimestamp(),
        },
      ])
      setInterviewState("idle")
    }
  }, [candidateId, displayName, sessionId])

  useEffect(() => {
    if (hasBootstrappedRef.current) return
    hasBootstrappedRef.current = true
    void initializeInterview()
  }, [initializeInterview])

  const handleSubmitAnswer = useCallback(async () => {
    if (interviewState !== "idle" || interviewComplete || !sessionId) return

    const userText = draftAnswer.trim()
    if (!userText) return

    const currentTurn = turnCount
    setDraftAnswer("")
    setInterviewState("processing")
    setErrorText(null)
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        sender: "user",
        text: userText,
        timestamp: makeTimestamp(),
      },
    ])

    try {
      const payload = await submitInterviewTurn(sessionId, userText)
      const nextTurn = currentTurn + 1
      const shouldComplete = payload.next_action.type === "END"
      setTurnCount(nextTurn)

      if (shouldComplete) {
        let summary = "That concludes your interview. Thank you for your answers."
        try {
          const ended = await finishInterviewSession(sessionId, "completed")
          summary = `Interview completed. Final score: ${formatScoreLabel(ended.report.overall)}.`
        } catch {
          // Keep fallback summary when end endpoint fails.
        }

        setInterviewComplete(true)
        setMessages((prev) => [
          ...prev,
          {
            id: `complete-${nextTurn}`,
            sender: "system",
            text: summary,
            timestamp: makeTimestamp(),
          },
        ])
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `system-${nextTurn}`,
            sender: "system",
            text: payload.next_action.text ?? "请继续说明你的思路。",
            timestamp: makeTimestamp(),
          },
        ])
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to submit answer"
      setErrorText(message)
      setMessages((prev) => [
        ...prev,
        {
          id: `system-turn-error-${Date.now()}`,
          sender: "system",
          text: `提交失败：${message}`,
          timestamp: makeTimestamp(),
        },
      ])
    } finally {
      setInterviewState("idle")
    }
  }, [draftAnswer, interviewComplete, interviewState, sessionId, turnCount])

  return (
    <div className="flex h-screen flex-col bg-background">
      <header className="shrink-0 border-b border-border bg-card">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <BrainCircuit className="h-4 w-4" />
            </div>
            <span className="text-sm font-semibold text-foreground">InterviewAI</span>
          </div>
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span className="font-mono text-sm font-medium tabular-nums">
              {formatTime(timeLeft)}
            </span>
          </div>
        </div>

        <div className="mx-auto max-w-3xl px-4 pb-3">
          <div className="flex items-center justify-between pb-1.5">
            <span className="text-xs font-semibold text-foreground">
              {interviewComplete
                ? "Interview Complete"
                : `Round ${turnCount + 1}`}
            </span>
            <span className="text-xs text-muted-foreground">{Math.round(progressPercent)}%</span>
          </div>
          <Progress value={progressPercent} className="h-1.5" />
        </div>
      </header>

      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
          {errorText ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              Backend error: {errorText}
            </div>
          ) : null}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.sender === "user" ? "flex-row-reverse" : "flex-row"}`}
            >
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                  msg.sender === "system"
                    ? "border border-primary/20 bg-primary/5"
                    : "border border-border bg-card"
                }`}
              >
                {msg.sender === "system" ? (
                  <Bot className="h-4 w-4 text-primary" />
                ) : (
                  <User className="h-4 w-4 text-muted-foreground" />
                )}
              </div>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                  msg.sender === "system"
                    ? "rounded-tl-sm border border-primary/20 bg-card text-foreground"
                    : "rounded-tr-sm bg-primary/10 text-foreground"
                }`}
              >
                <p className="text-sm leading-relaxed">{msg.text}</p>
                <p className="mt-1.5 text-[10px] text-muted-foreground">{msg.timestamp}</p>
              </div>
            </div>
          ))}

          {interviewState === "processing" ? (
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-primary/20 bg-primary/5">
                <Bot className="h-4 w-4 text-primary" />
              </div>
              <div className="rounded-2xl rounded-tl-sm border border-primary/20 bg-card px-4 py-3">
                <div className="flex items-center gap-1.5">
                  <span
                    className="h-2 w-2 animate-bounce rounded-full bg-primary/50"
                    style={{ animationDelay: "0ms" }}
                  />
                  <span
                    className="h-2 w-2 animate-bounce rounded-full bg-primary/50"
                    style={{ animationDelay: "150ms" }}
                  />
                  <span
                    className="h-2 w-2 animate-bounce rounded-full bg-primary/50"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </ScrollArea>

      <div className="shrink-0 border-t border-border bg-card">
        <div className="mx-auto max-w-3xl px-4 py-4">
          {!sessionId && errorText ? (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-4 py-3">
              <span className="text-sm text-muted-foreground">The interview could not start.</span>
              <Button variant="outline" onClick={() => void initializeInterview()}>
                Retry
              </Button>
            </div>
          ) : !interviewComplete ? (
            <form
              onSubmit={(event) => {
                event.preventDefault()
                void handleSubmitAnswer()
              }}
              className="flex flex-col gap-3"
            >
              <Textarea
                value={draftAnswer}
                onChange={(event) => setDraftAnswer(event.target.value)}
                placeholder="Type your answer here..."
                disabled={interviewState !== "idle" || !sessionId}
                className="min-h-[120px] resize-none bg-background"
              />
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-muted-foreground">
                  Real text mode is active. Each send creates a real interview turn.
                </p>
                <Button
                  type="submit"
                  disabled={interviewState !== "idle" || !sessionId || !draftAnswer.trim()}
                  className="bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  <Send className="mr-2 h-4 w-4" />
                  Send Answer
                </Button>
              </div>
            </form>
          ) : (
            <Button variant="outline" onClick={onLogout}>
              Exit Interview
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

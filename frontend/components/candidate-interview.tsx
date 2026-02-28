"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { BrainCircuit, Clock, Bot, User } from "lucide-react"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { MicCheckModal } from "@/components/mic-check-modal"
import { RecordButton } from "@/components/record-button"
import { WaveformVisualizer } from "@/components/waveform-visualizer"
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

const TARGET_TURNS = 6

const scriptedAnswers = [
  "我会先明确目标、约束和可用信息，再拆解出可验证的假设。",
  "我会先做最小可行验证，优先排除高风险假设。",
  "如果结果偏离预期，我会回到输入数据和边界条件重新检查。",
  "我会把方案分层实现，并预留观察指标做迭代。",
  "我会通过对照实验和回放日志来验证结论是否稳健。",
  "最终我会总结哪些策略有效，哪些需要在下一轮调整。",
]

function formatScoreLabel(score: { plan: number; monitor: number; evaluate: number; adapt: number }) {
  const avg = (score.plan + score.monitor + score.evaluate + score.adapt) / 4
  return `${Math.round(avg * 100)} / 100`
}

export function CandidateInterview({ onLogout, candidateId, displayName }: CandidateInterviewProps) {
  const [showMicCheck, setShowMicCheck] = useState(true)
  const [timeLeft, setTimeLeft] = useState(1800)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [interviewState, setInterviewState] = useState<InterviewState>("idle")
  const [interviewComplete, setInterviewComplete] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [turnCount, setTurnCount] = useState(0)
  const [errorText, setErrorText] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const progressPercent = interviewComplete ? 100 : (turnCount / TARGET_TURNS) * 100

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
  }

  useEffect(() => {
    if (showMicCheck || timeLeft <= 0 || interviewComplete) return
    const interval = setInterval(() => {
      setTimeLeft((t) => Math.max(0, t - 1))
    }, 1000)
    return () => clearInterval(interval)
  }, [showMicCheck, timeLeft, interviewComplete])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const makeTimestamp = () =>
    new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })

  const handleMicReady = useCallback(() => {
    setShowMicCheck(false)
    setInterviewState("processing")
    setErrorText(null)

    void (async () => {
      try {
        const candidateName = displayName?.trim() || "Web Candidate"
        const payload = await createInterviewSession(candidateId, candidateName)
        setSessionId(payload.session.session_id)
        setMessages([
          {
            id: "system-intro",
            sender: "system",
            text: "Welcome! Let's begin. Hold the microphone button to record your answer.",
            timestamp: makeTimestamp(),
          },
          {
            id: "system-first",
            sender: "system",
            text: payload.next_action.text ?? "请先说说你会如何拆解这个问题。",
            timestamp: makeTimestamp(),
          },
        ])
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
      } finally {
        setInterviewState("idle")
      }
    })()
  }, [candidateId, displayName])

  const handlePressStart = useCallback(() => {
    if (interviewState !== "idle" || interviewComplete || !sessionId) return
    setInterviewState("recording")
  }, [interviewState, interviewComplete, sessionId])

  const handlePressEnd = useCallback(() => {
    if (interviewState !== "recording" || !sessionId) return

    const currentTurn = turnCount
    const userText = scriptedAnswers[currentTurn % scriptedAnswers.length]

    setInterviewState("processing")
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${currentTurn}`,
        sender: "user",
        text: userText,
        timestamp: makeTimestamp(),
      },
    ])

    void (async () => {
      try {
        const payload = await submitInterviewTurn(sessionId, userText)
        const nextTurn = currentTurn + 1
        const shouldComplete = nextTurn >= TARGET_TURNS || payload.next_action.type === "END"

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
    })()
  }, [interviewState, sessionId, turnCount])

  return (
    <>
      <MicCheckModal open={showMicCheck} onReady={handleMicReady} />

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
                  : `Round ${Math.min(turnCount + 1, TARGET_TURNS)} of ${TARGET_TURNS}`}
              </span>
              <span className="text-xs text-muted-foreground">
                {Math.round(progressPercent)}%
              </span>
            </div>
            <Progress value={progressPercent} className="h-1.5" />
          </div>
        </header>

        <ScrollArea className="flex-1" ref={scrollRef}>
          <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
            {errorText && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                Backend error: {errorText}
              </div>
            )}

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

            {interviewState === "processing" && (
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
            )}
          </div>
        </ScrollArea>

        <div className="shrink-0 border-t border-border bg-card">
          <div className="mx-auto max-w-3xl px-4 py-4">
            <div
              className={`mb-3 transition-opacity duration-200 ${
                interviewState === "recording" ? "opacity-100" : "opacity-0 pointer-events-none"
              }`}
            >
              <WaveformVisualizer isActive={interviewState === "recording"} />
            </div>

            <div className="flex items-center justify-center">
              {!interviewComplete ? (
                <RecordButton
                  state={interviewState}
                  onPressStart={handlePressStart}
                  onPressEnd={handlePressEnd}
                />
              ) : (
                <Button variant="outline" onClick={onLogout}>
                  Exit Interview
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

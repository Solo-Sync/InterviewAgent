"use client"

import { useState } from "react"
import {
  ArrowLeft,
  BrainCircuit,
  Send,
  User,
  Bot,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { sampleTranscript } from "@/lib/mock-data"
import type { Candidate } from "@/lib/types"

interface AdminReviewProps {
  candidate: Candidate
  onBack: () => void
}

export function AdminReview({ candidate, onBack }: AdminReviewProps) {
  const [score, setScore] = useState<number>(candidate.score ?? 75)
  const [passed, setPassed] = useState(true)
  const [feedback, setFeedback] = useState("")

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Header */}
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
              <h1 className="text-sm font-semibold text-foreground">Review: {candidate.name}</h1>
              <p className="text-xs text-muted-foreground">{candidate.role}</p>
            </div>
          </div>
          <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">
            Completed
          </Badge>
        </div>
      </header>

      {/* Split Screen */}
      <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col lg:flex-row">
        {/* Left Panel - Transcript */}
        <div className="flex flex-1 flex-col border-b border-border lg:border-b-0 lg:border-r">
          <div className="border-b border-border bg-card px-6 py-4">
            <h2 className="text-sm font-semibold text-foreground">Interview Transcript</h2>
            <p className="text-xs text-muted-foreground">Full conversation history</p>
          </div>
          <ScrollArea className="flex-1 p-6" style={{ maxHeight: "calc(100vh - 180px)" }}>
            <div className="flex flex-col gap-4">
              {sampleTranscript.map((msg) => (
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
          </ScrollArea>
        </div>

        {/* Right Panel - Grading */}
        <div className="flex w-full flex-col lg:w-[420px]">
          <div className="border-b border-border bg-card px-6 py-4">
            <h2 className="text-sm font-semibold text-foreground">Evaluation</h2>
            <p className="text-xs text-muted-foreground">Score and provide feedback</p>
          </div>
          <div className="flex flex-1 flex-col gap-6 p-6">
            {/* Candidate Info */}
            <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
              <Avatar className="h-10 w-10 border border-border">
                <AvatarFallback className="bg-primary/10 text-sm font-medium text-primary">
                  {candidate.avatar}
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="font-medium text-foreground">{candidate.name}</p>
                <p className="text-xs text-muted-foreground">{candidate.email}</p>
              </div>
            </div>

            {/* Score Slider */}
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium text-foreground">Score</Label>
                <span className="rounded-md bg-primary/10 px-2.5 py-1 text-sm font-bold text-primary">
                  {score}/100
                </span>
              </div>
              <Slider
                value={[score]}
                onValueChange={(v) => setScore(v[0])}
                max={100}
                step={1}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0</span>
                <span>50</span>
                <span>100</span>
              </div>
            </div>

            {/* Pass / Reject Toggle */}
            <div className="flex items-center justify-between rounded-lg border border-border bg-card p-4">
              <div className="flex flex-col gap-0.5">
                <Label className="text-sm font-medium text-foreground">Decision</Label>
                <p className="text-xs text-muted-foreground">
                  {passed ? "Candidate will be passed" : "Candidate will be rejected"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-medium ${passed ? "text-muted-foreground" : "text-destructive"}`}>
                  Reject
                </span>
                <Switch
                  checked={passed}
                  onCheckedChange={setPassed}
                  aria-label="Pass or reject candidate"
                />
                <span className={`text-xs font-medium ${passed ? "text-emerald-600" : "text-muted-foreground"}`}>
                  Pass
                </span>
              </div>
            </div>

            {/* Feedback */}
            <div className="flex flex-col gap-2">
              <Label className="text-sm font-medium text-foreground">Feedback</Label>
              <Textarea
                placeholder="Write detailed feedback for this candidate..."
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                className="min-h-[120px] resize-none bg-card"
              />
            </div>

            {/* Submit */}
            <Button className="w-full bg-primary text-primary-foreground hover:bg-primary/90">
              <Send className="mr-2 h-4 w-4" />
              Submit Review
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

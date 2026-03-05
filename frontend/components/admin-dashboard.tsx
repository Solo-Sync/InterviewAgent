"use client"

import { useEffect, useMemo, useState } from "react"
import {
  BrainCircuit,
  LogOut,
  Search,
  ListChecks,
  Users,
  CheckCircle2,
  Clock,
  ChevronDown,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { fetchHealth, listAdminSessions, listQuestionSets, listRubrics } from "@/lib/api"
import type { AdminSessionSummary, CandidateStatus, ScoreDimensions } from "@/lib/types"

interface AdminDashboardProps {
  onReviewSession: (session: AdminSessionSummary) => void
  onLogout: () => void
}

function sessionStatus(item: AdminSessionSummary): Exclude<CandidateStatus, "pending"> {
  if (item.report || item.session.state === "S_END") {
    return "completed"
  }
  return "in-progress"
}

function sessionLabel(item: AdminSessionSummary) {
  return item.session.candidate?.display_name || item.session.candidate?.candidate_id || item.session.session_id
}

function averageScore(score: ScoreDimensions | null) {
  if (!score) return null
  return Math.round(((score.plan + score.monitor + score.evaluate + score.adapt) / 4) * 100)
}

function initials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("")
}

function StatusBadge({ status }: { status: Exclude<CandidateStatus, "pending"> }) {
  const config: Record<Exclude<CandidateStatus, "pending">, { label: string; className: string }> = {
    completed: {
      label: "Completed",
      className: "border-emerald-200 bg-emerald-50 text-emerald-700",
    },
    "in-progress": {
      label: "In Progress",
      className: "border-amber-200 bg-amber-50 text-amber-700",
    },
  }

  const { label, className } = config[status]

  return (
    <Badge variant="outline" className={className}>
      {label}
    </Badge>
  )
}

export function AdminDashboard({ onReviewSession, onLogout }: AdminDashboardProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState("")
  const [filterStatus, setFilterStatus] = useState<Exclude<CandidateStatus, "pending"> | "all">("all")
  const [backendState, setBackendState] = useState<"loading" | "online" | "degraded" | "offline">("loading")
  const [metaCounts, setMetaCounts] = useState<{ questionSets: number; rubrics: number }>({
    questionSets: 0,
    rubrics: 0,
  })
  const [sessions, setSessions] = useState<AdminSessionSummary[]>([])
  const [errorText, setErrorText] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    void (async () => {
      try {
        const [health, questionSets, rubrics, adminSessions] = await Promise.all([
          fetchHealth(),
          listQuestionSets(),
          listRubrics(),
          listAdminSessions(),
        ])
        if (cancelled) return
        setBackendState(health.status === "ready" ? "online" : "degraded")
        setMetaCounts({
          questionSets: questionSets.items.length,
          rubrics: rubrics.items.length,
        })
        setSessions(adminSessions.items)
        setErrorText(null)
      } catch (error) {
        if (cancelled) return
        setBackendState("offline")
        setErrorText(error instanceof Error ? error.message : "Failed to load admin data")
      }
    })()

    return () => {
      cancelled = true
    }
  }, [])

  const filteredSessions = useMemo(() => {
    const normalizedSearch = searchQuery.trim().toLowerCase()
    return sessions.filter((item) => {
      const status = sessionStatus(item)
      const matchesFilter = filterStatus === "all" || status === filterStatus
      if (!matchesFilter) return false
      if (!normalizedSearch) return true

      return [
        sessionLabel(item),
        item.session.candidate?.candidate_id ?? "",
        item.session.question_set_id,
        item.session.session_id,
      ].some((value) => value.toLowerCase().includes(normalizedSearch))
    })
  }, [filterStatus, searchQuery, sessions])

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (selectedIds.size === filteredSessions.length) {
      setSelectedIds(new Set())
      return
    }
    setSelectedIds(new Set(filteredSessions.map((item) => item.session.session_id)))
  }

  const stats = {
    total: sessions.length,
    completed: sessions.filter((item) => sessionStatus(item) === "completed").length,
    inProgress: sessions.filter((item) => sessionStatus(item) === "in-progress").length,
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-30 border-b border-border bg-card">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <BrainCircuit className="h-5 w-5" />
            </div>
            <span className="text-lg font-semibold text-foreground">InterviewAI</span>
          </div>
          <div className="flex items-center gap-3">
            <Badge
              variant="outline"
              className={
                backendState === "online"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : backendState === "degraded"
                    ? "border-amber-200 bg-amber-50 text-amber-700"
                    : backendState === "offline"
                      ? "border-destructive/30 bg-destructive/10 text-destructive"
                      : "border-border text-muted-foreground"
              }
            >
              API{" "}
              {backendState === "loading"
                ? "Checking"
                : backendState === "online"
                  ? "Online"
                  : backendState === "degraded"
                    ? "Degraded"
                    : "Offline"}
            </Badge>
            <div className="flex items-center gap-2">
              <Avatar className="h-8 w-8 border border-border">
                <AvatarFallback className="bg-primary/10 text-sm font-medium text-primary">
                  AD
                </AvatarFallback>
              </Avatar>
              <span className="hidden text-sm font-medium text-foreground sm:inline">Admin</span>
            </div>
            <Button variant="ghost" size="icon" onClick={onLogout} aria-label="Logout">
              <LogOut className="h-4 w-4 text-muted-foreground" />
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 py-6 lg:px-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="flex items-center gap-4 rounded-lg border border-border bg-card p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Users className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{stats.total}</p>
              <p className="text-sm text-muted-foreground">Interview Sessions</p>
            </div>
          </div>
          <div className="flex items-center gap-4 rounded-lg border border-border bg-card p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{stats.completed}</p>
              <p className="text-sm text-muted-foreground">Completed</p>
            </div>
          </div>
          <div className="flex items-center gap-4 rounded-lg border border-border bg-card p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50">
              <Clock className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{stats.inProgress}</p>
              <p className="text-sm text-muted-foreground">
                Active | QSets {metaCounts.questionSets} | Rubrics {metaCounts.rubrics}
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search sessions..."
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                className="w-64 bg-card pl-9"
              />
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="bg-card capitalize">
                  {filterStatus === "all" ? "All Status" : filterStatus}
                  <ChevronDown className="ml-2 h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem onClick={() => setFilterStatus("all")}>All Status</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setFilterStatus("completed")}>Completed</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setFilterStatus("in-progress")}>In Progress</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          {selectedIds.size > 0 ? (
            <Button variant="outline" className="bg-card" disabled>
              <ListChecks className="mr-2 h-4 w-4" />
              {selectedIds.size} Selected
            </Button>
          ) : null}
        </div>

        {errorText ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {errorText}
          </div>
        ) : null}

        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50 hover:bg-muted/50">
                <TableHead className="w-12">
                  <Checkbox
                    checked={selectedIds.size === filteredSessions.length && filteredSessions.length > 0}
                    onCheckedChange={toggleAll}
                    aria-label="Select all sessions"
                  />
                </TableHead>
                <TableHead className="text-foreground">Candidate</TableHead>
                <TableHead className="text-foreground">Question Set</TableHead>
                <TableHead className="text-foreground">Status</TableHead>
                <TableHead className="text-foreground">Score</TableHead>
                <TableHead className="text-right text-foreground">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredSessions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">
                    No interview sessions yet. Sign in as a candidate to create one.
                  </TableCell>
                </TableRow>
              ) : (
                filteredSessions.map((item) => {
                  const status = sessionStatus(item)
                  const score = averageScore(item.report?.overall ?? null)
                  const label = sessionLabel(item)
                  const candidateId = item.session.candidate?.candidate_id ?? "unknown"
                  return (
                    <TableRow key={item.session.session_id} className="hover:bg-muted/30">
                      <TableCell>
                        <Checkbox
                          checked={selectedIds.has(item.session.session_id)}
                          onCheckedChange={() => toggleSelect(item.session.session_id)}
                          aria-label={`Select ${label}`}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="h-8 w-8 border border-border">
                            <AvatarFallback className="bg-primary/10 text-xs font-medium text-primary">
                              {initials(label || candidateId)}
                            </AvatarFallback>
                          </Avatar>
                          <div>
                            <p className="font-medium text-foreground">{label}</p>
                            <p className="text-xs text-muted-foreground">{candidateId}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{item.session.question_set_id}</TableCell>
                      <TableCell>
                        <StatusBadge status={status} />
                      </TableCell>
                      <TableCell>
                        {score !== null ? (
                          <span className="font-semibold text-foreground">{score}/100</span>
                        ) : (
                          <span className="text-muted-foreground">In progress</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onReviewSession(item)}
                          className="text-primary hover:bg-primary/5 hover:text-primary"
                        >
                          {status === "completed" ? "Review" : "View"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </div>
      </main>
    </div>
  )
}

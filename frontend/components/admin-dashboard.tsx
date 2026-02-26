"use client"

import { useEffect, useState } from "react"
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
import { fetchHealth, listQuestionSets, listRubrics } from "@/lib/api"
import { candidates } from "@/lib/mock-data"
import type { Candidate, CandidateStatus } from "@/lib/types"

interface AdminDashboardProps {
  onReviewCandidate: (candidate: Candidate) => void
  onLogout: () => void
}

function StatusBadge({ status }: { status: CandidateStatus }) {
  const config: Record<CandidateStatus, { label: string; className: string }> = {
    completed: {
      label: "Completed",
      className: "bg-emerald-50 text-emerald-700 border-emerald-200",
    },
    "in-progress": {
      label: "In Progress",
      className: "bg-amber-50 text-amber-700 border-amber-200",
    },
    pending: {
      label: "Pending",
      className: "bg-secondary text-muted-foreground border-border",
    },
  }

  const { label, className } = config[status]

  return (
    <Badge variant="outline" className={className}>
      {label}
    </Badge>
  )
}

export function AdminDashboard({ onReviewCandidate, onLogout }: AdminDashboardProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState("")
  const [filterStatus, setFilterStatus] = useState<CandidateStatus | "all">("all")
  const [backendState, setBackendState] = useState<"loading" | "online" | "offline">("loading")
  const [metaCounts, setMetaCounts] = useState<{ questionSets: number; rubrics: number }>({
    questionSets: 0,
    rubrics: 0,
  })

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const [health, questionSets, rubrics] = await Promise.all([
          fetchHealth(),
          listQuestionSets(),
          listRubrics(),
        ])
        if (cancelled) return
        setBackendState(health.llm_ready && health.asr_ready ? "online" : "offline")
        setMetaCounts({
          questionSets: questionSets.items.length,
          rubrics: rubrics.items.length,
        })
      } catch {
        if (!cancelled) {
          setBackendState("offline")
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const filteredCandidates = candidates.filter((c) => {
    const matchesSearch =
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.role.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesFilter = filterStatus === "all" || c.status === filterStatus
    return matchesSearch && matchesFilter
  })

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (selectedIds.size === filteredCandidates.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredCandidates.map((c) => c.id)))
    }
  }

  const stats = {
    total: candidates.length,
    completed: candidates.filter((c) => c.status === "completed").length,
    pending: candidates.filter((c) => c.status === "pending").length,
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Top Bar */}
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
                  : backendState === "offline"
                    ? "border-destructive/30 bg-destructive/10 text-destructive"
                    : "border-border text-muted-foreground"
              }
            >
              API {backendState === "loading" ? "Checking" : backendState === "online" ? "Online" : "Offline"}
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
        {/* Stats */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="flex items-center gap-4 rounded-lg border border-border bg-card p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Users className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{stats.total}</p>
              <p className="text-sm text-muted-foreground">Total Candidates</p>
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
              <p className="text-2xl font-bold text-foreground">{stats.pending}</p>
              <p className="text-sm text-muted-foreground">
                Pending | QSets {metaCounts.questionSets} | Rubrics {metaCounts.rubrics}
              </p>
            </div>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search candidates..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
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
                <DropdownMenuItem onClick={() => setFilterStatus("pending")}>Pending</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          {selectedIds.size > 0 && (
            <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
              <ListChecks className="mr-2 h-4 w-4" />
              Assign Questions to Selected ({selectedIds.size})
            </Button>
          )}
        </div>

        {/* Table */}
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50 hover:bg-muted/50">
                <TableHead className="w-12">
                  <Checkbox
                    checked={selectedIds.size === filteredCandidates.length && filteredCandidates.length > 0}
                    onCheckedChange={toggleAll}
                    aria-label="Select all candidates"
                  />
                </TableHead>
                <TableHead className="text-foreground">Candidate</TableHead>
                <TableHead className="text-foreground">Applied Role</TableHead>
                <TableHead className="text-foreground">Status</TableHead>
                <TableHead className="text-foreground">Score</TableHead>
                <TableHead className="text-right text-foreground">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredCandidates.map((candidate) => (
                <TableRow key={candidate.id} className="hover:bg-muted/30">
                  <TableCell>
                    <Checkbox
                      checked={selectedIds.has(candidate.id)}
                      onCheckedChange={() => toggleSelect(candidate.id)}
                      aria-label={`Select ${candidate.name}`}
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar className="h-8 w-8 border border-border">
                        <AvatarFallback className="bg-primary/10 text-xs font-medium text-primary">
                          {candidate.avatar}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="font-medium text-foreground">{candidate.name}</p>
                        <p className="text-xs text-muted-foreground">{candidate.email}</p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{candidate.role}</TableCell>
                  <TableCell>
                    <StatusBadge status={candidate.status} />
                  </TableCell>
                  <TableCell>
                    {candidate.score !== null ? (
                      <span className="font-semibold text-foreground">{candidate.score}/100</span>
                    ) : (
                      <span className="text-muted-foreground">&mdash;</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {candidate.status === "completed" ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onReviewCandidate(candidate)}
                        className="text-primary hover:bg-primary/5 hover:text-primary"
                      >
                        Review
                      </Button>
                    ) : (
                      <Button variant="ghost" size="sm" disabled className="text-muted-foreground">
                        {candidate.status === "in-progress" ? "In Progress" : "Pending"}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </main>
    </div>
  )
}

"use client"

import { useState } from "react"
import { LoginScreen } from "@/components/login-screen"
import { AdminDashboard } from "@/components/admin-dashboard"
import { AdminReview } from "@/components/admin-review"
import { CandidateInterview } from "@/components/candidate-interview"
import { signOut } from "@/lib/auth-client"
import type { AdminSessionSummary, AppView, AuthSession } from "@/lib/types"

export default function Home() {
  const [view, setView] = useState<AppView>("login")
  const [authSession, setAuthSession] = useState<AuthSession | null>(null)
  const [selectedSession, setSelectedSession] = useState<AdminSessionSummary | null>(null)

  const handleLogin = (session: AuthSession) => {
    setAuthSession(session)
    if (session.role === "admin") {
      setView("admin-dashboard")
    } else {
      setView("candidate-interview")
    }
  }

  const handleLogout = () => {
    void signOut()
    setAuthSession(null)
    setView("login")
    setSelectedSession(null)
  }

  const handleReviewSession = (session: AdminSessionSummary) => {
    setSelectedSession(session)
    setView("admin-review")
  }

  const handleBackToDashboard = () => {
    setSelectedSession(null)
    setView("admin-dashboard")
  }

  switch (view) {
    case "login":
      return <LoginScreen onLogin={handleLogin} />
    case "admin-dashboard":
      return (
        <AdminDashboard
          onReviewSession={handleReviewSession}
          onLogout={handleLogout}
        />
      )
    case "admin-review":
      return selectedSession ? (
        <AdminReview sessionSummary={selectedSession} onBack={handleBackToDashboard} />
      ) : null
    case "candidate-interview":
      return authSession?.candidateId ? (
        <CandidateInterview
          onLogout={handleLogout}
          candidateId={authSession.candidateId}
          displayName={authSession.displayName}
        />
      ) : (
        <LoginScreen onLogin={handleLogin} />
      )
    default:
      return <LoginScreen onLogin={handleLogin} />
  }
}

"use client"

import { useState } from "react"
import { LoginScreen } from "@/components/login-screen"
import { AdminDashboard } from "@/components/admin-dashboard"
import { AdminReview } from "@/components/admin-review"
import { CandidateInterview } from "@/components/candidate-interview"
import { signOut } from "@/lib/auth-client"
import type { AppView, AuthSession, Candidate } from "@/lib/types"

export default function Home() {
  const [view, setView] = useState<AppView>("login")
  const [authSession, setAuthSession] = useState<AuthSession | null>(null)
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null)

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
    setSelectedCandidate(null)
  }

  const handleReviewCandidate = (candidate: Candidate) => {
    setSelectedCandidate(candidate)
    setView("admin-review")
  }

  const handleBackToDashboard = () => {
    setSelectedCandidate(null)
    setView("admin-dashboard")
  }

  switch (view) {
    case "login":
      return <LoginScreen onLogin={handleLogin} />
    case "admin-dashboard":
      return (
        <AdminDashboard
          onReviewCandidate={handleReviewCandidate}
          onLogout={handleLogout}
        />
      )
    case "admin-review":
      return selectedCandidate ? (
        <AdminReview candidate={selectedCandidate} onBack={handleBackToDashboard} />
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

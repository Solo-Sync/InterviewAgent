"use client"

import { useState } from "react"
import { LoginScreen } from "@/components/login-screen"
import { AdminDashboard } from "@/components/admin-dashboard"
import { AdminReview } from "@/components/admin-review"
import { CandidateInterview } from "@/components/candidate-interview"
import type { AppView, UserRole, Candidate } from "@/lib/types"

export default function Home() {
  const [view, setView] = useState<AppView>("login")
  const [, setRole] = useState<UserRole>(null)
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null)

  const handleLogin = (loginRole: UserRole) => {
    setRole(loginRole)
    if (loginRole === "admin") {
      setView("admin-dashboard")
    } else {
      setView("candidate-interview")
    }
  }

  const handleLogout = () => {
    setRole(null)
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
      return <CandidateInterview onLogout={handleLogout} />
    default:
      return <LoginScreen onLogin={handleLogin} />
  }
}

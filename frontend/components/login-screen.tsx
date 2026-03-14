"use client"

import { useEffect, useState } from "react"
import { BrainCircuit, ShieldCheck, User, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { registerCandidate, signIn } from "@/lib/auth-client"
import type { AuthSession } from "@/lib/types"

interface LoginScreenProps {
  onLogin: (session: AuthSession) => void
}

const USERNAME_RE = /^[A-Za-z0-9]{1,20}$/
const PASSWORD_RE = /^[A-Za-z0-9@_]{8,20}$/

function validateCandidateCredentials(username: string, password: string): string | null {
  if (!USERNAME_RE.test(username)) {
    return "用户名需为 1-20 位英文字母或数字"
  }
  if (!PASSWORD_RE.test(password)) {
    return "密码需为 8-20 位，且只能包含英文字母、数字、@、_"
  }
  const hasLetter = /[A-Za-z]/.test(password)
  const hasDigit = /\d/.test(password)
  const hasSpecial = /[@_]/.test(password)
  if (!(hasLetter && hasDigit && hasSpecial)) {
    return "密码必须同时包含英文字母、数字和特殊符号 @ 或 _"
  }
  return null
}

export function LoginScreen({ onLogin }: LoginScreenProps) {
  const [selectedRole, setSelectedRole] = useState<"admin" | "candidate">("candidate")
  const [candidateMode, setCandidateMode] = useState<"login" | "register">("register")
  const [adminEmail, setAdminEmail] = useState("admin@company.com")
  const [adminPassword, setAdminPassword] = useState("password123")
  const [candidateUsername, setCandidateUsername] = useState("")
  const [candidatePassword, setCandidatePassword] = useState("")
  const [errorText, setErrorText] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (selectedRole === "admin") {
      setCandidateMode("login")
      setAdminEmail("admin@company.com")
      setAdminPassword("password123")
    }
    setErrorText(null)
  }, [selectedRole])

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <BrainCircuit className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">InterviewAI</h1>
          <p className="text-sm text-muted-foreground">AI-powered automated interview platform</p>
        </div>

        <Card className="border-border shadow-lg">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg text-foreground">Sign In</CardTitle>
            <CardDescription>Choose your role and enter credentials validated by the backend</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="mb-6 flex rounded-lg border border-border bg-muted p-1">
              <button
                onClick={() => setSelectedRole("admin")}
                className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium transition-all ${
                  selectedRole === "admin"
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <ShieldCheck className="h-4 w-4" />
                Admin Login
              </button>
              <button
                onClick={() => setSelectedRole("candidate")}
                className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium transition-all ${
                  selectedRole === "candidate"
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <User className="h-4 w-4" />
                Candidate Login
              </button>
            </div>

            {selectedRole === "candidate" ? (
              <div className="mb-6 flex rounded-lg border border-border bg-muted p-1">
                <button
                  onClick={() => setCandidateMode("login")}
                  className={`flex flex-1 items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition-all ${
                    candidateMode === "login"
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Sign In
                </button>
                <button
                  onClick={() => setCandidateMode("register")}
                  className={`flex flex-1 items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition-all ${
                    candidateMode === "register"
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Register
                </button>
              </div>
            ) : null}

            <form
              onSubmit={async (e) => {
                e.preventDefault()
                setIsSubmitting(true)
                setErrorText(null)
                try {
                  let session: AuthSession
                  if (selectedRole === "admin") {
                    session = await signIn({
                      role: "admin",
                      email: adminEmail,
                      password: adminPassword,
                    })
                  } else {
                    const validationError = validateCandidateCredentials(candidateUsername, candidatePassword)
                    if (validationError) {
                      throw new Error(validationError)
                    }
                    session =
                      candidateMode === "register"
                        ? await registerCandidate(candidateUsername, candidatePassword)
                        : await signIn({
                            role: "candidate",
                            username: candidateUsername,
                            password: candidatePassword,
                          })
                  }
                  onLogin(session)
                } catch (error) {
                  setErrorText(error instanceof Error ? error.message : "Login failed")
                } finally {
                  setIsSubmitting(false)
                }
              }}
              className="flex flex-col gap-4"
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="identifier" className="text-foreground">
                  {selectedRole === "admin" ? "Email" : "Username"}
                </Label>
                <Input
                  id="identifier"
                  type={selectedRole === "admin" ? "email" : "text"}
                  placeholder={selectedRole === "admin" ? "admin@company.com" : "Only letters and digits, max 20"}
                  value={selectedRole === "admin" ? adminEmail : candidateUsername}
                  onChange={(event) =>
                    selectedRole === "admin"
                      ? setAdminEmail(event.target.value)
                      : setCandidateUsername(event.target.value)
                  }
                  className="bg-card"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="password" className="text-foreground">
                  Password
                </Label>
                <Input
                  id="password"
                  type="password"
                  placeholder={
                    selectedRole === "admin"
                      ? "Enter your password"
                      : "8-20 chars with letters, digits, @ or _"
                  }
                  value={selectedRole === "admin" ? adminPassword : candidatePassword}
                  onChange={(event) =>
                    selectedRole === "admin"
                      ? setAdminPassword(event.target.value)
                      : setCandidatePassword(event.target.value)
                  }
                  className="bg-card"
                />
              </div>
              {errorText ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                  {errorText}
                </div>
              ) : null}
              <p className="text-xs text-muted-foreground">
                {selectedRole === "admin"
                  ? "Admin login still uses backend configured credentials."
                  : "用户名仅支持英文字母和数字；密码需同时包含英文字母、数字和 @ 或 _。"}
              </p>
              <Button
                type="submit"
                disabled={isSubmitting}
                className="mt-2 w-full bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {selectedRole === "admin"
                  ? "Sign in as Admin"
                  : candidateMode === "register"
                    ? "Register and Start"
                    : "Start Interview"}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

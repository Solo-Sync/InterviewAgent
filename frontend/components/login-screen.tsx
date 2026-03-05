"use client"

import { useEffect, useState } from "react"
import { BrainCircuit, ShieldCheck, User, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { signIn } from "@/lib/auth-client"
import type { AuthSession } from "@/lib/types"

interface LoginScreenProps {
  onLogin: (session: AuthSession) => void
}

export function LoginScreen({ onLogin }: LoginScreenProps) {
  const [selectedRole, setSelectedRole] = useState<"admin" | "candidate">("candidate")
  const [email, setEmail] = useState("sarah.chen@email.com")
  const [password, setPassword] = useState("password123")
  const [errorText, setErrorText] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    setEmail(selectedRole === "admin" ? "admin@company.com" : "sarah.chen@email.com")
    setPassword(selectedRole === "admin" ? "password123" : "invite-sarah-001")
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

            <form
              onSubmit={async (e) => {
                e.preventDefault()
                setIsSubmitting(true)
                setErrorText(null)
                try {
                  const session = await signIn(selectedRole, email, password)
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
                <Label htmlFor="email" className="text-foreground">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder={selectedRole === "admin" ? "admin@company.com" : "candidate@email.com"}
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="bg-card"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="password" className="text-foreground">
                  {selectedRole === "admin" ? "Password" : "Invite Token"}
                </Label>
                <Input
                  id="password"
                  type="password"
                  placeholder={selectedRole === "admin" ? "Enter your password" : "Enter your invite token"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="bg-card"
                />
              </div>
              {errorText ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                  {errorText}
                </div>
              ) : null}
              <p className="text-xs text-muted-foreground">
                Candidate login uses email + invite token from the backend registry. Admin login uses backend credentials.
              </p>
              <Button
                type="submit"
                disabled={isSubmitting}
                className="mt-2 w-full bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {selectedRole === "admin" ? "Sign in as Admin" : "Start Interview"}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

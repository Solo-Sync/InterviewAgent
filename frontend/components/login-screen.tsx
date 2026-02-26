"use client"

import { useState } from "react"
import { BrainCircuit, ShieldCheck, User, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { UserRole } from "@/lib/types"

interface LoginScreenProps {
  onLogin: (role: UserRole) => void
}

export function LoginScreen({ onLogin }: LoginScreenProps) {
  const [selectedRole, setSelectedRole] = useState<"admin" | "candidate">("candidate")

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
            <CardDescription>Choose your role and enter your credentials</CardDescription>
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
              onSubmit={(e) => {
                e.preventDefault()
                onLogin(selectedRole)
              }}
              className="flex flex-col gap-4"
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="email" className="text-foreground">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder={selectedRole === "admin" ? "admin@company.com" : "candidate@email.com"}
                  defaultValue={selectedRole === "admin" ? "admin@company.com" : "sarah.chen@email.com"}
                  className="bg-card"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="password" className="text-foreground">Password</Label>
                <Input id="password" type="password" placeholder="Enter your password" defaultValue="password123" className="bg-card" />
              </div>
              <Button type="submit" className="mt-2 w-full bg-primary text-primary-foreground hover:bg-primary/90">
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

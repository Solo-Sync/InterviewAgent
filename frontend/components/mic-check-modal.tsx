"use client"

import { useState, useEffect, useCallback } from "react"
import { Mic, CheckCircle2, Volume2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface MicCheckModalProps {
  open: boolean
  onReady: () => void
}

export function MicCheckModal({ open, onReady }: MicCheckModalProps) {
  const [volume, setVolume] = useState(0)
  const [isTesting, setIsTesting] = useState(false)
  const [micReady, setMicReady] = useState(false)

  // Simulated mic level animation
  useEffect(() => {
    if (!isTesting) return
    const interval = setInterval(() => {
      setVolume(Math.random() * 100)
    }, 100)

    const timeout = setTimeout(() => {
      setIsTesting(false)
      setMicReady(true)
    }, 3000)

    return () => {
      clearInterval(interval)
      clearTimeout(timeout)
    }
  }, [isTesting])

  const handleTestMic = useCallback(() => {
    setIsTesting(true)
    setMicReady(false)
  }, [])

  return (
    <Dialog open={open}>
      <DialogContent className="sm:max-w-md" onPointerDownOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle className="text-foreground">Microphone Check</DialogTitle>
          <DialogDescription>
            Before we begin, let&apos;s make sure your microphone is working properly.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col items-center gap-6 py-4">
          {/* Mic Icon */}
          <div
            className={`flex h-20 w-20 items-center justify-center rounded-full transition-colors ${
              micReady
                ? "bg-emerald-100"
                : isTesting
                  ? "bg-primary/10"
                  : "bg-muted"
            }`}
          >
            {micReady ? (
              <CheckCircle2 className="h-10 w-10 text-emerald-600" />
            ) : (
              <Mic
                className={`h-10 w-10 ${
                  isTesting ? "text-primary" : "text-muted-foreground"
                }`}
              />
            )}
          </div>

          {/* Volume Bar */}
          <div className="flex w-full flex-col gap-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Volume2 className="h-3 w-3" />
                Input Level
              </span>
              <span>{isTesting ? "Listening..." : micReady ? "Mic is working" : "Click to test"}</span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full transition-all duration-100 ${
                  micReady ? "bg-emerald-500" : "bg-primary"
                }`}
                style={{ width: `${isTesting ? volume : micReady ? 100 : 0}%` }}
              />
            </div>
          </div>

          {/* Actions */}
          {!micReady ? (
            <Button
              onClick={handleTestMic}
              disabled={isTesting}
              className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {isTesting ? (
                <>
                  <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
                  Testing Microphone...
                </>
              ) : (
                <>
                  <Mic className="mr-2 h-4 w-4" />
                  Test Microphone
                </>
              )}
            </Button>
          ) : (
            <Button
              onClick={onReady}
              className="w-full bg-emerald-600 text-white hover:bg-emerald-700"
            >
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Start Interview
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

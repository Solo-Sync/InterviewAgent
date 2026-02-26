"use client"

import { Mic, Loader2 } from "lucide-react"
import type { InterviewState } from "@/lib/types"

interface RecordButtonProps {
  state: InterviewState
  onPressStart: () => void
  onPressEnd: () => void
}

export function RecordButton({ state, onPressStart, onPressEnd }: RecordButtonProps) {
  const isRecording = state === "recording"
  const isProcessing = state === "processing"

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Label */}
      <p className="text-xs font-medium text-muted-foreground">
        {isRecording
          ? "Release to send"
          : isProcessing
            ? "AI is thinking..."
            : "Hold to record"}
      </p>

      {/* Button Container */}
      <div className="relative flex items-center justify-center">
        {/* Pulse rings when recording */}
        {isRecording && (
          <>
            <span className="absolute h-20 w-20 animate-pulse-ring rounded-full bg-destructive/30" />
            <span
              className="absolute h-20 w-20 animate-pulse-ring rounded-full bg-destructive/20"
              style={{ animationDelay: "0.5s" }}
            />
          </>
        )}

        {/* Main Button */}
        <button
          onMouseDown={!isProcessing ? onPressStart : undefined}
          onMouseUp={isRecording ? onPressEnd : undefined}
          onMouseLeave={isRecording ? onPressEnd : undefined}
          onTouchStart={!isProcessing ? onPressStart : undefined}
          onTouchEnd={isRecording ? onPressEnd : undefined}
          disabled={isProcessing}
          className={`relative z-10 flex h-16 w-16 items-center justify-center rounded-full shadow-lg transition-all duration-200 ${
            isRecording
              ? "scale-110 bg-destructive text-white"
              : isProcessing
                ? "cursor-not-allowed bg-muted text-muted-foreground"
                : "bg-primary text-primary-foreground hover:bg-primary/90 active:scale-95"
          }`}
          aria-label={
            isRecording
              ? "Release to stop recording"
              : isProcessing
                ? "Processing your response"
                : "Hold to start recording"
          }
        >
          {isProcessing ? (
            <Loader2 className="h-6 w-6 animate-spin" />
          ) : (
            <Mic className="h-6 w-6" />
          )}
        </button>
      </div>
    </div>
  )
}

import type { Candidate, ChatMessage } from "./types"

export const candidates: Candidate[] = [
  {
    id: "1",
    name: "Sarah Chen",
    email: "sarah.chen@email.com",
    role: "Senior Frontend Engineer",
    status: "completed",
    score: 87,
    avatar: "SC",
  },
  {
    id: "2",
    name: "Marcus Johnson",
    email: "marcus.j@email.com",
    role: "Full Stack Developer",
    status: "completed",
    score: 92,
    avatar: "MJ",
  },
  {
    id: "3",
    name: "Priya Patel",
    email: "priya.p@email.com",
    role: "Backend Engineer",
    status: "in-progress",
    score: null,
    avatar: "PP",
  },
  {
    id: "4",
    name: "Alex Rivera",
    email: "alex.r@email.com",
    role: "DevOps Engineer",
    status: "pending",
    score: null,
    avatar: "AR",
  },
  {
    id: "5",
    name: "Jordan Lee",
    email: "jordan.l@email.com",
    role: "Senior Frontend Engineer",
    status: "pending",
    score: null,
    avatar: "JL",
  },
  {
    id: "6",
    name: "Emily Watson",
    email: "emily.w@email.com",
    role: "ML Engineer",
    status: "completed",
    score: 78,
    avatar: "EW",
  },
  {
    id: "7",
    name: "David Kim",
    email: "david.k@email.com",
    role: "Full Stack Developer",
    status: "pending",
    score: null,
    avatar: "DK",
  },
]

export const sampleTranscript: ChatMessage[] = [
  {
    id: "1",
    sender: "system",
    text: "Welcome to the interview, Sarah. Let's begin with your first question. Can you describe your experience with React and component architecture patterns?",
    timestamp: "10:00:15",
  },
  {
    id: "2",
    sender: "user",
    text: "I've been working with React for over five years now. I'm very familiar with component composition patterns, including render props, higher-order components, and more recently, custom hooks for logic reuse. I've led the frontend architecture at my current company, migrating from class components to functional components with hooks.",
    timestamp: "10:01:42",
  },
  {
    id: "3",
    sender: "system",
    text: "Great. How do you approach state management in large-scale React applications?",
    timestamp: "10:02:00",
  },
  {
    id: "4",
    sender: "user",
    text: "For large-scale apps, I prefer a layered approach. Local component state for UI-specific logic, React Context for shared concerns like themes and auth, and something like Zustand or Redux Toolkit for complex global state. I also heavily use React Query for server state, which has dramatically simplified our data fetching patterns.",
    timestamp: "10:03:30",
  },
  {
    id: "5",
    sender: "system",
    text: "Can you walk me through a challenging performance optimization you've implemented?",
    timestamp: "10:03:50",
  },
  {
    id: "6",
    sender: "user",
    text: "Absolutely. We had a dashboard with real-time data grids rendering thousands of rows. I implemented virtualization using react-window, memoized expensive computations with useMemo, and used React.memo strategically. We also implemented a web worker for heavy data transformations. The end result was a 60% reduction in main thread blocking time.",
    timestamp: "10:05:15",
  },
]

export interface InterviewQuestion {
  topic: string
  mainQuestion: string
  followUp: string
  simulatedAnswer: string
  simulatedFollowUpAnswer: string
}

export const interviewQuestions: InterviewQuestion[] = [
  {
    topic: "React Lifecycle",
    mainQuestion:
      "Can you describe your experience with React and component architecture patterns?",
    followUp:
      "Interesting. Can you give a specific example of when you chose one pattern (e.g., render props vs. hooks) over another, and why?",
    simulatedAnswer:
      "I have extensive experience with React and component patterns, including hooks, render props, and compound components. I've built complex UIs with performance-critical rendering requirements.",
    simulatedFollowUpAnswer:
      "Sure. When building a form library, I initially used render props to share validation logic, but later refactored to custom hooks because it simplified the consumer API and made the code more readable for the team.",
  },
  {
    topic: "State Management",
    mainQuestion:
      "How do you approach state management in large-scale React applications?",
    followUp:
      "You mentioned using multiple tools. How do you decide the boundary between local state and global state in a real project?",
    simulatedAnswer:
      "For state management I use a combination of local state, Context for shared concerns, and Zustand for complex global state. Server state is handled by React Query.",
    simulatedFollowUpAnswer:
      "My rule of thumb is: if two or more sibling components need the same data, it gets lifted to Context or Zustand. If only the component and its direct children need it, local state is fine. For server data, React Query handles caching so it rarely needs global state.",
  },
  {
    topic: "Performance Optimization",
    mainQuestion:
      "Can you walk me through a challenging performance optimization you've implemented?",
    followUp:
      "How did you measure the impact of those optimizations, and what tools did you use for profiling?",
    simulatedAnswer:
      "We optimized a dashboard rendering thousands of rows by implementing virtualization, strategic memoization, and offloading heavy computations to web workers.",
    simulatedFollowUpAnswer:
      "We used the React DevTools Profiler to identify unnecessary re-renders, Lighthouse for overall metrics, and the Performance tab in Chrome DevTools to track main thread blocking. We saw a 60% reduction in blocking time after the changes.",
  },
  {
    topic: "Testing Strategies",
    mainQuestion: "How do you handle testing in your frontend projects?",
    followUp:
      "What's your approach when a component is tightly coupled to external APIs? How do you test that reliably?",
    simulatedAnswer:
      "I follow a testing pyramid approach: unit tests with Vitest, integration tests with Testing Library, and E2E tests with Playwright for critical user flows.",
    simulatedFollowUpAnswer:
      "I use MSW (Mock Service Worker) to intercept network requests at the service worker level. This lets us test components in a realistic way without hitting real APIs, and the mocks live alongside the tests for easy maintenance.",
  },
  {
    topic: "CI/CD & Deployment",
    mainQuestion:
      "Describe your experience with CI/CD pipelines and deployment strategies.",
    followUp:
      "Have you ever had a deployment go wrong in production? How did you handle rollback and incident response?",
    simulatedAnswer:
      "Our CI/CD pipeline uses GitHub Actions for automated testing, preview deployments on Vercel, and feature flags for gradual rollouts in production.",
    simulatedFollowUpAnswer:
      "Yes, once a migration broke a critical API endpoint. We immediately rolled back using Vercel's instant rollback, communicated via Slack incident channel, and added a migration-specific integration test to prevent recurrence. The whole incident was resolved in under 15 minutes.",
  },
]

import { useState } from "react"
import { ArrowUpIcon, MoonIcon, RotateCcwIcon, SunIcon } from "lucide-react"
import { cn } from "cn"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Marker, MarkerContent } from "@/components/ui/marker"
import {
  Message,
  MessageAvatar,
  MessageContent,
} from "@/components/ui/message"
import {
  MessageScroller,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller"
import { useTheme } from "@/components/theme-provider"
import { useChat, type ChatMessage } from "@/hooks/useChat"

const WELCOME =
  "Hi, I'm front desk assistant here to help with room availability, bookings, reservations, payments, and more. How can I help?"

function DerekAvatar({ size = "default" }: { size?: "default" | "lg" }) {
  return (
    <Avatar
      size={size}
      className={cn(
        "ring-2 ring-brass/70 ring-offset-2 ring-offset-card",
        size === "lg" && "size-11"
      )}
    >
      <AvatarFallback
        className={cn(
          "bg-gradient-to-br from-[oklch(0.38_0.07_258)] to-[oklch(0.24_0.05_258)] font-heading font-semibold text-[oklch(0.86_0.09_80)]",
          size === "lg" ? "text-xl" : "text-sm"
        )}
      >
        D
      </AvatarFallback>
    </Avatar>
  )
}

function TypingIndicator() {
  return (
    <span
      className="flex h-[1.625rem] items-center gap-1.5 px-0.5"
      role="status"
      aria-label="Derek is typing"
    >
      <span className="typing-dot size-2 rounded-full bg-brass-strong" />
      <span className="typing-dot size-2 rounded-full bg-brass-strong" />
      <span className="typing-dot size-2 rounded-full bg-brass-strong" />
    </span>
  )
}

function AssistantBubble({ content, streaming }: { content: string; streaming: boolean }) {
  return (
    <Message align="start" className="message-in gap-2.5">
      <MessageAvatar className="bg-transparent p-1">
        <DerekAvatar />
      </MessageAvatar>
      <MessageContent>
        <Bubble variant="outline" align="start" className="max-w-[88%] sm:max-w-[80%]">
          <BubbleContent className="rounded-2xl rounded-bl-md border-border/80 !bg-card px-4 py-2.5 text-[0.95rem]/relaxed text-card-foreground shadow-[0_1px_2px_oklch(0.2_0.03_258/6%),0_4px_14px_-6px_oklch(0.2_0.03_258/10%)] dark:shadow-none">
            {streaming ? <TypingIndicator /> : content}
          </BubbleContent>
        </Bubble>
      </MessageContent>
    </Message>
  )
}

function UserBubble({ content }: { content: string }) {
  return (
    <Message align="end" className="message-in">
      <MessageContent>
        <Bubble variant="default" align="end" className="max-w-[88%] sm:max-w-[80%]">
          <BubbleContent className="rounded-2xl rounded-br-md px-4 py-2.5 text-[0.95rem]/relaxed shadow-[0_4px_14px_-6px_oklch(0.25_0.06_258/35%)] dark:shadow-[0_4px_14px_-8px_oklch(0.78_0.11_78/35%)]">
            {content}
          </BubbleContent>
        </Bubble>
      </MessageContent>
    </Message>
  )
}

function MessageRow({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return <UserBubble content={message.content} />
  }
  return (
    <AssistantBubble
      content={message.content}
      streaming={message.status === "streaming" && message.content.length === 0}
    />
  )
}

function ThemeToggle() {
  const { setTheme } = useTheme()

  const toggle = () => {
    const isDark = document.documentElement.classList.contains("dark")
    setTheme(isDark ? "light" : "dark")
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-lg"
      onClick={toggle}
      aria-label="Toggle light and dark mode"
      title="Toggle light and dark mode"
      className="text-muted-foreground hover:text-foreground"
    >
      <MoonIcon className="dark:hidden" />
      <SunIcon className="hidden dark:block" />
    </Button>
  )
}

export function App() {
  const { messages, isStreaming, send, reset } = useChat()
  const [input, setInput] = useState("")

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!input.trim() || isStreaming) return
    void send(input)
    setInput("")
  }

  const handleReset = () => {
    if (isStreaming) return
    void reset()
  }

  return (
    <div className="flex h-svh w-full justify-center sm:px-6 sm:py-6">
      <div className="flex h-full w-full max-w-3xl flex-col overflow-hidden bg-card/80 backdrop-blur-sm sm:rounded-3xl sm:border sm:shadow-[0_1px_3px_oklch(0.2_0.03_258/6%),0_24px_60px_-24px_oklch(0.2_0.04_258/25%)] dark:sm:shadow-[0_24px_60px_-24px_oklch(0_0_0/60%)]">
        <header className="relative flex items-center gap-3 border-b bg-card px-4 py-3 sm:px-6 sm:py-4">
          <div className="relative">
            <DerekAvatar size="lg" />
            <span
              className="absolute -right-0.5 -bottom-0.5 size-3 rounded-full bg-online ring-2 ring-card"
              aria-hidden="true"
            />
          </div>
          <div className="flex min-w-0 flex-col">
            <h1 className="font-heading text-xl leading-tight font-semibold tracking-tight">
              Derek
            </h1>
            <span className="truncate text-[0.8rem] text-muted-foreground">
              Front desk concierge
              <span className="hidden sm:inline"> · Available 24/7</span>
            </span>
          </div>
          <div className="ms-auto flex items-center gap-1">
            <Badge
              variant="outline"
              className="me-1 hidden border-brass/50 text-[0.7rem] tracking-wide text-brass-strong uppercase min-[420px]:inline-flex"
            >
              test agent
            </Badge>
            <ThemeToggle />
            <Button
              type="button"
              variant="ghost"
              size="icon-lg"
              onClick={handleReset}
              disabled={isStreaming}
              aria-label="Start a new conversation"
              title="Start a new conversation"
              className="text-muted-foreground hover:text-foreground"
            >
              <RotateCcwIcon />
            </Button>
          </div>
          <div
            className="pointer-events-none absolute inset-x-0 -bottom-px h-px bg-gradient-to-r from-transparent via-brass/70 to-transparent"
            aria-hidden="true"
          />
        </header>

        <MessageScrollerProvider autoScroll>
          <MessageScroller className="flex-1 bg-background/60">
            <MessageScrollerViewport>
              <MessageScrollerContent className="gap-5 px-3 py-6 sm:px-6">
                <MessageScrollerItem>
                  <Marker variant="separator" className="justify-center">
                    <MarkerContent className="font-heading text-[0.7rem] tracking-[0.2em] uppercase">
                      Welcome to the front desk
                    </MarkerContent>
                  </Marker>
                </MessageScrollerItem>
                <MessageScrollerItem>
                  <AssistantBubble content={WELCOME} streaming={false} />
                </MessageScrollerItem>
                {messages.map((message) => (
                  <MessageScrollerItem
                    key={message.id}
                    scrollAnchor={message.role === "user"}
                  >
                    <MessageRow message={message} />
                  </MessageScrollerItem>
                ))}
              </MessageScrollerContent>
            </MessageScrollerViewport>
          </MessageScroller>
        </MessageScrollerProvider>

        <div className="border-t bg-card px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6 sm:pt-4 sm:pb-4">
          <form
            onSubmit={handleSubmit}
            className="flex items-center gap-2 rounded-full border bg-background py-1.5 ps-4 pe-1.5 shadow-sm transition-[border-color,box-shadow] focus-within:border-brass focus-within:ring-3 focus-within:ring-brass/20"
          >
            <Input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Message Derek…"
              aria-label="Message Derek"
              autoFocus
              className="h-9 flex-1 border-0 bg-transparent px-0 text-[0.95rem] shadow-none focus-visible:border-0 focus-visible:ring-0 dark:bg-transparent"
            />
            <Button
              type="submit"
              size="icon"
              disabled={!input.trim() || isStreaming}
              aria-label="Send message"
              className="size-9 shrink-0 rounded-full [&_svg]:size-4"
            >
              <ArrowUpIcon />
            </Button>
          </form>
          <p className="mt-2 text-center text-[0.7rem] text-muted-foreground">
            Rooms, bookings, reservations and payments, any time of day.
          </p>
        </div>
      </div>
    </div>
  )
}

export default App

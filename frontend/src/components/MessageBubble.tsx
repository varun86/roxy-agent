"use client";

import { useState } from "react";
import { Message, SubagentEvent } from "@/types/chat";

interface MessageBubbleProps {
  message: Message;
}

function getStatusIcon(type: string): string {
  switch (type) {
    case "task_started": return "🟢";
    case "task_running": return "🔄";
    case "task_completed": return "✅";
    case "task_failed": return "❌";
    case "task_timed_out": return "⏱️";
    default: return "⚪";
  }
}

function formatEventLine(event: SubagentEvent): string {
  const icon = getStatusIcon(event.type);
  switch (event.type) {
    case "task_started":
      return `${icon} Started: ${event.description || event.task_id} (${event.subagent_type || "general-purpose"})`;
    case "task_running":
      return `${icon} ${event.message || event.task_id}`;
    case "task_completed":
      return `${icon} Completed: ${event.result || event.task_id}`;
    case "task_failed":
      return `${icon} Failed: ${event.error || event.task_id}`;
    case "task_timed_out":
      return `${icon} Timed out: ${event.error || event.task_id}`;
    default:
      return `${icon} ${event.type}: ${event.task_id}`;
  }
}

function getEventTime(event: SubagentEvent): string {
  const h = event.timestamp.getHours().toString().padStart(2, "0");
  const m = event.timestamp.getMinutes().toString().padStart(2, "0");
  return `${h}:${m}`;
}

function getSubagentTitle(events: SubagentEvent[]): string {
  const completed = events.find((e) => e.type === "task_completed");
  if (completed) {
    return completed.result || completed.task_id;
  }
  const failed = events.find((e) => e.type === "task_failed");
  if (failed) {
    return `Failed: ${failed.error || failed.task_id}`;
  }
  const timedOut = events.find((e) => e.type === "task_timed_out");
  if (timedOut) {
    return `Timed out: ${timedOut.error || timedOut.task_id}`;
  }
  const started = events.find((e) => e.type === "task_started");
  if (started) {
    return started.description || started.task_id;
  }
  const running = events.find((e) => e.type === "task_running");
  if (running) {
    return running.task_id;
  }
  return events[0]?.task_id || "Subagent";
}

function getFinalStatus(events: SubagentEvent[]): string {
  const completed = events.find((e) => e.type === "task_completed");
  if (completed) return "✅";
  const failed = events.find((e) => e.type === "task_failed");
  if (failed) return "❌";
  const timedOut = events.find((e) => e.type === "task_timed_out");
  if (timedOut) return "⏱️";
  const running = events.find((e) => e.type === "task_running");
  if (running) return "🔄";
  return "🟢";
}

function SubagentBubble({ message }: { message: Message }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const events = message.subagentEvents || [];
  const title = getSubagentTitle(events);
  const finalStatus = getFinalStatus(events);

  const formattedTime = (() => {
    const h = message.timestamp.getHours().toString().padStart(2, "0");
    const m = message.timestamp.getMinutes().toString().padStart(2, "0");
    return `${h}:${m}`;
  })();

  // Collapsed view - just show title and status
  if (!isExpanded) {
    return (
      <div className="flex justify-start mb-4">
        <div className="max-w-[70%] rounded-2xl border-l-4 border-indigo-500 bg-indigo-50 px-4 py-3 dark:bg-indigo-900 cursor-pointer hover:bg-indigo-100 dark:hover:bg-indigo-800 transition-colors"
          onClick={() => setIsExpanded(true)}>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm shrink-0">🤖</span>
              <span className="font-medium text-indigo-900 dark:text-indigo-100 truncate">
                {title}
              </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-lg">{finalStatus}</span>
              <span className="text-xs text-indigo-400 dark:text-indigo-500">
                {formattedTime}
              </span>
              <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Expanded view - show all events
  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[70%] rounded-2xl border-l-4 border-indigo-500 bg-indigo-50 px-4 py-3 dark:bg-indigo-900">
        {/* Header - clickable to collapse */}
        <div className="flex items-center justify-between gap-3 cursor-pointer hover:opacity-80"
          onClick={() => setIsExpanded(false)}>
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm shrink-0">🤖</span>
            <span className="font-medium text-indigo-900 dark:text-indigo-100 truncate">
              Subagent Details
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <svg className="w-4 h-4 text-indigo-400 rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-indigo-200 dark:border-indigo-700 my-2" />

        {/* Events list */}
        <div className="space-y-1">
          {events.map((event, index) => (
            <div key={index} className="flex justify-between items-start text-sm text-indigo-800 dark:text-indigo-200">
              <span className="whitespace-pre-wrap font-mono text-xs leading-relaxed break-all">
                {formatEventLine(event)}
              </span>
              <span className="text-xs text-indigo-400 dark:text-indigo-500 ml-2 shrink-0">
                {getEventTime(event)}
              </span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="text-xs mt-2 text-indigo-400 dark:text-indigo-500 flex justify-between items-center">
          <span>{formattedTime}</span>
        </div>
      </div>
    </div>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isSubagent = message.role === "subagent";

  const formattedTime = (() => {
    const h = message.timestamp.getHours().toString().padStart(2, "0");
    const m = message.timestamp.getMinutes().toString().padStart(2, "0");
    return `${h}:${m}`;
  })();

  if (isSubagent) {
    return <SubagentBubble message={message} />;
  }

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
    >
      <div
        className={`max-w-[70%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-zinc-900 text-zinc-50 dark:bg-zinc-100 dark:text-zinc-900"
            : "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
        }`}
      >
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
        <div
          className={`text-xs mt-1 ${
            isUser ? "text-zinc-500" : "text-zinc-400"
          }`}
        >
          {formattedTime}
        </div>
      </div>
    </div>
  );
}

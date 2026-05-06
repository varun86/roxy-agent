export type MessageRole = "user" | "assistant" | "subagent";

export interface SubagentEvent {
  type: "task_started" | "task_running" | "task_completed" | "task_failed" | "task_timed_out";
  task_id: string;
  description?: string;
  subagent_type?: string;
  message?: string;
  result?: string;
  error?: string;
  timestamp: Date;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  taskId?: string;
  subagentEvents?: SubagentEvent[];
  isExpanded?: boolean;
}

export interface ChatResponse {
  text: string;
  trace: {
    steps: number;
    tool_calls: number;
    errors: number;
    subagent_calls: number;
    subagent_errors: number;
  };
}

export interface StreamTraceInfo {
  steps: number;
  tool_calls: number;
  errors: number;
  subagent_calls: number;
  subagent_errors: number;
}

export interface ChatHistoryMessage {
  role: MessageRole;
  content: string;
}

export interface ChatRequest {
  message: string;
  model?: string;
  thread_id?: string;
  messages?: ChatHistoryMessage[];
}

export interface ModelInfo {
  name: string;
  display_name: string;
  provider: string;
  supports_vision: boolean;
  default: boolean;
}

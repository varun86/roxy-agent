import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import attentionSvg from "../../../assets/roxy/roxy-attention.svg";
import thinkingSvg from "../../../assets/roxy/roxy-thinking.svg";

type MessageRole = "assistant" | "user";

type TraceSummary = {
  steps: number;
  tool_calls: number;
  errors: number;
};

type ChatMessage = {
  id: string;
  role: MessageRole;
  content: string;
  isError?: boolean;
  includeInHistory?: boolean;
};

function createId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export default function DialogApp() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isOnline, setIsOnline] = useState(false);
  const [statusDetail, setStatusDetail] = useState("正在寻找后端连接...");
  const [isStreaming, setIsStreaming] = useState(false);
  const [showTyping, setShowTyping] = useState(false);
  const [trace, setTrace] = useState<TraceSummary | null>(null);

  const messagesContainerRef = useRef<HTMLElement | null>(null);
  const messageInputRef = useRef<HTMLInputElement | null>(null);
  const threadIdRef = useRef(createId("thread"));
  const assistantTextContentRef = useRef("");
  const streamingMessageIdRef = useRef<string | null>(null);
  const hasBootstrappedWelcomeRef = useRef(false);

  const placeholder = useMemo(
    () => (isOnline ? "给 Roxy 发一条消息..." : "后端离线时暂时无法对话"),
    [isOnline]
  );

  const pushMessage = (message: ChatMessage) => {
    setMessages((prev) => [...prev, message]);
  };

  const updateMessage = (messageId: string, updater: (message: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((message) => (message.id === messageId ? updater(message) : message)));
  };

  const bootstrapWelcome = () => {
    if (hasBootstrappedWelcomeRef.current) return;
    hasBootstrappedWelcomeRef.current = true;
    pushMessage({
      id: createId("assistant"),
      role: "assistant",
      content: "^_^",
      includeInHistory: false,
    });
  };

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages, showTyping, trace]);

  useEffect(() => {
    let disposed = false;

    const init = async () => {
      try {
        const healthy = await window.electronAPI.healthCheck();
        if (!healthy) {
          throw new Error("Backend health check failed");
        }

        if (disposed) return;
        setIsOnline(true);
        setStatusDetail("后端已连接，Roxy 随时待命");
        bootstrapWelcome();

        try {
          const models = await window.electronAPI.listModels();
          if (!disposed && Array.isArray(models) && models.length > 0) {
            setStatusDetail(`已连接后端，可用模型 ${models.length} 个`);
          }
        } catch (error) {
          console.warn("Could not load models:", error);
        }
      } catch (error) {
        console.warn("Backend not available:", error);
        if (disposed) return;
        setIsOnline(false);
        setStatusDetail("后端暂未连接");
        pushMessage({
          id: createId("assistant"),
          role: "assistant",
          content: "等服务启动后，再双击我回来聊天吧！。",
          isError: true,
          includeInHistory: false,
        });
      }
    };

    init();

    return () => {
      disposed = true;
    };
  }, []);

  const getConversationHistory = () =>
    messages
      .filter((message) => message.includeInHistory !== false)
      .map((message) => ({
        role: message.role,
        content: message.content.trim(),
      }))
      .filter((message) => Boolean(message.content))
      .slice(-12);

  const appendAssistantDelta = (delta: string) => {
    const streamMessageId = streamingMessageIdRef.current ?? createId("assistant");

    if (!streamingMessageIdRef.current) {
      streamingMessageIdRef.current = streamMessageId;
      pushMessage({
        id: streamMessageId,
        role: "assistant",
        content: delta,
      });
      return;
    }

    updateMessage(streamMessageId, (message) => ({
      ...message,
      content: `${message.content}${delta}`,
    }));
  };

  const finalizeAssistantMessage = (finalText: string, nextTrace: TraceSummary | null) => {
    const streamMessageId = streamingMessageIdRef.current;

    if (streamMessageId) {
      updateMessage(streamMessageId, (message) => ({
        ...message,
        content: finalText || "(empty response)",
      }));
    } else if (finalText) {
      pushMessage({
        id: createId("assistant"),
        role: "assistant",
        content: finalText,
      });
    }

    streamingMessageIdRef.current = null;
    setTrace(nextTrace);
  };

  const sendMessage = async (message: string) => {
    if (!message || isStreaming || !isOnline) return;

    assistantTextContentRef.current = "";
    streamingMessageIdRef.current = null;
    setIsStreaming(true);
    setTrace(null);

    pushMessage({
      id: createId("user"),
      role: "user",
      content: message,
    });
    setShowTyping(true);

    try {
      const events = await window.electronAPI.sendChatStream(
        message,
        threadIdRef.current,
        getConversationHistory()
      );

      for (const event of Array.isArray(events) ? events : []) {
        if (event.type === "start") {
          continue;
        }

        if (event.type === "delta" && typeof event.delta === "string") {
          assistantTextContentRef.current += event.delta;
          appendAssistantDelta(event.delta);
          continue;
        }

        if (event.type === "done") {
          if (event.thread_id) {
            threadIdRef.current = event.thread_id;
          }
          finalizeAssistantMessage(
            typeof event.text === "string" && event.text ? event.text : assistantTextContentRef.current,
            event.trace ?? null
          );
          continue;
        }

        if (event.type === "error") {
          throw new Error(event.error || "Unknown stream error");
        }
      }

      if (streamingMessageIdRef.current) {
        finalizeAssistantMessage(assistantTextContentRef.current, null);
      } else if (assistantTextContentRef.current) {
        pushMessage({
          id: createId("assistant"),
          role: "assistant",
          content: assistantTextContentRef.current,
        });
      }
    } catch (error) {
      console.error("Chat error:", error);
      const errorText =
        assistantTextContentRef.current ||
        `连接失败：${error instanceof Error ? error.message : "unknown error"}`;

      if (streamingMessageIdRef.current) {
        finalizeAssistantMessage(errorText, null);
      } else {
        pushMessage({
          id: createId("assistant"),
          role: "assistant",
          content: errorText,
          isError: !assistantTextContentRef.current,
        });
      }
    } finally {
      setShowTyping(false);
      setIsStreaming(false);
      setInputValue("");
      messageInputRef.current?.focus();
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await sendMessage(inputValue.trim());
  };

  const handleKeyDown = async (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await sendMessage(inputValue.trim());
    }
  };

  return (
    <div className="dialog-shell">
      <div className="dialog-frame">
        <div className="dialog-tail" aria-hidden="true" />
        <header className="dialog-header">
          <div className="header-avatar">
            <img src={attentionSvg} alt="Roxy avatar" />
          </div>
          <div className="header-copy">
            <div className="header-title-row">
              <h1>Roxy</h1>
              <span className={`status-badge ${isOnline ? "online" : "offline"}`}>
                {isOnline ? "Online" : "Offline"}
              </span>
            </div>
            <p>{statusDetail}</p>
          </div>
          <div className="header-actions">
            <button
              type="button"
              id="minimize-btn"
              className="header-btn"
              aria-label="Minimize"
              onClick={() => window.electronAPI.minimizeDialog()}
            >
              <span />
            </button>
            <button
              type="button"
              id="close-btn"
              className="header-btn close"
              aria-label="Close"
              onClick={() => window.electronAPI.closeDialog()}
            >
              <span />
            </button>
          </div>
        </header>

        <main id="messages" ref={messagesContainerRef} className="messages-container">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`message ${message.role}${message.isError ? " error" : ""}`}
            >
              <div className="bubble">{message.content}</div>
            </div>
          ))}
        </main>

        <div className={`typing-indicator${showTyping ? "" : " hidden"}`} aria-live="polite">
          <div className="typing-avatar">
            <img src={thinkingSvg} alt="" aria-hidden="true" />
          </div>
          <div className="typing-bubble">
            <span />
            <span />
            <span />
          </div>
        </div>

        <div className={`trace-info${trace ? "" : " hidden"}`}>
          <span>
            {trace
              ? `Steps ${trace.steps} · Tool calls ${trace.tool_calls} · Errors ${trace.errors}`
              : ""}
          </span>
        </div>

        <footer className="input-panel">
          <form id="chat-form" className="chat-form" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="message-input">
              Chat with Roxy
            </label>
            <input
              ref={messageInputRef}
              type="text"
              id="message-input"
              className="message-input"
              placeholder={placeholder}
              autoComplete="off"
              disabled={!isOnline || isStreaming}
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              onFocus={() => window.electronAPI.notifyDialogInputFocus()}
              onBlur={() => window.electronAPI.notifyDialogInputBlur()}
              onKeyDown={handleKeyDown}
            />
            <button
              type="submit"
              id="send-btn"
              className="send-btn"
              disabled={!isOnline || isStreaming}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 12.5 20 4l-4.5 16-4-5-7.5-2.5Z" />
              </svg>
            </button>
          </form>
        </footer>
      </div>
    </div>
  );
}

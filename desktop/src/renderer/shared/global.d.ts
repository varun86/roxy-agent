type PetState = "idle" | "working" | "working-typing" | "react-drag" | string;

type ChatStreamEvent =
  | { type: "start" }
  | { type: "delta"; delta: string }
  | {
      type: "tool_called";
      call_id?: string;
      tool_name?: string;
      arguments?: Record<string, unknown>;
      output?: string;
      is_error?: boolean;
    }
  | {
      type: "reminder_created";
      reminder_id?: string;
      thread_id?: string | null;
      title?: string;
      message?: string;
      trigger_at?: string;
      timezone?: string;
    }
  | {
      type: "done";
      text?: string;
      thread_id?: string;
      trace?: {
        steps: number;
        tool_calls: number;
        errors: number;
        subagent_calls?: number;
        subagent_errors?: number;
      } | null;
    }
  | { type: "error"; error?: string };

type ConversationSummary = {
  thread_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_preview: string;
  message_count: number;
};

type ConversationDetail = ConversationSummary & {
  messages: Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
    created_at: string;
    is_error?: boolean;
    tool_events?: Array<{
      call_id: string;
      tool_name: string;
      arguments: Record<string, unknown>;
      output: string;
      is_error?: boolean;
    }>;
    trace?: {
      steps: number;
      tool_calls: number;
      errors: number;
      subagent_calls?: number;
      subagent_errors?: number;
    } | null;
  }>;
};

type VoiceAssetPayload = {
  voiceKey: string;
  assetUrl: string;
};

type RandomActionPayload = {
  key: string;
  url: string;
  label: string;
};

type ReminderDetail = {
  id: string;
  thread_id?: string | null;
  title: string;
  message: string;
  trigger_at: string;
  timezone: string;
  status: string;
  created_at: string;
  fired_at?: string | null;
  delivery_error?: string | null;
};

type ReminderOpenPayload = {
  reminderId: string;
  threadId?: string | null;
};

interface ElectronAPI {
  dragLock: (locked: boolean) => void;
  dragMove: () => void;
  dragEnd: () => void;
  startDragReaction: () => void;
  endDragReaction: () => void;
  notifyPetInteraction: (type: "single" | "double") => void;
  openChatDialog: () => void;
  closeDialog: () => void;
  minimizeDialog: () => void;
  setDialogChatBusy: (active: boolean) => void;
  notifyDialogInputFocus: () => void;
  notifyDialogInputBlur: () => void;
  onStateChange: (callback: (state: PetState, svgPath: string) => void) => () => void;
  onPlayVoiceAsset: (callback: (payload: VoiceAssetPayload) => void) => () => void;
  playVoiceKey: (voiceKey: string) => void;
  playRandomAction: (actionKey: string, assetUrl: string) => void;
  getRandomAction: () => Promise<RandomActionPayload | null>;
  onPlayRandomAction: (
    callback: (actionKey: string, assetUrl: string) => void
  ) => () => void;
  onOpenReminderCard: (callback: (payload: ReminderOpenPayload) => void) => () => void;
  sendChatStream: (
    message: string,
    threadId?: string,
    messages?: Array<{ role: "user" | "assistant"; content: string }>
  ) => Promise<ChatStreamEvent[]>;
  sendChat: (
    message: string,
    threadId?: string,
    messages?: Array<{ role: "user" | "assistant"; content: string }>
  ) => Promise<unknown>;
  listModels: () => Promise<unknown>;
  fetchConversations: () => Promise<ConversationSummary[]>;
  fetchConversation: (threadId: string) => Promise<ConversationDetail>;
  fetchReminder: (reminderId: string) => Promise<ReminderDetail>;
  createConversation: () => Promise<ConversationSummary>;
  deleteConversation: (threadId: string) => Promise<{ status: string; thread_id: string }>;
  healthCheck: () => Promise<boolean>;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}

export {};

declare module "*.vrm?url" {
  const src: string;
  export default src;
}

declare module "*.fbx?url" {
  const src: string;
  export default src;
}

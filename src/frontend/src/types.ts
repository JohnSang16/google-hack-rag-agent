export interface DiscordMessage {
  time: string;
  author: string;
  content: string;
}

export interface Citation {
  title: string;
  date: string | null;
  file_id: string;
  source_type: string;
  drive_url: string | null;
  discord_url?: string | null;
  messages?: DiscordMessage[];
  relevance_score: number;
}

export interface AgentMessage {
  role: 'agent';
  content: string;
  summary?: string;
  mode: 'RECALL' | 'ANALYZE' | 'PLAN' | 'CHAT';
  citations: Citation[];
  created_doc_url?: string;
  calendar_event_url?: string;
  calendar_event_start_date?: string;
  gmail_draft_id?: string;
  gmail_draft_url?: string;
}

export interface UserMessage {
  role: 'user';
  content: string;
}

export interface ErrorMessage {
  role: 'error';
  content: string;
}

export type Message = UserMessage | AgentMessage | ErrorMessage;

export interface ChatResponse {
  mode: 'RECALL' | 'ANALYZE' | 'PLAN' | 'CHAT';
  answer: string;
  summary?: string;
  citations: Citation[];
  created_doc_url?: string;
  calendar_event_url?: string;
  calendar_event_id?: string;
  calendar_event_start_date?: string;
  gmail_draft_id?: string;
  gmail_draft_url?: string;
}

export interface HistoryItem {
  role: 'user' | 'agent';
  content: string;
}

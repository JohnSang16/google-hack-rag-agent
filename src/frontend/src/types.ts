export interface Citation {
  title: string;
  date: string | null;
  file_id: string;
  drive_url: string | null;
  relevance_score: number;
}

export interface AgentMessage {
  role: 'agent';
  content: string;
  mode: 'RECALL' | 'ANALYZE' | 'PLAN';
  citations: Citation[];
  created_doc_url?: string;
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
  mode: 'RECALL' | 'ANALYZE' | 'PLAN';
  answer: string;
  citations: Citation[];
  created_doc_url?: string;
}

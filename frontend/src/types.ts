export type Strategy = 'fixed' | 'section' | 'table_aware';
export type Retriever = 'hybrid' | 'dense' | 'bm25';
export type Citation = {
  n: number;
  chunk_id: string;
  ticker: string;
  company: string;
  item: string;
  heading: string;
  excerpt: string;
};
export type AskResponse = {
  answer: string;
  refused: boolean;
  refusal_reason: string | null;
  citations: Citation[];
  companies: string[];
  top_score?: number | null;
  timings: { total?: number; retrieve?: number; generate?: number; retrieve_breakdown?: Record<string, unknown> };
  config: string;
};
export type Health = {
  status: 'ready' | 'warming_up';
  chat_model: string;
  embed_model: string;
  rerank_model: string;
  access_code_required: boolean;
};
export type Options = {
  strategies: Strategy[];
  retrievers: Retriever[];
  examples: string[];
  default: { strategy: Strategy; retriever: Retriever; rerank: boolean };
};
export type Message = { id: string; role: 'user' | 'assistant'; text: string; response?: AskResponse };

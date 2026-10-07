export type Mode = 'mock' | 'live';

export interface Evidence {
  document: {
    id: string;
    version: number;
    title: string;
    text: string;
    domain: string;
  };
}

export interface Answer {
  request_id: string;
  mode: Mode;
  status: 'answered' | 'partial' | 'no_evidence' | 'failed';
  answer: string;
  citations: Evidence[];
  error: string | null;
  results: {
    task: { domain: string; subquery: string };
    error: string | null;
  }[];
  conflicts: {
    reason: string;
    selected_source_id: string | null;
  }[];
}

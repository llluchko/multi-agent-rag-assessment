import type { Answer, Mode } from './types';

export async function getMode(signal: AbortSignal): Promise<Mode> {
  const response = await fetch('/api/health', { signal });
  if (!response.ok) throw new Error('The API is unavailable.');
  const data: { mode: Mode } = await response.json();
  return data.mode;
}

export async function askQuestion(text: string): Promise<Answer> {
  const response = await fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    signal: AbortSignal.timeout(360_000),
  });
  if (response.status === 422) {
    throw new Error('Enter a question containing words, between 3 and 2000 characters.');
  }
  const data = await response.json();
  // Provider failures use HTTP 502 but still contain a useful answer trace.
  if (!response.ok && !(response.status === 502 && data.request_id)) {
    throw new Error(`The request failed (${response.status}). Please try again.`);
  }
  return data as Answer;
}

import { useEffect, useState, type FormEvent } from 'react';
import { AnswerView } from './AnswerView';
import { askQuestion, getMode } from './api';
import type { Answer, Mode } from './types';

type Entry = { question: string; result: Answer };

export function App() {
  const [question, setQuestion] = useState('');
  const [entries, setEntries] = useState<Entry[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [mode, setMode] = useState<Mode | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getMode(controller.signal).then(setMode).catch(() => {
      if (!controller.signal.aborted) setError('Could not reach the API. Check that it is running.');
    });
    return () => controller.abort();
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || question.trim().length < 3) return;
    setBusy(true);
    setError('');
    try {
      const text = question.trim();
      const result = await askQuestion(text);
      setEntries(previous => [...previous, { question: text, result }]);
      setMode(result.mode);
      setQuestion('');
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'The request failed.';
      setError(cause instanceof TypeError ? 'Could not reach the API. Please try again.' : message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Platform assistant</h1>
      <p>Ask about technical, business and compliance procedures.</p>
      <p className="muted">
        {mode === 'mock' && 'Demo mode: answers contain retrieved passages, without a generative LLM.'}
        {mode === 'live' && 'Live mode: an LLM writes answers using the retrieved sources.'}
        {!mode && 'Connecting to the API…'}
        {' '}<a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API documentation</a>
      </p>

      <form onSubmit={submit}>
        <label htmlFor="question">Your question</label>
        <textarea
          id="question"
          value={question}
          onChange={event => setQuestion(event.target.value)}
          minLength={3}
          maxLength={2000}
          rows={4}
          required
          disabled={busy}
        />
        <button type="submit" disabled={busy || question.trim().length < 3}>
          {busy ? 'Searching…' : 'Send question'}
        </button>
        <p className="muted">Each question is independent. The knowledge base contains synthetic demo data.</p>
      </form>

      {error && <p className="error" role="alert">{error}</p>}
      <div aria-live="polite" aria-busy={busy}>
        {entries.map(({ question, result }) => (
          <article key={result.request_id}>
            <h2>{question}</h2>
            <AnswerView result={result} />
          </article>
        ))}
      </div>
    </main>
  );
}

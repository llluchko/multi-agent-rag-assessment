import { useEffect, useRef, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Evidence = { document: { id: string; version: number; title: string; text: string; domain: string }; similarity: number };
type Answer = { request_id: string; mode: 'mock' | 'live'; status: string; answer: string; citations: Evidence[]; error: string | null; timings_ms: { total: number }; results: { task: { domain: string; subquery: string }; error: string | null }[]; conflicts: { reason: string; selected_source_id: string | null }[] };
type Entry = { question: string; result?: Answer; error?: string };
const examples = [
  ['Deploy a service', 'What’s the process for deploying a new microservice and what compliance checks are needed?'],
  ['Investigate performance', 'How do I troubleshoot API performance issues while following our security policies?'],
  ['Plan a data workflow', 'What business approvals are required for implementing a new data processing workflow?'],
];

function App() {
  const [question, setQuestion] = useState('');
  const [entries, setEntries] = useState<Entry[]>([]);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState('Connecting');
  const input = useRef<HTMLTextAreaElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/health', { signal: controller.signal }).then(r => {
      if (!r.ok) throw new Error('Unavailable');
      return r.json();
    }).then(data => setMode(data.mode === 'mock' ? 'Mock demo' : 'Live model')).catch(error => {
      if (error.name !== 'AbortError') setMode('API unavailable');
    });
    return () => controller.abort();
  }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [entries]);

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (busy || text.length < 3) return;
    setBusy(true);
    setEntries(previous => [...previous, { question: text }]);
    setQuestion('');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 360_000);
    try {
      const response = await fetch('/api/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }), signal: controller.signal });
      const data = await response.json();
      if (!response.ok && !data.request_id) throw new Error(`The request failed (${response.status}). Please try again.`);
      const result = data as Answer;
      setMode(result.mode === 'mock' ? 'Mock demo' : 'Live model');
      setEntries(previous => [...previous.slice(0, -1), { question: text, result }]);
    } catch (error) {
      const message = error instanceof Error && error.name === 'AbortError'
        ? 'The request timed out. Please try again.'
        : 'Could not reach the service. Check that the API is running, then try again.';
      setEntries(previous => [...previous.slice(0, -1), { question: text, error: message }]);
      setQuestion(text);
    } finally {
      clearTimeout(timer);
      setBusy(false);
      requestAnimationFrame(() => input.current?.focus());
    }
  }

  return <div className="shell">
    <header><a className="brand" href="/" aria-label="Platform assistant home"><span className="mark">P</span> Platform assistant</a><span className="mode"><span className="dot" />{mode}</span></header>
    <main>
      <section className="intro"><p className="eyebrow">YOUR INTERNAL KNOWLEDGE, CONNECTED</p><h1>One question.<br /><span>Three perspectives.</span></h1><p className="lede">Find the technical steps, business decisions and compliance requirements — with sources you can inspect.</p><div className="domains"><span>Technical</span><span>Business</span><span>Compliance</span></div></section>
      {entries.length === 0 && <section className="examples" aria-label="Example questions">{examples.map(([label, text], index) => <button key={label} onClick={() => { setQuestion(text); input.current?.focus(); }}><span className="example-number">0{index + 1}</span><strong>{label}</strong><span className="arrow">↗</span></button>)}</section>}
      <section className="conversation" aria-label="Conversation" aria-live="polite" aria-busy={busy}>
        {entries.map((entry, index) => <article className="exchange" key={index}>
          <div className="question"><span className="eyebrow">YOU ASKED</span><h2>{entry.question}</h2></div>
          {entry.error && <p className="error" role="alert">{entry.error}</p>}
          {!entry.result && !entry.error && <p className="loading">Searching the knowledge bases…</p>}
          {entry.result && <div className="response">
            <div className="response-meta"><strong>Platform assistant</strong><span className={`status ${entry.result.status}`}>{entry.result.status.replace('_', ' ')}</span><span>{(entry.result.timings_ms.total / 1000).toFixed(1)}s</span></div>
            <div className="answer">{entry.result.answer}</div>
            {entry.result.error && <p className="error">{entry.result.error}</p>}
            {entry.result.citations.length > 0 && <details className="sources"><summary>{entry.result.citations.length} sources · inspect the evidence</summary>{entry.result.citations.map(({ document: doc }) => <div className="source" key={`${doc.id}@${doc.version}`}><span className="eyebrow">{doc.domain} · VERSION {doc.version}</span><h3>{doc.title}</h3><p>{doc.text}</p><code>{doc.id}@v{doc.version}#0</code></div>)}</details>}
            <details className="trace"><summary>How this answer was assembled</summary>{entry.result.results.map(r => <p key={r.task.domain}><strong>{r.task.domain}:</strong> {r.task.subquery}{r.error && <span className="error"> — {r.error}</span>}</p>)}{entry.result.conflicts.map((c, i) => <p key={i}><strong>Conflict:</strong> {c.reason}</p>)}</details>
          </div>}
        </article>)}
        <div ref={bottom} />
      </section>
      <form onSubmit={send} className="composer"><label htmlFor="question">Ask about your platform</label><textarea id="question" ref={input} value={question} maxLength={2000} rows={3} disabled={busy} onChange={e => setQuestion(e.target.value)} placeholder="What do I need to know before deploying a new service?" /><div className="composer-footer"><span>Each question is answered independently.</span><button type="submit" disabled={busy || question.trim().length < 3}>{busy ? 'Working…' : 'Ask assistant'} <span aria-hidden="true">↑</span></button></div></form>
      <p className="footnote">Synthetic knowledge for a technical assessment. Check the cited evidence before relying on an answer.</p>
    </main>
    <footer><span>MULTI-AGENT RAG · DEMO</span><a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">Explore the API ↗</a></footer>
  </div>;
}

createRoot(document.getElementById('root')!).render(<App />);

import type { Answer } from './types';

export function AnswerView({ result }: { result: Answer }) {
  return (
    <section aria-label="Answer">
      <p className="muted">Status: {result.status.replace('_', ' ')}</p>
      <p className="answer">{result.answer}</p>
      {result.error && <p className="error" role="alert">{result.error}</p>}

      {result.citations.length > 0 && (
        <details>
          <summary>Sources ({result.citations.length})</summary>
          <ul>
            {result.citations.map(({ document }) => (
              <li key={`${document.id}@${document.version}`}>
                <strong>{document.title}</strong>
                <p>{document.text}</p>
                <small>{document.domain} · {document.id}@v{document.version}#0</small>
              </li>
            ))}
          </ul>
        </details>
      )}

      <details>
        <summary>Agent steps</summary>
        <ul>
          {result.results.map(({ task, error }) => (
            <li key={task.domain}>
              <strong>{task.domain}:</strong> {task.subquery}
              {error && <p className="error">{error}</p>}
            </li>
          ))}
          {result.conflicts.map((conflict, index) => (
            <li key={`conflict-${index}`}>Conflict: {conflict.reason}</li>
          ))}
        </ul>
      </details>
    </section>
  );
}

import { FormEvent, KeyboardEvent, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown, { Components } from 'react-markdown';
import type { AskResponse, Citation, Health, Message, Options, Retriever, Strategy } from './types';

const ACCESS_KEY = 'filing-lens-access-code';

async function getError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string };
    return payload.detail || `Request failed (${response.status}).`;
  } catch {
    return `Request failed (${response.status}).`;
  }
}

function Icon({ name }: { name: 'settings' | 'send' | 'close' }) {
  if (name === 'settings') return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 8.7a3.3 3.3 0 1 0 0 6.6 3.3 3.3 0 0 0 0-6.6Z" stroke="currentColor" strokeWidth="1.5"/><path d="m19.4 13.5 1.1.9-1.1 1.9-1.4-.5a7.7 7.7 0 0 1-1.6.9l-.2 1.5h-2.2l-.4-1.4a7.7 7.7 0 0 1-1.9 0l-.8 1.2-2-.9.2-1.5a7.6 7.6 0 0 1-1.3-1.4l-1.5.2-.7-2.1 1.2-.8a7.5 7.5 0 0 1-.1-1.9l-1.3-.8.8-2 1.5.2a7.4 7.4 0 0 1 1.4-1.3l-.1-1.5 2.1-.7.8 1.2a7.7 7.7 0 0 1 1.9-.1l.8-1.3 2 .8-.2 1.5a7.4 7.4 0 0 1 1.3 1.4l1.5-.1.7 2.1-1.2.8c.1.6.1 1.3 0 1.9Z" stroke="currentColor" strokeWidth="1.35" strokeLinejoin="round"/></svg>;
  if (name === 'send') return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m4.5 11.8 14.2-6.3-5.9 13.9-2.2-5.4-6.1-2.2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><path d="m10.6 14 4.2-4.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>;
  return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>;
}

function CitationChip({ citation, onClick, compact = false }: { citation: Citation; onClick: () => void; compact?: boolean }) {
  return <button className={compact ? 'cite-inline' : 'citation-pill'} onClick={onClick} aria-label={`Open source ${citation.n}: ${citation.company}, Item ${citation.item}, ${citation.heading}`}>
    {compact ? `[${citation.n}]` : `[${citation.n}]  ${citation.ticker} · Item ${citation.item} · ${citation.heading || 'Filing excerpt'}`}
  </button>;
}

function SourcePanel({ citation, onClose }: { citation: Citation; onClose: () => void }) {
  useEffect(() => {
    const handle = (event: globalThis.KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handle);
    return () => window.removeEventListener('keydown', handle);
  }, [onClose]);
  return <>
    <button className="sheet-backdrop" aria-label="Close source panel" onClick={onClose} />
    <aside className="source-panel" aria-label={`Source ${citation.n}`} role="dialog" aria-modal="true">
      <div className="source-top">
        <div><div className="source-kicker">Source [ {citation.n} ]</div><h2 className="source-title">Filing excerpt</h2></div>
        <button className="source-close" onClick={onClose} aria-label="Close source"><Icon name="close" /></button>
      </div>
      <div className="source-kicker">Company</div>
      <h3 className="source-company">{citation.company}</h3>
      <div className="source-tags"><span className="source-tag">{citation.ticker}</span><span className="source-tag">10-K · Item {citation.item}</span></div>
      <h4 className="source-heading">Section heading</h4>
      <div style={{ fontFamily: 'var(--serif)', fontSize: 18, lineHeight: 1.45 }}>{citation.heading || 'Unlabeled section'}</div>
      <h4 className="source-heading">Passage</h4>
      <div className="excerpt">{citation.excerpt || 'No excerpt was returned for this source.'}</div>
      <div className="source-heading">Chunk reference</div>
      <div style={{ font: '10px var(--mono)', color: 'var(--muted)', overflowWrap: 'anywhere' }}>{citation.chunk_id}</div>
    </aside>
  </>;
}

function SettingsPopover({ options, strategy, setStrategy, retriever, setRetriever, rerank, setRerank, close }: {
  options: Options | null; strategy: Strategy | null; setStrategy: (value: Strategy) => void;
  retriever: Retriever | null; setRetriever: (value: Retriever) => void; rerank: boolean | null; setRerank: (value: boolean) => void; close: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onPointer = (event: MouseEvent) => { if (ref.current && !ref.current.contains(event.target as Node)) close(); };
    const onKey = (event: globalThis.KeyboardEvent) => { if (event.key === 'Escape') close(); };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onPointer); document.removeEventListener('keydown', onKey); };
  }, [close]);
  const strategies: Strategy[] = options?.strategies || [];
  const retrievers: Retriever[] = options?.retrievers || [];
  const names: Record<string, string> = { table_aware: 'Table-aware', fixed: 'Fixed', section: 'Section', hybrid: 'Hybrid', dense: 'Dense', bm25: 'BM25' };
  return <div className="popover" ref={ref} role="dialog" aria-label="Retrieval settings">
    <h2 className="popover-title">Retrieval settings</h2>
    <p className="popover-copy">Switch settings to compare retrieval strategies. Changes apply to your next question.</p>
    <div className="setting-group"><span className="setting-label">Chunking strategy</span><div className="segmented">
    {strategies.map(value => <button key={value} className={`segment ${strategy === value ? 'active' : ''}`} aria-pressed={strategy === value} onClick={() => setStrategy(value)}>{names[value] || value}</button>)}
    {!strategies.length && <span className="popover-copy">Options are unavailable.</span>}
    </div></div>
    <div className="setting-group"><span className="setting-label">Retriever</span><div className="segmented">
    {retrievers.map(value => <button key={value} className={`segment ${retriever === value ? 'active' : ''}`} aria-pressed={retriever === value} onClick={() => setRetriever(value)}>{names[value] || value}</button>)}
    {!retrievers.length && <span className="popover-copy">Options are unavailable.</span>}
    </div></div>
    <div className="setting-group toggle-row"><span>Rerank passages</span><input className="switch" type="checkbox" checked={rerank ?? false} disabled={rerank === null} onChange={event => setRerank(event.target.checked)} aria-label="Rerank passages" /></div>
  </div>;
}

function AnswerContent({ response, onCitation }: { response: AskResponse; onCitation: (citation: Citation) => void }) {
  const citations = useMemo(() => new Map(response.citations.map(citation => [citation.n, citation])), [response.citations]);
  const answerWithLinks = response.answer.replace(/\[(\d+)\]/g, (match, rawNumber: string) => {
    const number = Number(rawNumber);
    return citations.has(number) ? `[${number}](citation:${number})` : match;
  });
  const reasons: Record<string, string> = {
    low_relevance: 'Nothing relevant was found in the filings.',
    not_in_context: "Related passages were found, but they don't answer this question.",
  };
  const reason = response.refusal_reason ? reasons[response.refusal_reason] || response.refusal_reason.replace(/_/g, ' ') : '';
  const componentMap: Components = {
    a: ({ href, children }: { href?: string; children?: ReactNode }) => {
      const match = href?.match(/^citation:(\d+)$/);
      if (match) {
        const citation = citations.get(Number(match[1]));
        if (citation) return <CitationChip citation={citation} compact onClick={() => onCitation(citation)} />;
      }
      return <span>{children}</span>;
    },
  };
  const seconds = (value?: number) => typeof value === 'number' ? `${value.toFixed(2)}s` : '—';
  return <div className="answer-body">
    {response.refused && <div className="refusal"><strong>Outside the evidence in these filings.</strong><br />{reason}</div>}
    <ReactMarkdown
      components={componentMap}
      urlTransform={url => {
        const match = url.match(/^citation:(\d+)$/);
        return match && citations.has(Number(match[1])) ? url : '';
      }}
    >{answerWithLinks}</ReactMarkdown>
    {response.citations.length > 0 && <div className="citation-list" aria-label="Sources">
      {response.citations.map(citation => <CitationChip key={`${citation.n}-${citation.chunk_id}`} citation={citation} onClick={() => onCitation(citation)} />)}
    </div>}
    <div className="answer-meta">
      <span>Total {seconds(response.timings.total)}</span><span>Retrieve {seconds(response.timings.retrieve)}</span><span>Generate {seconds(response.timings.generate)}</span>
      <span className="score">Top match {typeof response.top_score === 'number' ? response.top_score.toFixed(3) : '—'}</span><span>{response.config}</span>
    </div>
  </div>;
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [gateRequired, setGateRequired] = useState(false);
  const [accessCode, setAccessCode] = useState(() => sessionStorage.getItem(ACCESS_KEY) || '');
  const [gateInput, setGateInput] = useState('');
  const [gateError, setGateError] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [retriever, setRetriever] = useState<Retriever | null>(null);
  const [rerank, setRerank] = useState<boolean | null>(null);
  const [progress, setProgress] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const initializedSettings = useRef(false);

  const loadMeta = useCallback(async () => {
    setLoadError('');
    try {
      const [healthResponse, optionsResponse] = await Promise.all([fetch('/api/health'), fetch('/api/options')]);
      if (!healthResponse.ok) throw new Error(await getError(healthResponse));
      if (!optionsResponse.ok) throw new Error(await getError(optionsResponse));
      const nextHealth = await healthResponse.json() as Health;
      const nextOptions = await optionsResponse.json() as Options;
      setHealth(nextHealth);
      setOptions(nextOptions);
      setGateRequired(nextHealth.access_code_required && !sessionStorage.getItem(ACCESS_KEY));
      if (!initializedSettings.current) {
        setStrategy(nextOptions.default.strategy);
        setRetriever(nextOptions.default.retriever);
        setRerank(nextOptions.default.rerank);
        initializedSettings.current = true;
      }
      setLoading(false);
    } catch (reason) {
      setLoading(false);
      setLoadError(reason instanceof Error ? reason.message : 'Unable to connect to Filing Lens.');
    }
  }, []);

  useEffect(() => { void loadMeta(); }, [loadMeta]);
  useEffect(() => {
    if (health?.status !== 'warming_up') return;
    const interval = window.setInterval(() => { void loadMeta(); }, 3000);
    return () => window.clearInterval(interval);
  }, [health?.status, loadMeta]);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, busy]);
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [question]);

  const sendQuestion = async (event?: FormEvent) => {
    event?.preventDefault();
    const clean = question.trim();
    if (clean.length < 3 || clean.length > 500 || busy || !strategy || !retriever || rerank === null) return;
    const userMessage: Message = { id: `${Date.now()}-u`, role: 'user', text: clean };
    setMessages(previous => [...previous, userMessage]);
    setQuestion('');
    setBusy(true);
    setError('');
    setProgress(0);
    const interval = window.setInterval(() => setProgress(value => Math.min(value + 1, 2)), 1500);
    try {
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(accessCode ? { 'X-Access-Code': accessCode } : {}) },
        body: JSON.stringify({ question: clean, strategy, retriever, rerank }),
      });
      if (response.status === 401) {
        const message = await getError(response);
        sessionStorage.removeItem(ACCESS_KEY);
        setAccessCode('');
        setGateRequired(true);
        setGateError(message);
        setMessages(previous => previous.filter(messageItem => messageItem.id !== userMessage.id));
        return;
      }
      if (!response.ok) throw new Error(await getError(response));
      const result = await response.json() as AskResponse;
      setMessages(previous => [...previous, { id: `${Date.now()}-a`, role: 'assistant', text: result.answer, response: result }]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The request failed. Please try again.');
    } finally {
      window.clearInterval(interval);
      setBusy(false);
    }
  };

  const submitGate = async (event: FormEvent) => {
    event.preventDefault();
    if (!gateInput.trim()) return;
    setGateError('');
    sessionStorage.setItem(ACCESS_KEY, gateInput);
    setAccessCode(gateInput);
    setGateRequired(false);
    setGateInput('');
  };

  const handleComposerKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendQuestion();
    }
  };
  const chooseExample = (example: string) => { setQuestion(example); textareaRef.current?.focus(); };

  if (loading && !health) return <div className="load-state">Connecting to the research desk…</div>;
  if (gateRequired) return <main className="gate-screen">
    <form className="gate-card" onSubmit={submitGate}>
      <span className="brand-name">Filing Lens</span>
      <h1>A quiet place to verify.</h1>
      <p>Enter your access code to research the latest wealth-management 10-Ks. Answers are grounded in cited filing passages.</p>
      <input className="visually-hidden" type="text" name="username" autoComplete="username" tabIndex={-1} aria-hidden="true" />
      <label htmlFor="access-code">Access code</label>
      <input id="access-code" type="password" autoComplete="current-password" value={gateInput} onChange={event => setGateInput(event.target.value)} autoFocus />
      <button className="gate-submit" type="submit" disabled={!gateInput.trim()}>Continue</button>
      {gateError && <p className="gate-error" role="alert">{gateError}</p>}
    </form>
  </main>;

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><span className="brand-name">Filing Lens</span><span className="brand-subtitle">Latest 10-Ks · Raymond James · Schwab · LPL · Stifel · Items 1A and 7</span></div>
      <div className="header-actions">
        <div className="status-label" aria-live="polite"><span className={`status-dot ${health?.status === 'warming_up' ? 'warming' : ''}`} />{health?.status === 'warming_up' ? 'Starting up…' : 'Research desk ready'}</div>
        <div className="settings-anchor">
          <button className="icon-button" aria-label="Open retrieval settings" aria-expanded={settingsOpen} onClick={() => setSettingsOpen(value => !value)}><Icon name="settings" /></button>
          {settingsOpen && <SettingsPopover options={options} strategy={strategy} setStrategy={setStrategy} retriever={retriever} setRetriever={setRetriever} rerank={rerank} setRerank={setRerank} close={() => setSettingsOpen(false)} />}
        </div>
      </div>
    </header>
    <main className="workspace">
      <section className="thread" aria-label="Conversation">
        {messages.length === 0 ? <div className="welcome">
          <div className="eyebrow">A research desk for the latest filings</div>
          <h1>Find the filing evidence<br />behind the question.</h1>
          <p className="welcome-copy">Ask about Raymond James, Schwab, LPL Financial, or Stifel. Filing Lens searches their latest 10-Ks, then answers with passages you can inspect. If the filings do not support an answer, it will say so.</p>
          <div className="example-wrap">
            <p className="examples-heading">Start with a question</p>
            {options?.examples?.length ? <div className="example-list">{options.examples.map((example, index) => <button key={`${index}-${example}`} className="example-button" onClick={() => chooseExample(example)}>{example}</button>)}</div> : <p className="welcome-copy">Example questions are unavailable right now. You can still enter a question below.</p>}
          </div>
        </div> : <div className="conversation">
          {messages.map(message => <article key={message.id} className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'}`}>
            {message.role === 'user' ? <div className="user-bubble">{message.text}</div> : <>
              <div className="assistant-mark" aria-hidden="true">F</div>
              <AnswerContent response={message.response!} onCitation={citation => setActiveCitation(citation)} />
            </>}
          </article>)}
          {busy && <div className="typing" role="status" aria-live="polite"><span className="assistant-mark" aria-hidden="true">F</span><span className="typing-dots"><i/><i/><i/></span>{['Searching the filings…', 'Reranking passages…', 'Writing a cited answer…'][progress]}</div>}
          <div ref={bottomRef} />
        </div>}
      </section>
      {(error || loadError) && <div className="error-banner" role="alert"><span>{error || loadError}</span><button onClick={() => { if (loadError) void loadMeta(); else setError(''); }}>{loadError ? 'Retry' : 'Dismiss'}</button></div>}
      {health?.status === 'warming_up' && <div className="error-banner" role="status"><span>The filing index is starting. This page will check again automatically.</span><button onClick={() => void loadMeta()}>Check now</button></div>}
      <div className="composer-wrap">
        <form className="composer" onSubmit={sendQuestion}>
          <textarea ref={textareaRef} value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={handleComposerKey} placeholder="Ask a question about the latest 10-Ks…" maxLength={500} aria-label="Your question" disabled={busy || health?.status === 'warming_up'} rows={2} />
          <div className="composer-bottom"><span className="composer-hint">Enter to send · Shift + Enter for a new line</span><div className="composer-controls">
            <span className="count" aria-live="polite">{question.length > 420 ? `${question.length}/500` : ''}</span>
      <button className="send-button" type="submit" aria-label="Send question" disabled={busy || !strategy || !retriever || rerank === null || question.trim().length < 3 || question.trim().length > 500 || health?.status === 'warming_up'}><Icon name="send" /></button>
          </div></div>
        </form>
      </div>
    </main>
    {activeCitation && <SourcePanel citation={activeCitation} onClose={() => setActiveCitation(null)} />}
  </div>;
}

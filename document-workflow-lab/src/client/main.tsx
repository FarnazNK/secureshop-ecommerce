import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { createTRPCClient, httpBatchLink } from '@trpc/client';
import type { AppRouter } from '../server/router';
import './style.css';

const api = createTRPCClient<AppRouter>({ links: [httpBatchLink({ url: '/trpc' })] });
type Item = Awaited<ReturnType<typeof api.listCases.query>>[number];
type Doc = Awaited<ReturnType<typeof api.listDocuments.query>>[number];

function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState('');
  const [documents, setDocuments] = useState<Doc[]>([]);
  const [title, setTitle] = useState('');
  const [filename, setFilename] = useState('');
  const [body, setBody] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const active = items.find(item => item.id === selected);

  async function refresh() {
    const data = await api.listCases.query();
    setItems(data);
  }
  useEffect(() => { void refresh().catch(() => setError('Check the API and database connection.')); }, []);
  useEffect(() => {
    if (!selected) { setDocuments([]); return; }
    void api.listDocuments.query({ caseId: selected }).then(setDocuments).catch(() => setError('Unable to fetch documents.'));
  }, [selected]);
  async function execute(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); }
    finally { setBusy(false); }
  }
  return <div className="app">
    <header><span className="mark">◈</span> DOCUMENT WORKFLOW <span className="subtitle">LAB / 01</span></header>
    <div className="hero"><span className="eyebrow">DOCUMENT OPERATIONS / WORKSPACE</span><h1>Make reviews <em>flow.</em></h1><p>Track work, review drafts, and capture decisions in a structured workspace.</p></div>
    <main>
      <section className="panel sidebar">
        <div className="heading"><h2>Work items</h2><small>{items.length} ITEMS</small></div>
        <form onSubmit={e => { e.preventDefault(); void execute(async () => { const item = await api.createCase.mutate({ title }); setTitle(''); setSelected(item.id); }); }}>
          <label htmlFor="title">CREATE NEW</label>
          <div className="inline"><input id="title" required maxLength={120} value={title} placeholder="e.g. Contract review" onChange={e => setTitle(e.target.value)}/><button disabled={busy}>Add</button></div>
        </form>
        <div className="items">{items.map(item => <button className={'item '+(item.id===selected?'active':'')} key={item.id} onClick={() => setSelected(item.id)}><strong>{item.title}</strong><small>{item.status.toUpperCase()}</small></button>)}
          {items.length===0 && <p className="empty">No work items yet.</p>}
        </div>
      </section>
      <section className="panel detail">
        {!active ? <div className="placeholder"><div className="symbol">▤</div><h2>Select a work item</h2><p>Choose or create an item to view its documents.</p></div> : <>
          <div className="heading"><h2>{active.title}</h2><small>#{active.id.slice(0,8)}</small></div>
          <label htmlFor="status">REVIEW STATUS</label>
          <select id="status" disabled={busy} value={active.status} onChange={e => void execute(async () => { await api.setStatus.mutate({ caseId: active.id, status: e.target.value as Item['status'] }); })}>
            <option value="open">Open</option><option value="review">In review</option><option value="complete">Complete</option>
          </select>
          <h3>Documents <small>{documents.length}</small></h3>
          <div className="documents">{documents.length===0 && <p className="empty">No text documents saved yet.</p>}
            {documents.map(doc => <article key={doc.id}><span className="file-icon">≡</span><div><strong>{doc.filename}</strong><p>{doc.body.slice(0,160)}{doc.body.length>160?'…':''}</p></div></article>)}
          </div>
          <form className="document-form" onSubmit={e => { e.preventDefault(); void execute(async () => { await api.addDocument.mutate({caseId:active.id,filename,body}); setFilename(''); setBody(''); setDocuments(await api.listDocuments.query({caseId:active.id})); }); }}>
            <h3>Add text document</h3>
            <label htmlFor="filename">DOCUMENT NAME</label><input id="filename" required maxLength={120} value={filename} onChange={e=>setFilename(e.target.value)} placeholder="draft-notes.txt"/>
            <label htmlFor="body">CONTENT</label><textarea id="body" required maxLength={20000} value={body} onChange={e=>setBody(e.target.value)} placeholder="Use sample text only..." rows={5}/>
            <button disabled={busy}>Save document →</button>
          </form>
        </>}
      </section>
    </main>
    {error && <p role="alert" className="error">{error}</p>}
    <footer>DOCUMENT WORKFLOW LAB <span>REACT / TYPESCRIPT / tRPC / EFFECT / POSTGRESQL</span></footer>
  </div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);

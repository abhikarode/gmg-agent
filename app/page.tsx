"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { signIn, signOut, useSession } from "next-auth/react";
import { Brand } from "./workspace-brand";
import NetworkFinder from "./network-finder";
import MyExpertise from "./my-expertise";
import Reply from "./reply";

const paths = [
  { id: "people", label: "Find people", mark: "◎" },
  { id: "jobs", label: "Opportunities", mark: "↗" },
  { id: "community", label: "Ask GMG", mark: "✳" },
  { id: "expertise", label: "My expertise", mark: "+" },
] as const;

type Path = typeof paths[number]["id"];
type Message = { role: "user" | "assistant"; content: string };
type Stats = { total_users: number; total_jobs: number };
const number = new Intl.NumberFormat("en-US");

export default function ChatPage() {
  const { data: session, status, update } = useSession();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [selected, setSelected] = useState<Path>("people");
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<{ note: string; question: string } | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const field = useRef<HTMLInputElement>(null);
  const workspace = useRef<HTMLDivElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const newest = useRef<HTMLElement>(null);
  const active = useRef<AbortController | null>(null);
  const authorized = session?.gmgAccess === "member";
  const conversation = selected === "jobs" || selected === "community";

  useEffect(() => {
    if (status === "unauthenticated") void signIn();
  }, [status]);
  useEffect(() => {
    if (!authorized) return;
    const controller = new AbortController();
    fetch("/api/gmg/stats", { signal: controller.signal })
      .then((response) => response.ok ? response.json() : null)
      .then((data: Stats | null) => { if (data) setStats(data); })
      .catch(() => undefined);
    return () => controller.abort();
  }, [authorized]);
  useEffect(() => {
    if (failure) end.current?.scrollIntoView({ block: "nearest" });
    else if (messages.length) newest.current?.scrollIntoView({ block: "start" });
  }, [messages, failure]);
  useEffect(() => () => active.current?.abort(), []);

  const current = paths.find((path) => path.id === selected);
  const firstName = session?.user?.name?.trim().split(/\s+/)[0];

  async function ask(question: string, retry = false) {
    const message = question.trim();
    if (!message || message.length > 2000 || active.current) return;
    const controller = new AbortController();
    active.current = controller;
    setInput("");
    setFailure(null);
    setPending(true);
    if (!retry) setMessages((previous) => [...previous, { role: "user", content: message }]);
    try {
      const response = await fetch("/api/gmg/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
        signal: controller.signal,
      });
      if (!response.ok) {
        const note = response.status === 401 || response.status === 403
          ? "Your session no longer has chat access. Sign out and sign in again."
          : "The assistant is temporarily unavailable. Try your question again.";
        if (active.current === controller) setFailure({ note, question: message });
        return;
      }
      const data = await response.json();
      if (active.current === controller) {
        setMessages((previous) => [...previous, { role: "assistant", content: data.response }]);
      }
    } catch {
      if (active.current === controller) {
        setFailure({ note: "Couldn’t reach the assistant. Check your connection and try again.", question: message });
      }
    } finally {
      if (active.current === controller) {
        active.current = null;
        setPending(false);
      }
    }
  }

  function reset() {
    active.current?.abort();
    active.current = null;
    setPending(false);
    setMessages([]);
    setFailure(null);
    setSelected("community");
    setInput("");
    setCopied(null);
    field.current?.focus();
  }

  function openMode(path: Path) {
    if (selected === path) return;
    if (workspace.current) workspace.current.scrollTop = 0;
    if (path !== "people") {
      reset();
      if (path === "jobs") void ask("Show jobs");
    }
    setSelected(path);
  }

  function goHome() {
    reset();
    setSelected("people");
    if (workspace.current) workspace.current.scrollTop = 0;
  }

  async function copy(message: string, index: number) {
    try {
      await navigator.clipboard.writeText(message);
      setCopied(index);
    } catch {
      setCopied(null);
    }
  }

  if (status !== "authenticated") return <main className="loading-screen" aria-busy="true">Opening GMG…</main>;
  if (!authorized) return <main className="policy-page"><div className="policy-card">
    <Brand />
    <h1>{session?.gmgAccess === "unavailable" ? "We couldn’t check your membership" : "GMG membership required"}</h1>
    {session?.gmgAccess === "unavailable" ? <p>You’re signed in with LinkedIn. Try checking your membership again in a moment.</p>
      : session?.gmgAccess === "email-unverified" ? <p>You’re signed in, but LinkedIn didn’t provide a verified email. Verify your primary email on LinkedIn, then sign in again.</p>
        : <p>You’re signed in with LinkedIn. If you’re a GMG member, ask GMG to match your verified LinkedIn email to your member record.</p>}
    <div className="access-actions">
      <button className="solid-action" onClick={() => void update()}>Check access again</button>
      <button className="quiet-action" onClick={() => signOut({ callbackUrl: "/login" })}>Sign out</button>
    </div>
  </div></main>;

  return <div className="gmg-workspace">
    <aside className="workspace-rail">
      <Link className="rail-logo" href="/" onClick={goHome} aria-label="GMG home"><Brand priority /></Link>
      <nav className="rail-nav" aria-label="Explore GMG">
        {paths.map((path) => <button key={path.id} aria-pressed={selected === path.id}
          onClick={() => openMode(path.id)}><span aria-hidden="true">{path.mark}</span>{path.label}</button>)}
      </nav>
      <div className="rail-meta">
        {stats && <dl>
          <div><dt>Members</dt><dd>{number.format(stats.total_users)}</dd></div>
          <div><dt>Open roles</dt><dd>{number.format(stats.total_jobs)}</dd></div>
        </dl>}
        <a href="/privacy-policy">Privacy</a>
      </div>
    </aside>
    <main className="workspace-main">
      <header className="workspace-top">
        <Link className="mobile-logo" href="/" onClick={goHome} aria-label="GMG home"><Brand /></Link>
        <span className="workspace-label">Community desk</span>
        <div className="account-slot">
          {firstName && <span className="account-name">{firstName}</span>}
          <button className="quiet-action" onClick={() => signOut({ callbackUrl: "/login" })}>Sign out</button>
        </div>
        <nav className="mobile-modes" aria-label="Explore GMG">
          {paths.map((path) => <button key={path.id} aria-pressed={selected === path.id}
            onClick={() => openMode(path.id)}>{path.label}</button>)}
        </nav>
      </header>
      <div className="workspace-scroll" ref={workspace}>
        <section hidden={selected !== "people"} aria-label="Member directory"><NetworkFinder /></section>
        {selected === "expertise" && <MyExpertise />}
        {conversation && (!messages.length ? <div className="workspace-inner ask-intro">
          <h1>Ask GMG</h1>
          <p>Ask about Garje Marathi Global, its community, or the member directory.</p>
          <button className="start-button" onClick={() => ask("What is Garje Marathi?")}>What is Garje Marathi? <span aria-hidden="true">↗</span></button>
        </div> : <div className="workspace-inner thread">
          <div className="thread-top"><span>{current?.label || "Your question"}</span>
            <button className="quiet-action" onClick={reset}>New question</button></div>
          <div role="log" aria-live="polite" aria-label="Conversation">
            {messages.map((message, index) => <article key={index}
              ref={index === messages.length - 1 ? newest : null}
              className={`thread-message thread-${message.role}`}>
              <p className="thread-author">{message.role === "user" ? "You" : "Garje Marathi AI"}</p>
              {message.role === "user" ? <p className="question-text">{message.content}</p> : <>
                <Reply content={message.content} />
                <button className="quiet-action copy-action" onClick={() => copy(message.content, index)}>
                  {copied === index ? "Copied" : "Copy answer"}
                </button>
              </>}
            </article>)}
            {pending && <p className="thinking" role="status"><span aria-hidden="true" /> Checking the GMG network…</p>}
          </div>
          {failure && <div className="failure-note" role="alert">{failure.note}
            <button className="quiet-action" onClick={() => ask(failure.question, true)}>Try again</button>
          </div>}
          <div ref={end} />
        </div>)}
      </div>
      {conversation && <div className="compose-area">
        <form className="workspace-inner" onSubmit={(event) => { event.preventDefault(); void ask(input); }}>
          <label htmlFor="question">Ask the GMG network</label>
          <div className="compose-field">
            <input ref={field} id="question" value={input} onChange={(event) => setInput(event.target.value)}
              placeholder="Ask a question about GMG…" maxLength={2000} />
            <button className="solid-action" type="submit" disabled={!input.trim() || pending}>Ask <span aria-hidden="true">↑</span></button>
          </div>
        </form>
      </div>}
    </main>
  </div>;
}

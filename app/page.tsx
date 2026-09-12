"use client";

import { useEffect, useRef, useState } from "react";
import { signIn, signOut, useSession } from "next-auth/react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
const fallbackStats = [["5,132", "members"], ["36", "open roles"], ["2,478", "with photos"]];

export default function ChatPage() {
  const { data: session, status } = useSession();
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState(fallbackStats);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { if (status === "unauthenticated") signIn(); }, [status]);
  useEffect(() => {
    axios.get(`${API_URL}/stats`).then(({ data }) => setStats([[data.total_users.toLocaleString(), "members"], [data.total_jobs.toLocaleString(), "open roles"], [data.users_with_profiles.toLocaleString(), "with photos"]])).catch(() => undefined);
  }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, isLoading]);

  async function ask(question = input) {
    const message = question.trim();
    if (!message || isLoading) return;
    setInput(""); setError(null);
    setMessages((current) => [...current, { role: "user", content: message }]); setIsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/chat`, { message, model: "auto" });
      setMessages((current) => [...current, { role: "assistant", content: response.data.response }]);
    } catch { setError("The community assistant is taking a moment. Please try again."); }
    finally { setIsLoading(false); }
  }

  if (status === "loading") return <div className="loading-screen">Preparing your community desk…</div>;

  return <main className="app-shell">
    <aside className="side-rail">
      <div className="brand-mark"><span>ग</span><div>Garje<br /><em>Marathi</em></div></div>
      <div className="rail-rule" />
      <p className="rail-kicker">Community desk</p>
      <p className="rail-copy">A living index of people, opportunities, and the connections between them.</p>
      <div className="rail-stats">{stats.map(([value, label]) => <div key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>
      <div className="rail-bottom"><span><i className="status-dot" /> Data refreshed today</span><button onClick={() => signOut({ callbackUrl: "/login" })}>Sign out</button></div>
    </aside>
    <section className="chat-stage">
      <header className="topbar"><div><span className="eyebrow">Ask the network</span><span className="live-pill">● Live index</span></div><div className="user-chip">{session?.user?.name || "Member"}</div></header>
      <div className="conversation">{messages.length === 0 ? <div className="welcome">
        <p className="eyebrow">Namaskar</p><h1>Find the people<br /><i>who move things.</i></h1>
        <p className="welcome-copy">Search the Garje Marathi network in plain language. Discover a member, a role, or the next useful introduction.</p>
        <div className="prompt-grid">{["Find member Anand", "Show me jobs", "How many members?"].map((prompt) => <button key={prompt} onClick={() => ask(prompt)}>{prompt}<span>↗</span></button>)}</div>
      </div> : <div className="message-list">
        {messages.map((message, index) => <article className={`message ${message.role}`} key={`${message.role}-${index}`}><span className="message-label">{message.role === "user" ? "You" : "Garje AI"}</span><div>{message.content.split("\n").map((line, lineIndex) => <p key={lineIndex}>{line || " "}</p>)}</div></article>)}
        {isLoading && <article className="message assistant"><span className="message-label">Garje AI</span><div className="typing"><span /><span /><span /></div></article>}<div ref={endRef} />
      </div>}</div>
      <div className="composer-wrap">{error && <p className="error-message">{error}</p>}<form className="composer" onSubmit={(event) => { event.preventDefault(); ask(); }}><label htmlFor="question">Your question</label><div><input id="question" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask about members, roles, or opportunities…" disabled={isLoading} /><button type="submit" disabled={!input.trim() || isLoading}>Ask <span>↗</span></button></div></form><p className="composer-note">Answers draw from the latest member index · Ollama-assisted</p></div>
    </section>
  </main>;
}

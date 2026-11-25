"use client";

import { useEffect, useState } from "react";

type Expertise = { catalog: Record<string, Record<string, string>>; maxTopics: number; topics: string[] };

export default function MyExpertise() {
  const [data, setData] = useState<Expertise | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/gmg/expertise", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const expertise: Expertise = await response.json();
        if (controller.signal.aborted) return;
        setData(expertise);
        setSelected(expertise.topics);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError("Couldn’t load your expertise. Try again.");
      });
    return () => controller.abort();
  }, [attempt]);

  async function save() {
    if (saving || !data) return;
    setSaving(true);
    setNotice("");
    setError("");
    try {
      const response = await fetch("/api/gmg/expertise", {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topics: selected }),
      });
      if (!response.ok) throw new Error();
      const { topics }: { topics: string[] } = await response.json();
      setSelected(topics);
      setData({ ...data, topics });
      setNotice("Your expertise is saved.");
    } catch {
      setError("Couldn’t save your expertise. Your selections are still here. Try again.");
    } finally {
      setSaving(false);
    }
  }

  const changed = data && (data.topics.length !== selected.length || selected.some(topic => !data.topics.includes(topic)));
  const query = filter.trim().toLocaleLowerCase();
  const groups = Object.entries(data?.catalog ?? {}).map(([group, options]) => ({
    group,
    topics: Object.entries(options).filter(([, label]) => `${group} ${label}`.toLocaleLowerCase().includes(query)),
  })).filter(entry => entry.topics.length > 0);
  return <section className="workspace-inner ask-intro expertise-editor" aria-labelledby="expertise-heading">
    <h1 id="expertise-heading">Update my expertise</h1>
    <p>Choose the topics other GMG members can find you for. They’ll appear as member-reported expertise.</p>
    {error && <p role="alert">{error}</p>}
    {!data && (error
      ? <button className="start-button" onClick={() => { setError(""); setAttempt(attempt + 1); }}>Try again</button>
      : <p role="status">Loading expertise…</p>)}
    {data && <form onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <label className="expertise-search" htmlFor="expertise-filter">Find a topic
        <input id="expertise-filter" type="search" value={filter} onChange={event => setFilter(event.target.value)} placeholder="Search by topic or category" />
      </label>
      <p className="expertise-count" aria-live="polite">{selected.length} of {data.maxTopics} selected</p>
      {!groups.length && <p role="status">No topics match. Try a broader term.</p>}
      <div className="expertise-grid">
        {groups.map(({ group, topics }) => <fieldset key={group} disabled={saving}>
          <legend>{group}</legend>
          {topics.map(([id, label]) => {
            const checked = selected.includes(id);
            return <label key={id}>
              <input type="checkbox" checked={checked} disabled={!checked && selected.length === data.maxTopics}
                onChange={() => {
                  setNotice("");
                  setSelected(current => checked ? current.filter(topic => topic !== id) : [...current, id]);
                }} />
              <span>{label}</span>
            </label>;
          })}
        </fieldset>)}
      </div>
      <button className="solid-action" type="submit" disabled={!changed || saving}>{saving ? "Saving…" : "Save expertise"}</button>
      <span className="expertise-notice" role="status">{notice}</span>
    </form>}
  </section>;
}

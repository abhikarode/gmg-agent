"use client";

import { useEffect, useRef, useState } from "react";
import { directoryQuery, memberKey, parseDirectoryResults } from "../directory-results";
import type { DirectoryMember } from "../directory-results";
import MemberPreview from "./member-preview";

const locations = ["Bay Area", "San Francisco", "San Jose", "Mountain View", "San Ramon", "Fremont", "Palo Alto", "Pleasanton"];
const suggestions = ["Marketing", "Software", "Product", "Design"];
const examples = [
  { label: "Startup finances", need: "I’m starting a company and need someone to help me get the books and taxes in order." },
  { label: "Career change", need: "I want to move into designing apps and need someone who has done user research or interface design." },
  { label: "व्यवसायासाठी मदत", need: "माझ्या नव्या व्यवसायाचे हिशेब आणि कर व्यवस्थित करण्यासाठी अनुभवी व्यक्ती हवी आहे." },
];
type Search = { label: string; members: DirectoryMember[]; ranking?: "model" | "directory"; place?: string };
type Mode = "need" | "exact";

export default function NetworkFinder() {
  const [mode, setMode] = useState<Mode>("need");
  const [need, setNeed] = useState("");
  const [needPlace, setNeedPlace] = useState("");
  const [place, setPlace] = useState("");
  const [term, setTerm] = useState("");
  const [search, setSearch] = useState<Search | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<DirectoryMember[]>([]);
  const [error, setError] = useState("");
  const [copyNote, setCopyNote] = useState("");
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  function changeMode(next: Mode) {
    if (next === mode || request.current) return;
    setError("");
    setSearch(null);
    setMode(next);
  }

  async function find(expertise = term) {
    if (request.current) return;
    const match = mode === "need";
    if (match ? need.trim().length < 8 : !place && !expertise.trim()) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(match ? "/api/gmg/recommendations" : "/api/gmg/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(match ? { need, place: needPlace } : { message: directoryQuery(place, expertise) }),
        signal: controller.signal,
      });
      if (!response.ok) {
        if (request.current === controller) setError(response.status === 401 || response.status === 403
          ? "Your session no longer has access. Sign back in to search the directory."
          : match ? "AI matching is temporarily unavailable. Try again or switch to Exact search."
            : "Couldn’t load the directory. Try the search again.");
        return;
      }
      const data = await response.json();
      if (match) {
        if (request.current === controller) setSearch({
          label: "Suggested people",
          members: data.members,
          ranking: data.ranking,
          place: data.place,
        });
        return;
      }
      const matches = parseDirectoryResults(data.response);
      if (request.current === controller) setSearch({
        label: [expertise.trim(), place].filter(Boolean).join(" · "),
        members: !place || place === "Bay Area" ? matches : matches.filter(member =>
          member.location?.split(",")[0].trim().toLowerCase() === place.toLowerCase(),
        ),
      });
    } catch {
      if (request.current === controller) setError("Couldn’t reach the directory. Try again.");
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
      }
    }
  }

  function toggle(member: DirectoryMember) {
    setCopyNote("");
    setSelected(previous => previous.some(item => memberKey(item) === memberKey(member))
      ? previous.filter(item => memberKey(item) !== memberKey(member))
      : [...previous, member]);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(selected.map(member =>
        [member.name, member.summary || member.work, member.location, member.linkedin].filter(Boolean).join(" — "),
      ).join("\n"));
      setCopyNote("Shortlist copied");
    } catch {
      setCopyNote("Couldn’t copy the shortlist.");
    }
  }

  return <div className="finder">
    <section className="finder-intro" aria-labelledby="finder-title">
      <div>
        <p className="finder-kicker">The member directory</p>
        <h1 id="finder-title">Who’s in<br /><em>your corner?</em></h1>
      </div>
      <div className="finder-note">
        <p>Tell us what you’re trying to do, or search the directory by name. Save people for your next introduction.</p>
        <span lang="mr">आपली माणसं, आपल्या जवळ.</span>
      </div>
    </section>
    <fieldset className="finder-controls" aria-label="People search" disabled={busy}>
    <div className="finder-modes" aria-label="How to find people">
      <button type="button" aria-pressed={mode === "need"} onClick={() => changeMode("need")}>
        Describe your need <span lang="mr">तुमची गरज</span>
      </button>
      <button type="button" aria-pressed={mode === "exact"} onClick={() => changeMode("exact")}>
        Exact search <span lang="mr">नाव किंवा शब्द</span>
      </button>
    </div>
    {mode === "need" ? <>
      <form className="need-form" onSubmit={event => { event.preventDefault(); void find(); }}>
        <label htmlFor="finder-need">
          What do you need help with? <span lang="mr">कशासाठी मदत हवी आहे?</span>
        </label>
        <textarea id="finder-need" value={need} onChange={event => setNeed(event.target.value)}
          placeholder="I need someone who can help me…" maxLength={600} rows={3} />
        <div className="need-form-actions">
          <label htmlFor="need-location"><span>Location · <span lang="mr">ठिकाण</span></span>
            <select id="need-location" value={needPlace} onChange={event => setNeedPlace(event.target.value)}>
              <option value="">Anywhere</option>
              {locations.map(location => <option key={location}>{location}</option>)}
            </select>
          </label>
          <button className="solid-action finder-submit" disabled={busy || need.trim().length < 8}>
            {busy ? "Finding matches…" : "Find matches"} <span aria-hidden="true">↗</span>
          </button>
        </div>
      </form>
      <div className="finder-suggestions" aria-label="Examples">
        <span>Try an example</span>
        {examples.map(example => <button type="button" key={example.label} onClick={() => setNeed(example.need)}>
          <span lang={example.label === "व्यवसायासाठी मदत" ? "mr" : "en"}>{example.label}</span>
        </button>)}
      </div>
    </> : <>
    <form className="finder-form" onSubmit={(event) => { event.preventDefault(); void find(); }}>
      <label htmlFor="finder-location">
        <span>Where · <span lang="mr">कुठे</span></span>
        <select id="finder-location" value={place} onChange={event => setPlace(event.target.value)}>
          <option value="">Anywhere</option>
          {locations.map(location => <option key={location}>{location}</option>)}
        </select>
      </label>
      <label htmlFor="finder-term">
        <span>Who or what · <span lang="mr">कोण किंवा काय</span></span>
        <input id="finder-term" value={term} onChange={event => setTerm(event.target.value)}
          placeholder="Name or expertise" maxLength={90} />
      </label>
      <button className="solid-action finder-submit" type="submit" disabled={busy || (!place && !term.trim())}>
        {busy ? "Finding…" : "Find people"} <span aria-hidden="true">↗</span>
      </button>
    </form>
    <div className="finder-suggestions" aria-label="Suggested expertise">
      <span>Try a search</span>
      {suggestions.map(suggestion => <button key={suggestion} onClick={() => {
        setTerm(suggestion);
        void find(suggestion);
      }}>{suggestion}</button>)}
    </div>
    </>}
    </fieldset>
    {selected.length > 0 && !busy && <a className="jump-shortlist shortlist-link" href="#finder-shortlist">Shortlist ({selected.length}) ↓</a>}
    {busy && <div className="finder-progress" role="status">
      <span className="finder-progress-mark" aria-hidden="true" />
      <div><strong>{mode === "need" ? "Finding relevant people…" : "Searching the directory…"}</strong>
        <span lang="mr">शोध सुरू आहे</span>
        <p>{mode === "need" ? "Checking recorded experience for your request." : "Looking up matching member records."}</p>
      </div>
    </div>}
    <div className="finder-board">
      <section className="finder-results" aria-labelledby="finder-results-title" aria-busy={busy} inert={busy}>
        <h2 id="finder-results-title">{search ? search.label : "Member results"}</h2>
        {error && <p role="alert">{error}</p>}
        {!search && !busy && !error && <p className="empty-hint">{mode === "need"
          ? "Describe your goal in English or Marathi. Suggestions will include the directory evidence behind each match."
          : "Enter a name or expertise, or search by location alone."}</p>}
        {search && !busy && <p className="finder-result-count" role="status">
          {search.members.length === 10 ? "First 10 matches. Refine your search to narrow them down." :
            search.members.length ? `${search.members.length} ${search.members.length === 1 ? "match" : "matches"}` :
              "No strong matches found. Try a broader location or describe a related skill."}
          {search.place && ` · ${search.place}`}
        </p>}
        {search?.ranking && !busy && search.members.length > 0 && <p className="finder-match-note">
          {search.ranking === "directory" ? "Showing directory matches because AI ranking was unavailable." :
            "Suggestions are based on recorded experience. Contact the member to confirm fit and availability."}
        </p>}
        <div className="finder-cards">
          {search?.members.map((member, index) => {
            const saved = selected.some(item => memberKey(item) === memberKey(member));
            return <article key={`${memberKey(member)}-${index}`} className="member-card">
              <span className="member-initial" aria-hidden="true">
                {member.name.split(/\s+/).slice(0, 2).map(word => Array.from(word)[0]).join("")}
              </span>
              <div className="member-details">
                <h3><MemberPreview member={member} /></h3>
                {(member.summary || member.work) && (!member.evidence || member.evidence !== member.summary) &&
                  <p className="member-summary">{member.summary || member.work}</p>}
                {member.summarySource && <small>{member.summarySource} · <span lang="mr">प्रोफाइल माहिती</span></small>}
                {member.location && <p className="member-location">{member.location}</p>}
                {!!member.expertise?.length && <p className="member-summary"><strong>Member-reported expertise</strong><br />{member.expertise.join(" · ")}</p>}
                {member.linkedin && <a href={member.linkedin} target="_blank" rel="noreferrer">LinkedIn profile ↗</a>}
                {!member.linkedin && <small>LinkedIn link isn’t on file</small>}
                {member.evidence && <div className="member-evidence"><strong>Why this matched · <span lang="mr">जुळण्याचे कारण</span></strong>
                  <p>{member.evidence}</p>
                </div>}
                {member.source && <small>{member.sourceUrl
                  ? <a href={member.sourceUrl} target="_blank" rel="noreferrer">{member.source} ↗</a>
                  : member.source}</small>}
              </div>
              <button className="member-save" aria-pressed={saved} aria-label={`${saved ? "Remove" : "Save"} ${member.name} ${saved ? "from" : "to"} shortlist`}
                onClick={() => toggle(member)}>{saved ? "✓ Saved" : "+ Save"}</button>
            </article>;
          })}
        </div>
      </section>
      <aside id="finder-shortlist" className="shortlist" aria-labelledby="shortlist-heading">
        <div className="shortlist-title"><div><h2 id="shortlist-heading">Shortlist</h2><small lang="mr">निवडक नावे</small></div><span>{selected.length}</span></div>
        {selected.length === 0 ? <p>Save members to keep them together while you explore. Your shortlist is kept for this visit.</p> : <>
          <ul>{selected.map(member => <li key={memberKey(member)}>
            <MemberPreview member={member} />
            <button className="quiet-action" aria-label={`Remove ${member.name} from shortlist`} onClick={() => toggle(member)}>Remove</button>
          </li>)}</ul>
          <button className="solid-action" onClick={copy}>Copy shortlist</button>
          {copyNote && <p role="status">{copyNote}</p>}
        </>}
      </aside>
    </div>
  </div>;
}

"use client";

import { useId, useRef, useState } from "react";
import type { DirectoryMember } from "../directory-results";

type Visibility = "closed" | "hover" | "pinned";

export default function MemberPreview({ member }: { member: DirectoryMember }) {
  const [visibility, setVisibility] = useState<Visibility>("closed");
  const trigger = useRef<HTMLButtonElement>(null);
  const previewId = useId();
  const summary = member.summary || member.work || member.evidence;
  const open = visibility !== "closed";
  return <span className="person-preview" onPointerEnter={(event) => {
    if (event.pointerType === "mouse" && window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
      setVisibility((state) => state === "closed" ? "hover" : state);
    }
  }} onPointerLeave={(event) => {
    if (!event.currentTarget.contains(document.activeElement)) {
      setVisibility((state) => state === "hover" ? "closed" : state);
    }
  }} onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) setVisibility("closed");
  }} onKeyDown={(event) => {
    if (event.key === "Escape" && open) {
      event.stopPropagation();
      setVisibility("closed");
      trigger.current?.focus();
    }
  }}>
    <button type="button" ref={trigger} className="person-preview-trigger"
      aria-expanded={open} aria-controls={previewId}
      onClick={() => setVisibility((state) => state === "pinned" ? "closed" : "pinned")}>
      {member.name}
    </button>
    <span className="person-preview-card" id={previewId} hidden={!open}>
      <strong>{member.name}</strong>
      {summary && <span>{summary}</span>}
      {member.location && <span className="person-preview-location">{member.location}</span>}
      {member.linkedin && <a href={member.linkedin} target="_blank" rel="noreferrer">View LinkedIn profile ↗</a>}
      {(member.summarySource || member.source) &&
        <small>{member.summarySource || member.source}</small>}
    </span>
  </span>;
}

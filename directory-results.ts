export type DirectoryMember = {
  name: string;
  work?: string;
  location?: string;
  linkedin?: string;
  source?: string;
  sourceUrl?: string;
  evidence?: string;
  summary?: string;
  summarySource?: string;
  expertise?: string[];
};

export function directoryQuery(place: string, term: string) {
  return `Find members ${[place, term.trim()].filter(Boolean).join(" ")}`;
}

export function cleanLinkedInProfile(url: string) {
  return url.match(/^https?:\/\/(?:[\w-]+\.)?linkedin\.com\/(?:in|pub)\/[a-z0-9_%./-]+/i)?.[0];
}

export function parseDirectoryResults(reply: string): DirectoryMember[] {
  if (!/^Found \d+ member\(s\):/.test(reply)) return [];
  return reply.split(/\n\s*\n/).flatMap((block) => {
    const [heading, ...details] = block.split("\n");
    const name = heading.match(/^\*\*(.+)\*\*$/)?.[1];
    if (!name) return [];
    const member: DirectoryMember = { name };
    for (const line of details) {
      if (line.startsWith("- 💼 ")) member.work = line.slice("- 💼 ".length);
      if (line.startsWith("- 📍 ")) member.location = line.slice("- 📍 ".length);
      if (line.startsWith("- Source: ") && !member.sourceUrl) member.source = line.slice("- Source: ".length);
      const profileSummary = line.match(/^- (LinkedIn (?:profile|export)) summary: (.+)$/);
      if (profileSummary) {
        member.summarySource = profileSummary[1];
        member.summary = profileSummary[2];
      }
      if (line.startsWith("- Profile evidence: ")) member.evidence = line.slice("- Profile evidence: ".length);
      if (line.startsWith("- Member-reported expertise: ")) {
        member.expertise = line.slice("- Member-reported expertise: ".length).split(" | ");
      }
      if (line.startsWith("- Profile source: ")) {
        const [source, url] = line.slice("- Profile source: ".length).split(" | ", 2);
        member.source = source;
        if (url?.startsWith("https://")) member.sourceUrl = url;
      }
      if (line.startsWith("- 🔗 ")) {
        const profile = cleanLinkedInProfile(line.slice("- 🔗 ".length));
        if (profile) member.linkedin = profile;
      }
    }
    return [member];
  });
}

export function memberKey(member: DirectoryMember) {
  return member.linkedin || JSON.stringify([member.name, member.work, member.location]);
}

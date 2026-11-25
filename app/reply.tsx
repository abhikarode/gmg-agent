import Markdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cleanLinkedInProfile } from "../directory-results";

function safeLink(url: string) {
  return /^https?:\/\//i.test(url) ? defaultUrlTransform(url) : "";
}

export default function Reply({ content }: { content: string }) {
  return <div className="reply-text">
    <Markdown
      skipHtml
      disallowedElements={["img", "input"]}
      remarkPlugins={[remarkGfm]}
      urlTransform={safeLink}
      components={{
        a: ({ href, children }) => {
          if (!href) return <span>{children}</span>;
          const profile = cleanLinkedInProfile(href);
          return <a href={profile || href} target="_blank" rel="noreferrer">
            {profile && typeof children === "string" && children === href ? "View LinkedIn profile" : children}
          </a>;
        },
        table: ({ children }) => <div className="reply-table"><table>{children}</table></div>,
      }}
    >{content}</Markdown>
  </div>;
}

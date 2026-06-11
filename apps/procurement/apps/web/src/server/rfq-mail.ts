import type { FilledSection } from "@procurement/db";

interface RfqMailContent {
  subject: string;
  text: string;
  html: string;
}

interface RenderInput {
  rfqTitle: string;
  projectName: string;
  versionNumber: number;
  sections: FilledSection[];
  responseDueDays?: number;
  vendorName?: string;
  gcName?: string;
  fromEmail: string;
  documentTitles?: Record<string, string>;
}

// Renders an RFQ as a plain-text + HTML email body. Citation markers
// [doc:<uuid> p<n>] become (Document Title, p<n>) inline. Stripped down so
// the message is readable in any mail client — no images, no fancy CSS.
export function renderRfqMail(input: RenderInput): RfqMailContent {
  const dueLine =
    input.responseDueDays && input.responseDueDays > 0
      ? `Please reply within ${input.responseDueDays} business days.`
      : "Please reply with your quote at your earliest convenience.";

  const greeting = input.vendorName ? `Dear ${input.vendorName} team,` : "Hello,";
  const sender = input.gcName ?? "Procurement";

  const titles = input.documentTitles ?? {};

  // ---- Plain text ----
  const textParts: string[] = [];
  textParts.push(greeting, "");
  textParts.push(
    `We are issuing a Request for Quote on the following scope for project: ${input.projectName}.`,
    "",
    `RFQ: ${input.rfqTitle} (version ${input.versionNumber})`,
    dueLine,
    "",
    "---",
    "",
  );
  for (const sec of input.sections) {
    textParts.push(sec.title, "-".repeat(sec.title.length));
    textParts.push(replaceCitationsText(sec.body, titles));
    textParts.push("");
  }
  textParts.push("---");
  textParts.push("");
  textParts.push(
    "Please return your quote by reply, including:",
    "  • Itemized pricing per the scope above",
    "  • Lead time",
    "  • COI naming our company as additional insured",
    "  • Any exclusions or clarifications",
    "",
    `Reply directly to ${input.fromEmail}.`,
    "",
    `Thanks,`,
    sender,
  );

  // ---- HTML ----
  const htmlParts: string[] = [];
  htmlParts.push(`<p>${escapeHtml(greeting)}</p>`);
  htmlParts.push(
    `<p>We are issuing a Request for Quote on the following scope for project: <strong>${escapeHtml(
      input.projectName,
    )}</strong>.</p>`,
  );
  htmlParts.push(
    `<p><strong>RFQ:</strong> ${escapeHtml(input.rfqTitle)} (version ${input.versionNumber})<br/>${escapeHtml(dueLine)}</p>`,
  );
  htmlParts.push("<hr/>");
  for (const sec of input.sections) {
    htmlParts.push(`<h3>${escapeHtml(sec.title)}</h3>`);
    htmlParts.push(`<div>${markdownishToHtml(sec.body, titles)}</div>`);
  }
  htmlParts.push("<hr/>");
  htmlParts.push(
    "<p>Please return your quote by reply, including:</p>",
    "<ul><li>Itemized pricing per the scope above</li><li>Lead time</li><li>COI naming our company as additional insured</li><li>Any exclusions or clarifications</li></ul>",
    `<p>Reply directly to <a href="mailto:${escapeAttr(input.fromEmail)}">${escapeHtml(input.fromEmail)}</a>.</p>`,
    `<p>Thanks,<br/>${escapeHtml(sender)}</p>`,
  );

  return {
    subject: `RFQ — ${input.rfqTitle} (v${input.versionNumber})`,
    text: textParts.join("\n"),
    html: htmlParts.join("\n"),
  };
}

// Convert [doc:<uuid> p<n>] markers to "(Doc Title, p<n>)" in plain text.
function replaceCitationsText(body: string, titles: Record<string, string>): string {
  return body.replace(/\[doc:([0-9a-f-]{36})\s+p(\d+)\]/gi, (_, id: string, pg: string) => {
    const t = titles[id] ?? `Document ${id.slice(0, 8)}`;
    return ` (${t}, p${pg})`;
  });
}

// Minimal markdown-ish → HTML for the email body. Handles paragraphs,
// bullets, and inline citation markers. Not a full markdown renderer —
// covers the patterns the LLM agents typically produce.
function markdownishToHtml(body: string, titles: Record<string, string>): string {
  const cited = replaceCitationsText(body, titles);
  const lines = cited.split("\n");
  const out: string[] = [];
  let bulletOpen = false;
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      if (bulletOpen) {
        out.push("</ul>");
        bulletOpen = false;
      }
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      if (!bulletOpen) {
        out.push("<ul>");
        bulletOpen = true;
      }
      out.push(`<li>${escapeHtml(line.replace(/^[-*]\s+/, ""))}</li>`);
    } else if (/^#{2,}\s+/.test(line)) {
      if (bulletOpen) {
        out.push("</ul>");
        bulletOpen = false;
      }
      out.push(`<h4>${escapeHtml(line.replace(/^#+\s+/, ""))}</h4>`);
    } else {
      if (bulletOpen) {
        out.push("</ul>");
        bulletOpen = false;
      }
      out.push(`<p>${escapeHtml(line)}</p>`);
    }
  }
  if (bulletOpen) out.push("</ul>");
  return out.join("\n");
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
function escapeAttr(s: string): string {
  return escapeHtml(s).replace(/`/g, "&#96;");
}

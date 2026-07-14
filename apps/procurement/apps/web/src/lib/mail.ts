import { env } from "./env";

export interface MailMessage {
  to: string;
  subject: string;
  text: string;
  html?: string;
  replyTo?: string;
  cc?: string[];
  bcc?: string[];
}

export interface MailSendResult {
  providerMessageId: string;
  provider: string;
}

// Generic mail sender — dispatches to the configured provider.
// Returns a provider message id (or a synthetic one for console) you can
// persist for audit / threading later.
export async function sendMail(msg: MailMessage): Promise<MailSendResult> {
  switch (env.MAIL_TRANSPORT) {
    case "console":
      return sendViaConsole(msg);
    case "resend":
      return sendViaResend(msg);
    case "smtp":
      return sendViaSmtp(msg);
    default:
      throw new Error(`MAIL_TRANSPORT=${env.MAIL_TRANSPORT} is not implemented`);
  }
}

async function sendViaConsole(msg: MailMessage): Promise<MailSendResult> {
  // eslint-disable-next-line no-console
  console.log(
    [
      "",
      "=============== OUTBOUND MAIL (console transport) ===============",
      `To:      ${msg.to}`,
      `CC:      ${msg.cc?.join(", ") ?? "-"}`,
      `From:    ${env.MAIL_FROM}`,
      `ReplyTo: ${msg.replyTo ?? env.MAIL_REPLY_TO ?? "-"}`,
      `Subject: ${msg.subject}`,
      "---",
      msg.text,
      "================================================================",
      "",
    ].join("\n"),
  );
  return {
    providerMessageId: `console-${Date.now()}-${Math.floor(Math.random() * 1e6)}`,
    provider: "console",
  };
}

async function sendViaResend(msg: MailMessage): Promise<MailSendResult> {
  if (!env.RESEND_API_KEY) {
    throw new Error("RESEND_API_KEY is not set");
  }
  const body = {
    from: env.MAIL_FROM,
    to: [msg.to],
    cc: msg.cc,
    bcc: msg.bcc,
    reply_to: msg.replyTo ?? env.MAIL_REPLY_TO,
    subject: msg.subject,
    text: msg.text,
    html: msg.html,
  };
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.text().catch(() => `${res.status} ${res.statusText}`);
    throw new Error(`Resend send failed (${res.status}): ${err}`);
  }
  const payload = (await res.json()) as { id?: string };
  if (!payload.id) throw new Error("Resend response missing id");
  return { providerMessageId: payload.id, provider: "resend" };
}

async function sendViaSmtp(msg: MailMessage): Promise<MailSendResult> {
  if (!env.SMTP_HOST || !env.SMTP_USER || !env.SMTP_PASS) {
    throw new Error("SMTP_HOST, SMTP_USER, SMTP_PASS required for smtp transport");
  }
  // Lazy-import nodemailer so the dep is only loaded when smtp is configured.
  const mod = (await import("nodemailer")) as typeof import("nodemailer");
  const transporter = mod.createTransport({
    host: env.SMTP_HOST,
    port: env.SMTP_PORT,
    secure: env.SMTP_PORT === 465,
    auth: { user: env.SMTP_USER, pass: env.SMTP_PASS },
  });
  const info = await transporter.sendMail({
    from: env.MAIL_FROM,
    to: msg.to,
    cc: msg.cc,
    bcc: msg.bcc,
    replyTo: msg.replyTo ?? env.MAIL_REPLY_TO,
    subject: msg.subject,
    text: msg.text,
    html: msg.html,
  });
  return { providerMessageId: info.messageId, provider: "smtp" };
}

// Convenience wrapper preserved from the original API.
interface MagicLinkMail {
  to: string;
  url: string;
}
export async function sendMagicLink(mail: MagicLinkMail): Promise<void> {
  await sendMail({
    to: mail.to,
    subject: "Sign in to Construction Procurement",
    text: `Sign in by opening this link (valid for 30 minutes):\n\n${mail.url}\n`,
    html: `<p>Sign in by opening this link (valid for 30 minutes):</p><p><a href="${mail.url}">${mail.url}</a></p>`,
  });
}

import { env } from "./env.js";

interface MagicLinkMail {
  to: string;
  url: string;
}

export async function sendMagicLink(mail: MagicLinkMail): Promise<void> {
  if (env.MAIL_TRANSPORT === "console") {
    // Dev: print the link to the server console so you can click it.
    // eslint-disable-next-line no-console
    console.log(
      `\n=============== MAGIC LINK ===============\nTo: ${mail.to}\nFrom: ${env.MAIL_FROM}\n${mail.url}\n==========================================\n`,
    );
    return;
  }
  // Stub for production — wire up Resend/SES here.
  throw new Error(`MAIL_TRANSPORT=${env.MAIL_TRANSPORT} is not implemented yet`);
}

import { z } from "zod";

const baseSchema = z.object({
  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url(),
  S3_ENDPOINT: z.string().url(),
  S3_REGION: z.string().default("us-east-1"),
  S3_ACCESS_KEY_ID: z.string().min(1),
  S3_SECRET_ACCESS_KEY: z.string().min(1),
  S3_BUCKET: z.string().min(1),
  S3_FORCE_PATH_STYLE: z
    .string()
    .optional()
    .transform((v) => v !== "false"),
  SESSION_SECRET: z.string().min(16),
  NEXTAUTH_URL: z.string().url().default("http://localhost:3000"),
  ANTHROPIC_API_KEY: z.string().optional().default(""),
  ANTHROPIC_MODEL: z.string().default("claude-sonnet-4-6"),
  MAIL_FROM: z.string().email().default("procurement@example.test"),
  MAIL_TRANSPORT: z.enum(["console", "resend", "smtp"]).default("console"),
  MAIL_REPLY_TO: z.string().email().optional(),
  RESEND_API_KEY: z.string().optional().default(""),
  SMTP_HOST: z.string().optional(),
  SMTP_PORT: z
    .string()
    .optional()
    .transform((v) => (v ? parseInt(v, 10) : 587)),
  SMTP_USER: z.string().optional(),
  SMTP_PASS: z.string().optional(),
});

export type Env = z.infer<typeof baseSchema>;

let cached: Env | null = null;

export function loadEnv(source: NodeJS.ProcessEnv = process.env): Env {
  if (cached) return cached;
  const parsed = baseSchema.safeParse(source);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `  ${i.path.join(".")}: ${i.message}`)
      .join("\n");
    throw new Error(`Invalid environment:\n${issues}`);
  }
  cached = parsed.data;
  return cached;
}

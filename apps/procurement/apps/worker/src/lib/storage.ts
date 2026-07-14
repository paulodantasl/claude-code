import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { loadEnv } from "@procurement/shared/env";

const env = loadEnv();

export const s3 = new S3Client({
  region: env.S3_REGION,
  endpoint: env.S3_ENDPOINT,
  forcePathStyle: env.S3_FORCE_PATH_STYLE,
  credentials: {
    accessKeyId: env.S3_ACCESS_KEY_ID,
    secretAccessKey: env.S3_SECRET_ACCESS_KEY,
  },
});
export const BUCKET = env.S3_BUCKET;

export async function getObjectBytes(storageKey: string): Promise<Buffer> {
  const out = await s3.send(new GetObjectCommand({ Bucket: BUCKET, Key: storageKey }));
  if (!out.Body) throw new Error("object body missing");
  const chunks: Buffer[] = [];
  // @ts-expect-error - Node Readable iterator
  for await (const chunk of out.Body) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks);
}

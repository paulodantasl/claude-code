import {
  S3Client,
  PutObjectCommand,
  GetObjectCommand,
  HeadObjectCommand,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { env } from "./env";

const client = new S3Client({
  region: env.S3_REGION,
  endpoint: env.S3_ENDPOINT,
  forcePathStyle: env.S3_FORCE_PATH_STYLE,
  credentials: {
    accessKeyId: env.S3_ACCESS_KEY_ID,
    secretAccessKey: env.S3_SECRET_ACCESS_KEY,
  },
});

const BUCKET = env.S3_BUCKET;

const UPLOAD_URL_TTL = 60 * 15; // 15 min
const DOWNLOAD_URL_TTL = 60 * 60; // 1 hour

export async function createUploadUrl(opts: {
  storageKey: string;
  contentType: string;
}): Promise<{ url: string; expiresIn: number }> {
  const cmd = new PutObjectCommand({
    Bucket: BUCKET,
    Key: opts.storageKey,
    ContentType: opts.contentType,
  });
  const url = await getSignedUrl(client, cmd, { expiresIn: UPLOAD_URL_TTL });
  return { url, expiresIn: UPLOAD_URL_TTL };
}

export async function createDownloadUrl(storageKey: string): Promise<string> {
  const cmd = new GetObjectCommand({ Bucket: BUCKET, Key: storageKey });
  return getSignedUrl(client, cmd, { expiresIn: DOWNLOAD_URL_TTL });
}

export async function headObject(storageKey: string) {
  return client.send(new HeadObjectCommand({ Bucket: BUCKET, Key: storageKey }));
}

export async function getObjectBytes(storageKey: string): Promise<Buffer> {
  const out = await client.send(new GetObjectCommand({ Bucket: BUCKET, Key: storageKey }));
  if (!out.Body) throw new Error("object body missing");
  const chunks: Buffer[] = [];
  // @ts-expect-error - the SDK returns a Node Readable here in our runtime
  for await (const chunk of out.Body) {
    chunks.push(Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

export { client as s3Client, BUCKET };

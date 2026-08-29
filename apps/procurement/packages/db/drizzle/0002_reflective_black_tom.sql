CREATE TYPE "public"."rfq_send_status" AS ENUM('pending', 'sent', 'failed');--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "rfq_sends" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"version_id" uuid NOT NULL,
	"vendor_id" uuid,
	"to_email" varchar(320) NOT NULL,
	"from_email" varchar(320) NOT NULL,
	"subject" text NOT NULL,
	"status" "rfq_send_status" DEFAULT 'pending' NOT NULL,
	"provider_message_id" text,
	"error" text,
	"sent_at" timestamp with time zone,
	"sent_by" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "rfq_sends" ADD CONSTRAINT "rfq_sends_version_id_rfq_draft_versions_id_fk" FOREIGN KEY ("version_id") REFERENCES "public"."rfq_draft_versions"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "rfq_sends" ADD CONSTRAINT "rfq_sends_vendor_id_vendors_id_fk" FOREIGN KEY ("vendor_id") REFERENCES "public"."vendors"("id") ON DELETE set null ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "rfq_sends" ADD CONSTRAINT "rfq_sends_sent_by_users_id_fk" FOREIGN KEY ("sent_by") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "rfq_sends_version_idx" ON "rfq_sends" USING btree ("version_id");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "rfq_sends_vendor_idx" ON "rfq_sends" USING btree ("vendor_id");
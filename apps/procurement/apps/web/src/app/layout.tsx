import type { Metadata } from "next";
import { TrpcProvider } from "@/lib/trpc";
import "./globals.css";

export const metadata: Metadata = {
  title: "Construction Procurement",
  description: "RFQs, bids, compliance — grounded in your project documents.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <TrpcProvider>{children}</TrpcProvider>
      </body>
    </html>
  );
}

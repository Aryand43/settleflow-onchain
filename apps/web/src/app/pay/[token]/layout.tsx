import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pay invoice",
  robots: { index: false, follow: false },
};

export default function PayLayout({ children }: { children: React.ReactNode }) {
  return <div className="payer-theme min-h-screen bg-canvas text-content">{children}</div>;
}

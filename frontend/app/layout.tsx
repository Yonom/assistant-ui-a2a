import type { Metadata } from "next";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

export const metadata: Metadata = {
  title: "assistant-ui with A2A",
  description:
    "An example of using assistant-ui with the A2A protocol via assistant-transport",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <TooltipProvider>
          <div className="flex h-screen flex-col">
            <header className="border-b bg-background px-4 py-2">
              <h1 className="font-semibold text-lg">A2A Example</h1>
            </header>
            <main className="flex-1 overflow-hidden">{children}</main>
          </div>
        </TooltipProvider>
      </body>
    </html>
  );
}

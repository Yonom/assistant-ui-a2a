"use client";

import { useState } from "react";
import { Thread } from "@/components/assistant-ui/thread";
import { useAui, AuiProvider, Suggestions } from "@assistant-ui/react";
import { MyRuntimeProvider } from "./MyRuntimeProvider";
import { A2AAgentTool } from "./A2AAgentTool";

function ThreadWithSuggestions() {
  const aui = useAui({
    suggestions: Suggestions([
      {
        title: "Say hello",
        label: "and introduce yourself",
        prompt: "Hello! Who are you?",
      },
      {
        title: "Tell me about",
        label: "the A2A protocol",
        prompt: "What is the A2A (Agent-to-Agent) protocol?",
      },
    ]),
  });
  return (
    <AuiProvider value={aui}>
      <A2AAgentTool />
      <Thread />
    </AuiProvider>
  );
}

export default function Home() {
  const [a2aServerUrl, setA2aServerUrl] = useState("http://localhost:9999");

  return (
    <MyRuntimeProvider a2aServerUrl={a2aServerUrl}>
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-2 border-b px-4 py-2">
          <label htmlFor="a2a-url" className="text-muted-foreground text-sm">
            A2A Server:
          </label>
          <input
            id="a2a-url"
            type="text"
            value={a2aServerUrl}
            onChange={(e) => setA2aServerUrl(e.target.value)}
            className="flex-1 rounded-md border bg-background px-3 py-1 text-sm"
            placeholder="http://localhost:9999"
          />
        </div>
        <div className="flex-1 overflow-hidden">
          <ThreadWithSuggestions />
        </div>
      </div>
    </MyRuntimeProvider>
  );
}

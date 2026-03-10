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
        title: "Chat",
        label: "streaming response",
        prompt: "Explain the A2A protocol in 3 sentences",
      },
      {
        title: "Artifacts",
        label: "code + data + file",
        prompt: "/artifacts a fibonacci function in Python",
      },
      {
        title: "Multi-step",
        label: "input-required state",
        prompt: "/multistep",
      },
      {
        title: "Failure",
        label: "error handling",
        prompt: "/fail",
      },
      {
        title: "Slow task",
        label: "cancellable",
        prompt: "/slow",
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

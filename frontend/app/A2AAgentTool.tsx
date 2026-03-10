"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";

type A2AAgentArgs = {
  query: string;
  serverUrl: string;
  status: "connecting" | "working" | "complete";
  agentName: string;
  response: string;
};

export const A2AAgentTool = makeAssistantToolUI<A2AAgentArgs, string>({
  toolName: "a2a_agent",
  render: function A2AAgentUI({ args, status }) {
    const isRunning = status.type === "running";
    const agentStatus = args.status ?? "connecting";

    return (
      <div className="my-2 overflow-hidden rounded-lg border">
        <div className="flex items-center gap-2 border-b bg-muted/50 px-3 py-2">
          {isRunning ? (
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
            </span>
          ) : (
            <span className="inline-flex h-2 w-2 rounded-full bg-green-500" />
          )}
          <span className="text-sm font-medium">
            {args.agentName || "A2A Agent"}
          </span>
          <span className="text-muted-foreground ml-auto text-xs">
            {agentStatus === "connecting" && "Connecting..."}
            {agentStatus === "working" && "Working..."}
            {agentStatus === "complete" && "Complete"}
          </span>
        </div>

        <div className="p-3">
          <p className="text-muted-foreground mb-2 text-xs">
            {args.serverUrl}
          </p>

          {args.response ? (
            <div className="whitespace-pre-wrap text-sm">{args.response}</div>
          ) : (
            isRunning && (
              <div className="text-muted-foreground text-sm italic">
                Waiting for response...
              </div>
            )
          )}
        </div>
      </div>
    );
  },
});

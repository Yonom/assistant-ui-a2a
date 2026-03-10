"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";

type AgentCardInfo = {
  name: string;
  description: string;
  version: string;
  url: string;
  skills: Array<{
    id: string;
    name: string;
    description: string;
    tags: string[];
    examples: string[];
  }>;
  streaming: boolean;
  provider: { organization: string; url: string } | null;
};

type ArtifactPart =
  | { kind: "text"; text: string }
  | { kind: "data"; data: Record<string, unknown> }
  | {
      kind: "file";
      name: string;
      mimeType: string;
      hasBytes: boolean;
      uri?: string;
    };

type ArtifactInfo = {
  artifactId: string;
  name: string;
  description?: string;
  parts: ArtifactPart[];
};

type A2AAgentArgs = {
  query: string;
  serverUrl: string;
  taskState: string;
  agentCard: AgentCardInfo | null;
  statusText: string;
  artifacts: ArtifactInfo[];
  error: string | null;
};

const STATE_CONFIG: Record<
  string,
  { label: string; color: string; bg: string }
> = {
  connecting: {
    label: "Connecting",
    color: "text-blue-600",
    bg: "bg-blue-100 dark:bg-blue-900/30",
  },
  submitted: {
    label: "Submitted",
    color: "text-blue-600",
    bg: "bg-blue-100 dark:bg-blue-900/30",
  },
  working: {
    label: "Working",
    color: "text-amber-600",
    bg: "bg-amber-100 dark:bg-amber-900/30",
  },
  "input-required": {
    label: "Input Required",
    color: "text-purple-600",
    bg: "bg-purple-100 dark:bg-purple-900/30",
  },
  completed: {
    label: "Completed",
    color: "text-green-600",
    bg: "bg-green-100 dark:bg-green-900/30",
  },
  failed: {
    label: "Failed",
    color: "text-red-600",
    bg: "bg-red-100 dark:bg-red-900/30",
  },
  canceled: {
    label: "Canceled",
    color: "text-gray-600",
    bg: "bg-gray-100 dark:bg-gray-900/30",
  },
  rejected: {
    label: "Rejected",
    color: "text-red-600",
    bg: "bg-red-100 dark:bg-red-900/30",
  },
};

function StateBadge({ state }: { state: string }) {
  const config = STATE_CONFIG[state] ?? {
    label: state,
    color: "text-gray-600",
    bg: "bg-gray-100",
  };
  const isActive =
    state === "working" || state === "connecting" || state === "submitted";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${config.color} ${config.bg}`}
    >
      {isActive ? (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
        </span>
      ) : (
        <span className="inline-flex h-1.5 w-1.5 rounded-full bg-current" />
      )}
      {config.label}
    </span>
  );
}

function ArtifactCard({ artifact }: { artifact: ArtifactInfo }) {
  return (
    <div className="overflow-hidden rounded-md border bg-muted/30">
      <div className="flex items-center gap-2 border-b bg-muted/50 px-3 py-1.5">
        <span className="text-xs font-medium">{artifact.name}</span>
        {artifact.description && (
          <span className="text-muted-foreground text-xs">
            {artifact.description}
          </span>
        )}
      </div>
      <div className="space-y-2 p-3">
        {artifact.parts.map((part, i) => (
          <ArtifactPartView key={i} part={part} />
        ))}
      </div>
    </div>
  );
}

function ArtifactPartView({ part }: { part: ArtifactPart }) {
  if (part.kind === "text") {
    return (
      <pre className="overflow-x-auto whitespace-pre-wrap rounded border bg-background p-2 font-mono text-xs">
        {part.text}
      </pre>
    );
  }
  if (part.kind === "data") {
    return (
      <div className="rounded border bg-background p-2">
        <div className="text-muted-foreground mb-1 text-xs font-medium">
          Data
        </div>
        <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs">
          {JSON.stringify(part.data, null, 2)}
        </pre>
      </div>
    );
  }
  if (part.kind === "file") {
    return (
      <div className="flex items-center gap-2 rounded border bg-background p-2">
        <svg
          className="text-muted-foreground h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
          />
        </svg>
        <span className="text-xs font-medium">{part.name}</span>
        {part.mimeType && (
          <span className="text-muted-foreground text-xs">{part.mimeType}</span>
        )}
      </div>
    );
  }
  return null;
}

function AgentCardView({ card }: { card: AgentCardInfo }) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {card.skills.map((skill) => (
          <span
            key={skill.id}
            className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs"
            title={skill.description}
          >
            {skill.name}
          </span>
        ))}
      </div>
      <div className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <span>v{card.version}</span>
        {card.streaming && <span>Streaming</span>}
        {card.provider && <span>{card.provider.organization}</span>}
      </div>
    </div>
  );
}

export const A2AAgentTool = makeAssistantToolUI<A2AAgentArgs, string>({
  toolName: "a2a_agent",
  render: function A2AAgentUI({ args, status }) {
    const isRunning = status.type === "running";
    const taskState = args.taskState ?? "connecting";
    const hasError =
      taskState === "failed" ||
      taskState === "canceled" ||
      taskState === "rejected";

    return (
      <div className="my-2 overflow-hidden rounded-lg border">
        {/* Header */}
        <div className="flex items-center gap-2 border-b bg-muted/50 px-3 py-2">
          <span className="text-sm font-medium">
            {args.agentCard?.name ?? "A2A Agent"}
          </span>
          <div className="ml-auto">
            <StateBadge state={taskState} />
          </div>
        </div>

        <div className="space-y-3 p-3">
          {/* Agent Card info */}
          {args.agentCard && <AgentCardView card={args.agentCard} />}

          {/* Error display */}
          {hasError && args.error && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950/30">
              <p className="text-sm text-red-700 dark:text-red-300">
                {args.error}
              </p>
            </div>
          )}

          {/* Status text / streaming response */}
          {args.statusText && !hasError && (
            <div className="whitespace-pre-wrap text-sm">{args.statusText}</div>
          )}

          {/* Waiting state */}
          {!args.statusText && !hasError && isRunning && (
            <div className="text-muted-foreground text-sm italic">
              Waiting for response...
            </div>
          )}

          {/* Artifacts */}
          {args.artifacts.length > 0 && (
            <div className="space-y-2">
              <div className="text-muted-foreground text-xs font-medium">
                Artifacts ({args.artifacts.length})
              </div>
              {args.artifacts.map((artifact) => (
                <ArtifactCard key={artifact.artifactId} artifact={artifact} />
              ))}
            </div>
          )}
        </div>
      </div>
    );
  },
});

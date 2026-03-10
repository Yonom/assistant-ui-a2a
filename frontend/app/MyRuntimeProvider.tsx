"use client";

import {
  AssistantRuntimeProvider,
  AssistantTransportConnectionMetadata,
  unstable_createMessageConverter as createMessageConverter,
  useAssistantTransportRuntime,
} from "@assistant-ui/react";
import {
  convertLangChainMessages,
  LangChainMessage,
} from "@assistant-ui/react-langgraph";
import { ReactNode, useRef } from "react";

type MyRuntimeProviderProps = {
  children: ReactNode;
  a2aServerUrl: string;
};

type State = {
  messages: LangChainMessage[];
};

const LangChainMessageConverter = createMessageConverter(
  convertLangChainMessages,
);

const converter = (
  state: State,
  connectionMetadata: AssistantTransportConnectionMetadata,
) => {
  const optimisticStateMessages = connectionMetadata.pendingCommands.map(
    (c): LangChainMessage[] => {
      if (c.type === "add-message") {
        return [
          {
            type: "human" as const,
            content: [
              {
                type: "text" as const,
                text: c.message.parts
                  .map((p) => (p.type === "text" ? p.text : ""))
                  .join("\n"),
              },
            ],
          },
        ];
      }
      return [];
    },
  );

  const messages = [...state.messages, ...optimisticStateMessages.flat()];
  return {
    messages: LangChainMessageConverter.toThreadMessages(messages),
    isRunning: connectionMetadata.isSending || false,
  };
};

export function MyRuntimeProvider({
  children,
  a2aServerUrl,
}: MyRuntimeProviderProps) {
  const a2aServerUrlRef = useRef(a2aServerUrl);
  a2aServerUrlRef.current = a2aServerUrl;

  const runtime = useAssistantTransportRuntime({
    initialState: {
      messages: [],
    },
    api:
      process.env["NEXT_PUBLIC_API_URL"] || "http://localhost:8000/assistant",
    converter,
    headers: {},
    body: () => ({
      a2aServerUrl: a2aServerUrlRef.current,
    }),
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}

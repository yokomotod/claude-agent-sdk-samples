import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type UserMessage = { type: "UserMessage"; content: string };
type AssistantMessage = {
  type: "AssistantMessage";
  content: {
    type: string;
    text?: string;
  }[];
};
type Message = UserMessage | AssistantMessage;

function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    console.log("[WebSocket] Attempting to connect...");
    const ws = new WebSocket("ws://localhost:8000/ws");
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WebSocket] Connected successfully!");
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("[WebSocket] Received:", data);

      if (data.type === "AssistantMessage") {
        setMessages((prev) => [...prev, data]);
      }

      if (data.type === "ResultMessage") {
        setIsLoading(false);
      }
    };

    ws.onclose = (event) => {
      console.log("[WebSocket] Disconnected", event.code, event.reason);
      setIsConnected(false);
    };

    ws.onerror = (error) => {
      console.error("[WebSocket] Error:", error);
      console.error("[WebSocket] Error details:", {
        url: ws.url,
        readyState: ws.readyState,
        protocol: ws.protocol,
      });
    };

    return () => {
      ws.close();
    };
  }, []);

  const sendMessage = async () => {
    console.log("[sendMessage] isConnected:", isConnected, "wsRef.current:", wsRef.current);
    if (!wsRef.current || !isConnected) {
      console.error("[WebSocket] Not connected");
      return;
    }

    setIsLoading(true);

    const userMessage: Message = { type: "UserMessage", content: input };
    setMessages((prev) => [...prev, userMessage]);
    const currentInput = input;
    setInput("");

    wsRef.current.send(
      JSON.stringify({
        prompt: currentInput,
      })
    );
  };

  return { messages, input, setInput, isLoading, isConnected, sendMessage };
}

function AgentMessageItem({ message }: { message: AssistantMessage }) {
  return (
    <div
      className={`p-3 rounded-lg text-sm bg-cyan-50 text-cyan-800 border-l-4 border-cyan-400`}
    >
      {message.content
        .filter(({ type }) => type === "TextBlock")
        .map((block, blockIdx) => (
          <div key={blockIdx} className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {block.text}
            </ReactMarkdown>
          </div>
        ))}
    </div>
  );
}

function App() {
  const { messages, input, setInput, isLoading, isConnected, sendMessage } =
    useChat();

  return (
    <div className="h-[100dvh] bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 flex-shrink-0">
        <div className="px-4 py-3 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">Claude Code Web</h1>
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className="text-sm text-gray-600">
              {isConnected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.map((msg, idx) =>
          msg.type === "UserMessage" ? (
            <div
              key={idx}
              className="p-3 rounded-lg whitespace-pre-wrap text-sm bg-gray-100 text-gray-800 ml-12 border-l-4 border-gray-400"
            >
              {msg.content}
            </div>
          ) : (
            <AgentMessageItem key={idx} message={msg} />
          ),
        )}
      </div>

      <div className="border-t border-gray-200 bg-white p-3 flex-shrink-0">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
            rows={1}
            className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 resize-none field-sizing-content"
            placeholder="prompt..."
          />
          <button
            onClick={sendMessage}
            disabled={!isConnected || isLoading || !input.trim()}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            {isLoading ? "Loading..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;

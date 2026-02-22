"use client";

import { useState, useEffect, useRef } from "react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function ChatPage() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = input.trim();
    setInput("");
    setIsLoading(true);
    setError(null);

    // Add user message
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

    try {
      const response = await axios.post(`${API_URL}/chat`, {
        message: userMessage,
        model: "mistral",
      });

      const aiResponse = response.data.response;
      setMessages((prev) => [...prev, { role: "assistant", content: aiResponse }]);
    } catch (err) {
      console.error("Error:", err);
      setError("Failed to get response. Please check your connection.");
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "I'm having trouble connecting to the AI service. Please try again later." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-indigo-900">Garje Marathi AI</h1>
            <p className="text-sm text-gray-600">Community Assistant</p>
          </div>
          <button
            onClick={handleClear}
            className="text-sm text-gray-600 hover:text-indigo-600 px-3 py-1 rounded hover:bg-gray-100 transition"
          >
            Clear Chat
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-6 flex flex-col">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-2xl font-bold text-indigo-600">4188</div>
            <div className="text-sm text-gray-600">Members</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-2xl font-bold text-green-600">35</div>
            <div className="text-sm text-gray-600">Jobs</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-2xl font-bold text-blue-600">2478</div>
            <div className="text-sm text-gray-600">Profiles</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-2xl font-bold text-purple-600">1242</div>
            <div className="text-sm text-gray-600">With Experience</div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden flex flex-col min-h-[400px]">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="text-center text-gray-500 mt-20">
                <p className="text-lg">Ask me anything about the community!</p>
                <p className="text-sm mt-2">Try: "Find member Anand" or "How many members?"</p>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-4 py-3 ${
                    msg.role === "user"
                      ? "bg-indigo-600 text-white"
                      : "bg-gray-100 text-gray-800"
                  }`}
                >
                  <div className="prose prose-sm max-w-none">
                    {msg.content.split("\n").map((line, i) => (
                      <p key={i} className="mb-1 last:mb-0">
                        {line}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-lg px-4 py-3">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="flex justify-center">
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                  {error}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-gray-200 bg-gray-50">
            <form onSubmit={handleSubmit} className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about members, jobs, or the community..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                Send
              </button>
            </form>
            <p className="text-xs text-gray-500 mt-2 text-center">
              Powered by local Ollama • Hosted on Vercel
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}

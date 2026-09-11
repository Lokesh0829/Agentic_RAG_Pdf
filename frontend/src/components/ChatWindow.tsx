// components/ChatWindow.tsx — Message history with streaming display and text-to-speech
import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Message, Citation } from '../api/client';

interface StreamingMessage {
  role: 'assistant';
  content: string;
  status?: string;
  isStreaming: boolean;
}

interface ChatWindowProps {
  messages: Message[];
  streamingMsg: StreamingMessage | null;
  conversationTitle?: string;
  docFilename?: string;
}

function CitationChip({ cite }: { cite: Citation }) {
  return (
    <span className="citation-chip" title={cite.snippet}>
      📄 Page {cite.page}
    </span>
  );
}

function ReasoningSteps({ steps }: { steps: string[] }) {
  const [open, setOpen] = useState(false);
  if (!steps || steps.length === 0) return null;

  return (
    <div>
      <button className="reasoning-toggle" onClick={() => setOpen(!open)}>
        {open ? '▾' : '▸'} Reasoning steps ({steps.length})
      </button>
      {open && (
        <div className="reasoning-steps">
          {steps.map((s, i) => (
            <div key={i} className="reasoning-step">{s}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function SpeechButton({ text }: { text: string }) {
  const [speaking, setSpeaking] = useState(false);

  const toggleSpeech = () => {
    if (!('speechSynthesis' in window)) {
      alert('Text-to-speech is not supported in your browser.');
      return;
    }

    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    window.speechSynthesis.cancel();
    // Clean markdown characters before reading out loud
    const cleanText = text.replace(/[*#`_]/g, '');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  return (
    <button
      className="btn btn-ghost btn-sm"
      onClick={toggleSpeech}
      title={speaking ? 'Stop speaking' : 'Read answer out loud'}
      style={{
        marginTop: '8px',
        padding: '2px 8px',
        fontSize: '12px',
        color: speaking ? '#ef4444' : 'var(--text-muted)',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
      }}
    >
      {speaking ? '🔇 Stop' : '🔊 Listen'}
    </button>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  return (
    <button
      className="btn btn-ghost btn-sm"
      onClick={handleCopy}
      title="Copy to clipboard"
      style={{
        marginTop: '8px',
        padding: '2px 8px',
        fontSize: '12px',
        color: copied ? '#10b981' : 'var(--text-muted)',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
      }}
    >
      {copied ? '✓ Copied' : '📋 Copy'}
    </button>
  );
}

function AssistantBubble({ msg }: { msg: Message }) {
  return (
    <div className="message-row assistant">
      <div className="message-avatar">🤖</div>
      <div>
        <div className="message-bubble">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {msg.content}
          </ReactMarkdown>

          {msg.from_cache && (
            <div className="cache-badge">⚡ Semantic cache hit</div>
          )}

          {msg.citations && msg.citations.length > 0 && (
            <div className="message-citations">
              {msg.citations.map((c, i) => (
                <CitationChip key={i} cite={c} />
              ))}
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', marginTop: '6px' }}>
            <ReasoningSteps steps={msg.reasoning_steps} />
            <div style={{ display: 'flex', gap: '6px' }}>
              <SpeechButton text={msg.content} />
              <CopyButton text={msg.content} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StreamingBubble({ msg }: { msg: StreamingMessage }) {
  return (
    <div className="message-row assistant">
      <div className="message-avatar">🤖</div>
      <div>
        {msg.status && !msg.content && (
          <div className="status-message">
            <span className="spinner" />
            {msg.status}
          </div>
        )}
        {msg.content && (
          <div className="message-bubble">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {msg.content}
            </ReactMarkdown>
            {msg.isStreaming && <span className="streaming-cursor" />}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatWindow({
  messages,
  streamingMsg,
  conversationTitle,
  docFilename,
}: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, streamingMsg?.content]);

  if (messages.length === 0 && !streamingMsg) {
    return (
      <div className="messages-container">
        <div className="empty-chat">
          <div className="empty-chat-icon">💬</div>
          <h3>Start a conversation</h3>
          <p>
            {docFilename
              ? `Ask anything about "${docFilename}"`
              : 'Upload a PDF above or choose a document to start chatting'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="messages-container" id="chat-messages">
      {messages.map((msg) =>
        msg.role === 'user' ? (
          <div key={msg.id} className="message-row user">
            <div className="message-avatar">👤</div>
            <div className="message-bubble">{msg.content}</div>
          </div>
        ) : (
          <AssistantBubble key={msg.id} msg={msg} />
        )
      )}

      {streamingMsg && <StreamingBubble msg={streamingMsg} />}
      <div ref={bottomRef} />
    </div>
  );
}

// components/MessageInput.tsx — Message input with quick actions, speech recognition, and stop generation
import { useState, useRef, KeyboardEvent } from 'react';

const QUICK_ACTIONS = [
  { icon: '📊', label: 'Summarize tables', prompt: 'Summarize all tables and key data in this document' },
  { icon: '🖼️', label: 'Describe figures', prompt: 'Describe the figures and charts in this document' },
  { icon: '📋', label: 'Key findings', prompt: 'What are the key findings and conclusions in this document?' },
  { icon: '🔍', label: 'Main topics', prompt: 'What are the main topics covered in this document?' },
];

interface MessageInputProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  docReady?: boolean;
}

export default function MessageInput({ onSend, onStop, disabled, docReady }: MessageInputProps) {
  const [value, setValue] = useState('');
  const [isListening, setIsListening] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);

  const handleSend = () => {
    const msg = value.trim();
    if (!msg || disabled) return;
    onSend(msg);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  };

  const handleQuickAction = (prompt: string) => {
    setValue(prompt);
    textareaRef.current?.focus();
  };

  const toggleSpeechRecognition = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in your browser. Please use Chrome or Edge.');
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => setIsListening(true);
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setValue((prev) => (prev ? `${prev} ${transcript}` : transcript));
      setIsListening(false);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);

    recognitionRef.current = recognition;
    recognition.start();
  };

  return (
    <div className="input-area">
      <div className="quick-actions">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            className="quick-action-btn"
            onClick={() => handleQuickAction(action.prompt)}
            disabled={disabled || !docReady}
            title={action.prompt}
          >
            {action.icon} {action.label}
          </button>
        ))}
      </div>

      <div className="input-row">
        <button
          type="button"
          className={`btn btn-ghost ${isListening ? 'listening-active' : ''}`}
          onClick={toggleSpeechRecognition}
          disabled={disabled || !docReady}
          title={isListening ? 'Stop listening' : 'Speak your question (Voice Input)'}
          style={{
            padding: '12px',
            fontSize: '18px',
            borderRadius: '12px',
            background: isListening ? 'rgba(239, 68, 68, 0.2)' : 'var(--bg-input)',
            border: isListening ? '1px solid #ef4444' : '1px solid var(--border-subtle)',
            color: isListening ? '#ef4444' : 'var(--text-primary)',
          }}
        >
          {isListening ? '🔴' : '🎤'}
        </button>

        <textarea
          ref={textareaRef}
          id="message-input"
          className="message-textarea"
          placeholder={
            !docReady
              ? 'Upload and wait for PDF to finish processing...'
              : isListening
              ? 'Listening to your voice...'
              : 'Ask anything about your PDF... (Enter to send, Shift+Enter for new line)'
          }
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          disabled={disabled || !docReady}
          rows={1}
        />

        {disabled ? (
          <button
            type="button"
            className="send-btn"
            onClick={onStop}
            title="Stop generating message"
            style={{ background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)', width: 'auto', padding: '0 16px', gap: '6px' }}
          >
            ⏹ Stop
          </button>
        ) : (
          <button
            id="send-btn"
            className="send-btn"
            onClick={handleSend}
            disabled={!docReady || !value.trim()}
            title="Send message"
          >
            ➤
          </button>
        )}
      </div>

      <div className="input-hint">
        {disabled
          ? 'Agents generating... Click ⏹ Stop to cancel anytime'
          : docReady
          ? 'Multi-agent RAG · Voice input & Speech synthesis enabled'
          : 'Upload a PDF to start chatting'}
      </div>
    </div>
  );
}

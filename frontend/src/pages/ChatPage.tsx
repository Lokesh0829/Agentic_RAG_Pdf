// pages/ChatPage.tsx — Main chat interface with all components assembled
import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Conversation, Message, PdfStatus,
  conversationApi, pdfApi,
  streamMessage, StreamEvent, Citation,
} from '../api/client';
import Sidebar from '../components/Sidebar';
import ChatWindow from '../components/ChatWindow';
import PDFUpload from '../components/PDFUpload';
import MessageInput from '../components/MessageInput';
import '../styles/chat.css';

interface StreamingMsg {
  role: 'assistant';
  content: string;
  status?: string;
  isStreaming: boolean;
}

interface NewConvModalProps {
  onClose: () => void;
  onCreate: (title: string) => void;
}

function NewConvModal({ onClose, onCreate }: NewConvModalProps) {
  const [title, setTitle] = useState('');

  const handleCreate = () => {
    if (!title.trim()) return;
    onCreate(title.trim());
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-title">New Conversation</div>
        <div className="modal-subtitle">Give this conversation a name to get started</div>

        <div className="form-group">
          <label className="form-label">Conversation Title</label>
          <input
            id="new-conv-title"
            className="input"
            placeholder="e.g. Q&A about Research Paper"
            value={title}
            onChange={e => setTitle(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
            autoFocus
          />
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            id="create-conv-btn"
            className="btn btn-primary"
            onClick={handleCreate}
            disabled={!title.trim()}
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  const navigate = useNavigate();
  const userRaw = localStorage.getItem('user');
  const user = userRaw ? JSON.parse(userRaw) : null;

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingMsg, setStreamingMsg] = useState<StreamingMsg | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);
  const [docs, setDocs] = useState<PdfStatus[]>([]);
  const [activeDoc, setActiveDoc] = useState<PdfStatus | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Redirect if not logged in
  useEffect(() => {
    if (!localStorage.getItem('token')) navigate('/');
  }, []);

  // Load conversations and docs
  useEffect(() => {
    loadConversations();
    loadDocs();
  }, []);

  const loadConversations = async () => {
    try {
      const result = await conversationApi.list();
      setConversations(result.conversations);
    } catch { navigate('/'); }
  };

  const loadDocs = async () => {
    try {
      const result = await pdfApi.list();
      setDocs(result.documents as PdfStatus[]);
    } catch {}
  };

  const selectConversation = async (conv: Conversation) => {
    setActiveConv(conv);
    setMessages([]);
    setStreamingMsg(null);

    // Load messages
    try {
      const result = await conversationApi.getMessages(conv.id);
      setMessages(result.messages);
    } catch {}

    // Load doc info
    if (conv.doc_id) {
      try {
        const docStatus = await pdfApi.getStatus(conv.doc_id);
        setActiveDoc(docStatus);
      } catch {}
    } else {
      setActiveDoc(null);
    }
  };

  const handleDocReady = async (doc: PdfStatus) => {
    setActiveDoc(doc);
    setDocs(prev => {
      const exists = prev.find(d => d.doc_id === doc.doc_id);
      if (exists) return prev.map(d => d.doc_id === doc.doc_id ? doc : d);
      return [doc, ...prev];
    });

    if (activeConv && activeConv.doc_id !== doc.doc_id) {
      try {
        const updatedConv = await conversationApi.update(activeConv.id, doc.doc_id);
        setActiveConv(updatedConv);
        setConversations(prev =>
          prev.map(c => (c.id === updatedConv.id ? updatedConv : c))
        );
      } catch (err) {
        console.error('Failed to update conversation with document association:', err);
      }
    }
  };

  const createConversation = async (title: string) => {
    setShowNewModal(false);
    try {
      const conv = await conversationApi.create(title);
      setConversations(prev => [conv, ...prev]);
      await selectConversation(conv);
    } catch (e: any) {
      console.error('Create conv failed', e);
    }
  };

  const deleteConversation = (id: string) => {
    setConversations(prev => prev.filter(c => c.id !== id));
    if (activeConv?.id === id) {
      setActiveConv(null);
      setMessages([]);
      setActiveDoc(null);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/');
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  };

  const handleSend = (content: string) => {
    if (!activeConv || !activeDoc || isStreaming) return;

    const userMsg: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      citations: [],
      from_cache: false,
      reasoning_steps: [],
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setIsStreaming(true);
    setStreamingMsg({ role: 'assistant', content: '', status: 'Analyzing your question...', isStreaming: true });

    let fullContent = '';
    let finalCitations: Citation[] = [];
    let finalReasoningSteps: string[] = [];
    let fromCache = false;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    streamMessage(
      activeConv.id,
      activeDoc.doc_id,
      content,
      (event: StreamEvent) => {
        if (event.type === 'token') {
          fullContent += event.content || '';
          setStreamingMsg({ role: 'assistant', content: fullContent, isStreaming: true });
        } else if (event.type === 'status') {
          setStreamingMsg(prev => prev ? { ...prev, status: event.content } : null);
        } else if (event.type === 'done') {
          finalCitations = event.citations || [];
          finalReasoningSteps = event.reasoning_steps || [];
          fromCache = event.from_cache || false;
        }
      },
      () => {
        // On done
        abortControllerRef.current = null;
        const assistantMsg: Message = {
          id: `done-${Date.now()}`,
          role: 'assistant',
          content: fullContent || 'Response stopped.',
          citations: finalCitations,
          from_cache: fromCache,
          reasoning_steps: finalReasoningSteps,
          created_at: new Date().toISOString(),
        };
        setMessages(prev => [...prev, assistantMsg]);
        setStreamingMsg(null);
        setIsStreaming(false);
        loadConversations();
      },
      (err: string) => {
        abortControllerRef.current = null;
        const errMsg: Message = {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: `❌ Error: ${err}`,
          citations: [],
          from_cache: false,
          reasoning_steps: [],
          created_at: new Date().toISOString(),
        };
        setMessages(prev => [...prev, errMsg]);
        setStreamingMsg(null);
        setIsStreaming(false);
      },
      controller.signal
    );
  };

  const docReady = activeDoc?.status === 'ready';

  return (
    <div className="chat-layout">
      <Sidebar
        user={user || { name: 'User', email: '' }}
        conversations={conversations}
        activeConvId={activeConv?.id || null}
        onSelect={selectConversation}
        onNew={() => setShowNewModal(true)}
        onDelete={deleteConversation}
        onLogout={handleLogout}
      />

      <main className="chat-main">
        {/* Header */}
        <div className="chat-header">
          <div className="chat-header-left">
            {activeConv ? (
              <>
                <div className="chat-title">{activeConv.title}</div>
                {activeDoc?.status === 'ready' && (
                  <span className="badge badge-green">● Ready</span>
                )}
                {activeDoc?.status === 'processing' && (
                  <span className="badge badge-amber">⚙ Processing</span>
                )}
              </>
            ) : (
              <div className="chat-title" style={{ color: 'var(--text-muted)' }}>
                Select or create a conversation
              </div>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {activeDoc?.status === 'ready' && (
              <span className="badge badge-purple">
                📄 {activeDoc.total_pages.toLocaleString()} pages
              </span>
            )}
            <span className="badge badge-cyan">🤖 Groq Llama-3.3</span>
          </div>
        </div>

        {/* PDF Upload panel — only when conversation is active */}
        {activeConv && (
          <PDFUpload
            onDocumentReady={handleDocReady}
            currentDocId={activeConv.doc_id || undefined}
          />
        )}

        {/* Chat Window */}
        {activeConv ? (
          <>
            <ChatWindow
              messages={messages}
              streamingMsg={streamingMsg}
              conversationTitle={activeConv.title}
              docFilename={activeDoc?.filename}
            />

            <MessageInput
              onSend={handleSend}
              onStop={handleStop}
              disabled={isStreaming}
              docReady={docReady}
            />
          </>
        ) : (
          <div className="empty-chat" style={{ flex: 1 }}>
            <div className="empty-chat-icon">🔮</div>
            <h3>AgenticRAG PDF Chatbot</h3>
            <p>Create a new conversation and upload a PDF to get started</p>
            <button
              className="btn btn-primary"
              onClick={() => setShowNewModal(true)}
              style={{ marginTop: 12 }}
            >
              + New Conversation
            </button>
          </div>
        )}
      </main>

      {showNewModal && (
        <NewConvModal
          onClose={() => setShowNewModal(false)}
          onCreate={createConversation}
        />
      )}
    </div>
  );
}

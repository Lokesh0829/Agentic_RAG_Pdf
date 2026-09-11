// components/Sidebar.tsx — Conversation list with create/delete actions
import { useState } from 'react';
import { Conversation, conversationApi, pdfApi, PdfDoc } from '../api/client';

interface SidebarProps {
  user: { name: string; email: string };
  conversations: Conversation[];
  activeConvId: string | null;
  onSelect: (conv: Conversation) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onLogout: () => void;
}

export default function Sidebar({
  user,
  conversations,
  activeConvId,
  onSelect,
  onNew,
  onDelete,
  onLogout,
}: SidebarProps) {
  const [deleting, setDeleting] = useState<string | null>(null);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;
    setDeleting(id);
    try {
      await conversationApi.delete(id);
      onDelete(id);
    } catch (err) {
      console.error('Delete failed', err);
    } finally {
      setDeleting(null);
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffDays === 0) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString();
  };

  const initials = user.name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">🔮</div>
          <span className="sidebar-logo-name">AgenticRAG</span>
        </div>
        <button
          id="new-conversation-btn"
          className="sidebar-new-btn"
          onClick={onNew}
        >
          + New Conversation
        </button>
      </div>

      {conversations.length > 0 && (
        <div className="sidebar-section-title">Conversations</div>
      )}

      <div className="sidebar-conversations">
        {conversations.length === 0 ? (
          <div style={{ padding: '20px 12px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
            No conversations yet.<br />Upload a PDF and start chatting!
          </div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              id={`conv-${conv.id}`}
              className={`conv-item ${activeConvId === conv.id ? 'active' : ''}`}
              onClick={() => onSelect(conv)}
            >
              <div className="conv-icon">
                {conv.doc_id ? '📄' : '💬'}
              </div>
              <div className="conv-info">
                <div className="conv-title" title={conv.title}>{conv.title}</div>
                <div className="conv-meta">
                  {conv.doc_filename
                    ? `${conv.doc_filename.slice(0, 20)}${conv.doc_filename.length > 20 ? '…' : ''}`
                    : formatDate(conv.updated_at)}
                  {conv.message_count > 0 && ` · ${conv.message_count / 2 | 0} msgs`}
                </div>
              </div>
              <button
                className="conv-delete-btn"
                onClick={(e) => handleDelete(e, conv.id)}
                title="Delete conversation"
                disabled={deleting === conv.id}
              >
                {deleting === conv.id ? '…' : '🗑'}
              </button>
            </div>
          ))
        )}
      </div>

      <div className="sidebar-user">
        <div className="sidebar-avatar">{initials}</div>
        <div className="sidebar-user-info">
          <div className="sidebar-user-name">{user.name}</div>
          <div className="sidebar-user-email">{user.email}</div>
        </div>
        <button
          id="logout-btn"
          className="sidebar-logout-btn"
          onClick={onLogout}
          title="Sign out"
        >
          ⏻
        </button>
      </div>
    </aside>
  );
}

// api/client.ts — Typed API client for the FastAPI backend

const BASE_URL = '';

function getToken(): string | null {
  return localStorage.getItem('token');
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...options.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ─── Auth ───────────────────────────────────────────────────────

export interface User {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export const authApi = {
  register: (name: string, email: string, password: string) =>
    request<AuthResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    }),

  login: (email: string, password: string) =>
    request<AuthResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<User>('/api/auth/me'),
};

// ─── PDF ─────────────────────────────────────────────────────────

export interface PdfDoc {
  doc_id: string;
  filename: string;
  status: 'queued' | 'processing' | 'ready' | 'error';
  progress: number;
  total_pages: number;
  file_size_bytes: number;
  created_at: string;
}

export interface PdfStatus extends PdfDoc {
  total_chunks: number;
  total_vectors: number;
  error_message?: string;
}

export const pdfApi = {
  upload: async (file: File): Promise<{ doc_id: string; filename: string; status: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${BASE_URL}/api/pdf/upload`, {
      method: 'POST',
      headers: authHeaders(),
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  getStatus: (docId: string) => request<PdfStatus>(`/api/pdf/status/${docId}`),

  list: () => request<{ documents: PdfDoc[] }>('/api/pdf/list'),

  delete: (docId: string) =>
    request<{ message: string }>(`/api/pdf/${docId}`, { method: 'DELETE' }),
};

// ─── Conversations ───────────────────────────────────────────────

export interface Conversation {
  id: string;
  title: string;
  doc_id?: string;
  doc_filename?: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
  from_cache: boolean;
  reasoning_steps: string[];
  created_at: string;
}

export interface Citation {
  page: number;
  filename: string;
  content_type: string;
  snippet: string;
}

export const conversationApi = {
  list: () => request<{ conversations: Conversation[] }>('/api/conversations'),

  create: (title: string, doc_id?: string) =>
    request<Conversation>('/api/conversations', {
      method: 'POST',
      body: JSON.stringify({ title, doc_id }),
    }),

  delete: (id: string) =>
    request<{ message: string }>(`/api/conversations/${id}`, { method: 'DELETE' }),

  update: (id: string, doc_id: string) =>
    request<Conversation>(`/api/conversations/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ doc_id }),
    }),

  getMessages: (id: string) =>
    request<{ messages: Message[] }>(`/api/conversations/${id}/messages`),
};

// ─── Chat Streaming ──────────────────────────────────────────────

export interface StreamEvent {
  type: 'token' | 'status' | 'done' | 'error';
  content?: string;
  message_id?: string;
  citations?: Citation[];
  reasoning_steps?: string[];
  from_cache?: boolean;
}

export function streamMessage(
  conversationId: string,
  docId: string,
  content: string,
  onEvent: (event: StreamEvent) => void,
  onDone: () => void,
  onError: (err: string) => void,
  signal?: AbortSignal
): void {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  fetch(`${BASE_URL}/api/chat/message`, {
    method: 'POST',
    headers,
    signal,
    body: JSON.stringify({
      content,
      conversation_id: conversationId,
      doc_id: docId,
    }),
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Stream failed' }));
      onError(err.detail || 'Stream request failed');
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) { onError('No stream reader'); return; }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) { onDone(); break; }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event: StreamEvent = JSON.parse(line.slice(6));
            onEvent(event);
            if (event.type === 'done') { onDone(); return; }
            if (event.type === 'error') { onError(event.content || 'Unknown error'); return; }
          } catch { /* malformed line, skip */ }
        }
      }
    }
  }).catch((err) => {
    if (err.name === 'AbortError') {
      onDone();
    } else {
      onError(err.message || 'Stream connection failed');
    }
  });
}

// pages/AuthPage.tsx — Sign In / Sign Up page
import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';
import '../styles/auth.css';

type Tab = 'login' | 'register';

const FEATURES = [
  {
    icon: '🤖',
    title: 'Multi-Agent AI Pipeline',
    desc: 'LangGraph agents for reasoning, retrieval & OCR',
  },
  {
    icon: '📊',
    title: 'Tables & Image Analysis',
    desc: 'Extract data from charts, diagrams & scanned pages',
  },
  {
    icon: '🧠',
    title: 'Persistent Memory',
    desc: 'Conversations stored across sessions in MongoDB',
  },
  {
    icon: '⚡',
    title: 'Semantic Cache',
    desc: 'Instant answers for similar questions via cache',
  },
];

export default function AuthPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Form fields
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let response;
      if (tab === 'login') {
        response = await authApi.login(email, password);
      } else {
        if (!name.trim()) { setError('Name is required'); setLoading(false); return; }
        response = await authApi.register(name, email, password);
      }
      localStorage.setItem('token', response.access_token);
      localStorage.setItem('user', JSON.stringify(response.user));
      navigate('/chat');
    } catch (err: any) {
      setError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      {/* Hero Side */}
      <div className="auth-hero">
        <div className="auth-hero-grid" />
        
        <div className="auth-logo">
          <div className="auth-logo-icon">🔮</div>
          <span className="auth-logo-text">AgenticRAG</span>
        </div>

        <div className="auth-hero-content">
          <h1>
            Chat with any<br />
            <span>PDF Document</span><br />
            intelligently.
          </h1>

          <p>
            Upload massive PDFs. Ask questions. Get accurate answers
            with page citations — powered by local AI agents that
            reason, retrieve, and learn.
          </p>

          <div className="auth-features">
            {FEATURES.map((f) => (
              <div key={f.title} className="auth-feature">
                <div className="auth-feature-icon">{f.icon}</div>
                <div className="auth-feature-text">
                  <strong>{f.title}</strong>
                  <span>{f.desc}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Form Side */}
      <div className="auth-form-side">
        <div className="auth-form-wrapper">
          <h2 className="auth-form-title">
            {tab === 'login' ? 'Welcome back' : 'Create account'}
          </h2>
          <p className="auth-form-subtitle">
            {tab === 'login'
              ? 'Sign in to continue your conversations'
              : 'Start chatting with your PDFs today'}
          </p>

          <div className="auth-tabs">
            <button
              className={`auth-tab ${tab === 'login' ? 'active' : ''}`}
              onClick={() => { setTab('login'); setError(''); }}
            >
              Sign In
            </button>
            <button
              className={`auth-tab ${tab === 'register' ? 'active' : ''}`}
              onClick={() => { setTab('register'); setError(''); }}
            >
              Register
            </button>
          </div>

          {error && <div className="auth-error">⚠️ {error}</div>}

          <form onSubmit={handleSubmit}>
            {tab === 'register' && (
              <div className="form-group">
                <label className="form-label" htmlFor="auth-name">Full Name</label>
                <input
                  id="auth-name"
                  className="input"
                  type="text"
                  placeholder="John Doe"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  autoComplete="name"
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="auth-email">Email Address</label>
              <input
                id="auth-email"
                className="input"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="auth-password">Password</label>
              <input
                id="auth-password"
                className="input"
                type="password"
                placeholder={tab === 'register' ? 'Min. 6 characters' : '••••••••'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
              />
            </div>

            <button
              id="auth-submit-btn"
              type="submit"
              className="btn btn-primary auth-submit-btn"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="spinner" />
                  {tab === 'login' ? 'Signing in...' : 'Creating account...'}
                </>
              ) : (
                tab === 'login' ? '→ Sign In' : '→ Create Account'
              )}
            </button>
          </form>

          <div className="auth-divider">Powered by Ollama · qwen2.5:7b · 100% Local</div>
        </div>
      </div>
    </div>
  );
}

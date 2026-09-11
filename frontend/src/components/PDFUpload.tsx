// components/PDFUpload.tsx — PDF, Word, and Image drag-and-drop upload with progress tracking
import { useState, useRef, useCallback, useEffect } from 'react';
import { pdfApi, PdfDoc, PdfStatus } from '../api/client';

interface PDFUploadProps {
  onDocumentReady: (doc: PdfStatus) => void;
  currentDocId?: string;
}

export default function PDFUpload({ onDocumentReady, currentDocId }: PDFUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadedDoc, setUploadedDoc] = useState<PdfStatus | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  const pollStatus = useCallback(async (docId: string) => {
    try {
      const status = await pdfApi.getStatus(docId);
      setUploadedDoc(status);

      if (status.status === 'ready') {
        clearInterval(pollInterval.current!);
        onDocumentReady(status);
      } else if (status.status === 'error') {
        clearInterval(pollInterval.current!);
        setError(status.error_message || 'Processing failed');
      }
    } catch (e: any) {
      clearInterval(pollInterval.current!);
      setError(e.message);
    }
  }, [onDocumentReady]);

  // If already have a docId, load status
  useEffect(() => {
    if (currentDocId && !uploadedDoc) {
      pdfApi.getStatus(currentDocId).then(s => {
        setUploadedDoc(s);
        if (s.status === 'ready') onDocumentReady(s);
      }).catch(() => {});
    }
  }, [currentDocId]);

  const handleFile = async (file: File) => {
    const allowedExtensions = ['.pdf', '.docx', '.doc', '.png', '.jpg', '.jpeg'];
    const hasAllowedExtension = allowedExtensions.some(ext => file.name.toLowerCase().endsWith(ext));

    if (!hasAllowedExtension) {
      setError('Supported formats: PDF, Word (.docx, .doc), or Images (.png, .jpg, .jpeg)');
      return;
    }

    setError('');
    setUploading(true);
    setUploadedDoc(null);

    try {
      const result = await pdfApi.upload(file);
      const initialStatus: PdfStatus = {
        doc_id: result.doc_id,
        filename: result.filename,
        status: 'queued',
        progress: 0,
        total_pages: 0,
        total_chunks: 0,
        total_vectors: 0,
        file_size_bytes: file.size,
        created_at: new Date().toISOString(),
      };
      setUploadedDoc(initialStatus);
      setUploading(false);

      // Poll for status every 2 seconds
      pollInterval.current = setInterval(() => pollStatus(result.doc_id), 2000);
    } catch (e: any) {
      setError(e.message);
      setUploading(false);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getStatusIcon = (status: string) => {
    if (status === 'ready') return '✅';
    if (status === 'error') return '❌';
    if (status === 'processing') return '⚙️';
    return '⏳';
  };

  // Cleanup on unmount
  useEffect(() => () => { if (pollInterval.current) clearInterval(pollInterval.current); }, []);

  return (
    <div className="pdf-upload-panel">
      {error && (
        <div className="auth-error" style={{ marginBottom: 10, fontSize: 12 }}>
          ⚠️ {error}
        </div>
      )}

      {!uploadedDoc ? (
        <div
          className={`pdf-upload-zone ${dragOver ? 'drag-over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            id="pdf-file-input"
            type="file"
            accept=".pdf,.docx,.doc,.png,.jpg,.jpeg"
            style={{ display: 'none' }}
            onChange={handleInputChange}
          />
          {uploading ? (
            <>
              <div className="pdf-upload-icon">⏳</div>
              <div className="pdf-upload-title">Uploading...</div>
            </>
          ) : (
            <>
              <div className="pdf-upload-icon">📁</div>
              <div className="pdf-upload-title">Drop PDF, Word, or Image here or click to browse</div>
              <div className="pdf-upload-subtitle">Supports PDF · Word (.docx) · Images (PNG, JPG)</div>
            </>
          )}
        </div>
      ) : (
        <div className="pdf-status-row">
          <span>{getStatusIcon(uploadedDoc.status)}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="pdf-status-name" title={uploadedDoc.filename}>
              {uploadedDoc.filename.length > 30
                ? '...' + uploadedDoc.filename.slice(-27)
                : uploadedDoc.filename}
            </div>
            <div className="pdf-status-pages">
              {uploadedDoc.status === 'ready'
                ? `${uploadedDoc.total_pages.toLocaleString()} pages · ${uploadedDoc.total_chunks.toLocaleString()} chunks · Ready`
                : uploadedDoc.status === 'error'
                ? 'Processing failed'
                : `Processing... ${uploadedDoc.progress}%`}
            </div>
            {(uploadedDoc.status === 'processing' || uploadedDoc.status === 'queued') && (
              <div className="pdf-progress-bar" style={{ marginTop: 6 }}>
                <div
                  className="pdf-progress-fill"
                  style={{ width: `${uploadedDoc.progress}%` }}
                />
              </div>
            )}
          </div>
          <span
            style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}
          >
            {formatBytes(uploadedDoc.file_size_bytes)}
          </span>
          <button
            id="pdf-change-btn"
            onClick={() => { setUploadedDoc(null); setError(''); }}
            className="btn btn-ghost btn-sm"
            title="Upload different document"
          >
            ↺
          </button>
        </div>
      )}
    </div>
  );
}

import React from 'react';

const ErrorOverlay = ({ error, onClose, onRefresh }) => {
    if (!error) {
        return null;
    }

    const errorMessage = typeof error === 'string' ? error : error?.message || 'An unexpected error occurred.';

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px', textAlign: 'center' }}>
                {onClose && (
                    <button className="modal-close-btn" onClick={onClose}>×</button>
                )}
                <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⚠️</div>
                <h2 style={{ color: 'var(--accent-rose, #f43f5e)', marginTop: 0, marginBottom: '0.75rem' }}>
                    Server Connection Error
                </h2>
                <p style={{ color: 'var(--text-secondary, #94a3b8)', marginBottom: '1.5rem', lineHeight: '1.5', fontSize: '0.95rem' }}>
                    {errorMessage}
                </p>
                <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem' }}>
                    {onRefresh && (
                        <button className="btn btn-primary" onClick={onRefresh}>
                            🔄 Refresh Page
                        </button>
                    )}
                    {onClose && (
                        <button className="btn btn-secondary" onClick={onClose}>
                            Close
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ErrorOverlay;
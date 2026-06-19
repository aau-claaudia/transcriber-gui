import React, { useState, useEffect } from 'react';

const EditPage = ({ transcriptionKey, transcriptionData, onBack, logFiles, zipFile }) => {
    const [notes, setNotes] = useState([]);
    const [newNote, setNewNote] = useState('');

    // Load notes from localStorage on mount/key change
    useEffect(() => {
        const savedNotes = localStorage.getItem(`notes_${transcriptionKey}`);
        if (savedNotes) {
            try {
                setNotes(JSON.parse(savedNotes));
            } catch (e) {
                console.error("Error parsing saved notes:", e);
                setNotes([]);
            }
        } else {
            setNotes([]);
        }
    }, [transcriptionKey]);

    // Save note to localStorage
    const handleSaveNote = () => {
        if (!newNote.trim()) return;
        const noteObj = {
            id: Date.now(),
            text: newNote,
            timestamp: new Date().toLocaleString()
        };
        const updatedNotes = [noteObj, ...notes];
        setNotes(updatedNotes);
        localStorage.setItem(`notes_${transcriptionKey}`, JSON.stringify(updatedNotes));
        setNewNote('');
    };

    // Delete note
    const handleDeleteNote = (noteId) => {
        const updatedNotes = notes.filter(note => note.id !== noteId);
        setNotes(updatedNotes);
        localStorage.setItem(`notes_${transcriptionKey}`, JSON.stringify(updatedNotes));
    };

    const getFileExtension = (fileName) => {
        const specialCases = ['dote.json'];
        for (const ext of specialCases) {
            if (fileName.endsWith(ext)) {
                return ext;
            }
        }
        return fileName.split('.').pop();
    };

    const extensionToolTip = new Map();
    extensionToolTip.set('aud', 'A subtitle-like format used by INRS-Telecom');
    extensionToolTip.set('csv', 'Comma-separated value format used for spreadsheets');
    extensionToolTip.set('docx', 'Word document format');
    extensionToolTip.set('dote.json', 'AAU based JSON transcription format: Distributed Open Transcription Environment');
    extensionToolTip.set('json', 'JSON output file containing full detailed transcription metadata');
    extensionToolTip.set('srt', 'SubRip Subtitle (SRT) format');
    extensionToolTip.set('tsv', 'Tab-separated values tabular data');
    extensionToolTip.set('txt', 'A simple text file format without speaker segments');
    extensionToolTip.set('vtt', 'WebVTT subtitle and captioning format');

    const getTitleForFileExtension = (extension) => {
        return extensionToolTip.get(extension) || 'Download transcription file';
    };

    const hasStandardFiles = transcriptionData?.files?.length > 0;
    const hasMergedFiles = transcriptionData?.mergedFiles?.length > 0;

    return (
        <div className="edit-page-layout">
            {/* Left Column: Results Download */}
            <div className="card-panel">
                <div className="page-header">
                    <button className="btn btn-secondary" onClick={onBack}>
                        ← Back to Dashboard
                    </button>
                    <h2>Transcription Results</h2>
                </div>

                <div style={{ marginBottom: '1.5rem' }}>
                    <h3 style={{ fontFamily: 'Outfit', color: 'var(--text-primary)' }}>
                        📄 {transcriptionKey}
                    </h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                        Click on any format card below to download the transcribed file.
                    </p>
                </div>

                {hasStandardFiles && (
                    <div style={{ marginBottom: '2rem' }}>
                        <h3>Standard Outputs</h3>
                        <div className="download-grid">
                            {transcriptionData.files.map((file, idx) => {
                                const ext = getFileExtension(file.file_name);
                                return (
                                    <a
                                        key={idx}
                                        href={file.file_url}
                                        className="download-btn-card"
                                        title={getTitleForFileExtension(ext)}
                                        download
                                        rel="noreferrer"
                                    >
                                        <span className="ext-badge">{ext}</span>
                                        <span className="ext-desc">{getTitleForFileExtension(ext).slice(0, 30)}...</span>
                                    </a>
                                );
                            })}
                        </div>
                    </div>
                )}

                {hasMergedFiles && (
                    <div style={{ marginBottom: '2rem' }}>
                        <h3>Merged Speaker Formats</h3>
                        <div className="download-grid">
                            {transcriptionData.mergedFiles.map((file, idx) => {
                                const ext = getFileExtension(file.file_name);
                                return (
                                    <a
                                        key={idx}
                                        href={file.file_url}
                                        className="download-btn-card"
                                        title={getTitleForFileExtension(ext)}
                                        download
                                        rel="noreferrer"
                                    >
                                        <span className="ext-badge">{ext}</span>
                                        <span className="ext-desc">{getTitleForFileExtension(ext).slice(0, 30)}...</span>
                                    </a>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Log & Zip section in Edit Page for contextual convenience */}
                {zipFile && (
                    <div style={{ marginTop: '2rem', padding: '1rem', background: 'rgba(255,255,255,0.01)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                        <h4 style={{ marginBottom: '0.5rem' }}>📦 Entire Output Archive</h4>
                        <p style={{ fontSize: '0.85rem', marginBottom: '0.75rem' }}>Download a zip archive containing all format outputs for this transcription.</p>
                        <a href={zipFile.file_url} className="btn btn-secondary" download>
                            Download Zip File
                        </a>
                    </div>
                )}
            </div>

            {/* Right Column: Notes & Annotation System */}
            <div className="card-panel">
                <div className="notes-container">
                    <h2>Notes & Annotation</h2>
                    <p style={{ fontSize: '0.85rem', marginBottom: '1rem' }}>
                        Store your notes, markers, or summaries here. Notes are stored locally and will persist.
                    </p>

                    <div className="notes-input-area">
                        <textarea
                            className="notes-textarea"
                            placeholder="Add a new note for this transcription..."
                            value={newNote}
                            onChange={(e) => setNewNote(e.target.value)}
                        />
                        <button className="btn btn-primary" onClick={handleSaveNote}>
                            Save Note
                        </button>
                    </div>

                    <hr style={{ border: 'none', borderBottom: '1px solid var(--border-color)', margin: '1rem 0' }} />

                    <h3>Saved Notes ({notes.length})</h3>
                    <div className="notes-list">
                        {notes.length === 0 ? (
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textAlign: 'center', marginTop: '1rem' }}>
                                No notes recorded yet.
                            </p>
                        ) : (
                            notes.map(note => (
                                <div className="note-item" key={note.id}>
                                    <div className="note-header">
                                        <span>📅 {note.timestamp}</span>
                                        <button
                                            className="note-delete-btn"
                                            onClick={() => handleDeleteNote(note.id)}
                                            title="Delete note"
                                        >
                                            🗑️
                                        </button>
                                    </div>
                                    <div className="note-text">{note.text}</div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default EditPage;

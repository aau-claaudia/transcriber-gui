import React, { useState, useEffect, useRef, useMemo } from 'react';

// Utility helper to convert HH:MM:SS.mmm to seconds
function timestampToSeconds(timestamp) {
    if (!timestamp) return 0;
    const parts = timestamp.split(':');
    if (parts.length !== 3) return 0;
    const hours = parseInt(parts[0], 10);
    const minutes = parseInt(parts[1], 10);
    const secondsWithMs = parseFloat(parts[2]);
    return hours * 3600 + minutes * 60 + secondsWithMs;
}

// Single-control UI for one segment, driven by shared player state
const SegmentAudioPlayer = ({
                                audioUrl,
                                segmentId,
                                activeSegmentId,
                                currentTimeBySegment,
                                onToggleSegment,
                                onSeekSegment,
                                startTimeStr,
                                endTimeStr
                            }) => {
    const startSecs = timestampToSeconds(startTimeStr);
    const endSecs = timestampToSeconds(endTimeStr);
    const duration = Math.max(0.1, endSecs - startSecs);

    const isPlaying = activeSegmentId === segmentId;
    const currentTime = currentTimeBySegment[segmentId] ?? 0;
    const progressPercent = Math.max(0, Math.min(100, (currentTime / duration) * 100));

    const handleProgressClick = (e) => {
        if (!audioUrl) return;
        const rect = e.currentTarget.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const width = rect.width || 1;
        const clickRatio = Math.max(0, Math.min(1, clickX / width));
        const relativeTime = clickRatio * duration;
        onSeekSegment(segmentId, relativeTime);
    };

    if (!audioUrl) {
        return (
            <div className="segment-audio-player" style={{ opacity: 0.5 }} title="Audio source file not available">
                <button className="play-segment-btn" disabled>▶️</button>
                <div className="segment-progress-container" style={{ cursor: 'not-allowed' }}>
                    <div className="segment-progress-bar" style={{ width: '0%' }}></div>
                </div>
                <span className="segment-time-label">0.0s / {duration.toFixed(1)}s</span>
            </div>
        );
    }

    return (
        <div className="segment-audio-player">
            <button
                className="play-segment-btn"
                onClick={() => onToggleSegment(segmentId)}
                title={isPlaying ? 'Pause Segment' : 'Play Segment'}
            >
                {isPlaying ? '⏸️' : '▶️'}
            </button>
            <div className="segment-progress-container" onClick={handleProgressClick}>
                <div className="segment-progress-bar" style={{ width: `${progressPercent}%` }}></div>
            </div>
            <span className="segment-time-label">
                {currentTime.toFixed(1)}s / {duration.toFixed(1)}s
            </span>
        </div>
    );
};

// Segment Card containing speaker, duration, audio controls, text and selection-based note adding form
const SegmentCard = ({
                         segment,
                         segmentId,
                         audioUrl,
                         activeSegmentId,
                         currentTimeBySegment,
                         onToggleSegment,
                         onSeekSegment,
                         onAddNote
                     }) => {
    const [selectionState, setSelectionState] = useState({ text: '', isOpen: false });
    const [correctiveText, setCorrectiveText] = useState('');

    const handleTextSelection = (e) => {
        const selection = window.getSelection();
        const selectedText = selection?.toString().trim();

        if (selectedText && e.currentTarget.contains(selection.anchorNode)) {
            setSelectionState({ text: selectedText, isOpen: true });
        }
    };

    const handleSaveNote = () => {
        if (!correctiveText.trim()) return;

        const formattedNote = `[${segment.startTime}][${segment.endTime}]:..${selectionState.text}..: ${correctiveText}`;
        onAddNote(formattedNote);

        setCorrectiveText('');
        setSelectionState({ text: '', isOpen: false });
    };

    const handleCancel = () => {
        setCorrectiveText('');
        setSelectionState({ text: '', isOpen: false });
    };

    return (
        <div className="segment-card">
            <div className="segment-header">
                <span className="speaker-badge">👤 {segment.speakerDesignation}</span>
                <span className="time-badge">⏱️ {segment.startTime} - {segment.endTime}</span>
            </div>

            <SegmentAudioPlayer
                audioUrl={audioUrl}
                segmentId={segmentId}
                activeSegmentId={activeSegmentId}
                currentTimeBySegment={currentTimeBySegment}
                onToggleSegment={onToggleSegment}
                onSeekSegment={onSeekSegment}
                startTimeStr={segment.startTime}
                endTimeStr={segment.endTime}
            />

            <div
                className="segment-text"
                onMouseUp={handleTextSelection}
                title="Highlight text to add corrective note"
            >
                {segment.text}
            </div>

            {selectionState.isOpen && (
                <div className="segment-selection-form">
                    <div className="selected-text-preview">
                        Highlight: "<strong>{selectionState.text}</strong>"
                    </div>
                    <input
                        type="text"
                        className="note-input-field"
                        placeholder="Enter corrective note / comments..."
                        value={correctiveText}
                        onChange={(e) => setCorrectiveText(e.target.value)}
                        autoFocus
                    />
                    <div className="form-actions">
                        <button className="btn btn-secondary" onClick={handleCancel} style={{ padding: '0.3rem 0.75rem', fontSize: '0.8rem' }}>
                            Cancel
                        </button>
                        <button className="btn btn-primary" onClick={handleSaveNote} style={{ padding: '0.3rem 0.75rem', fontSize: '0.8rem' }}>
                            Save Note
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

const Notes = ({ transcriptionKey, transcriptionData, onBackToDashboard, onBackToEdit }) => {
    const [notes, setNotes] = useState([]);
    const [segments, setSegments] = useState([]);
    const [loadingSegments, setLoadingSegments] = useState(true);
    const [errorSegments, setErrorSegments] = useState(null);

    // Audio URL state — may be updated after server-side conversion
    const [audioUrl, setAudioUrl] = useState(transcriptionData?.inputFileUrl ?? null);
    const [audioConverting, setAudioConverting] = useState(false);

    // Shared audio state
    const audioRef = useRef(null);
    const [activeSegmentId, setActiveSegmentId] = useState(null);
    const [currentTimeBySegment, setCurrentTimeBySegment] = useState({});

    // Segment timing cache for shared player logic
    const segmentBounds = useMemo(() => {
        return segments.map((s) => ({
            start: timestampToSeconds(s.startTime),
            end: timestampToSeconds(s.endTime)
        }));
    }, [segments]);

    // Get .dote.json file from transcriptionData files
    const doteFile = transcriptionData?.files?.find(f => f.file_name.endsWith('.dote.json'));

    // method for creating relative links from the file URLs
    const toRelativeFetchUrl = (fileUrl) => {
        if (!fileUrl) return fileUrl;
        try {
            const parsedUrl = new URL(fileUrl, window.location.href, true);

            const pathname = parsedUrl.pathname || '';
            const search = parsedUrl.search || '';

            return `${pathname}${search}`;
        } catch (err) {
            console.warn('Could not parse file URL, using original value:', fileUrl, err);
            return fileUrl;
        }
    }

    // On mount: if the audio source isn't already .mp3 or .wav, request server conversion
    useEffect(() => {
        const rawUrl = transcriptionData?.inputFileUrl;
        const dirName = transcriptionData?.name;
        if (!rawUrl) {
            setAudioUrl(null);
            return;
        }

        // Extract the path extension
        let ext = '';
        try {
            ext = new URL(rawUrl).pathname.split('.').pop().toLowerCase();
        } catch {
            ext = rawUrl.split('.').pop().toLowerCase();
        }

        const nativeFormats = new Set(['mp3', 'wav']);
        if (nativeFormats.has(ext)) {
            // Already in a browser-native format — use as-is
            setAudioUrl(rawUrl);
            return;
        }

        // Trigger conversion of video/audio file
        if (!dirName) {
            // No dir context to convert — fall back to original URL
            setAudioUrl(rawUrl);
            return;
        }

        setAudioConverting(true);
        fetch('/convert-audio/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dir_name: dirName, input_file_url: rawUrl }),
        })
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json();
            })
            .then(data => {
                setAudioUrl(data.input_file_url || rawUrl);
            })
            .catch(err => {
                console.error('Audio conversion request failed:', err);
                setAudioUrl(rawUrl); // graceful fallback
            })
            .finally(() => {
                setAudioConverting(false);
            });
    }, [transcriptionData?.inputFileUrl, transcriptionData?.name]);

    // Load notes on mount
    useEffect(() => {
        const savedNotes = localStorage.getItem(`notes_${transcriptionKey}`);
        if (savedNotes) {
            try {
                setNotes(JSON.parse(savedNotes));
            } catch (e) {
                console.error('Error parsing saved notes:', e);
                setNotes([]);
            }
        } else {
            setNotes([]);
        }
    }, [transcriptionKey]);

    // Fetch transcription segments from dote.json
    useEffect(() => {
        if (!doteFile) {
            setSegments([]);
            setLoadingSegments(false);
            setErrorSegments('No .dote.json file found for this transcription run.');
            return;
        }

        setLoadingSegments(true);
        setErrorSegments(null);

        fetch(toRelativeFetchUrl(doteFile.file_url))
            .then(res => {
                if (!res.ok) {
                    throw new Error(`Failed to load dote.json: ${res.statusText}`);
                }
                return res.json();
            })
            .then(data => {
                if (data && Array.isArray(data.lines)) {
                    setSegments(data.lines);
                } else {
                    setSegments([]);
                    setErrorSegments("Dote file format invalid (missing 'lines' array).");
                }
                setLoadingSegments(false);
            })
            .catch(err => {
                console.error('Error loading dote file:', err);
                setErrorSegments('Could not load transcription segments from the server.');
                setLoadingSegments(false);
            });
    }, [doteFile?.file_url]);

    // Refs so that event listeners always see current values without being recreated
    const activeSegmentIdRef = useRef(null);
    const segmentBoundsRef = useRef([]);

    // Keep refs in sync with state/memo
    useEffect(() => { activeSegmentIdRef.current = activeSegmentId; }, [activeSegmentId]);
    useEffect(() => { segmentBoundsRef.current = segmentBounds; }, [segmentBounds]);

    // Create one shared Audio element — only recreated when the source URL changes
    useEffect(() => {
        if (!audioUrl) {
            audioRef.current = null;
            setActiveSegmentId(null);
            setCurrentTimeBySegment({});
            return;
        }

        const audio = new Audio(audioUrl);
        audio.preload = 'metadata';
        audio.autoplay = false;
        audioRef.current = audio;

        const onTimeUpdate = () => {
            const segId = activeSegmentIdRef.current;
            if (segId == null) return;
            const bounds = segmentBoundsRef.current[segId];
            if (!bounds) return;

            const relative = Math.max(0, audio.currentTime - bounds.start);

            if (audio.currentTime >= bounds.end) {
                audio.pause();
                audio.currentTime = bounds.start;
                setCurrentTimeBySegment(prev => ({ ...prev, [segId]: 0 }));
                setActiveSegmentId(null);
                activeSegmentIdRef.current = null;
                return;
            }

            setCurrentTimeBySegment(prev => ({ ...prev, [segId]: relative }));
        };

        const onEnded = () => {
            const segId = activeSegmentIdRef.current;
            if (segId != null) {
                setCurrentTimeBySegment(prev => ({ ...prev, [segId]: 0 }));
            }
            setActiveSegmentId(null);
            activeSegmentIdRef.current = null;
        };

        audio.addEventListener('timeupdate', onTimeUpdate);
        audio.addEventListener('ended', onEnded);

        return () => {
            audio.pause();
            audio.removeEventListener('timeupdate', onTimeUpdate);
            audio.removeEventListener('ended', onEnded);
        };
    }, [audioUrl]);

    // Toggle play/pause for a segment using shared audio
    const handleToggleSegment = (segmentId) => {
        const audio = audioRef.current;
        if (!audio) return;

        const bounds = segmentBounds[segmentId];
        if (!bounds) return;

        if (activeSegmentId === segmentId) {
            audio.pause();
            setActiveSegmentId(null);
            return;
        }

        setActiveSegmentId(segmentId);

        // Ensure playhead is inside target segment window
        if (audio.currentTime < bounds.start || audio.currentTime >= bounds.end) {
            audio.currentTime = bounds.start;
            setCurrentTimeBySegment(prev => ({ ...prev, [segmentId]: 0 }));
        }

        audio.play().catch(err => {
            // AbortError is expected when a pending play gets superseded by pause/seek
            if (err?.name !== 'AbortError') {
                console.error('Audio playback error:', err);
            }
        });
    };

    // Seek within one segment (relative seconds)
    const handleSeekSegment = (segmentId, relativeTime) => {
        const audio = audioRef.current;
        if (!audio) return;

        const bounds = segmentBounds[segmentId];
        if (!bounds) return;

        const duration = Math.max(0.1, bounds.end - bounds.start);
        const clampedRelative = Math.max(0, Math.min(duration, relativeTime));
        const absoluteTarget = bounds.start + clampedRelative;

        audio.currentTime = absoluteTarget;
        setCurrentTimeBySegment(prev => ({ ...prev, [segmentId]: clampedRelative }));

        if (activeSegmentId !== segmentId) {
            setActiveSegmentId(segmentId);
            audio.play().catch(err => {
                if (err?.name !== 'AbortError') {
                    console.error('Audio playback error:', err);
                }
            });
        }
    };

    const handleAddNote = (noteText) => {
        const noteObj = {
            id: Date.now(),
            text: noteText,
            timestamp: new Date().toLocaleString()
        };
        const updatedNotes = [noteObj, ...notes];
        setNotes(updatedNotes);
        localStorage.setItem(`notes_${transcriptionKey}`, JSON.stringify(updatedNotes));
    };

    const handleDeleteNote = (noteId) => {
        const updatedNotes = notes.filter(note => note.id !== noteId);
        setNotes(updatedNotes);
        localStorage.setItem(`notes_${transcriptionKey}`, JSON.stringify(updatedNotes));
    };

    return (
        <div className="notes-page" style={{ animation: 'fadeIn 0.4s ease-out' }}>
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                    <button className="btn btn-secondary" onClick={onBackToDashboard}>
                        ← Back to Dashboard
                    </button>
                    <button className="btn btn-secondary" onClick={onBackToEdit}>
                        ← Back to Results Page
                    </button>
                </div>
                <h2 style={{ margin: 0, fontSize: '1.5rem' }}>Annotating: {transcriptionKey}</h2>
            </div>

            <div className="notes-page-layout">
                <div className="card-panel" style={{ position: 'relative' }}>
                    <h3 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
                        🎙️ Transcription Segments
                    </h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                        To take a corrective note, highlight any text within a segment. Use the audio controls next to each segment to verify speaker pronunciation.
                    </p>

                    {/* Audio conversion loading overlay */}
                    {audioConverting && (
                        <div style={{
                            position: 'absolute',
                            inset: 0,
                            borderRadius: 'var(--radius-lg, 12px)',
                            background: 'rgba(10, 10, 18, 0.82)',
                            backdropFilter: 'blur(6px)',
                            WebkitBackdropFilter: 'blur(6px)',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '1rem',
                            zIndex: 10,
                        }}>
                            <div style={{
                                width: '48px',
                                height: '48px',
                                borderRadius: '50%',
                                border: '3px solid rgba(139, 92, 246, 0.25)',
                                borderTopColor: 'var(--accent-violet, #8b5cf6)',
                                animation: 'spin 0.9s linear infinite',
                            }} />
                            <div style={{ textAlign: 'center' }}>
                                <p style={{ margin: 0, fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary, #f1f5f9)' }}>
                                    🎵 Converting audio to MP3…
                                </p>
                                <p style={{ margin: '0.35rem 0 0', fontSize: '0.8rem', color: 'var(--text-muted, #64748b)' }}>
                                    This may take a moment for large files
                                </p>
                            </div>
                            {/* Shimmer bar */}
                            <div style={{
                                width: '180px',
                                height: '4px',
                                borderRadius: '2px',
                                background: 'rgba(139, 92, 246, 0.15)',
                                overflow: 'hidden',
                            }}>
                                <div style={{
                                    height: '100%',
                                    width: '40%',
                                    borderRadius: '2px',
                                    background: 'linear-gradient(90deg, transparent, var(--accent-violet, #8b5cf6), transparent)',
                                    animation: 'shimmer 1.4s ease-in-out infinite',
                                }} />
                            </div>
                        </div>
                    )}

                    {loadingSegments && (
                        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                            Loading transcription segments...
                        </div>
                    )}

                    {errorSegments && (
                        <div style={{ padding: '1rem', background: 'rgba(244, 63, 94, 0.1)', border: '1px solid var(--accent-rose)', borderRadius: 'var(--radius-md)', color: '#fda4af', fontSize: '0.9rem' }}>
                            {errorSegments}
                        </div>
                    )}

                    {!loadingSegments && !errorSegments && segments.length === 0 && (
                        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                            No transcription segments found in the dote output file.
                        </div>
                    )}

                    {!loadingSegments && !errorSegments && segments.length > 0 && (
                        <div className="segment-list">
                            {segments.map((segment, idx) => (
                                <SegmentCard
                                    key={idx}
                                    segmentId={idx}
                                    segment={segment}
                                    audioUrl={audioUrl}
                                    activeSegmentId={activeSegmentId}
                                    currentTimeBySegment={currentTimeBySegment}
                                    onToggleSegment={handleToggleSegment}
                                    onSeekSegment={handleSeekSegment}
                                    onAddNote={handleAddNote}
                                />
                            ))}
                        </div>
                    )}
                </div>


                <div className="card-panel">
                    <h3 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
                        📝 Saved Notes & Corrections ({notes.length})
                    </h3>

                    <div className="notes-list" style={{ maxHeight: 'calc(70vh - 50px)' }}>
                        {notes.length === 0 ? (
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textAlign: 'center', marginTop: '2rem' }}>
                                No notes recorded yet. Select text in transcription segments on the left to start.
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

export default Notes;
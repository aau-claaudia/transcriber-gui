import React from 'react';

const TranscriptionStatus = ({ statusText, activeTask, percentageDone, transcribeAndShutdown, serverStopped}) => {

    return (
        <div style={{marginBottom: '5%'}}>
            { (transcribeAndShutdown && !serverStopped) && (
                <p><b><i> The "transcribe and stop" setting is on. The UCloud job will stop when the transcription completes. The browser window can be closed.</i></b></p>
            )}
            { (transcribeAndShutdown && serverStopped) && (
                <p><b><i> The "transcribe and stop" setting is on. The UCloud job has now stopped.</i></b></p>
            )}
            <p>{statusText}</p>
            <h3>Active transcription file list</h3>
            <table>
                <thead>
                <tr>
                    <th>Name</th>
                    <th>Size (MB)</th>
                    <th>File origin</th>
                </tr>
                </thead>
                <tbody>
                {activeTask.map((file, index) => (
                    <tr key={index}>
                        <td title={file.name} style={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxWidth: '200px'}}>
                                {file.name}
                        </td>
                        <td>{(file.size / 1000000).toFixed(2)}</td>
                        <td>{file.ucloud ? "UCloud" : "Upload"}</td>
                    </tr>
                ))}
                </tbody>
            </table>
            <h3>Estimated progress based on data size</h3>
            <progress className="progress-bar" value={transcribeAndShutdown && serverStopped ? 1.0 : percentageDone}/>
        </div>
    );
};

export default TranscriptionStatus;
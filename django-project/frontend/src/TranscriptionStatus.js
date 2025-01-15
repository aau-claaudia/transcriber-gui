import React from 'react';

const TranscriptionStatus = ({ statusText, activeTask, percentageDone}) => {

    return (
        <div>
            <p className='waitingText'>{statusText}</p>
            <h3>Active transcription file list</h3>
            <table>
                <thead>
                <tr>
                    <th>Name</th>
                    <th>Size (MB)</th>
                    <th>File Origin</th>
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
                        <td>{file.ucloud ? "UCLoud" : "Upload"}</td>
                    </tr>
                ))}
                </tbody>
            </table>
            <h3>Estimated progress based on data size</h3>
            <progress className="progress-bar" value={percentageDone}/>
        </div>
    );
};

export default TranscriptionStatus;
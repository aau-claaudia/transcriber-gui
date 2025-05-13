import React from 'react';

const Results = ({ zipFile, maxFilesInGroup, groupedFiles, groupedFilesMergedFormat, logFiles }) => {

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
    extensionToolTip.set('aud', 'A subtitle-like format used by INRS-Telecom, a research university in Quebec');
    extensionToolTip.set('csv', 'Comma-separated value format used for spead sheets');
    extensionToolTip.set('docx', 'Word document format');
    extensionToolTip.set('dote.json', 'AAU based JSON transcription format: Distributed Open Transcription Environment');
    extensionToolTip.set('json', 'A JSON output file with maximum details from the transcription algorithm');
    extensionToolTip.set('srt', 'SubRip Subtitle (SRT) is a Popular subtitle format');
    extensionToolTip.set('tsv', 'Tab-separated values (TSV) is a simple, text-based file format for storing tabular data');
    extensionToolTip.set('txt', 'A simple text file format. This format does not contain the speaker data.');
    extensionToolTip.set('vtt', 'A popular subtitle/captioning file format');

    const getTitleForFileExtension = (extension) => {
        return extensionToolTip.get(extension);
    }

    return (
        <div style={{marginBottom: '5%'}}>
            <h2>Transcribed files</h2>
            <p>
                The download of transcriptions is possible as a single file or
                as a zip-file containing all transcribed files.
            </p>
            <div>
                {zipFile && (
                    <div>
                        <h3>Zip file</h3>
                        <div>
                            <p>The zip file contains all the transcribed files for easy download.</p>
                            <a href={zipFile.file_url} rel="noreferrer" download>Download zip file.</a>
                        </div>
                    </div>
                )}
                <h3>Standard files</h3>
                <table>
                    <thead>
                    <tr>
                        <th>File</th>
                        <th colSpan={maxFilesInGroup}>Extensions</th>
                    </tr>
                    </thead>
                    <tbody>
                    {Object.keys(groupedFiles).map((key, index) => (
                        <tr key={index}>
                            <td className='file-name' title={key}>{key}</td>
                            {groupedFiles[key].map((result, subIndex) => (
                                <td key={subIndex}>
                                    <a href={result.file_url}
                                       title={getTitleForFileExtension(getFileExtension(result.file_name))}
                                       rel="noreferrer" className="button" download>
                                        {getFileExtension(result.file_name)}
                                    </a>
                                </td>
                            ))}
                        </tr>
                    ))}
                    </tbody>
                </table>
                <h3>Merged speaker format</h3>
                <table>
                    <thead>
                    <tr>
                        <th>File</th>
                        <th colSpan={maxFilesInGroup}>Extensions</th>
                    </tr>
                    </thead>
                    <tbody>
                    {Object.keys(groupedFilesMergedFormat).map((key, index) => (
                        <tr key={index}>
                            <td className='file-name-merged' title={key}>{key}</td>
                            {groupedFilesMergedFormat[key].map((result, subIndex) => (
                                <td key={subIndex}>
                                    <a href={result.file_url}
                                       title={getTitleForFileExtension(getFileExtension(result.file_name))}
                                       rel="noreferrer" className="button" download>
                                        {getFileExtension(result.file_name)}
                                    </a>
                                </td>
                            ))}
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>
            <div>
                <h3>Log files</h3>
                <p>
                    The log files contain output from the transcription process and from the application running
                    the transcription.
                    <br/> If something goes wrong these files can help determine the issue.
                </p>
                {logFiles.map((result, index) => (
                    <div key={index}>
                        <a href={result.file_url} rel="noreferrer" download>{result.file_name}</a>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default Results;
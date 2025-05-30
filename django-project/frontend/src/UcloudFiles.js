import React, {useState} from 'react';
import Spinner from "./spinners";

const UcloudFiles = ({ onAddUcloudFiles, scannedFiles, onScan, scanning}) => {
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [checkedFiles, setCheckedFiles] = useState({});

    // Function to handle checkbox change
    const handleAddFile = (file, fileIndex) => {
        // change the state to checked for the input
        setCheckedFiles((prev) => ({
            ...prev,
            [fileIndex]: !prev[fileIndex], // Toggle the checkbox state
        }));
        // add the file to selection list
        setSelectedFiles(prevSelectedFiles => {
            if (prevSelectedFiles.includes(file)) {
                return prevSelectedFiles.filter(f => f !== file);
            } else {
                return [...prevSelectedFiles, file];
            }
        });
    };

    // Function to handle scan button click
    const handleScan = async (e) => {
        await onScan(e);
        setSelectedFiles([]);
        setCheckedFiles([]);
    };

    // Function to add files from UCloud to transcription list
    const addULoudFiles = async () => {
        await onAddUcloudFiles(selectedFiles);
        setSelectedFiles([]);
        setCheckedFiles([]);
    };

    return (
        <div style={{marginBottom: '5%'}}>
            <h2>Use files from UCloud</h2>
            <div style={{display: 'flex'}}>
                <div>
                    <h3>Select UCloud files</h3>
                    <button
                        type='button'
                        style={{width: '200px'}}
                        onClick={addULoudFiles}
                        className='transcribe-button'
                        disabled={selectedFiles.length === 0}
                    >
                        Add UCloud files
                    </button>
                    <button
                        type='submit'
                        style={{width: '200px'}}
                        onClick={(e) => handleScan(e)}
                        className='transcribe-button'
                        disabled={scanning}
                    >
                        Scan UCloud folder {scanning &&
                        <Spinner loading={scanning}/>} {/* Show spinner next to the button */}
                    </button>
                </div>
                <div style={{marginLeft: '1%', overflowY: 'scroll', maxHeight: '500px', width: '100%'}}>
                    <h3>UCloud files available for transcription</h3>
                    <p>
                        After selection, click the button <b>Add UCloud files</b>.
                        The files will be added to the <b>Selected files</b> list at the top of the page.
                    </p>
                    <p>
                        Click the <b>Scan UCloud folder</b> button to re-scan the UCloud folder. Only audio and video files will appear in the list.
                        Folders with the name <b>UPLOADS</b> and <b>COMPLETED</b> will not be scanned, as these names
                        are reserved by the application.
                    </p>
                    {scannedFiles.length > 0 && (
                        <table>
                            <thead>
                            <tr>
                                <th>Select</th>
                                <th>Name</th>
                                <th>Path</th>
                                <th>Size (MB)</th>
                            </tr>
                            </thead>
                            <tbody>
                            {scannedFiles.map((file, index) => (
                                <tr key={index}>
                                    <td><input type="checkbox"
                                               onChange={() => handleAddFile(file, index)}
                                               checked={!!checkedFiles[index]}/></td>
                                    <td className="file-name-scan" title={file.name}>{file.name}</td>
                                    <td className="file-name-scan" title={file.filepath}>{file.filepath}</td>
                                    <td>{(file.size / 1000000).toFixed(2)}</td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    )}
                    {(!scannedFiles.length > 0) && (
                        <p>No applicable media files found in UCloud mounted folder. </p>
                    )}
                </div>
            </div>
            <hr/>
        </div>
    );
};

export default UcloudFiles;
import React, {useState} from 'react';
import Spinner from "./spinners";

const Settings = ({ onScan, onAddUcloudFiles, scanning, transcribing, uploading, scannedFiles}) => {
    const [selectedFiles, setSelectedFiles] = useState([]);

    // Function to handle checkbox change
    const handleAddFile = (file) => {
        setSelectedFiles(prevSelectedFiles => {
            if (prevSelectedFiles.includes(file)) {
                return prevSelectedFiles.filter(f => f !== file);
            } else {
                return [...prevSelectedFiles, file];
            }
        });
    };

    // Function to add files from UCloud to transcription list
    const addULoudFiles = () => {
        onAddUcloudFiles(selectedFiles);
    };

    return (
        <div>
            {/* Section for setting a model */}
            <div>
                <h3>Select Model</h3>
                <select defaultValue={"large-v3"}>
                    <option value="base">base</option>
                    <option value="small">small</option>
                    <option value="medium">medium</option>
                    <option value="large-v3">large-v3</option>
                    <option value="large-v3-turbo">large-v3-turbo</option>
                </select>
            </div>
            <hr/>

            {/* Section for setting a language */}
            <div>
                <h3>Select Language</h3>
                <select>
                    <option value="en">English</option>
                    <option value="es">Spanish</option>
                    <option value="fr">French</option>
                    {/* Add more languages as needed */}
                </select>
            </div>
            <hr />

            {/* Section for scan button and file list */}
            <div style={{display: 'flex'}}>
                <div>
                    <h3>Select UCloud files</h3>
                    <button
                        type='submit'
                        style={{width: '200px'}}
                        onClick={(e) => onScan(e)}
                        className='transcribe-button'
                        disabled={transcribing || uploading || scanning}
                    >
                        Scan UCloud folder {scanning &&
                        <Spinner loading={scanning}/>} {/* Show spinner next to the button */}
                    </button>
                    <button
                        type='button'
                        style={{width: '200px'}}
                        onClick={addULoudFiles}
                        className='transcribe-button'
                        disabled={selectedFiles.length === 0}
                    >
                        Add selected files
                    </button>
                </div>
                <div style={{marginLeft: '20px', overflowY: 'scroll', maxHeight: '500px', width: '100%'}}>
                    <h3>UCloud files available for transcription</h3>
                    <p>
                        Please select a folder in UCloud before starting the application in order to select files.
                        Click the button to scan the UCloud folder. Only audio and video files will appear in the list.
                        Folders with the name 'uploads' will not be scanned, as this is reserved by the application.
                    </p>
                    <table>
                        <thead>
                        <tr>
                            <th>Select</th>
                            <th>Name</th>
                            <th>Path</th>
                            <th>Size</th>
                        </tr>
                        </thead>
                        <tbody>
                        {scannedFiles.map((file, index) => (
                            <tr key={index}>
                                <td><input type="checkbox" onChange={() => handleAddFile(file)}/></td>
                                <td>{file.name}</td>
                                <td title={file.filepath} style={{
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    maxWidth: '200px'
                                }}>{file.filepath}</td>
                                <td>{file.size}</td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default Settings;
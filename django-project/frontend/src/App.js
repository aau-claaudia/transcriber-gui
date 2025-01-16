import React, { useCallback, useState, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import Spinner  from './spinners'
import { csrfToken } from './csrf';
import Settings from "./Settings";
import TranscriptionStatus from "./TranscriptionStatus";
import transcriberImage from "./logo-transcriber.png";

function App() {
    const formatDuration = (duration) => {
        // Convert duration from milliseconds to seconds
        const totalSeconds = Math.floor(duration / 1000);

        // Calculate minutes and seconds
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;

        // Format the result
        return `${minutes} minute(s) and ${seconds} second(s)`;
    }
    const getInitialArrayState = (keyname) => {
        const dataFromSession = sessionStorage.getItem(keyname);
        return dataFromSession ? JSON.parse(dataFromSession) : [];
    }
    const getInitialBooleanState = (keyname, state) => {
        const dataFromSession = sessionStorage.getItem(keyname);
        return dataFromSession ? JSON.parse(dataFromSession) : state;
    }
    const getInitialTranscriptionId = () => {
        const dataFromSession = sessionStorage.getItem("transcriptionId");
        return dataFromSession ? JSON.parse(dataFromSession) : null;
    }
    const getInitialTranscriptionStatus = () => {
        const dataFromSession = sessionStorage.getItem("statusText");
        return dataFromSession ? JSON.parse(dataFromSession) : null;
    }
    const getInitialInteger = (keyname) => {
        const dataFromSession = sessionStorage.getItem(keyname);
        return dataFromSession ? JSON.parse(dataFromSession) : 0;
    }
    const getInitialTranscriptionStartTime = () => {
        const dataFromSession = sessionStorage.getItem("transcriptionStartTime");
        return dataFromSession ? JSON.parse(dataFromSession) : null;
    }
    const getInitialString = (keyname, value) => {
        const dataFromSession = sessionStorage.getItem(keyname);
        return dataFromSession ? JSON.parse(dataFromSession) : value;
    }

    const [files, setFiles] = useState([]);
    const [scannedFiles, setScannedFiles] = useState([]);
    const [scannedAndLinkedFiles, setScannedAndLinkedFiles] = useState([]);
    const [activeTask, setActiveTask] = useState(getInitialArrayState("activeTask"));
    const [rejected, setRejected] = useState([]);
    const [results, setResults] = useState(getInitialArrayState("results"));
    const [transcribing, setTranscribing] = useState(getInitialBooleanState("transcribing",false)); // State to control spinner visibility
    const [buttonDisabled, setButtonDisabled] = useState(getInitialBooleanState("buttonDisabled", true)); // State to control button disabled
    const [progress, setProgress] = useState(0)
    const [transcriptionId, setTranscriptionId] = useState(getInitialTranscriptionId);
    const [uploading, setUploading] = useState(getInitialBooleanState("uploading",false));
    const [statusText, setStatusText] = useState(getInitialTranscriptionStatus);
    const [dataSize, setDataSize] = useState(getInitialInteger("dataSize"));
    const [percentageDone, setPercentageDone] = useState(getInitialInteger("percentageDone"));
    const [transcriptionStartTime, setTranscriptionStartTime] = useState(getInitialTranscriptionStartTime);
    const [scanning, setScanning] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const [modelSize, setModelSize] = useState(getInitialString("modelSize", "large-v3"))
    const [language, setLanguage] = useState(getInitialString("language", "auto"))

    useEffect(() => {
        sessionStorage.setItem("modelSize", JSON.stringify(modelSize))
    }, [modelSize]);
    useEffect(() => {
        sessionStorage.setItem("language", JSON.stringify(language))
    }, [language]);
    useEffect(() => {
        sessionStorage.setItem("results", JSON.stringify(results))
    }, [results]);
    useEffect(() => {
        sessionStorage.setItem("activeTask", JSON.stringify(activeTask))
    }, [activeTask]);
    useEffect(() => {
        sessionStorage.setItem("buttonDisabled", JSON.stringify(buttonDisabled))
    }, [buttonDisabled]);
    useEffect(() => {
        sessionStorage.setItem("transcribing", JSON.stringify(transcribing))
    }, [transcribing]);
    useEffect(() => {
        // file objects cannot be serialized properly with JSON.stringify. If we really want this serialization to the session we must pick metadata or store using library
        if (files.length === 0 && scannedAndLinkedFiles.length === 0) {
            setButtonDisabled(true);
        } else if (!transcribing) {
            setButtonDisabled(false);
        }
    }, [files, scannedAndLinkedFiles]);
    useEffect(() => {
        sessionStorage.setItem("transcriptionId", JSON.stringify(transcriptionId))
    }, [transcriptionId]);
    useEffect(() => {
        sessionStorage.setItem("statusText", JSON.stringify(statusText))
    }, [statusText]);
    useEffect(() => {
        sessionStorage.setItem("uploading", JSON.stringify(uploading))
    }, [uploading]);
    useEffect(() => {
        sessionStorage.setItem("dataSize", JSON.stringify(dataSize))
    }, [dataSize]);
    useEffect(() => {
        sessionStorage.setItem("percentageDone", JSON.stringify(percentageDone))
    }, [percentageDone]);
    useEffect(() => {
        sessionStorage.setItem("transcriptionStartTime", JSON.stringify(transcriptionStartTime))
    }, [transcriptionStartTime]);

    // Function for showing or hiding the settings
    const showOrHideSettings = () => {
        setShowSettings(!showSettings);
    }

    // Function to poll the server for transcription status
    const pollTranscriptionStatus = useCallback((taskId) => {
        console.debug("Running poll funtion.")
        fetch(`http://localhost:8000/poll-transcription-status/${taskId}/`)
            .then(response => response.json())
            .then(data => {
                // debug logging the data returned from the server
                console.debug('Task status:', data);
                if (data.state === 'SUCCESS') {
                    console.debug('Task result:', data.result);
                    setResults(data.result);
                    setTranscriptionId(null);
                    setTranscribing(false);
                    setDataSize(0);
                    setTranscriptionStartTime(null);
                    if (files.length === 0 && scannedAndLinkedFiles.length === 0) {
                        setButtonDisabled(true);
                    }
                    setActiveTask([]);
                    setPercentageDone(0);
                } else if (data.state === 'FAILURE') {
                    setTranscriptionId(null);
                    setTranscribing(false);
                    setDataSize(0);
                    setTranscriptionStartTime(null);
                    setActiveTask([]);
                    setPercentageDone(0);
                    console.error('Task failed:', data.status);
                } else {
                    // Task is still processing, poll again after a delay
                    setTimeout(() => pollTranscriptionStatus(taskId), 5000);
                    let dataText = "";
                    if (dataSize > 1000000000) {
                        dataText = (dataSize / 1000000000).toFixed(2) + " GB";
                    } else {
                        dataText = (dataSize / 1000000).toFixed(2) + " MB";
                    }
                    let duration = Date.now() - transcriptionStartTime;
                    let waitingText = "Transcribing " + dataText + " of Data. The transcription time on a GPU can be roughly estimated to 1 minute pr. 1 MB of data. ";
                    waitingText += "Total duration of the transcription so far is: " + formatDuration(duration);
                    setStatusText(waitingText);
                    let expectedDurationSeconds = Math.floor(dataSize / 1000000 * 60)
                    let durationSeconds = Math.floor(duration / 1000 )
                    let percentage = durationSeconds / expectedDurationSeconds;
                    // don't show higher progress percentage than 90 %
                    setPercentageDone(percentage < 0.9 ? percentage : 0.9);
                }
            })
            .catch(error => {
                console.error('Error polling task:', error);
            });
    }, [dataSize, transcriptionStartTime]);

    // effect for starting to poll the server for transcription status if there is an active taskID
    useEffect(() => {
        console.debug("Checking for active transcription ID.");
        transcriptionId ? setTimeout(() => pollTranscriptionStatus(transcriptionId), 5000) : console.log("No active transcription task to poll.")
    }, [transcriptionId, pollTranscriptionStatus])

    // Separate the log files, grouped files, and the zip file
    const { logFiles, groupedFiles, zipFile } = results.reduce((acc, result) => {
        const fileName = result.file_name;
        if (fileName === 'transcribe.log' || fileName === 'transcriber_output.txt') {
            acc.logFiles.push(result);
        } else if (fileName === 'files.zip') {
            acc.zipFile = result;
        } else {
            const key = fileName.split('.')[0];
            if (!acc.groupedFiles[key]) {
                acc.groupedFiles[key] = [];
            }
            acc.groupedFiles[key].push(result);
        }
        return acc;
    }, { logFiles: [], groupedFiles: {}, zipFile: null });

    // Calculate the maximum number of files in any group
    const maxFilesInGroup = Math.max(...Object.values(groupedFiles).map(group => group.length), 0);

    const getFileExtension = (fileName) => {
        const specialCases = ['dote.json'];
        for (const ext of specialCases) {
            if (fileName.endsWith(ext)) {
                return ext;
            }
        }
        return fileName.split('.').pop();
    };

    // Upload files and start a transcription on the server
    const onTranscribe = async (e) => {
        e.preventDefault();
        setButtonDisabled(true); // Disable the button
        setUploading(true)
        setShowSettings(false); // hide settings

        let totalDataSizeBytes = 0;
        const formData = new FormData();
        files.forEach((file) => {
            formData.append('files', file);
            totalDataSizeBytes += file.size;
        });
        formData.append('model', modelSize);
        formData.append('language', language);
        // also sum datasize for linked UCloud files
        scannedAndLinkedFiles.forEach((file) => {
            totalDataSizeBytes += file.size;
        })
        setDataSize(totalDataSizeBytes);
        setTranscriptionStartTime(Date.now())

        try {
            const response = await axios.post('http://localhost:8000/upload/', formData, {
                onUploadProgress: (progressEvent) => {
                    const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                    setProgress(percentCompleted);
                },
                //headers: {
                //    'X-CSRFToken': csrfToken
                //}
            });
            console.debug('the transcription id is: ' + response.data.task_id)
            setTranscriptionId(response.data.task_id)
            // update the list of files that is currently worked on
            let activeTranscriptionList = [];
            files.forEach((file) => {
                addFileDataToList(file,activeTranscriptionList, false)
            });
            scannedAndLinkedFiles.forEach((file) => {
                addFileDataToList(file, activeTranscriptionList, true)
            });
            setActiveTask(activeTranscriptionList);
        } catch (error) {
            console.error('Error uploading file:', error);
        } finally {
            setUploading(false);
            setTranscribing(true);
            setStatusText('Starting to transcribe selected files...');
            setProgress(0);
            setFiles([]);
            setRejected([]);
            setScannedAndLinkedFiles([]);
        }
    };

    const addFileDataToList = (file, list, ucloud) => {
        list.push({
            "name": file.name,
            "size": file.size,
            "ucloud": ucloud
        })
    }

    const onScan = async (e) => {
        e.preventDefault();
        setScanning(true); // Disable the scan button
        try {
            const response = await fetch('http://localhost:8000/scan-files/');
            const fileList = await response.json();
            //console.debug('Scanned files:', fileList);
            setScannedFiles(fileList)
        } catch (error) {
            console.error('Error scanning UCloud mounted folder for upload files:', error);
        } finally {
            setScanning(false);
        }
    }

    const onAddUcloudFiles = async (filesToAdd) => {
        if (filesToAdd?.length > 0) {
            let formData = new FormData();
            formData.append('files', JSON.stringify(filesToAdd));
            try {
                // call view to create the symlinks
                const response = await axios.post('http://localhost:8000/link-files/', formData);
                // add the files to setScannedAndLinkedFiles
                if (response.status === 200) {
                    let newFiles = filesToAdd.filter((file) =>
                        !scannedAndLinkedFiles.some(scannedFile => scannedFile.filepath === file.filepath));
                    setScannedAndLinkedFiles(previousFiles => [
                        ...previousFiles,
                        ...newFiles
                    ])
                } else {
                    console.error("Error from server when creating links to UCLoud files.")
                }
            } catch (error) {
                console.error('Error creating symlinks for UCloud files:', error);
            } finally {
            }
        }
    }

    const onUpdateModel = (modelSize) => {
        setModelSize(modelSize)
    }

    const onUpdateLanguage = (language) => {
        setLanguage(language)
    }

    const onDrop = useCallback((acceptedFiles, rejectedFiles) => {
        if (acceptedFiles?.length) {
            if (!transcribing) {
                setButtonDisabled(false);
            }
            setFiles(previousFiles => [
                ...previousFiles,
                ...acceptedFiles
            ])
        }
        setRejected([...rejectedFiles])
    }, [transcribing]);

    const removeFile = (name) => {
        setFiles(files => files.filter(file => file.name !== name))
    }

    const removeUCloudLinkedFile = async (path) => {
        if (path) {
            let formData = new FormData();
            formData.append('path', path);
            try {
                // call view to remove the symbolic link to the UCloud file
                const response = await axios.post('http://localhost:8000/remove-link/', formData);
                if (response.status === 200) {
                    // remove the file in the list of linked files to update the UI
                    setScannedAndLinkedFiles(files => files.filter(file => file.target_path_sym_link !== path))
                } else {
                    console.error("Error from server when removing link to UCLoud file.")
                }
            } catch (error) {
                console.error('Error removing symlink for UCloud file:', error);
            } finally {
            }
        }
    }

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            "audio/mpeg": [".mp3"],
            "audio/wav": [".wav"],
            "audio/x-m4a": [".m4a"],
            "video/mp4": [".mp4"],
            "video/mpeg": [".mpeg"]
        }
    });

    return (
        <div className="App">
            <div className="title-container">
                <img src={transcriberImage} alt="Transcriber" className="centered-image"/>
            </div>
            <div {...getRootProps({className: 'dropzone'})}>
                <input {...getInputProps()} />
                {
                    isDragActive ?
                        <p>Drop the files here ...</p> :
                        <p>Drag 'n' drop file(s) here, or click to select file(s)</p>
                }
            </div>
            {
                (!transcribing && results.length === 0) && (
                    <p className='helpText'>
                        This application can help you transcribe audio and video files.
                        When files are dropped into the area above the 'Selected files' list shows which files are selected
                        for transcription.
                        When you are happy with the selection press the 'Transcribe' button to start a transcription on the
                        selected files.
                    </p>
                )
            }
            {(files.length > 0 || scannedAndLinkedFiles.length > 0 ) > 0 && (
                <h2>Selected files</h2>
            )}
            {
                files.length > 0 && files.map((file, index) => (
                    <ul key={index}>
                        <li key={file.name + index}> {file.name} &nbsp;
                            <button type='button' onClick={() => removeFile(file.name)}>Remove</button>
                        </li>
                    </ul>
                ))
            }
            {
                scannedAndLinkedFiles.length > 0 && scannedAndLinkedFiles.map((file, index) => (
                    <ul key={index}>
                        <li key={file.name + index}> {file.name} &nbsp;
                            <button type='button' onClick={() => removeUCloudLinkedFile(file.target_path_sym_link)}>Remove</button>
                            <span className="ucloud-file">UCloud file</span>
                        </li>
                    </ul>
                ))
            }
            {rejected.length > 0 && (
                <h2>Rejected files</h2>
            )}
            {
                rejected.length > 0 && rejected.map((file, index) => (
                    <ul key={index}>
                        <li key={file.file.name + index}>
                            <div>
                                <p>
                                    {file.file.name}
                                </p>
                                <ul>
                                    {file.errors.map(error => (
                                        <li key={error.code} className="fileTypeError"> {error.message}</li>
                                    ))}
                                </ul>
                            </div>
                        </li>
                    </ul>
                ))
            }

            <button
                type='submit'
                onClick={(e) => onTranscribe(e)}
                className='transcribe-button'
                disabled={buttonDisabled} // Bind the button's disabled attribute to the state
            >
                Start transcription {transcribing &&
                <Spinner loading={transcribing}/>} {/* Show spinner next to the button */}
            </button>

            <button
                type='submit'
                onClick={showOrHideSettings}
                className='transcribe-button'
            >
                Show / Hide settings
            </button>

            {
                showSettings && (
                    <Settings
                        onScan={onScan}
                        onAddUcloudFiles={onAddUcloudFiles}
                        scanning={scanning}
                        transcribing={transcribing}
                        uploading={uploading}
                        scannedFiles={scannedFiles}
                        onUpdateModel={onUpdateModel}
                        currentModelSize={modelSize}
                        onUpdateLanguage={onUpdateLanguage}
                        currentLanguage={language}
                    />
                )
            }

            {
                (uploading || transcribing) && (
                    <h2>Status</h2>
                )
            }
            {
                uploading && (
                    <p>Uploading {progress} %</p>
                )
            }
            {
                transcribing && (
                    <TranscriptionStatus
                        statusText={statusText}
                        activeTask={activeTask}
                        percentageDone={percentageDone}
                    />
                )
            }

            {results.length > 0 && (
                <div>
                    <h3>Transcribed files</h3>
                    <div>
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
                                            <a href={result.file_url} rel="noreferrer" className="button" download>
                                                {getFileExtension(result.file_name)}
                                            </a>
                                        </td>
                                    ))}
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </div>

                    {zipFile && (
                        <div>
                            <h3>Zip file</h3>
                            <div>
                                <p>The zip file contains all the transcribed files for easy download.</p>
                                <a href={zipFile.file_url} rel="noreferrer" download>Download zip file.</a>
                            </div>
                        </div>
                    )}
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
                    <br/>
                    <br/>
                </div>
            )}
        </div>
    );
}

export default App;
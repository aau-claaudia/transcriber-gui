import React, {useCallback, useState, useEffect, useRef} from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
//import Spinner  from './spinners'
import { csrfToken } from './csrf';
import Settings from "./Settings";
import TranscriptionStatus from "./TranscriptionStatus";
import Results from "./Results";
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
    const [transcribing, setTranscribing] = useState(getInitialBooleanState("transcribing",false));
    const [buttonDisabled, setButtonDisabled] = useState(getInitialBooleanState("buttonDisabled", true));
    const [progress, setProgress] = useState(0)
    const [transcriptionId, setTranscriptionId] = useState(getInitialTranscriptionId);
    const transcriptionIdRef = useRef(transcriptionId);
    const [uploading, setUploading] = useState(getInitialBooleanState("uploading",false));
    const [statusText, setStatusText] = useState(getInitialTranscriptionStatus);
    const [dataSize, setDataSize] = useState(getInitialInteger("dataSize"));
    const [percentageDone, setPercentageDone] = useState(getInitialInteger("percentageDone"));
    const [transcriptionStartTime, setTranscriptionStartTime] = useState(getInitialTranscriptionStartTime);
    const [scanning, setScanning] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const [modelSize, setModelSize] = useState(getInitialString("modelSize", "large-v3"))
    const [language, setLanguage] = useState(getInitialString("language", "auto"))
    const [errorState, setErrorState] = useState(false);

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
    // Keep the ref updated with the latest transcriptionId
    useEffect(() => {
        transcriptionIdRef.current = transcriptionId;
    }, [transcriptionId]);

    // Function for showing or hiding the settings
    const showOrHideSettings = () => {
        setShowSettings(!showSettings);
    }

    // Function to poll the server for transcription status
    const pollTranscriptionStatus = useCallback((taskId) => {
        console.debug("Running poll funtion.")
        console.debug("Transcriptionid = " + taskId)
        if (taskId) {
            fetch(`/poll-transcription-status/${taskId}/`)
                .then(response => response.json())
                .then(data => {
                    // debug logging the data returned from the server
                    console.debug('Task status:', data);
                    if (data.state === 'SUCCESS') {
                        if (!(data.status === 'TASK ABORTED')) {
                            console.debug('Task result:', data.result);
                            setResults(data.result);
                        }
                        setTranscriptionId(null);
                        setTranscribing(false);
                        setDataSize(0);
                        setTranscriptionStartTime(null);
                        setActiveTask([]);
                        setPercentageDone(0);
                        if (files.length > 0 || scannedAndLinkedFiles.length > 0) {
                            setButtonDisabled(false);
                        }
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
                        setTimeout(() => pollTranscriptionStatus(transcriptionIdRef.current), 5000);
                        let dataText = "";
                        if (dataSize > 1000000000) {
                            dataText = (dataSize / 1000000000).toFixed(2) + " GB";
                        } else {
                            dataText = (dataSize / 1000000).toFixed(2) + " MB";
                        }
                        let duration = Date.now() - transcriptionStartTime;
                        let waitingText = "Transcribing " + dataText + " of data. The transcription time on a GPU can be roughly estimated to 1 minute pr. 1 MB of data. ";
                        waitingText += "Total duration of the transcription so far is: " + formatDuration(duration);
                        setStatusText(waitingText);
                        let expectedDurationSeconds = Math.floor(dataSize / 1000000 * 60)
                        let durationSeconds = Math.floor(duration / 1000)
                        let percentage = durationSeconds / expectedDurationSeconds;
                        // don't show higher progress percentage than 90 %
                        setPercentageDone(percentage < 0.9 ? percentage : 0.9);
                    }
                })
                .catch(error => {
                    console.error('Error polling task:', error);
                });
        } else {
            console.debug("Transcription task was cancelled.")
        }
    }, [dataSize, transcriptionStartTime, files, scannedAndLinkedFiles, transcriptionId]);

    // effect for starting to poll the server for transcription status if there is an active transcriptionId
    useEffect(() => {
        console.debug("Checking for active transcription ID.");
        transcriptionId ? setTimeout(() => pollTranscriptionStatus(transcriptionIdRef.current), 5000) : console.log("No active transcription task to poll.")
    }, [transcriptionId, pollTranscriptionStatus])

    // Separate the log files, grouped files, and the zip file
    const { logFiles, groupedFiles, groupedFilesMergedFormat, zipFile } = results.reduce((acc, result) => {
        const fileName = result.file_name;
        if (fileName === 'transcribe.log' || fileName === 'transcriber_output.txt') {
            acc.logFiles.push(result);
        } else if (fileName === 'files.zip') {
            acc.zipFile = result;
        } else {
            const key = fileName.split('.')[0];
            if (key.endsWith('_merged')) {
                if (!acc.groupedFilesMergedFormat[key]) {
                    acc.groupedFilesMergedFormat[key] = [];
                }
                acc.groupedFilesMergedFormat[key].push(result);
            } else {
                if (!acc.groupedFiles[key]) {
                    acc.groupedFiles[key] = [];
                }
                acc.groupedFiles[key].push(result);
            }
        }
        return acc;
    }, { logFiles: [], groupedFiles: {}, groupedFilesMergedFormat: {},zipFile: null });

    // transform the rejected file data to group the files by the error type
    const groupedErrors = rejected.reduce((acc, file) => {
        file.errors.forEach(error => {
            if (!acc[error.message]) {
                acc[error.message] = [];
            }
            acc[error.message].push(file.file.name);
        });
        return acc;
    }, {});

    // Calculate the maximum number of files in any group
    const maxFilesInGroup = Math.max(...Object.values(groupedFiles).map(group => group.length), 0);

    // Upload files and start a transcription on the server
    const onTranscribe = async (e) => {
        e.preventDefault();
        setButtonDisabled(true); // Disable the button
        setUploading(true)
        setShowSettings(false); // hide settings
        setErrorState(false);

        let totalDataSizeBytes = 0;
        const formData = new FormData();
        // also create file meta data object to use for file size validation on uploads on the server side
        const fileMetaDataForValidation = [];
        files.forEach((file) => {
            formData.append('files', file);
            totalDataSizeBytes += file.size;
            fileMetaDataForValidation.push({
                "filepath": "",
                "name": file.name,
                "size": file.size,
                "target_path_sym_link": "",
            })
        });
        formData.append('file_meta_data', JSON.stringify(fileMetaDataForValidation));
        formData.append('model', modelSize);
        formData.append('language', language);
        // also sum datasize for linked UCloud files
        scannedAndLinkedFiles.forEach((file) => {
            totalDataSizeBytes += file.size;
        })
        setDataSize(totalDataSizeBytes);
        setTranscriptionStartTime(Date.now())

        try {
            const response = await axios.post('/upload/', formData, {
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
            setUploading(false);
            setTranscribing(true);
            setStatusText('Starting to transcribe selected files...');
        } catch (error) {
            console.error('Error uploading file:', error);
            setUploading(false);
            setStatusText("Something went wrong when trying to upload files.")
            setErrorState(true);
        } finally {
            setProgress(0);
            resetFileArrays()
        }
    };

    const resetData = () => {
        setTranscriptionId(null);
        setTranscribing(false);
        setDataSize(0);
        setTranscriptionStartTime(null);
        setActiveTask([]);
        setPercentageDone(0);
        resetFileArrays()
    }

    const onStopTranscription = async (e) => {
        // send stop request to backend
        console.debug("Stopping transcription.")
        if (transcriptionId) {
            fetch(`/stop_transcription_task/${transcriptionId}/`)
                .then(response => response.json())
                .then(data => {
                    // debug logging the data returned from the server
                    console.debug('Task status:', data);
                })
                .catch(error => {
                    console.error('Error stopping task:', error);
                });
        } else {
            console.debug("No active transcription id, nothing to stop.")
        }
        // reset data
        resetData();
    };

    const resetFileArrays = () => {
        setFiles([]);
        setRejected([]);
        setScannedAndLinkedFiles([]);
    }

    const addFileDataToList = (file, list, ucloud) => {
        list.push({
            "name": file.name,
            "size": file.size,
            "ucloud": ucloud
        })
    }

    const onScan = async (e) => {
        e.preventDefault();
        setErrorState(false);
        setScanning(true); // Disable the scan button
        try {
            const response = await fetch('/scan-files/');
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
        setErrorState(false);
        if (filesToAdd?.length > 0) {
            let formData = new FormData();
            formData.append('files', JSON.stringify(filesToAdd));
            try {
                // call view to create the symlinks
                const response = await axios.post('/link-files/', formData);
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
        setErrorState(false);
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
                const response = await axios.post('/remove-link/', formData);
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
                        <div>
                            <p>Drop the files here ...</p>
                        </div>
                        :
                        <div>
                            <p>Drag 'n' drop file(s) here, or click to browse from your computer.</p>
                        </div>
                }
            </div>
            {
                (!transcribing && results.length === 0) && (
                    <div>
                    <p className='helpText'>
                        This application enables you to transcribe audio and video files. When files are dropped into the area above the <b>Selected files</b> list shows which files are selected for transcription.
                        Choose <b>Show settings</b> if you need to modify the transcription model and/or language (default <b>large-v3</b> and <b>Automatic</b> respectively) or if you want to add files from a UCloud folder.
                    </p>
                    <p className='helpText'>
                        When you are happy with the selection press the <b>Start transcription</b> button to start the transcription of the selected files.
                    </p>
                    </div>
                )
            }
            {(files.length > 0 || scannedAndLinkedFiles.length > 0) > 0 && (
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
                Object.keys(groupedErrors).length > 0 && Object.keys(groupedErrors).map((errorMessage, index) => (
                    <ul key={index}>
                        <li key={errorMessage + index}>
                            <div>
                                <p className="fileTypeError">{errorMessage}</p>
                                <ul>
                                    {groupedErrors[errorMessage].map((fileName, fileIndex) => (
                                        <li key={fileName + fileIndex}>{fileName}</li>
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
                style={{width: '200px'}}
                className='transcribe-button'
                disabled={buttonDisabled} // Bind the button's disabled attribute to the state
            >
                {transcribing ? 'In progress' : 'Start transcription'}
            </button>

            <button
                type='submit'
                onClick={(e) => onStopTranscription(e)}
                style={{width: '200px'}}
                className='transcribe-stop-button'
                disabled={!transcribing} // Stop button is enabled when we are transcribing
            >
                Stop transcription
            </button>

            <button
                type='submit'
                onClick={showOrHideSettings}
                style={{width: '200px'}}
                className='transcribe-button'
            >
                {showSettings ? 'Hide settings' : 'Show settings'}
            </button>

            {
                showSettings && (
                    <Settings
                        onScan={onScan}
                        onAddUcloudFiles={onAddUcloudFiles}
                        scanning={scanning}
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
                errorState && (
                    <p>{statusText}</p>
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
                <Results
                    zipFile={zipFile}
                    maxFilesInGroup={maxFilesInGroup}
                    groupedFiles={groupedFiles}
                    groupedFilesMergedFormat={groupedFilesMergedFormat}
                    logFiles={logFiles}
                />
            )}
        </div>
    );
}

export default App;
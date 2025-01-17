import React, {useState} from 'react';
import Spinner from "./spinners";

const Settings = ({ onScan, onAddUcloudFiles, scanning, scannedFiles, onUpdateModel, currentModelSize, onUpdateLanguage, currentLanguage}) => {
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

    // Function to handle model change
    const handleModelChange = (event) => {
        onUpdateModel(event.target.value);
    };

    // Function to handle model change
    const handleLangaugeChange = (event) => {
        onUpdateLanguage(event.target.value);
    };

    return (
        <div>
            {/* Section for setting a model */}
            <div>
                <h3>Select Model</h3>
                <div className="select-box">
                    <select defaultValue={currentModelSize} onChange={handleModelChange}>
                        <option value="base">base</option>
                        <option value="small">small</option>
                        <option value="medium">medium</option>
                        <option value="large-v3">large-v3</option>
                        <option value="large-v3-turbo">large-v3-turbo</option>
                    </select>
                </div>
            </div>
            <hr/>

            {/* Section for setting a language */}
            <div>
                <h3>Select Language</h3>
                <div className="select-box">
                    <select defaultValue={currentLanguage} onChange={handleLangaugeChange}>
                        <option value="auto">Automatic</option>
                        <option value="af">Afrikaans</option>
                        <option value="sq">Albanian</option>
                        <option value="am">Amharic</option>
                        <option value="ar">Arabic</option>
                        <option value="hy">Armenian</option>
                        <option value="as">Assamese</option>
                        <option value="az">Azerbaijani</option>
                        <option value="ba">Bashkir</option>
                        <option value="eu">Basque</option>
                        <option value="be">Belarusian</option>
                        <option value="bn">Bengali</option>
                        <option value="bs">Bosnian</option>
                        <option value="br">Breton</option>
                        <option value="bg">Bulgarian</option>
                        <option value="ca">Catalan</option>
                        <option value="zh">Chinese</option>
                        <option value="hr">Croatian</option>
                        <option value="cs">Czech</option>
                        <option value="da">Danish</option>
                        <option value="nl">Dutch</option>
                        <option value="en">English</option>
                        <option value="et">Estonian</option>
                        <option value="fo">Faroese</option>
                        <option value="fi">Finnish</option>
                        <option value="fr">French</option>
                        <option value="ka">Georgian</option>
                        <option value="de">German</option>
                        <option value="gl">Galician</option>
                        <option value="el">Greek</option>
                        <option value="gu">Gujarati</option>
                        <option value="ht">Haitian creole</option>
                        <option value="ha">Hausa</option>
                        <option value="haw">Hawaiian</option>
                        <option value="he">Hebrew</option>
                        <option value="hi">Hindi</option>
                        <option value="hu">Hungarian</option>
                        <option value="id">Indonesian</option>
                        <option value="is">Icelandic</option>
                        <option value="it">Italian</option>
                        <option value="ja">Japanese</option>
                        <option value="jw">Javanese</option>
                        <option value="kn">Kannada</option>
                        <option value="kk">Kazakh</option>
                        <option value="km">Khmer</option>
                        <option value="ko">Korean</option>
                        <option value="lo">Lao</option>
                        <option value="la">Latin</option>
                        <option value="lv">Latvian</option>
                        <option value="ln">Lingala</option>
                        <option value="lt">Lithuanian</option>
                        <option value="lb">Luxembourgish</option>
                        <option value="mk">Macedonian</option>
                        <option value="mg">Malagasy</option>
                        <option value="ms">Malay</option>
                        <option value="ml">Malayalam</option>
                        <option value="mt">Maltese</option>
                        <option value="mi">Maori</option>
                        <option value="mr">Marathi</option>
                        <option value="mn">Mongolian</option>
                        <option value="my">Myanmar</option>
                        <option value="ne">Nepali</option>
                        <option value="no">Norwegian</option>
                        <option value="nn">Nynorsk</option>
                        <option value="oc">Occitan</option>
                        <option value="ps">Pashto</option>
                        <option value="fa">Persian</option>
                        <option value="pl">Polish</option>
                        <option value="pt">Portuguese</option>
                        <option value="pa">Punjabi</option>
                        <option value="ro">Romanian</option>
                        <option value="ru">Russian</option>
                        <option value="sa">Sanskrit</option>
                        <option value="sr">Serbian</option>
                        <option value="sn">Shona</option>
                        <option value="si">Sinhala</option>
                        <option value="sd">Sindhi</option>
                        <option value="sk">Slovak</option>
                        <option value="sl">Slovenian</option>
                        <option value="so">Somali</option>
                        <option value="es">Spanish</option>
                        <option value="su">Sundanese</option>
                        <option value="sw">Swahili</option>
                        <option value="sv">Swedish</option>
                        <option value="tl">Tagalog</option>
                        <option value="tg">Tajik</option>
                        <option value="ta">Tamil</option>
                        <option value="tt">Tatar</option>
                        <option value="te">Telugu</option>
                        <option value="th">Thai</option>
                        <option value="bo">Tibetan</option>
                        <option value="tr">Turkish</option>
                        <option value="tk">Turkmen</option>
                        <option value="uk">Ukrainian</option>
                        <option value="ur">Urdu</option>
                        <option value="uz">Uzbek</option>
                        <option value="vi">Vietnamese</option>
                        <option value="cy">Welsh</option>
                        <option value="yi">Yiddish</option>
                        <option value="yo">Yoruba</option>
                    </select>
                </div>
            </div>
            <hr/>

            {/* Section for scan button and file list */}
            <div style={{display: 'flex'}}>
                <div>
                    <h3>Select UCloud files</h3>
                    <button
                        type='submit'
                        style={{width: '200px'}}
                        onClick={(e) => onScan(e)}
                        className='transcribe-button'
                        disabled={scanning}
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
                        Click the button to scan the UCloud folder. Only audio and video files will appear in the
                        list.
                        Folders with the name 'uploads' will not be scanned, as this is reserved by the application.
                    </p>
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
                                <td><input type="checkbox" onChange={() => handleAddFile(file)}/></td>
                                <td>{file.name}</td>
                                <td title={file.filepath} style={{
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    maxWidth: '200px'
                                }}>{file.filepath}</td>
                                <td>{(file.size / 1000000).toFixed(2)}</td>
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
from celery import shared_task
from celery.contrib.abortable import AbortableTask
import subprocess
import os
import shutil
import signal
import logging
import json
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task(bind=True, base=AbortableTask)
def transcription_task(self, model_size, language):
    logger.info('Starting the transcription task now...')
    directory_path: str = os.path.join(settings.MEDIA_ROOT, 'UPLOADS/INPUT')

    # Use a temporary output directory during the transcription run
    output_dir_path: str = os.path.join(settings.MEDIA_ROOT, 'TRANSCRIPTIONS_TEMP')
    os.makedirs(output_dir_path, exist_ok=True)
    transcriber_output_file: str = os.path.join(output_dir_path, "transcriber_output.txt")
    process = None  # Initialize the process variable

    try:
        # Prepare the command based on the language
        if language == 'auto':
            command = [
                'python', 'transcriber/aau-whisper/app.py', '--job_name', 'files',
                '-o', output_dir_path, '-m', model_size, '--input_dir', directory_path,
                '--merge_speakers', '--threads', '4', '--transcriber_gui'
            ]
        else:
            command = [
                'python', 'transcriber/aau-whisper/app.py', '--job_name', 'files',
                '-o', output_dir_path, '-m', model_size, '--language', language,
                '--input_dir', directory_path, '--merge_speakers', '--threads', '4',
                '--transcriber_gui'
            ]

        # Start the subprocess
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Capture the output and error after the process completes
        output, error = process.communicate()
        write_transcriber_output(error, output, transcriber_output_file, directory_path, model_size)

        # Distribute files to separate directories for each input file
        input_files = [f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]
        for filename in input_files:
            filename_without_ext, _ = os.path.splitext(filename)
            base_transcription_key = f"{filename_without_ext}_{model_size}_{language}"
            transcription_key = build_unique_transcription_key(settings.MEDIA_ROOT, base_transcription_key)
            transcription_dir = os.path.join(settings.MEDIA_ROOT, transcription_key)

            trans_dir = os.path.join(transcription_dir, 'TRANSCRIPTIONS')
            comp_dir = os.path.join(transcription_dir, 'COMPLETED')
            data_dir = os.path.join(transcription_dir, 'data')

            os.makedirs(trans_dir, exist_ok=True)
            os.makedirs(comp_dir, exist_ok=True)
            os.makedirs(data_dir, exist_ok=True)


            # Move the input file from UPLOADS/INPUT to the COMPLETED folder in the new directory
            src_file = os.path.join(directory_path, filename)
            dst_file = os.path.join(comp_dir, filename)
            shutil.move(src_file, dst_file)
            logger.info(f"Moved input file: {src_file} to {dst_file}")

            # Move matching output files from TRANSCRIPTIONS_TEMP to TRANSCRIPTIONS
            for out_item in os.listdir(output_dir_path):
                if out_item.startswith(filename_without_ext):
                    src_out = os.path.join(output_dir_path, out_item)
                    dst_out = os.path.join(trans_dir, out_item)
                    shutil.move(src_out, dst_out)

            # Copy transcription output log files and zip archive
            for file_to_copy in ["transcriber_output.txt", "transcribe.log", "files.zip"]:
                src_path = os.path.join(output_dir_path, file_to_copy)
                if os.path.exists(src_path):
                    shutil.copy(src_path, os.path.join(trans_dir, file_to_copy))

            # Copy .dote.json to /data/edited_output.json
            edit_file_name = "edited_output.json"
            edited_output_file = os.path.join(data_dir, edit_file_name)
            dote_file = next(
                (
                    os.path.join(trans_dir, item)
                    for item in os.listdir(trans_dir)
                    if item.endswith(".dote.json") and not item.endswith("_merged.dote.json")
                ),
                None,
            )
            if os.path.exists(src_path):
                shutil.copy(dote_file, edited_output_file)
            # annotate output file for editing with ids
            annotate_with_ids(edited_output_file)

            # Write metadata.json
            metadata_content = {
                "input_file_name": filename,
                "input_file_url": f"/media/{transcription_key}/COMPLETED/{filename}",
                "edit_file_url": f"/media/{transcription_key}/data/{edit_file_name}",
            }
            metadata_file = os.path.join(data_dir, 'metadata.json')
            with open(metadata_file, 'w') as mf:
                json.dump(metadata_content, mf, indent=4)

    except subprocess.CalledProcessError as e:
        write_transcriber_output(e.stderr, e.stdout, transcriber_output_file, directory_path, model_size)

    finally:
        # Ensure the subprocess is terminated if it is still running
        if process and process.poll() is None:
            # this is only executed if the task was revoked before the proces could complete
            logger.info("Transcription task was aborted. Terminating subprocess...")
            process.terminate()  # Terminate the subprocess
            process.wait()  # Wait for the process to terminate
            logger.info("Process terminated.")
            # clean up the input files
            clean_dir(directory_path)

        # Clean up the TRANSCRIPTIONS_TEMP directory
        if os.path.exists(output_dir_path):
            shutil.rmtree(output_dir_path)

    return "Task completed"

@shared_task(bind=True, base=AbortableTask)
def shutdown_server_task(model_size, language, master_pid):
    """
    A Celery task to gracefully shut down the server.
    """
    logger.info("Transcription task has finished, stopping server.")
    try:
        #logging.debug(f"Shutting down Gunicorn master process (PID: {master_pid})...")
        # SIGTERM is a more common signal for graceful shutdown.
        os.kill(master_pid, signal.SIGTERM)
        # and shut down the celery worker
        os.kill(os.getppid(), signal.SIGTERM)
    except Exception as e:
        logging.warning(f"Error shutting down server: {e}")

def write_transcriber_output(error, output, transcriber_output_file, directory: str, model: str, ):
    # create a list of input files
    path = Path(directory)
    # Check if the path exists and is a directory
    if not path.exists():
        logger.error(f"Error when writing transcription output: The path '{directory}' does not exist.")
        return []
    if not path.is_dir():
        logger.error(f"Error when writing transcription output: '{directory}' is not a directory.")
        return []
    # Iterate through the directory and filter for files
    input_file_list = [item.name for item in path.iterdir() if item.is_file()]
    output_header = f"Model: {model}, Input files:\n"
    for file_name in input_file_list:
        output_header = output_header + f"{file_name}\n"
    with open(transcriber_output_file, 'a') as t_file:
        t_file.write(output_header)
        t_file.write(output)
        t_file.write(error)

def clean_dir(directory):
    for item in os.listdir(directory):
        source_path = os.path.join(directory, item)
        # Check if the item is a file (not a directory)
        if os.path.isfile(source_path):
            os.remove(source_path)
            #logging.debug(f"Removed file: {source_path}")

def annotate_with_ids(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        for i, line in enumerate(data.get('lines', [])):
            data['lines'][i] = {'id': i, **line}

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

    except Exception as e:
        logger.error(f"Error when creating IDs for output file for editing '{file_path}': {e}")

def build_unique_transcription_key(media_root: str, base_key: str) -> str:
    """Return a collision-safe key by appending _runN when needed."""
    candidate = base_key
    suffix = 2

    while os.path.exists(os.path.join(media_root, candidate)):
        candidate = f"{base_key}_run{suffix}"
        suffix += 1

    return candidate
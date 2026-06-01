from celery import shared_task
from celery.contrib.abortable import AbortableTask
import subprocess
import os
import shutil
import signal
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task(bind=True, base=AbortableTask)
def transcription_task(self, model_size, language):
    logger.info('Starting the transcription task now...')
    directory_path: str = os.path.join(settings.MEDIA_ROOT, 'UPLOADS/INPUT')
    output_dir_path: str = os.path.join(settings.MEDIA_ROOT, 'TRANSCRIPTIONS/')
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

    # moved uploaded files from the input directory to COMPLETED folder
    transcribed_path: str = os.path.join(settings.MEDIA_ROOT, 'COMPLETED')
    os.makedirs(transcribed_path, exist_ok=True)

    for item in os.listdir(directory_path):
        source_path = os.path.join(directory_path, item)
        target_path = os.path.join(transcribed_path, item)
        # Check if the item is a file (not a directory)
        if os.path.isfile(source_path):
            shutil.move(source_path, target_path)
            logging.info(f"Moved file: {source_path} to {target_path}")

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
from celery import shared_task
import subprocess
import os
import shutil

from django.conf import settings


@shared_task
def transcription_task(model_size, language):
    print('starting the transcription task now...')
    directory_path: str = os.path.join(settings.MEDIA_ROOT, 'uploads/input')
    output_dir_path: str = os.path.join(settings.MEDIA_ROOT, 'TRANSCRIPTIONS/')
    transcriber_output_file: str = os.path.join(output_dir_path, "transcriber_output.txt")
    try:
        #result = subprocess.run(['python', 'transcriber/aau-whisper/app.py', '--job_name', 'files', '-o', output_dir_path, '-m', model_size, '--input_dir', directory_path, '--no-cuda', '--no-mps', '--threads', '4'],
        if language == 'auto':
            result = subprocess.run(['python', 'transcriber/aau-whisper/app.py', '--job_name', 'files', '-o', output_dir_path, '-m', model_size, '--input_dir', directory_path, '--merge_speakers', '--threads', '4'], capture_output=True, text=True, check=True)
        else:
            result = subprocess.run(['python', 'transcriber/aau-whisper/app.py', '--job_name', 'files', '-o', output_dir_path, '-m', model_size, '--language', language, '--input_dir', directory_path, '--merge_speakers', '--threads', '4'], capture_output=True, text=True, check=True)
        output = result.stdout
        error = result.stderr
        write_transcriber_output(error, output, transcriber_output_file)
    except subprocess.CalledProcessError as e:
        write_transcriber_output(e.stderr, e.stdout, transcriber_output_file)

    # clean the uploads directory so only the newly uploaded files will be transcribed on the next transcription
    transcribed_path: str = os.path.join(settings.MEDIA_ROOT, 'COMPLETED')
    os.makedirs(transcribed_path, exist_ok=True)

    for item in os.listdir(directory_path):
        source_path = os.path.join(directory_path, item)
        target_path = os.path.join(transcribed_path, item)
        # Check if the item is a file (not a directory)
        if os.path.isfile(source_path):
            shutil.move(source_path, target_path)
            print(f"Moved file: {source_path} to {target_path}")

    return "Task completed"

def write_transcriber_output(error, output, transcriber_output_file):
    with open(transcriber_output_file, 'w') as t_file:
        t_file.write(output)
        t_file.write(error)
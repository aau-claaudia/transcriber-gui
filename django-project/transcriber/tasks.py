from celery import shared_task
import subprocess
import os

from django.conf import settings


@shared_task
def transcription_task():
    print('starting the transcription task now...')
    directory_path: str = os.path.join(settings.MEDIA_ROOT, 'uploads')
    output_dir_path: str = os.path.join(directory_path, "output")
    transcriber_output_file: str = os.path.join(output_dir_path, "transcriber_output.txt")
    # TODO: remember to change to use the large model
    try:
        #result = subprocess.run(['python', 'transcriber/aau-whisper/app.py', '--job_name', 'files', '-o', output_dir_path, '-m', 'base', '--input_dir', directory_path, '--no-cuda', '--no-mps', '--threads', '4'],
        result = subprocess.run(['python', 'transcriber/aau-whisper/app.py', '--job_name', 'files', '-o', output_dir_path, '-m', 'small', '--input_dir', directory_path, '--threads', '4'],
                                capture_output=True, text=True, check=True)
        output = result.stdout
        error = result.stderr
        write_transcriber_output(error, output, transcriber_output_file)
    except subprocess.CalledProcessError as e:
        write_transcriber_output(e.stderr, e.stdout, transcriber_output_file)

    # TODO: save transcribed files to UCLoud job mounted folder

    return "Task completed"

def write_transcriber_output(error, output, transcriber_output_file):
    with open(transcriber_output_file, 'w') as t_file:
        t_file.write(output)
        t_file.write(error)
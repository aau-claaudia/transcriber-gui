from pathlib import Path
import subprocess
import logging

logger = logging.getLogger(__name__)

def convert_to_mp3(input_file, output_file):
    """
    Converts an audio/video file to .mp3 using ffmpeg via subprocess.
    """
    command = [
        'ffmpeg',
        '-i', input_file,    # Input file
        '-vn',               # Disable video (useful if input is a video file)
        '-ar', '16000',      # Set audio sampling rate
        '-ac', '1',          # Set number of audio channels
        '-b:a', '128k',      # Set audio bitrate
        '-y',                # Accept overwrite
        output_file          # Output file
    ]

    try:
        # check=True will raise a CalledProcessError if the command fails
        # capture_output=True allows access to the error message if the command fails
        subprocess.run(command, check=True, capture_output=True, text=True)
        logger.info(f"Successfully converted audio/video file to: {output_file}")
        return True, Path(output_file)

    except subprocess.CalledProcessError as e:
        logger.info(f"Conversion failed for {input_file}.")
        logger.info(f"FFmpeg Error Output: {e.stderr}")
        return False, input_file
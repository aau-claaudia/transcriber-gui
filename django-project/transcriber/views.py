from celery import chain
from django.conf import settings
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import FileUploadSerializer, MultipleFileUploadSerializer, MultipleFileMetaDataSerializer
import os
import json
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from .tasks import transcription_task, shutdown_server_task
from .model_memory_util import calculate_available_memory
from pathlib import Path
import subprocess
import logging

logger = logging.getLogger(__name__)

def index(request):
    return render(request, 'frontend/build/index.html')

class FileUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        file_meta_data_list = []
        if request.data and request.data.get('files') and request.data.get('file_meta_data'):
            # parse drop zone file meta data
            file_meta_data = request.data.get('file_meta_data')
            if file_meta_data:
                meta_data = json.loads(file_meta_data)
                serializer = MultipleFileMetaDataSerializer(data={'files': meta_data})
                if serializer.is_valid():
                    file_meta_data_list = serializer.validated_data['files']
            # parse uploaded file data
            serializer = MultipleFileUploadSerializer(data=request.data)
            if serializer.is_valid():
                files = serializer.validated_data['files']
                for file in files:
                    file_serializer = FileUploadSerializer(data={'file': file})
                    if file_serializer.is_valid():
                        file_upload = file_serializer.save()
                        # validate the file size sent by the client against the file size calculated by Django
                        if not validate_file_size(file_upload.file.size, file_upload.file.name, file_meta_data_list):
                            return Response("The file size of the uploaded file does not match the expected size.", status=400)
                        file_upload.save()
                    else:
                        return Response(file_serializer.errors, status=400)
            else:
                return Response(serializer.errors, status=400)
        # Get the model, language and shutdown flag from the request
        model = request.data.get('model')
        cleaned_model_name = clean_model_name(model)

        language = request.data.get('language')
        transcribe_and_shutdown = request.data.get('transcribe_and_shutdown')

        if transcribe_and_shutdown == 'true':
            # This gets the proces id of the parent proces
            master_pid = os.getppid()
            # Chain the transcription task with the shutdown task.
            # The shutdown_server_task will only execute after transcription_task succeeds.
            # Note: The result of the chain is the result of the *last* task in the chain.
            task_chain = chain(transcription_task.s(cleaned_model_name, language), shutdown_server_task.s(master_pid))
            # Start the chained Celery task
            task = task_chain.apply_async()
            return JsonResponse({'task_id': task.parent.id})
        else:
            # Start only the transcription task
            task = transcription_task.delay(cleaned_model_name, language)
            return JsonResponse({'task_id': task.id})


class LinkFilesView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        files_json = request.data.get('files')
        if files_json:
            files_data = json.loads(files_json)
            serializer = MultipleFileMetaDataSerializer(data={'files': files_data})
            if serializer.is_valid():
                file_meta_data = serializer.validated_data['files']
                for file in file_meta_data:
                    if not os.path.exists(file.get('target_path_sym_link')):
                        os.symlink(file.get('filepath'), file.get('target_path_sym_link'))
                return JsonResponse({'status': 'success'}, status=200)
            return Response(serializer.errors, status=400)
        return Response({'error': 'No files data provided'}, status=400)

def get_initialization_data(request):
    source_directory = settings.UCLOUD_DIRECTORY
    target_directory = os.path.join(settings.MEDIA_ROOT, 'UPLOADS/INPUT')
    scan_info = {}
    file_list = []

    # check if there is a mounted folder
    mounted_folder = has_subdirectories(source_directory)
    scan_info['mounted_folder'] = mounted_folder

    # Ensure the target directory exists
    os.makedirs(target_directory, exist_ok=True)

    # Define the allowed file extensions
    allowed_extensions = {'.mp3', '.wav', '.m4a', '.mp4', '.mpeg', '.mpg', '.wma', '.mkv'}

    if mounted_folder:
        logger.info("UCloud mounted folder detected.")
        for root, dirs, files in os.walk(source_directory):
            # Don't look in the 'UPLOADS' or 'COMPLETED' directories (used for user uploaded files and already completed)
            if 'UPLOADS' in dirs:
                dirs.remove('UPLOADS')
            if 'COMPLETED' in dirs:
                dirs.remove('COMPLETED')
            for filename in files:
                file_path = os.path.join(root, filename)
                file_extension = os.path.splitext(filename)[1].lower()

                if file_extension in allowed_extensions:
                    target_path = os.path.join(target_directory, filename)

                    file_info = {
                        'name': filename,
                        'size': os.path.getsize(file_path),
                        'filepath': file_path,
                        'target_path_sym_link': target_path
                    }
                    file_list.append(file_info)

    scan_info['file_list'] = file_list

    # get the available memory
    scan_info['available_memory'] = calculate_available_memory()
    logger.info(f"Available memory: {scan_info['available_memory']}")

    # Return transcription results along with the initialization data
    scan_info['transcriptions'] = prepare_results(request)
    scan_info['results'] = scan_info['transcriptions']

    return JsonResponse(scan_info)

class RemoveLinkView(APIView):

    def post(self, request, *args, **kwargs):
        path = request.data.get('path')
        if path:
            try:
                if os.path.islink(path):
                    os.unlink(path)
                    logger.info(f"Deleted symlink: {path}")
                else:
                    logger.info(f"Path is not a symlink: {path}")
            except FileNotFoundError:
                logger.warning(f"Symlink not found: {path}")
            return JsonResponse({'status': 'success'}, status=200)
        return Response({'error': 'No path provided'}, status=400)

def poll_transcription_status(request, task_id):
    # Get the task result
    task_result = transcription_task.AsyncResult(task_id)
    if task_result.state == 'PENDING':
        response = {
            'state': task_result.state,
            'status': 'Task is still processing...'
        }
    elif task_result.state != 'FAILURE':
        response = {
            'state': task_result.state,
            'status': task_result.info,  # This is the result returned by the task
        }
        if task_result.state == 'SUCCESS':
            response = {
                'state': task_result.state,
                'status': task_result.info,  # This is the result returned by the task
            }
            # only add results if the task was not aborted
            if not "TASK ABORTED" in task_result.info:
                responses = prepare_results(request)
                response['result'] = responses
    else:
        # Something went wrong in the background job
        response = {
            'state': task_result.state,
            'status': str(task_result.info),  # This is the exception raised
        }
    return JsonResponse(response)

def get_completed_transcriptions(request):
    response = {}
    responses = prepare_results(request)
    response['result'] = responses
    return JsonResponse(response)

def prepare_results(request):
    responses = []

    if os.path.isdir(settings.MEDIA_ROOT):
        # avoid scanning folders in "old" transcriber-gui data structure
        exclude_dirs = {'UPLOADS', 'COMPLETED', 'TRANSCRIPTIONS', 'TRANSCRIPTIONS_TEMP'}
        for dir_name in os.listdir(settings.MEDIA_ROOT):
            if dir_name in exclude_dirs or dir_name.startswith('.'):
                continue
            dir_path = os.path.join(settings.MEDIA_ROOT, dir_name)
            if not os.path.isdir(dir_path):
                continue

            # Check if a TRANSCRIPTIONS folder exists within this directory
            trans_dir = os.path.join(dir_path, 'TRANSCRIPTIONS')
            if os.path.isdir(trans_dir):
                # Read metadata.json if it exists
                metadata_path = os.path.join(dir_path, 'data', 'metadata.json')
                input_file_url = None
                edit_file_url = None
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r') as f:
                            meta_data = json.load(f)
                            raw_url = meta_data.get('input_file_url')
                            if raw_url:
                                input_file_url = request.build_absolute_uri(raw_url)
                            raw_edit_url = meta_data.get('edit_file_url')
                            if raw_edit_url:
                                edit_file_url = request.build_absolute_uri(raw_edit_url)
                    except Exception as e:
                        logger.error(f"Error reading metadata.json in {dir_name}: {e}")

                # Fallback to scanning COMPLETED/ if metadata was missing/incomplete
                if not input_file_url:
                    completed_dir = os.path.join(dir_path, 'COMPLETED')
                    if os.path.isdir(completed_dir):
                        completed_files = [f for f in os.listdir(completed_dir) if os.path.isfile(os.path.join(completed_dir, f))]
                        if completed_files:
                            input_file_url = request.build_absolute_uri(f"{settings.MEDIA_URL}{dir_name}/COMPLETED/{completed_files[0]}")
                # Fallback to default edit_file_url
                if not edit_file_url:
                    edit_file_url = request.build_absolute_uri(f"{settings.MEDIA_URL}{dir_name}/data/edited_output.json")

                for filename in os.listdir(trans_dir):
                    file_path = os.path.join(trans_dir, filename)
                    if os.path.isfile(file_path):
                        try:
                            created_at = os.path.getmtime(file_path)
                        except OSError:
                            created_at = 0.0
                        file_url = request.build_absolute_uri(f"{settings.MEDIA_URL}{dir_name}/TRANSCRIPTIONS/{filename}")
                        responses.append({
                            'file_name': filename,
                            'file_url': file_url,
                            'created_at': created_at,
                            'input_file_url': input_file_url,
                            'dir_name': dir_name,
                            'edit_file_url': edit_file_url
                        })

    responses.sort(key=lambda x: x['file_name'])
    return responses

def stop_transcription_task(request, task_id):
    task_result = transcription_task.AsyncResult(task_id)
    task_result.revoke(terminate=True)
    return JsonResponse({'status': 'Task aborted successfully'})

def serve_file(request, path):
    # Determine the base directory based on the URL prefix
    if request.path.startswith('/work/'):
        base_dir = '/work'  # the files are saved here on UCloud
    elif 'media/' in request.path:
        base_dir = settings.MEDIA_ROOT
    else:
        raise Http404("File not found")

    # Construct the full file path
    file_path = os.path.join(base_dir, path)
    # Check if the file exists
    if not os.path.exists(file_path):
        raise Http404("File not found")

    file_size = os.path.getsize(file_path)
    content_type = _guess_content_type(file_path)

    # Handle HTTP Range requests — required by browsers for audio/video seeking
    range_header = request.META.get('HTTP_RANGE', '').strip()
    if range_header and range_header.startswith('bytes='):
        try:
            # Send back a chunk of the audio file, the browser will automatically request more data as needed
            chunk_size = 256 * 1024  # 256 KB
            range_spec = range_header[6:]  # strip 'bytes='
            start_str, _, end_str = range_spec.partition('-')
            start = int(start_str) if start_str else 0
            if end_str:
                end = min(int(end_str), file_size - 1)
            else:
                # Open-ended request: cap how much we serve per response
                end = min(start + chunk_size - 1, file_size - 1)
            if start > end or start < 0:
                response = HttpResponse(status=416)
                response['Content-Range'] = f'bytes */{file_size}'
                return response
            length = end - start + 1
            with open(file_path, 'rb') as f:
                f.seek(start)
                data = f.read(length)
            response = HttpResponse(data, status=206, content_type=content_type)
            response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response['Content-Length'] = str(length)
            response['Accept-Ranges'] = 'bytes'
            return response
        except (ValueError, IOError):
            pass  # fall through to full response on any parse error

    # Full file response (also advertises range support)
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type=content_type)
    response['Content-Length'] = str(file_size)
    response['Accept-Ranges'] = 'bytes'
    response['Content-Disposition'] = 'inline; filename="{}"'.format(os.path.basename(file_path))
    return response


def _guess_content_type(file_path):
    """Return a suitable MIME type for common audio/video files."""
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
    }
    return mime_map.get(ext, 'application/octet-stream')

def validate_file_size(actual_file_size, file_name, meta_data_list):
    size = get_size_by_name(meta_data_list, file_name)
    if size is not None:
        if size != actual_file_size :
            return False
    else:
        # the user must have uploaded the file more than once, and it will be post fixed by django with _xyz.
        # file already checked
        return True
    return True

def get_size_by_name(dict_list, file_name):
    for item in dict_list:
        if item.get('name') == file_name.removeprefix('UPLOADS/INPUT/'):
            return item.get('size')
    return None

def has_subdirectories(directory_path):
    # Iterate through the entries in the directory
    for entry in os.scandir(directory_path):
        # Check if the entry is a directory
        if entry.is_dir():
            return True
    return False

def clean_model_name(model_name):
    # Clean parakeet model name
    if "parakeet" in model_name:
        return "parakeet"

    # Handle prefix removal from whisper model names
    prefix_to_remove = "whisper/"
    if model_name.startswith(prefix_to_remove):
        return model_name[len(prefix_to_remove):]

    return model_name

@csrf_exempt
def convert_audio(request):
    """
    POST endpoint: convert the input audio/video file for a transcription to .mp3.
    Called when editing notes and the input file format is unsupported.
    Expected JSON body:
        { "dir_name": "<transcription dir>", "input_file_url": "<absolute url>" }
    Returns:
        { "status": "converted"|"already_converted"|"unchanged", "input_file_url": "<absolute url>" }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    dir_name = body.get('dir_name', '').strip()
    input_file_url = body.get('input_file_url', '').strip()

    if not dir_name or not input_file_url:
        return JsonResponse({'error': 'dir_name and input_file_url are required'}, status=400)

    # Resolve the URL to an absolute filesystem path
    try:
        parsed = input_file_url
        # Strip scheme + host if present, leaving only the path
        if '://' in parsed:
            from urllib.parse import urlparse
            parsed = urlparse(input_file_url).path

        # Determine base directory from the URL path prefix
        if parsed.startswith('/work/'):
            input_fs_path = parsed  # /work/... is an absolute path on UCloud
        elif settings.MEDIA_URL and parsed.startswith(settings.MEDIA_URL):
            rel = parsed[len(settings.MEDIA_URL):]
            input_fs_path = os.path.join(settings.MEDIA_ROOT, rel)
        else:
            # Fallback: try treating it as relative to MEDIA_ROOT
            input_fs_path = os.path.join(settings.MEDIA_ROOT, parsed.lstrip('/'))
    except Exception as e:
        logger.error(f"convert_audio: could not resolve input URL '{input_file_url}': {e}")
        return JsonResponse({'status': 'unchanged', 'input_file_url': input_file_url})

    if not os.path.exists(input_fs_path):
        logger.warning(f"convert_audio: input file not found at '{input_fs_path}'")
        return JsonResponse({'status': 'unchanged', 'input_file_url': input_file_url})

    # Determine output path: <MEDIA_ROOT>/<dir_name>/data/converted_audio.mp3
    data_dir = os.path.join(settings.MEDIA_ROOT, dir_name, 'data')
    os.makedirs(data_dir, exist_ok=True)
    output_fs_path = os.path.join(data_dir, 'converted_audio.mp3')

    # Idempotency: if already converted, skip ffmpeg
    if os.path.exists(output_fs_path):
        logger.info(f"convert_audio: already converted for '{dir_name}', returning cached path.")
        output_media_url = f"{settings.MEDIA_URL}{dir_name}/data/converted_audio.mp3"
        new_abs_url = request.build_absolute_uri(output_media_url)
        return JsonResponse({'status': 'already_converted', 'input_file_url': new_abs_url})

    # Run conversion
    success, result_path = convert_to_mp3(input_fs_path, output_fs_path)

    if not success:
        logger.warning(f"convert_audio: ffmpeg conversion failed for '{dir_name}'")
        return JsonResponse({'status': 'unchanged', 'input_file_url': input_file_url})

    # Update metadata.json with the new URL
    output_media_url = f"{settings.MEDIA_URL}{dir_name}/data/converted_audio.mp3"
    metadata_path = os.path.join(data_dir, 'metadata.json')
    try:
        meta = {}
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                meta = json.load(f)
        meta['input_file_url'] = output_media_url
        with open(metadata_path, 'w') as f:
            json.dump(meta, f, indent=2)
        logger.info(f"convert_audio: updated metadata.json for '{dir_name}'")
    except Exception as e:
        logger.error(f"convert_audio: failed to update metadata.json for '{dir_name}': {e}")

    new_abs_url = request.build_absolute_uri(output_media_url)
    return JsonResponse({'status': 'converted', 'input_file_url': new_abs_url})


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

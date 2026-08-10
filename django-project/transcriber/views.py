from celery import chain
from django.conf import settings
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import FileUploadSerializer, MultipleFileUploadSerializer, MultipleFileMetaDataSerializer
import os
import json
from datetime import datetime, timezone
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from .tasks import transcription_task, shutdown_server_task
from .model_memory_util import calculate_available_memory
from pathlib import Path
import subprocess
import logging
from urllib.parse import urlparse

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


def _realpath(path):
    return os.path.realpath(str(path))


def _is_within_directory(path, directory):
    """Return True when path is inside directory (after resolving symlinks)."""
    try:
        return os.path.commonpath([_realpath(path), _realpath(directory)]) == _realpath(directory)
    except ValueError:
        return False


def _media_url_prefix():
    media_url = str(settings.MEDIA_URL or '/media/')
    if not media_url.startswith('/'):
        media_url = f'/{media_url}'
    if not media_url.endswith('/'):
        media_url = f'{media_url}/'
    return media_url


def _media_path_to_url(path):
    """Convert a MEDIA_ROOT file path to a media URL path (e.g. /media/x or /work/x)."""
    media_root_real = _realpath(settings.MEDIA_ROOT)
    file_real = _realpath(path)
    if not _is_within_directory(file_real, media_root_real):
        return None

    relative_path = os.path.relpath(file_real, media_root_real).replace(os.sep, '/')
    return f"{_media_url_prefix()}{relative_path}"


def _resolve_candidate_path(raw_value):
    """Resolve URL/path-like value to a filesystem path candidate."""
    if not raw_value:
        return None

    parsed_path = raw_value.strip()
    if '://' in parsed_path:
        parsed_path = urlparse(parsed_path).path

    media_prefix = _media_url_prefix()
    if parsed_path.startswith(media_prefix):
        relative_path = parsed_path[len(media_prefix):].lstrip('/')
        return os.path.join(settings.MEDIA_ROOT, relative_path)
    if parsed_path.startswith('/work/'):
        return parsed_path
    if os.path.isabs(parsed_path):
        return parsed_path
    return os.path.join(settings.MEDIA_ROOT, parsed_path.lstrip('/'))


def _first_completed_file(base_dir):
    logger.info(f"Debug - base_dir = {base_dir}")
    completed_dir = os.path.join(base_dir, 'COMPLETED')
    if not os.path.isdir(completed_dir):
        return None

    completed_files = sorted(
        f for f in os.listdir(completed_dir)
        if os.path.isfile(os.path.join(completed_dir, f))
    )
    if not completed_files:
        logger.info(f"Debug - no files listed in Completed dir.")
        return None
    logger.info(f"Debug - returning: {os.path.join(completed_dir, completed_files[0])}")
    return os.path.join(completed_dir, completed_files[0])


def _resolve_transcription_paths(request, relative_dir, base_dir, metadata=None, input_file_hint=None):
    """
    Resolve safe input/edit file paths and URLs for a transcription directory.
    Any metadata URL/path that does not resolve under MEDIA_ROOT and the current
    transcription directory is treated as stale and replaced with a safe fallback.
    """
    metadata = metadata or {}
    base_dir_real = _realpath(base_dir)
    media_root_real = _realpath(settings.MEDIA_ROOT)

    raw_input = input_file_hint or metadata.get('input_file_url')
    raw_edit = metadata.get('edit_file_url')
    input_source = 'request' if input_file_hint else 'metadata'

    input_file_path = None
    edit_file_path = None
    stale_metadata_events = []

    input_candidate = _resolve_candidate_path(raw_input) if raw_input else None
    if input_candidate:
        candidate_real = _realpath(input_candidate)
        if _is_within_directory(candidate_real, media_root_real) and _is_within_directory(candidate_real, base_dir_real) and os.path.exists(candidate_real):
            input_file_path = candidate_real
        else:
            if not _is_within_directory(candidate_real, media_root_real):
                reason = 'outside_media_root'
            elif not _is_within_directory(candidate_real, base_dir_real):
                reason = 'outside_transcription_dir'
            else:
                reason = 'path_not_found'
            stale_metadata_events.append({
                'field': 'input_file_url',
                'source': input_source,
                'old_value': raw_input,
                'candidate_path': candidate_real,
                'reason': reason,
            })

    edit_candidate = _resolve_candidate_path(raw_edit) if raw_edit else None
    if edit_candidate:
        candidate_real = _realpath(edit_candidate)
        if _is_within_directory(candidate_real, media_root_real) and _is_within_directory(candidate_real, base_dir_real) and os.path.exists(candidate_real):
            edit_file_path = candidate_real
        else:
            if not _is_within_directory(candidate_real, media_root_real):
                reason = 'outside_media_root'
            elif not _is_within_directory(candidate_real, base_dir_real):
                reason = 'outside_transcription_dir'
            else:
                reason = 'path_not_found'
            stale_metadata_events.append({
                'field': 'edit_file_url',
                'source': 'metadata',
                'old_value': raw_edit,
                'candidate_path': candidate_real,
                'reason': reason,
            })

    if not input_file_path:
        input_file_path = _first_completed_file(base_dir_real)

    if not edit_file_path:
        default_edit_path = os.path.join(base_dir_real, 'data', 'edited_output.json')
        if _is_within_directory(default_edit_path, media_root_real):
            edit_file_path = default_edit_path

    canonical_input_url = _media_path_to_url(input_file_path) if input_file_path else None
    canonical_edit_url = _media_path_to_url(edit_file_path) if edit_file_path else None

    resolved_input_url = request.build_absolute_uri(canonical_input_url) if canonical_input_url else None
    resolved_edit_url = request.build_absolute_uri(canonical_edit_url) if canonical_edit_url else None

    metadata_needs_update = False
    if canonical_input_url and metadata.get('input_file_url') != canonical_input_url:
        metadata_needs_update = True
    if canonical_edit_url and metadata.get('edit_file_url') != canonical_edit_url:
        metadata_needs_update = True

    return {
        'input_file_path': input_file_path,
        'edit_file_path': edit_file_path,
        'input_file_url': resolved_input_url,
        'edit_file_url': resolved_edit_url,
        'canonical_input_file_url': canonical_input_url,
        'canonical_edit_file_url': canonical_edit_url,
        'metadata_needs_update': metadata_needs_update,
        'stale_metadata_events': stale_metadata_events,
        'dir_name': relative_dir,
    }


def _log_stale_metadata_events(dir_name, resolved_paths):
    """Write audit logs for rejected stale URL/path values and their corrected URLs."""
    events = resolved_paths.get('stale_metadata_events') or []
    if not events:
        return

    corrected_values = {
        'input_file_url': resolved_paths.get('canonical_input_file_url'),
        'edit_file_url': resolved_paths.get('canonical_edit_file_url'),
    }

    for event in events:
        logger.warning(
            "Metadata URL rejected for dir='%s': source=%s field=%s old_value='%s' candidate_path='%s' reason=%s corrected_value='%s'",
            dir_name,
            event.get('source'),
            event.get('field'),
            event.get('old_value'),
            event.get('candidate_path'),
            event.get('reason'),
            corrected_values.get(event.get('field')),
        )


def _safe_write_metadata_urls(metadata_path, metadata, canonical_input_url, canonical_edit_url, dir_name):
    """Persist corrected metadata URLs for self-healing stale metadata entries."""
    try:
        updated = dict(metadata or {})
        if canonical_input_url:
            updated['input_file_url'] = canonical_input_url
        if canonical_edit_url:
            updated['edit_file_url'] = canonical_edit_url

        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        with open(metadata_path, 'w') as f:
            json.dump(updated, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to update metadata.json in {dir_name}: {e}")

def prepare_results(request):
    responses = []

    if os.path.isdir(settings.MEDIA_ROOT):
        # avoid scanning folders in "old" transcriber-gui data structure
        exclude_dirs = {'UPLOADS', 'COMPLETED', 'TRANSCRIPTIONS', 'TRANSCRIPTIONS_TEMP'}
        candidate_dirs = []
        for dir_name in os.listdir(settings.MEDIA_ROOT):
            if dir_name in exclude_dirs or dir_name.startswith('.'):
                continue
            dir_path = os.path.join(settings.MEDIA_ROOT, dir_name)
            if not os.path.isdir(dir_path):
                continue

            # Include first-level folders under MEDIA_ROOT.
            candidate_dirs.append((dir_name, dir_path))

            # Also include folders exactly one level deeper.
            for child_name in os.listdir(dir_path):
                if child_name.startswith('.'):
                    continue
                child_path = os.path.join(dir_path, child_name)
                if os.path.isdir(child_path):
                    candidate_dirs.append((os.path.join(dir_name, child_name), child_path))

        for relative_dir, base_dir in candidate_dirs:
            # Check if a TRANSCRIPTIONS folder exists within this directory
            trans_dir = os.path.join(base_dir, 'TRANSCRIPTIONS')
            if os.path.isdir(trans_dir):
                # Read metadata.json if it exists
                metadata_path = os.path.join(base_dir, 'data', 'metadata.json')
                metadata = {}
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                    except Exception as e:
                        logger.error(f"Error reading metadata.json in {relative_dir}: {e}")
                        metadata = {}

                resolved_paths = _resolve_transcription_paths(
                    request=request,
                    relative_dir=relative_dir,
                    base_dir=base_dir,
                    metadata=metadata,
                )

                input_file_url = resolved_paths['input_file_url']
                edit_file_url = resolved_paths['edit_file_url']
                _log_stale_metadata_events(relative_dir, resolved_paths)

                if resolved_paths['metadata_needs_update']:
                    _safe_write_metadata_urls(
                        metadata_path=metadata_path,
                        metadata=metadata,
                        canonical_input_url=resolved_paths['canonical_input_file_url'],
                        canonical_edit_url=resolved_paths['canonical_edit_file_url'],
                        dir_name=relative_dir,
                    )

                for filename in os.listdir(trans_dir):
                    file_path = os.path.join(trans_dir, filename)
                    if os.path.isfile(file_path):
                        try:
                            created_at = os.path.getmtime(file_path)
                        except OSError:
                            created_at = 0.0
                        media_file_url = _media_path_to_url(os.path.join(trans_dir, filename))
                        if not media_file_url:
                            continue
                        file_url = request.build_absolute_uri(media_file_url)
                        responses.append({
                            'file_name': filename,
                            'file_url': file_url,
                            'created_at': created_at,
                            'input_file_url': input_file_url,
                            'dir_name': relative_dir,
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


def export_file(request):
    """
    GET /export-file/?dir_name=<str>&target=<edited_output|notes>&format=<json|txt|docx>
    Handles request to download specified export file (edited_output.json or notes.json).
    Returns file as an attachment response.
    """
    dir_name = request.GET.get('dir_name', '').strip()
    target = request.GET.get('target', 'edited_output').strip()
    export_format = request.GET.get('format', 'json').strip().lower()

    if not dir_name:
        return JsonResponse({'error': 'dir_name parameter is required'}, status=400)

    # Determine target file name based on target parameter
    target_filename = 'notes.json' if target == 'notes' else 'edited_output.json'
    file_path = os.path.join(settings.MEDIA_ROOT, dir_name, 'data', target_filename)

    if not os.path.exists(file_path):
        raise Http404(f"Export file {target_filename} not found for directory '{dir_name}'.")

    download_name = f"{dir_name}_{target}.{export_format if export_format in ['json', 'txt', 'docx'] else 'json'}"

    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()

        content_type = 'application/json'
        if export_format == 'txt':
            content_type = 'text/plain; charset=utf-8'
        elif export_format == 'docx':
            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

        response = HttpResponse(file_data, content_type=content_type)
        response['Content-Length'] = str(len(file_data))
        response['Content-Disposition'] = f'attachment; filename="{download_name}"'
        return response
    except Exception as e:
        logger.error(f"export_file: failed to read '{file_path}': {e}")
        return JsonResponse({'error': 'Could not process export file'}, status=500)


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

    base_dir = os.path.join(settings.MEDIA_ROOT, dir_name)
    if not _is_within_directory(base_dir, settings.MEDIA_ROOT):
        return JsonResponse({'error': 'Invalid dir_name path'}, status=400)

    data_dir = os.path.join(base_dir, 'data')
    metadata_path = os.path.join(data_dir, 'metadata.json')
    metadata = {}
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        except Exception as e:
            logger.error(f"convert_audio: failed to read metadata.json for '{dir_name}': {e}")

    resolved_paths = _resolve_transcription_paths(
        request=request,
        relative_dir=dir_name,
        base_dir=base_dir,
        metadata=metadata,
        input_file_hint=input_file_url,
    )
    _log_stale_metadata_events(dir_name, resolved_paths)

    if resolved_paths['metadata_needs_update']:
        _safe_write_metadata_urls(
            metadata_path=metadata_path,
            metadata=metadata,
            canonical_input_url=resolved_paths['canonical_input_file_url'],
            canonical_edit_url=resolved_paths['canonical_edit_file_url'],
            dir_name=dir_name,
        )

    input_fs_path = resolved_paths['input_file_path']
    if not input_fs_path or not os.path.exists(input_fs_path):
        logger.warning(f"convert_audio: input file not found or out of scope for '{dir_name}'")
        return JsonResponse({'status': 'unchanged', 'input_file_url': input_file_url})

    # Determine output path: <MEDIA_ROOT>/<dir_name>/data/converted_audio.mp3
    os.makedirs(data_dir, exist_ok=True)
    output_fs_path = os.path.join(data_dir, 'converted_audio.mp3')

    # Idempotency: if already converted, skip ffmpeg
    if os.path.exists(output_fs_path):
        logger.info(f"convert_audio: already converted for '{dir_name}', returning cached path.")
    else:
        # Run conversion
        success, result_path = convert_to_mp3(input_fs_path, output_fs_path)
        if not success:
            logger.warning(f"convert_audio: ffmpeg conversion failed for '{dir_name}'")
            return JsonResponse({'status': 'unchanged', 'input_file_url': input_file_url})

    # Update metadata.json with the new URL
    output_media_url = _media_path_to_url(output_fs_path)
    if not output_media_url:
        logger.warning(f"convert_audio: converted file path could not be mapped to MEDIA_URL for '{dir_name}'")
        return JsonResponse({'status': 'unchanged', 'input_file_url': input_file_url})

    try:
        meta = dict(metadata or {})
        meta['input_file_url'] = output_media_url
        if resolved_paths.get('canonical_edit_file_url'):
            meta['edit_file_url'] = resolved_paths['canonical_edit_file_url']
        with open(metadata_path, 'w') as f:
            json.dump(meta, f, indent=2)
        logger.info(f"convert_audio: updated metadata.json for '{dir_name}'")
    except Exception as e:
        logger.error(f"convert_audio: failed to update metadata.json for '{dir_name}': {e}")

    new_abs_url = request.build_absolute_uri(output_media_url)
    return JsonResponse({'status': 'converted', 'input_file_url': new_abs_url})

@csrf_exempt
def edit_transcription_segment(request):
    """
    POST endpoint: update segment text and speaker
    Called when editing notes for updating the edited output file
    Expected JSON body:
        { "dir_name": "<transcription dir>", "payload": "<update object>" }
    Returns:
        { status, type, dirName, editFileUrl }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    dir_name = str(body.get('dir_name', '')).strip()
    payload = body.get('payload')

    if not dir_name:
        return JsonResponse({'error': 'dir_name is required'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'error': 'payload must be an object'}, status=400)

    base_dir = os.path.join(settings.MEDIA_ROOT, dir_name)
    if not _is_within_directory(base_dir, settings.MEDIA_ROOT):
        return JsonResponse({'error': 'Invalid dir_name path'}, status=400)

    data_dir = os.path.join(base_dir, 'data')
    metadata_path = os.path.join(data_dir, 'metadata.json')

    if not os.path.exists(metadata_path):
        return JsonResponse({'error': 'metadata.json not found for this transcription'}, status=404)

    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
    except Exception as e:
        logger.error(f"edit_transcription_segment: failed to read metadata for '{dir_name}': {e}")
        return JsonResponse({'error': 'Could not read metadata.json'}, status=500)

    resolved_paths = _resolve_transcription_paths(
        request=request,
        relative_dir=dir_name,
        base_dir=base_dir,
        metadata=metadata,
    )
    _log_stale_metadata_events(dir_name, resolved_paths)

    if resolved_paths['metadata_needs_update']:
        _safe_write_metadata_urls(
            metadata_path=metadata_path,
            metadata=metadata,
            canonical_input_url=resolved_paths['canonical_input_file_url'],
            canonical_edit_url=resolved_paths['canonical_edit_file_url'],
            dir_name=dir_name,
        )

    edit_file_url = resolved_paths['edit_file_url']
    edit_file_path = resolved_paths['edit_file_path']

    if not edit_file_path or not os.path.exists(edit_file_path):
        return JsonResponse({'error': 'Target edit file not found'}, status=404)

    try:
        with open(edit_file_path, 'r') as f:
            edited_output = json.load(f)
    except Exception as e:
        logger.error(f"edit_transcription_segment: failed to read edit file '{edit_file_path}': {e}")
        return JsonResponse({'error': 'Could not read target edit file'}, status=500)

    lines = edited_output.get('lines')
    if not isinstance(lines, list):
        return JsonResponse({'error': "Target edit file format invalid (missing 'lines' array)"}, status=400)

    edit_type = payload.get('type')

    if edit_type == 'text_edit':
        segment_id = payload.get('segmentId')
        new_text = payload.get('newText')

        if not isinstance(segment_id, int) or segment_id < 0 or segment_id >= len(lines):
            return JsonResponse({'error': 'Invalid segmentId for text_edit'}, status=400)
        if not isinstance(new_text, str):
            return JsonResponse({'error': 'newText must be a string'}, status=400)

        if not isinstance(lines[segment_id], dict):
            return JsonResponse({'error': 'Segment entry has invalid structure'}, status=400)

        lines[segment_id]['text'] = new_text

    elif edit_type == 'speaker_edit':
        old_name = payload.get('oldName')
        new_name = payload.get('newName')
        update_all = payload.get('updateAll')
        segment_id = payload.get('segmentId')

        if not isinstance(old_name, str) or not isinstance(new_name, str):
            return JsonResponse({'error': 'oldName and newName must be strings'}, status=400)
        if not isinstance(update_all, bool):
            return JsonResponse({'error': 'updateAll must be a boolean'}, status=400)

        updates = 0
        if update_all:
            for line in lines:
                if isinstance(line, dict) and line.get('speakerDesignation') == old_name:
                    line['speakerDesignation'] = new_name
                    updates += 1
        else:
            if not isinstance(segment_id, int) or segment_id < 0 or segment_id >= len(lines):
                return JsonResponse({'error': 'Invalid segmentId for speaker_edit'}, status=400)
            if not isinstance(lines[segment_id], dict):
                return JsonResponse({'error': 'Segment entry has invalid structure'}, status=400)

            lines[segment_id]['speakerDesignation'] = new_name
            updates = 1

        if updates == 0:
            logger.info(
                f"edit_transcription_segment: speaker_edit made no changes for dir='{dir_name}', "
                f"old_name='{old_name}', update_all={update_all}"
            )
    else:
        return JsonResponse({'error': 'Unsupported payload type'}, status=400)

    try:
        with open(edit_file_path, 'w') as f:
            json.dump(edited_output, f, indent=2)
    except Exception as e:
        logger.error(f"edit_transcription_segment: failed to write edit file '{edit_file_path}': {e}")
        return JsonResponse({'error': 'Failed to write target edit file'}, status=500)

    return JsonResponse({
        'status': 'ok',
        'type': edit_type,
        'dir_name': dir_name,
        'edit_file_url': edit_file_url
    })

def _read_notes_file(notes_path):
    """Return the parsed notes dict, or a blank one if the file doesn't exist."""
    if not os.path.exists(notes_path):
        return {'notes': []}
    try:
        with open(notes_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {'notes': []}


def _write_notes_file(notes_path, data):
    """Write the notes dict back to disk with pretty formatting."""
    with open(notes_path, 'w') as f:
        json.dump(data, f, indent=2)


def get_notes(request):
    """
    GET /get-notes/?dir_name=<str>
    Returns all notes for the transcription, sorted by date ascending.
    Response: { "notes": [ { "id", "date", "note" }, … ] }
    """
    dir_name = request.GET.get('dir_name', '').strip()
    if not dir_name:
        return JsonResponse({'error': 'dir_name query parameter is required'}, status=400)

    notes_path = os.path.join(settings.MEDIA_ROOT, dir_name, 'data', 'notes.json')
    data = _read_notes_file(notes_path)
    notes = data.get('notes', [])

    # Sort ascending by date (ISO strings sort correctly lexicographically)
    notes_sorted = sorted(notes, key=lambda n: n.get('date', ''))
    return JsonResponse({'notes': notes_sorted})


@csrf_exempt
def save_note(request):
    """
    POST /save-note/
    Body: { "dir_name": "<str>", "note": "<str>" }
    Creates <MEDIA_ROOT>/<dir_name>/data/notes.json if it does not exist.
    Appends a new note object with an auto-incremented id and an ISO-8601 UTC date.
    Response: { "status": "ok", "note": { "id": <int>, "date": "<iso>", "note": "<str>" } }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    dir_name = str(body.get('dir_name', '')).strip()
    note_text = body.get('note')

    if not dir_name:
        return JsonResponse({'error': 'dir_name is required'}, status=400)
    if not isinstance(note_text, str) or not note_text.strip():
        return JsonResponse({'error': 'note must be a non-empty string'}, status=400)

    data_dir = os.path.join(settings.MEDIA_ROOT, dir_name, 'data')
    os.makedirs(data_dir, exist_ok=True)
    notes_path = os.path.join(data_dir, 'notes.json')

    try:
        data = _read_notes_file(notes_path)
        notes = data.get('notes', [])

        next_id = (max(n['id'] for n in notes if isinstance(n.get('id'), int)) + 1) if notes else 1
        new_note = {
            'id': next_id,
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') +
                    f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z",
            'note': note_text.strip()
        }
        notes.append(new_note)
        data['notes'] = notes
        _write_notes_file(notes_path, data)
    except Exception as e:
        logger.error(f"save_note: failed to write notes for '{dir_name}': {e}")
        return JsonResponse({'error': 'Failed to save note'}, status=500)

    return JsonResponse({'status': 'ok', 'note': new_note})


@csrf_exempt
def delete_note(request):
    """
    POST /delete-note/
    Body: { "dir_name": "<str>", "note_id": <int> }
    Removes the note with the matching id from notes.json.
    Response: { "status": "ok", "deleted_id": <int> }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    dir_name = str(body.get('dir_name', '')).strip()
    note_id = body.get('note_id')

    if not dir_name:
        return JsonResponse({'error': 'dir_name is required'}, status=400)
    if not isinstance(note_id, int):
        return JsonResponse({'error': 'note_id must be an integer'}, status=400)

    notes_path = os.path.join(settings.MEDIA_ROOT, dir_name, 'data', 'notes.json')

    if not os.path.exists(notes_path):
        return JsonResponse({'error': 'notes.json not found for this transcription'}, status=404)

    try:
        data = _read_notes_file(notes_path)
        original_count = len(data.get('notes', []))
        data['notes'] = [n for n in data.get('notes', []) if n.get('id') != note_id]
        if len(data['notes']) == original_count:
            logger.warning(f"delete_note: note_id={note_id} not found in '{dir_name}'")
        _write_notes_file(notes_path, data)
    except Exception as e:
        logger.error(f"delete_note: failed to update notes for '{dir_name}': {e}")
        return JsonResponse({'error': 'Failed to delete note'}, status=500)

    return JsonResponse({'status': 'ok', 'deleted_id': note_id})


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

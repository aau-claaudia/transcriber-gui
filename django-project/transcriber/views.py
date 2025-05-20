from django.conf import settings
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import FileUploadSerializer, MultipleFileUploadSerializer, MultipleFileMetaDataSerializer
import os
import json
from django.http import JsonResponse, HttpResponse, Http404
from rest_framework.views import APIView
from .tasks import transcription_task
from celery.result import AsyncResult

def index(request):
    print(request)
    return render(request, 'frontend/build/index.html')

class FileUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        #print(request.data)
        file_meta_data_list = []
        if request.data and request.data.get('files') and request.data.get('file_meta_data'):
            # parse drop zone file meta data
            file_meta_data = request.data.get('file_meta_data')
            if file_meta_data:
                meta_data = json.loads(file_meta_data)
                serializer = MultipleFileMetaDataSerializer(data={'files': meta_data})
                if serializer.is_valid():
                    file_meta_data_list = serializer.validated_data['files']
                    #print(file_meta_data_list)
            # parse uploaded file data
            serializer = MultipleFileUploadSerializer(data=request.data)
            if serializer.is_valid():
                files = serializer.validated_data['files']
                #print(files)
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
        # Get the model and language from the request
        model = request.data.get('model')
        language = request.data.get('language')
        # Start the Celery task
        task = transcription_task.delay(model, language)
        # Return the task ID to the client
        return JsonResponse({'task_id': task.id})

class LinkFilesView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        files_json = request.data.get('files')
        if files_json:
            files_data = json.loads(files_json)
            #print(files_data)
            serializer = MultipleFileMetaDataSerializer(data={'files': files_data})
            if serializer.is_valid():
                file_meta_data = serializer.validated_data['files']
                for file in file_meta_data:
                    if not os.path.exists(file.get('target_path_sym_link')):
                        os.symlink(file.get('filepath'), file.get('target_path_sym_link'))
                return JsonResponse({'status': 'success'}, status=200)
            return Response(serializer.errors, status=400)
        return Response({'error': 'No files data provided'}, status=400)

def scan_files(request):
    source_directory = settings.UCLOUD_DIRECTORY
    target_directory = os.path.join(settings.MEDIA_ROOT, 'UPLOADS/INPUT')
    file_list = []

    # Ensure the target directory exists
    os.makedirs(target_directory, exist_ok=True)

    # Define the allowed file extensions
    allowed_extensions = {'.mp3', '.wav', '.m4a', '.mp4', '.mpeg'}

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

    return JsonResponse(file_list, safe=False)

class RemoveLinkView(APIView):

    def post(self, request, *args, **kwargs):
        path = request.data.get('path')
        #print(path)
        if path:
            try:
                if os.path.islink(path):
                    os.unlink(path)
                    print(f"Deleted symlink: {path}")
                else:
                    print(f"Path is not a symlink: {path}")
            except FileNotFoundError:
                print(f"Symlink not found: {path}")
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
                responses = []
                output_dir_path: str = os.path.join(settings.MEDIA_ROOT, 'TRANSCRIPTIONS/')
                # List the files in the output directory and construct the URLs
                for filename in os.listdir(output_dir_path):
                    file_url = request.build_absolute_uri(os.path.join(settings.MEDIA_ROOT, 'TRANSCRIPTIONS', filename))
                    responses.append({
                        'file_name': filename,
                        'file_url': file_url
                    })
                responses.sort(key=lambda x: x['file_name'])
                response['result'] = responses
    else:
        # Something went wrong in the background job
        response = {
            'state': task_result.state,
            'status': str(task_result.info),  # This is the exception raised
        }
    return JsonResponse(response)

def stop_transcription_task(request, task_id):
    task_result = transcription_task.AsyncResult(task_id)
    task_result.abort()  # Abort the task
    return JsonResponse({'status': 'Task aborted successfully'})

def serve_file(request, path):
    # Determine the base directory based on the URL prefix
    if request.path.startswith('/work/'):
        base_dir = '/work'  # the files are saved here on UCloud
    elif 'media/TRANSCRIPTIONS' in request.path:
        base_dir = os.path.join(settings.MEDIA_ROOT, 'TRANSCRIPTIONS/')
    else:
        raise Http404("File not found")

    # Construct the full file path
    file_path = os.path.join(base_dir, path)
    # Check if the file exists
    if not os.path.exists(file_path):
        raise Http404("File not found")

    # Open the file and create the response
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(os.path.basename(file_path))
        return response


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
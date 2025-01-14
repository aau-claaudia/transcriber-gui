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

def index(request):
    print(request)
    return render(request, 'frontend/build/index.html')

class FileUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        #print(request.data)
        if request.data:
            serializer = MultipleFileUploadSerializer(data=request.data)
            if serializer.is_valid():
                files = serializer.validated_data['files']
                #print(files)
                for file in files:
                    file_serializer = FileUploadSerializer(data={'file': file})
                    if file_serializer.is_valid():
                        file_upload = file_serializer.save()
                        file_upload.save()
                    else:
                        return Response(file_serializer.errors, status=400)
            else:
                return Response(serializer.errors, status=400)
        # TODO: Make model optional to select in the UI.
        # Start the Celery task
        task = transcription_task.delay('small')
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
    target_directory = os.path.join(settings.MEDIA_ROOT, 'uploads')
    file_list = []

    # Ensure the target directory exists
    os.makedirs(target_directory, exist_ok=True)

    # Define the allowed file extensions
    allowed_extensions = {'.mp3', '.wav', '.m4a', '.mp4', '.mpeg'}

    for root, dirs, files in os.walk(source_directory):
        # Don't look in the 'uploads' directory (used for user uploaded files and output files)
        if 'uploads' in dirs:
            dirs.remove('uploads')
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
            responses = []
            directory_path: str = os.path.join(settings.MEDIA_ROOT, 'uploads')
            output_dir_path: str = os.path.join(directory_path, "output")
            # List the files in the output directory and construct the URLs
            for filename in os.listdir(output_dir_path):
                file_url = request.build_absolute_uri(os.path.join(settings.MEDIA_URL, 'uploads/output', filename))
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

def serve_file(request, path):
    # Determine the base directory based on the URL prefix
    if request.path.startswith('/media/'):
        base_dir = settings.MEDIA_ROOT
    elif request.path.startswith('/work/'):
        base_dir = '/work'  # the files are saved here on UCloud
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


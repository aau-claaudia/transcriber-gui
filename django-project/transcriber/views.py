from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import FileUploadSerializer, MultipleFileUploadSerializer
import os
from django.http import JsonResponse
from rest_framework.views import APIView
from .tasks import transcription_task

class FileUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        #print(request.data)
        directory_path: str = os.path.join(settings.MEDIA_ROOT, 'uploads')
        # clean the uploads directory so only the newly uploaded files will be transcribed
        delete_all_files_in_directory(directory_path)

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

            # Start the Celery task
            task = transcription_task.delay()
            # Return the task ID to the client
            return JsonResponse({'task_id': task.id})
        return Response(serializer.errors, status=400)

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

def delete_all_files_in_directory(directory):
    # List all files and directories in the specified directory
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        # Check if the item is a file
        if os.path.isfile(file_path):
            try:
                # Delete the file
                os.remove(file_path)
                print(f"Deleted file: {file_path}")
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

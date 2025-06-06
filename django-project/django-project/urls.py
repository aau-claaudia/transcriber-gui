"""
URL configuration for django-project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path
from transcriber.views import FileUploadView, poll_transcription_status, stop_transcription_task, index, serve_file, scan_files, LinkFilesView, RemoveLinkView, get_completed_transcriptions

urlpatterns = [
    path('admin/', admin.site.urls),
    path('upload/', FileUploadView.as_view(), name='file_upload'),
    path('poll-transcription-status/<str:task_id>/', poll_transcription_status, name='poll_transcription_status'),
    path('stop_transcription_task/<str:task_id>/', stop_transcription_task, name='stop_transcription_task'),
    path('get-completed-transcriptions/', get_completed_transcriptions, name='get_completed_transcriptions'),
    path('scan-files/', scan_files, name='scan_files'),
    path('link-files/', LinkFilesView.as_view(), name='link_files'),
    path('remove-link/', RemoveLinkView.as_view(), name='remove_link'),
    re_path(r'^.*media/TRANSCRIPTIONS/(?P<path>.*)$', serve_file, name='serve_media_file'), # pattern for download
    re_path(r'^work/(?P<path>.*)$', serve_file, name='serve_work_file'), # pattern for download
    re_path(r'^.*$', index, name='index'),  # Catch-all pattern to serve the React app
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
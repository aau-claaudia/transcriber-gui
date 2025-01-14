from rest_framework import serializers
from .models import FileUpload, FileMetaData

class FileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileUpload
        fields = ['file']

class MultipleFileUploadSerializer(serializers.Serializer):
    files = serializers.ListField(
        child=serializers.FileField(),
        allow_empty=False
    )

class FileMetaDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileMetaData
        fields = ['filepath', 'name', 'size', 'target_path_sym_link']

class MultipleFileMetaDataSerializer(serializers.Serializer):
    files = FileMetaDataSerializer(many=True)
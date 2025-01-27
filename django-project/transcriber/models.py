from django.db import models

# Create your models here.

class FileUpload(models.Model):
    file = models.FileField(upload_to='uploads/')

class FileMetaData(models.Model):
    filepath = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255)
    size = models.IntegerField()
    target_path_sym_link = models.CharField(max_length=255, blank=True, null=True)
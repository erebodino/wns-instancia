import os
from rest_framework import serializers

class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


    def validate_file(self, value):
        """
        value es un objeto UploadedFile
        """
        # 1. Obtenemos la extensión (ej: '.pdf')
        ext = os.path.splitext(value.name)[1].lower()
        
        if ext not in ['.pdf', '.xls', '.xlsx', '.md']:
            raise serializers.ValidationError("Tipo de archivo no soportado. Se esperaba: .pdf, .xls, .xlsx, .md")

        return value
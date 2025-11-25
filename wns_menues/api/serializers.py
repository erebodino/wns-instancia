import os
from rest_framework import serializers

class FileUploadSerializer(serializers.Serializer):
    """
    Serializer for handling file uploads.

    Validates the file extension to ensure it is one of the supported types.
    """
    file = serializers.FileField()

    def validate_file(self, value):
        """
        Validates that the uploaded file has a supported extension.

        Args:
            value (UploadedFile): The file object being validated.

        Returns:
            UploadedFile: The validated file object.

        Raises:
            serializers.ValidationError: If the file extension is not supported.
        """
        # 1. Obtenemos la extensión (ej: '.pdf')
        ext = os.path.splitext(value.name)[1].lower()
        
        if ext not in ['.pdf', '.xls', '.xlsx', '.md']:
            raise serializers.ValidationError("Tipo de archivo no soportado. Se esperaba: .pdf, .xls, .xlsx, .md")

        return value
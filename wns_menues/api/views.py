from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from .serializers import FileUploadSerializer
from core.parsers import ETLService
from .helpers import PricingService

class BaseUploadView(APIView):
    parser_classes = [MultiPartParser]

    def process_upload(self, request, service_method):
        serializer = FileUploadSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # request.FILES['file'] viene validado por el serializer
                file_obj = serializer.validated_data['file']
                result_data = service_method(file_obj)
                human_message = f"Se procesaron {result_data['processed_count']} items."
                if result_data.get('errors'):
                    human_message += " Se encontraron algunos errores."

                response_payload = {
                    "message": human_message, # Mensaje corto para un Toast/Alerta simple
                    "data": result_data       # Datos crudos para que el Frontend renderice detalles
                }
                return Response(response_payload, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RecetasUploadView(BaseUploadView):
    def post(self, request):
        return self.process_upload(request, ETLService().import_recipes)

class VerdurasUploadView(BaseUploadView):
    def post(self, request):
        return self.process_upload(request, ETLService().import_vegetables)

class CarnesUploadView(BaseUploadView):
    def post(self, request):
        return self.process_upload(request, ETLService().import_meats)

class CalculatePriceView(APIView):
    def post(self, request):
        recipe_id = request.data.get('recipe_id')
        date_str = request.data.get('date')

        if not recipe_id or not date_str:
            return Response(
                {"error": "Faltan parámetros (recipe_id, date)"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            service = PricingService()
            result = service.calculate_recipe_cost(recipe_id, date_str)
            return Response(result, status=status.HTTP_200_OK)   
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Error interno: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
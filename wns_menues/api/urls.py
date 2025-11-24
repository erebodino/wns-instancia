from django.urls import path
from .views import RecetasUploadView, CarnesUploadView, VerdurasUploadView, CalculatePriceView

app_name = 'api'

urlpatterns = [
    path('upload/recipes/', RecetasUploadView.as_view(), name='upload_recipes'),
    path('upload/meats/', CarnesUploadView.as_view(), name='upload_meats'),
    path('upload/vegetables/', VerdurasUploadView.as_view(), name='upload_vegetables'),
    path('calculate-price/', CalculatePriceView.as_view(), name='calculate_price'),
]

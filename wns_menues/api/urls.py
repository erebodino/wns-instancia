from django.urls import path
from .views import RecipesUploadView, MeatsUploadView, VegetablesUploadView, CalculatePriceView

app_name = 'api'

urlpatterns = [
    path('upload/recipes/', RecipesUploadView.as_view(), name='upload_recipes'),
    path('upload/meats/', MeatsUploadView.as_view(), name='upload_meats'),
    path('upload/vegetables/', VegetablesUploadView.as_view(), name='upload_vegetables'),
    path('calculate-price/', CalculatePriceView.as_view(), name='calculate_price'),
]

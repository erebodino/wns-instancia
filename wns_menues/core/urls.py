
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload_data/', views.upload_data, name='upload_data'),
    path('recipe_prices/', views.recipe_prices, name='recipe_prices'),
]

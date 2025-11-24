from django.shortcuts import render, HttpResponse
from core.models import CookingRecipe
def home(request):
    return render(request, 'home_2.html')

def upload_data(request):
    return render(request, 'data_upload.html')

def recipe_prices(request):
    recipes = CookingRecipe.objects.prefetch_related('items').all()
    return render(request, 'recipe_catalog.html', {'recipes': recipes})
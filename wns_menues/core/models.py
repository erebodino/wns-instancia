from django.db import models

class Ingredient(models.Model):
    """
    Represents an ingredient that can be used in a cooking recipe.
    """
    name = models.CharField(max_length=150, unique=True)
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (${self.price_per_kg}/kg)"


class CookingRecipe(models.Model):
    """
    The header of the recipe.
    """
    name = models.CharField(max_length=200, unique=True)
    instructions = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.name


class CookingRecipeItem(models.Model):
    """
    Intermediate table. Links Recipe <-> Ingredient.
    Saves the original quantity of the recipe and the calculated quantity for purchase.
    """
    recipe = models.ForeignKey(CookingRecipe, related_name='items', on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.SET_NULL, null=True, blank=True)
    quantity_raw = models.DecimalField(max_digits=8, decimal_places=3)
    quantity_normalized = models.DecimalField(max_digits=8, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ingredient.name} - {self.quantity_raw} kg"

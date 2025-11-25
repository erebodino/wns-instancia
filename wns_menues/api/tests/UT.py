import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.utils import timezone
from api.services import PricingService
from core.models import CookingRecipe, Ingredient, CookingRecipeItem

@pytest.mark.django_db
class TestPricingService:
    """
    Unit tests for PricingService.
    Tests recipe cost calculation and currency conversion.
    """

    def setup_method(self):
        self.service = PricingService()
        
        # Setup basic data
        self.ingredient = Ingredient.objects.create(
            name='carne', 
            price_per_kg=1000.0
        )
        self.recipe = CookingRecipe.objects.create(name='Asado')
        CookingRecipeItem.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity_raw=1.0,
            quantity_normalized=1.0
        )

    @patch('api.services.requests.get')
    def test_calculate_cost_normal_case(self, mock_get):
        """
        Test normal cost calculation with successful external API call.
        """
        # Mock API response for USD rate = 1000 ARS
        mock_response = MagicMock()
        mock_response.json.return_value = {'usd': {'ars': 1000.0}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        target_date = (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        result = self.service.calculate_recipe_cost(self.recipe.id, target_date)
        
        # Cost in ARS = 1.0 kg * 1000 $/kg = 1000
        # Cost in USD = 1000 ARS / 1000 rate = 1.0 USD
        assert result['total_ars'] == 1000.0
        assert result['total_usd'] == 1.0
        assert result['exchange_rate'] == 1000.0
        assert result['recipe_name'] == 'Asado'

    def test_calculate_cost_invalid_recipe(self):
        """
        Test error when recipe ID does not exist.
        """
        with pytest.raises(ValueError, match="La receta solicitada no existe"):
            self.service.calculate_recipe_cost(999, "2023-01-01")

    def test_calculate_cost_invalid_date_format(self):
        """
        Test error when date format is incorrect.
        """
        with pytest.raises(ValueError, match="Formato de fecha inválido"):
            self.service.calculate_recipe_cost(self.recipe.id, "01-01-2023")

    def test_calculate_cost_date_out_of_range(self):
        """
        Test error when date is older than 30 days.
        """
        old_date = (timezone.now() - timedelta(days=31)).strftime("%Y-%m-%d")
        with pytest.raises(ValueError, match="La fecha debe estar dentro de los últimos 30 días"):
            self.service.calculate_recipe_cost(self.recipe.id, old_date)

    @patch('api.services.requests.get')
    def test_calculate_cost_api_failure(self, mock_get):
        """
        Test error handling when external API fails.
        """
        mock_get.side_effect = Exception("Connection timeout")
        
        target_date = (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        with pytest.raises(ValueError, match="No se pudo obtener la cotización"):
            self.service.calculate_recipe_cost(self.recipe.id, target_date)

    @patch('api.services.requests.get')
    def test_calculate_cost_zero_cost_items(self, mock_get):
        """
        Test calculation with items that have 0 cost.
        """
        # Add free ingredient
        water = Ingredient.objects.create(name='water', price_per_kg=0.0)
        CookingRecipeItem.objects.create(
            recipe=self.recipe,
            ingredient=water,
            quantity_raw=1.0,
            quantity_normalized=1.0
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {'usd': {'ars': 1000.0}}
        mock_get.return_value = mock_response

        target_date = (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        result = self.service.calculate_recipe_cost(self.recipe.id, target_date)

        # Cost should still be 1000 (1000 + 0)
        assert result['total_ars'] == 1000.0

    @patch('api.services.requests.get')
    def test_calculate_cost_missing_ingredient_link(self, mock_get):
        """
        Test calculation gracefully handles items with missing ingredient links (integrity check).
        """
        # Create item without ingredient
        CookingRecipeItem.objects.create(
            recipe=self.recipe,
            ingredient=None,
            quantity_raw=1.0,
            quantity_normalized=1.0
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {'usd': {'ars': 1000.0}}
        mock_get.return_value = mock_response

        target_date = (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        result = self.service.calculate_recipe_cost(self.recipe.id, target_date)

        # Should ignore the broken item
        assert result['total_ars'] == 1000.0


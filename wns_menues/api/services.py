import requests
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from core.models import CookingRecipe

class PricingService:
    """
    Service responsible for calculating recipe costs.

    Handles currency conversion and recipe pricing logic.
    """
    
    API_URL_TEMPLATE = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/v1/currencies/usd.json"

    def calculate_recipe_cost(self, recipe_id: int, date_str: str) -> dict:
        """
        Calculates the cost in ARS and USD for a given recipe and date.

        Args:
            recipe_id (int): The ID of the recipe to calculate.
            date_str (str): The date for the calculation in "YYYY-MM-DD" format.

        Returns:
            dict: A dictionary containing the recipe name, total cost in ARS and USD,
                  and the exchange rate used.

        Raises:
            ValueError: If the recipe does not exist, the date format is invalid,
                        or the date is not within the last 30 days.
        """
        # 1. Validar Receta
        try:
            recipe = CookingRecipe.objects.prefetch_related('items__ingredient').get(pk=recipe_id)
        except CookingRecipe.DoesNotExist:
            raise ValueError("La receta solicitada no existe.")

        # 2. Validar Fecha (Últimos 30 días)
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Formato de fecha inválido. Use YYYY-MM-DD.")
            
        today = timezone.now().date()
        limit_date = today - timedelta(days=30)
        
        if target_date > today or target_date < limit_date:
            raise ValueError("La fecha debe estar dentro de los últimos 30 días.")

        # 3. Calcular Costo en Pesos (ARS)
        total_ars = Decimal('0.00')

        for item in recipe.items.all():
            # Solo sumamos si el ingrediente existe y tiene precio (Integridad)
            if item.ingredient:
                cost = item.quantity_normalized * item.ingredient.price_per_kg
                total_ars += cost

        # 4. Obtener Cotización Dólar (External API)
        usd_rate = self._get_usd_rate(target_date)
        
        # 5. Conversión
        total_usd = total_ars / usd_rate if usd_rate else 0

        return {
            "recipe_name": recipe.name,
            "total_ars": float(total_ars),
            "total_usd": float(total_usd),
            "exchange_rate": float(usd_rate),
        }

    def _get_usd_rate(self, date_obj) -> Decimal:
        """
        Queries the external API to retrieve the USD exchange rate.

        Args:
            date_obj (date): The date object for which to get the exchange rate.

        Returns:
            Decimal: The USD to ARS exchange rate.

        Raises:
            ValueError: If the exchange rate cannot be retrieved.
        """
        date_str = date_obj.strftime("%Y-%m-%d")
        url = self.API_URL_TEMPLATE.format(date=date_str)
        
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            rate = Decimal(str(data['usd']['ars']))
            return rate
        except Exception as e:
            raise ValueError(f"No se pudo obtener la cotización del dólar para {date_str}: {str(e)}")
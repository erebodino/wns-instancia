import requests
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from core.models import CookingRecipe

class PricingService:
    
    API_URL_TEMPLATE = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/v1/currencies/usd.json"

    def calculate_recipe_cost(self, recipe_id: int, date_str: str) -> dict:
        """
        Calcula el costo en ARS y USD para una receta y fecha dadas.
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
        """Consulta la API externa"""
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
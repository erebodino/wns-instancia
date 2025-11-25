from typing import List, Dict, Any, IO, Tuple
from django.db import transaction
from core.models import Ingredient, CookingRecipe, CookingRecipeItem
from decimal import Decimal
import math
from core.parsers import FileParser

class ETLService:
    """
    Service responsible for Extract, Transform, Load (ETL) logic.

    Handles atomic transactions to ensure data integrity during data import.
    """

    def import_meats(self, file_obj: IO) -> str:
        """
        Import meat product data from an Excel file.

        Args:
            file_obj (IO): The Excel file object to import.

        Returns:
            Dict[str, Any]: A summary of the import process status.

        Raises:
            Exception: If the ETL process fails.
        """
        result_summary = {
            'precios_creados': 0
        }
        try:
            with transaction.atomic():
                raw_carnes = FileParser.parse_excel(file_obj)
                self._save_base_ingredients(raw_carnes)
                result_summary['precios_creados'] = len(raw_carnes)
                return {
                    "status": "success" if result_summary['precios_creados'] > 0 else "failed",
                    "type": "carnes",
                    "processed_count": result_summary['precios_creados'],
                    "total_input": len(raw_carnes)
                }
        except Exception as e:
            raise Exception(f"Fallo en el proceso ETL: {str(e)}")
    
    def import_vegetables(self, file_obj: IO) -> str:
        """
        Import vegetable product data from a PDF file.

        Args:
            file_obj (IO): The PDF file object to import.

        Returns:
            Dict[str, Any]: A summary of the import process status.

        Raises:
            Exception: If the ETL process fails.
        """
        result_summary = {
            'precios_creados': 0
        }
        try:
            with transaction.atomic():
                raw_verduras = FileParser.parse_pdf(file_obj)
                self._save_base_ingredients(raw_verduras)
                result_summary['precios_creados'] = len(raw_verduras)
                return {
                    "status": "success" if result_summary['precios_creados'] > 0 else "failed",
                    "type": "verduras",
                    "processed_count": result_summary['precios_creados'],
                    "total_input": len(raw_verduras)
                }
        except Exception as e:
            raise Exception(f"Fallo en el proceso ETL: {str(e)}")
    
    def import_recipes(self, file_obj: IO) -> str:
        """
        Import recipe data from a Markdown file.

        Args:
            file_obj (IO): The Markdown file object to import.

        Returns:
            Dict[str, Any]: A summary of the import process status.

        Raises:
            Exception: If the ETL process fails.
        """
        result_summary = {
            'recetas_creadas': 0,
            'recetas_fallidas': []
        }
        try:
            with transaction.atomic():
                CookingRecipe.objects.all().delete()
                raw_recetas = FileParser.parse_md(file_obj.read().decode('utf-8'))
                created_count, errors = self._save_cooking_recipe(raw_recetas)
                return {
                    "status": "success" if created_count > 0 else "failed",
                    "type": "recetas",
                    "processed_count": created_count,
                    "errors": errors,
                    "total_input": len(raw_recetas)
                }
        except Exception as e:
            raise Exception(f"Fallo en el proceso ETL: {str(e)}")

    def _save_base_ingredients(self, data: List[Dict[str, Any]]):
        """
        Persist base ingredients to the database.

        Args:
            data (List[Dict[str, Any]]): A list of dictionaries containing
                'nombre' (str) and 'precio' (float).

        Returns:
            int: The number of ingredients processed.
        """
        ingredients_objs = []
        
        for item in data:
            name_clean = item['nombre'].strip().lower()
            ingredients_objs.append(Ingredient(
                name=name_clean,
                price_per_kg=item['precio']
            ))
        
        # bulk_create devuelve la lista de objetos
        objs = Ingredient.objects.bulk_create(
            ingredients_objs,
            update_conflicts=True,
            unique_fields=['name'],
            update_fields=['price_per_kg', 'updated_at']
        )

        # Retornamos simplemente la cantidad total procesada
        return len(objs)

    def _save_cooking_recipe(self, data: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
        """
        Save recipes to the database, ensuring all ingredients exist.

        Recipes are saved only if all their ingredients match existing entries in the database.

        Args:
            data (List[Dict[str, Any]]): A list of recipe dictionaries. Each dictionary should contain:
                - 'nombre' (str): Recipe name.
                - 'ingredientes' (List[Dict]): List of ingredients with 'nombre' and 'cantidad_kg'.
                - 'instrucciones' (str): Cooking instructions.

        Returns:
            Tuple[int, List[str]]: A tuple containing the count of created recipes and a list of error messages.
        """
        db_ingredients = {ing.name.lower(): ing for ing in Ingredient.objects.all()}
        print(f"db_ingredients: {db_ingredients}")

        created_count = 0
        errors = []

        for receta_data in data:
            nombre_receta = receta_data['nombre']
            ingredientes_input = receta_data['ingredientes']
            
            missing_ingredients = []
            valid_items_buffer = []

            for item in ingredientes_input:
                raw_name = item['nombre'].strip().lower()
                
                if raw_name not in db_ingredients:
                    missing_ingredients.append(item['nombre']) # Guardamos el nombre original para el msj
                else:
                    valid_items_buffer.append({
                        'ingredient_obj': db_ingredients[raw_name],
                        'raw_name': item['nombre'],
                        'raw_qty': float(item['cantidad_kg'])
                    })


            if missing_ingredients:
                miss_str = ", ".join(missing_ingredients)
                errors.append(f"Receta '{nombre_receta}': El ingrediente ({miss_str}) no existe en la base de datos")
                continue


            recipe = CookingRecipe.objects.create(
                name=nombre_receta,
                instructions=receta_data['instrucciones']
            )

            items_objs = []
            for item_data in valid_items_buffer:

                raw_qty = item_data['raw_qty']
                qty_normalized = math.ceil(raw_qty / 0.25) * 0.25

                items_objs.append(CookingRecipeItem(
                    recipe=recipe,
                    ingredient=item_data['ingredient_obj'],
                    quantity_raw=Decimal(str(raw_qty)),
                    quantity_normalized=Decimal(str(qty_normalized))
                ))
            
            CookingRecipeItem.objects.bulk_create(items_objs)
            created_count += 1

        return created_count, errors
import re
import pdfplumber
import pandas as pd
from typing import List, Dict, Any, IO, Optional, Tuple
from django.db import transaction
from logging import getLogger
from core.models import Ingredient, CookingRecipe, CookingRecipeItem
from decimal import Decimal
import math

logger = getLogger(__name__)

class FileParser:
    """
    Clase utilitaria para extraer información estructurada
    de archivos PDF, Excel y Markdown.
    """


    @staticmethod
    def parse_excel(file_buffer: IO) -> List[Dict[str, Any]]:
        """
        Busca celdas con precios ($ o números) y extrae el producto de la celda izquierda.
        """
        try:
            df = pd.read_excel(file_buffer, engine='openpyxl', header=None)
            productos = []
            
            ENCABEZADOS = {'carnicería', 'carne vacuna', 'carne de cerdo', 'corte', 'precio'}
            
            for row_idx in range(len(df)):
                for col_idx in range(1, len(df.columns)):  # Empezar en col 1 (necesitamos izquierda)
                    
                    precio_raw = df.iloc[row_idx, col_idx]
                    
                    # Saltar si no hay valor
                    if pd.isna(precio_raw):
                        continue
                    
                    precio_str = str(precio_raw).strip()
                   
                    # Debe contener $ o ser numérico
                    if '$' not in precio_str and not re.search(r'[\d\.,]+', precio_str):
                        continue
                    
                    # Extraer número
                    match = re.search(r'([\d\.,]+)', precio_str)
                    if not match:
                        continue
                    
                    try:
                        precio = float(match.group(1).replace('.', '').replace(',', '.'))
                    except ValueError:
                        continue
                    
                    # Obtener nombre (celda izquierda)
                    nombre_raw = df.iloc[row_idx, col_idx - 1]
                    if pd.isna(nombre_raw):
                        continue
                    
                    nombre = str(nombre_raw).strip()
                    
                    # Validaciones finales
                    if (not nombre or 
                        nombre.lower() in ENCABEZADOS or 
                        nombre.replace('.', '').replace(',', '').isdigit()):
                        continue
                    
                    productos.append({
                        'nombre': nombre,
                        'precio': precio,
                    })
            return productos
        
        except Exception as e:
            raise ValueError(f"Error al procesar el Excel de carnes: {str(e)}")

    @staticmethod
    def parse_pdf(file_buffer: IO) -> List[Dict[str, Any]]:
        """
        Lee el PDF de la verdulería usando pdfplumber.
        Extrae nombres y precios de verduras.
        """
        productos = []
        try:
            with pdfplumber.open(file_buffer) as pdf:
                full_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
                
                lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                for line in lines:
                    if '$' in line:

                        nombre = line.split('$')[0].strip()
                        precio = line.split('$')[1].strip().replace('.', '')
                        productos.append({
                            'nombre': nombre,
                            'precio': float(precio),
                        })
                return productos
                
        except Exception as e:
            raise ValueError(f"Error al procesar el PDF de verduras: {str(e)}")

    @staticmethod
    def parse_md(file_content: str) -> List[Dict[str, Any]]:
        """
        Parsea el contenido de texto del archivo Markdown.
        """
        recetas = []
        lines = file_content.split('\n')
        current_receta = {}
        reading_ingredientes = False
        
        # Regex para capturar ingredientes (soporta "1 kg de X" y "X: 1 kg")
        regex_ing = re.compile(
            r'(?:^[-*a-zA-Z0-9]+\.?\s+)(?:(?P<c1>[\d,.]+)\s*(?P<u1>kg|g)\s*de\s*(?P<n1>.+)|(?P<n2>.+):\s*(?P<c2>[\d,.]+)\s*(?P<u2>kg|g))',
            re.IGNORECASE
        )

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detectar Título (# Nombre)
            if line.startswith('# '):
                if current_receta:
                    recetas.append(current_receta)
                current_receta = {
                    'nombre': line.replace('# ', '').strip(),
                    'ingredientes': [],
                    'instrucciones': ''
                }
                reading_ingredientes = False

            # Detectar Sección
            elif ('ingredientes' in line.lower() or 'lista' in line.lower()) and line.startswith('##'):
                reading_ingredientes = True
            elif ('instrucciones' in line.lower() or 'preparación' in line.lower()) and line.startswith('##'):
                reading_ingredientes = False

            # Parsear Ingrediente
            elif reading_ingredientes:
                match = regex_ing.search(line)
                if match:
                    parts = match.groupdict()
                    cant = parts['c1'] or parts['c2']
                    unit = parts['u1'] or parts['u2']
                    name = parts['n1'] or parts['n2']
                    
                    if cant and unit and name:
                        try:
                            cant_float = float(cant.replace(',', '.'))
                            # Normalizar a KG
                            if unit.lower() == 'g':
                                cant_float /= 1000.0
                            
                            
                            
                            current_receta['ingredientes'].append({
                                'nombre': name.strip(),
                                'cantidad_kg': cant_float
                            })
                        except ValueError:
                            pass
            
            # Guardar instrucciones
            elif current_receta and not reading_ingredientes and not line.startswith('#'):
                current_receta['instrucciones'] += line + "\n"

        if current_receta:
            recetas.append(current_receta)
        
        import pprint
        pprint.pprint(recetas)
        return recetas



class ETLService:
    """
    Servicio encargado de la lógica de carga de datos (ETL).
    Maneja transacciones atómicas para asegurar integridad.
    """

    def import_meats(self, file_obj: IO) -> str:
        """
        Importa datos desde un archivo Excel.
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
        Importa datos desde un archivo PDF.
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
        Importa datos desde un archivo MD.
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
        Persists base ingredients.
        args:
            data: list of dicts {'nombre': str, 'precio': float}
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
        Saves recipes only if all their ingredients exist in the database (Exact Match).
        args:
            data: list of dicts {'nombre': str, 'ingredientes': list of dicts {'nombre': str, 'cantidad_kg': float}}
        returns:
            tuple: (created_count, errors)
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



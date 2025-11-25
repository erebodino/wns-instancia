import re
import pdfplumber
import pandas as pd
from typing import List, Dict, Any, IO, Tuple
from django.db import transaction
from core.models import Ingredient, CookingRecipe, CookingRecipeItem
from decimal import Decimal
import math


class FileParser:
    """Utility class for extracting structured information from PDF, Excel, and Markdown files."""


    @staticmethod
    def parse_excel(file_buffer: IO) -> List[Dict[str, Any]]:
        """
        Parse an Excel file to extract product names and prices.

        Scans cells for prices (indicated by '$' or numeric values) and extracts the
        product name from the cell immediately to the left.

        Args:
            file_buffer (IO): The file-like object containing the Excel data.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing 'nombre' and 'precio'.

        Raises:
            ValueError: If an error occurs during processing.
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
        Parse a PDF file to extract vegetable names and prices.

        Uses pdfplumber to read the PDF content and extracts lines containing prices.

        Args:
            file_buffer (IO): The file-like object containing the PDF data.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing 'nombre' and 'precio'.

        Raises:
            ValueError: If an error occurs during processing.
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
        Parse Markdown content to extract recipes.

        Parses the text content to identify recipe titles, ingredients, and instructions.

        Args:
            file_content (str): The content of the Markdown file as a string.

        Returns:
            List[Dict[str, Any]]: A list of recipes with 'nombre', 'ingredientes', and 'instrucciones'.
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






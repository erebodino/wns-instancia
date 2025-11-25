import io
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from decimal import Decimal
from core.parsers import FileParser
from core.services import ETLService
from core.models import Ingredient, CookingRecipe


class TestFileParser:
    """
    Unit tests for the FileParser class.
    Tests parsing of Excel, PDF, and Markdown files.
    """

    def test_parse_excel_normal_case(self):
        """
        Test parsing a valid Excel file with standard 2-column layout.
        """
        # Create a sample DataFrame resembling the Excel file
        data = {
            0: ['Carnicería', 'Asado', 'Vacío', 'Pollo'],  # Column A (Names)
            1: ['Precio', '$ 1.200', '1500,50', '800'],    # Column B (Prices)
        }
        df = pd.DataFrame(data)
        
        # Mock pd.read_excel to return this DataFrame
        with patch('pandas.read_excel', return_value=df):
            # The file_buffer argument is ignored by the mock
            result = FileParser.parse_excel(io.BytesIO(b"dummy"))
            
        assert len(result) == 3
        assert result[0]['nombre'] == 'Asado'
        assert result[0]['precio'] == 1200.0
        assert result[1]['nombre'] == 'Vacío'
        assert result[1]['precio'] == 1500.50
        assert result[2]['nombre'] == 'Pollo'
        assert result[2]['precio'] == 800.0

    def test_parse_excel_edge_cases(self):
        """
        Test parsing Excel with "dirty" data (inconsistent formats, empty rows).
        """
        data = {
            0: ['Corte', 'Matambre', None, 'Chorizo', '123'], 
            1: ['Precio', '$ 2.000', '500', 'invalid', '100'], 
        }
        df = pd.DataFrame(data)

        with patch('pandas.read_excel', return_value=df):
            result = FileParser.parse_excel(io.BytesIO(b"dummy"))

        # Should capture Matambre ($ 2.000)
        # Should skip row 2 (None name)
        # Should skip row 3 (invalid price)
        # Should skip row 4 (numeric name '123')
        
        assert len(result) == 1
        assert result[0]['nombre'] == 'Matambre'
        assert result[0]['precio'] == 2000.0

    def test_parse_excel_error(self):
        """
        Test error handling when Excel parsing fails.
        """
        with patch('pandas.read_excel', side_effect=Exception("File corrupted")):
            with pytest.raises(ValueError, match="Error al procesar el Excel de carnes"):
                FileParser.parse_excel(io.BytesIO(b"dummy"))
    
    @pytest.mark.this
    def test_parse_pdf_normal_case(self):
        """
        Test parsing a valid PDF with vegetable prices.
        """
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Papa $ 500\nLechuga $ 1.200\nTomate 300" # Tomate missing $
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__.return_value = mock_pdf
        
        with patch('pdfplumber.open', return_value=mock_pdf):
            result = FileParser.parse_pdf(io.BytesIO(b"dummy"))

        # Should capture Papa and Lechuga, skip Tomate (no $)
        assert len(result) == 2
        assert result[0]['nombre'] == 'Papa'
        assert result[0]['precio'] == 500.0
        assert result[1]['nombre'] == 'Lechuga'
        assert result[1]['precio'] == 1200.0

    def test_parse_pdf_error(self):
        """
        Test error handling when PDF parsing fails.
        """
        with patch('pdfplumber.open', side_effect=Exception("Corrupted PDF")):
            with pytest.raises(ValueError, match="Error al procesar el PDF de verduras"):
                FileParser.parse_pdf(io.BytesIO(b"dummy"))

    def test_parse_md_normal_case(self):
        """
        Test parsing a valid Markdown file with recipes.
        """
        md_content = """
            # Pastel de Papa
            ## Ingredientes
            - 1 kg de Papa
            - Carne: 0.5 kg
            ## Instrucciones
            Hervir papa.
            Cocinar carne.

            # Ensalada
            ## Lista
            - 200 g de Lechuga
            ## Preparación
            Lavar lechuga.
                    """
        result = FileParser.parse_md(md_content)

        assert len(result) == 2
        
        # Recipe 1
        r1 = result[0]
        assert r1['nombre'] == 'Pastel de Papa'
        assert len(r1['ingredientes']) == 2
        assert r1['ingredientes'][0]['nombre'] == 'Papa'
        assert r1['ingredientes'][0]['cantidad_kg'] == 1.0
        assert r1['ingredientes'][1]['nombre'] == 'Carne'
        assert r1['ingredientes'][1]['cantidad_kg'] == 0.5
        assert "Hervir papa" in r1['instrucciones']

        # Recipe 2
        r2 = result[1]
        assert r2['nombre'] == 'Ensalada'
        assert len(r2['ingredientes']) == 1
        assert r2['ingredientes'][0]['nombre'] == 'Lechuga'
        assert r2['ingredientes'][0]['cantidad_kg'] == 0.2  # 200g -> 0.2kg

    def test_parse_md_edge_cases(self):
        """
        Test edge cases in Markdown parsing (missing sections, invalid formats).
        """
        md_content = """
                # Receta Rota
                ## Ingredientes
                - Una pizca de sal
                - 1 litro de leche
                ## Instrucciones
                Mezclar.
                """
        result = FileParser.parse_md(md_content)
        
        # Should capture recipe but ignore ingredients that don't match regex
        assert len(result) == 1
        assert result[0]['nombre'] == 'Receta Rota'
        assert len(result[0]['ingredientes']) == 0




@pytest.mark.django_db
class TestETLService:
    """
    Unit tests for ETLService.
    Tests import logic and database interactions.
    """

    def setup_method(self):
        self.service = ETLService()

    @patch('core.parsers.FileParser.parse_excel')
    def test_import_meats_success(self, mock_parse):
        """
        Test successful import of meats (ingredients).
        """
        mock_parse.return_value = [
            {'nombre': 'Asado', 'precio': 1000.0},
            {'nombre': 'Pollo', 'precio': 500.0}
        ]
        
        result = self.service.import_meats(io.BytesIO(b"dummy"))
        
        assert result['status'] == 'success'
        assert result['processed_count'] == 2
        assert Ingredient.objects.count() == 2
        assert Ingredient.objects.get(name='asado').price_per_kg == 1000.0

    @patch('core.parsers.FileParser.parse_excel')
    def test_import_meats_update_existing(self, mock_parse):
        """
        Test that existing ingredients are updated with new prices.
        """
        Ingredient.objects.create(name='asado', price_per_kg=800.0)
        
        mock_parse.return_value = [
            {'nombre': 'Asado', 'precio': 1200.0}
        ]
        
        result = self.service.import_meats(io.BytesIO(b"dummy"))
        
        assert result['processed_count'] == 1
        assert Ingredient.objects.count() == 1
        assert Ingredient.objects.get(name='asado').price_per_kg == 1200.0

    @patch('core.parsers.FileParser.parse_md')
    def test_import_recipes_success(self, mock_parse):
        """
        Test successful import of recipes.
        """
        # Pre-create ingredients
        Ingredient.objects.create(name='papa', price_per_kg=100.0)
        Ingredient.objects.create(name='carne', price_per_kg=1000.0)

        mock_parse.return_value = [{
            'nombre': 'Pastel',
            'ingredientes': [
                {'nombre': 'Papa', 'cantidad_kg': 1.0},
                {'nombre': 'Carne', 'cantidad_kg': 0.5}
            ],
            'instrucciones': 'Cocinar.'
        }]

        result = self.service.import_recipes(MagicMock())

        assert result['status'] == 'success'
        assert CookingRecipe.objects.count() == 1
        recipe = CookingRecipe.objects.first()
        assert recipe.name == 'Pastel'
        assert recipe.items.count() == 2
        
        # Check normalization (logic in _save_cooking_recipe: ceil(qty / 0.25) * 0.25)
        # 0.5 -> 0.5
        # 1.0 -> 1.0
        item = recipe.items.get(ingredient__name='carne')
        assert item.quantity_normalized == Decimal('0.50')

    @patch('core.parsers.FileParser.parse_md')
    def test_import_recipes_missing_ingredient(self, mock_parse):
        """
        Test recipe import when an ingredient is missing in DB.
        """
        mock_parse.return_value = [{
            'nombre': 'Fantasma',
            'ingredientes': [
                {'nombre': 'Unicornio', 'cantidad_kg': 1.0}
            ],
            'instrucciones': '...'
        }]

        result = self.service.import_recipes(MagicMock())

        assert result['status'] == 'failed'
        assert result['processed_count'] == 0
        assert len(result['errors']) == 1
        assert "Unicornio" in result['errors'][0]
        assert CookingRecipe.objects.count() == 0

    @patch('core.parsers.FileParser.parse_md')
    def test_import_recipes_normalization(self, mock_parse):
        """
        Test quantity normalization logic (rounding up to nearest 0.25).
        """
        Ingredient.objects.create(name='harina', price_per_kg=100.0)
        
        mock_parse.return_value = [{
            'nombre': 'Pan',
            'ingredientes': [
                {'nombre': 'Harina', 'cantidad_kg': 0.3} # Should round to 0.5
            ],
            'instrucciones': '...'
        }]

        self.service.import_recipes(MagicMock())
        
        recipe = CookingRecipe.objects.get(name='Pan')
        item = recipe.items.first()
        # 0.3 -> ceil(0.3/0.25)*0.25 -> ceil(1.2)*0.25 -> 2*0.25 -> 0.5
        assert item.quantity_normalized == Decimal('0.50')


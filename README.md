# WNS Menu Pricing & ETL System

Sistema integral para la gestión automatizada de costos de recetas e ingesta de datos de proveedores. Esta solución procesa archivos heterogéneos (PDF, Excel, Markdown) para actualizar precios de ingredientes y recalcular costos de menús dinámicamente.

## 📋 Tabla de Contenidos
1. [Descripción General](#descripción-general)
2. [Arquitectura y Diseño](#arquitectura-y-diseño)
3. [Instalación y Ejecución](#instalación-y-ejecución)
4. [Decisiones Técnicas](#decisiones-técnicas)
5. [Supuestos y Limitaciones](#supuestos-y-limitaciones)
6. [Escalabilidad y Futuro](#escalabilidad-y-futuro)

---

## Descripción General

El objetivo del proyecto es resolver un challenge tecnico para WNS. El sistema actúa como un pipeline ETL (Extract, Transform, Load) que:
1.  **Extrae** información no estructurada de listas de precios de proveedores (PDFs, Excels) y recetas (Markdown).
2.  **Transforma** y normaliza unidades (conversión a KG, normalización de cantidades).
3.  **Carga** la información en una base de datos relacional manteniendo la integridad referencial.
4.  **Calcula** el costo de una receta en ARS y USD según una fecha específica provista por el usuario.

---

## Arquitectura y Diseño

El proyecto fue construido utilizando **Python 3.x** y **Django**, siguiendo una arquitectura híbrida:

*   **Backend Core (Django):** Maneja la persistencia de datos, el ORM y la lógica de negocio principal.
*   **Service Layer (`core/parsers.py`):** Se implementó un patrón de *Servicios* (`ETLService`) para desacoplar la lógica de extracción de las vistas. Esto facilita el testing unitario y la reutilización de código.
*   **API REST (Django Rest Framework):** Expone endpoints para las operaciones de carga (POST) y cálculo, permitiendo que el frontend opere de manera asíncrona sin recargas completas.
*   **Frontend (Django Templates):** Se utiliza *Server-Side Rendering* (SSR) para la entrega rápida de vistas de lectura (GET), manteniendo la simplicidad del desarrollo.

### Stack Tecnológico
*   **Web Framework:** Django + DRF
*   **Data Processing:** `pandas`, `openpyxl` (Excel), `pdfplumber` (PDF)
*   **Frontend:** JavaScript
*   **Testing:** pytest
*   **Database:** SQLite
*   **Deployment:** Docker

---

## Instalación y Ejecución

### Requisitos Previos
*   Docker y Docker Compose (Recomendado)

### Despliegue con Docker
El proyecto incluye una configuración de contenedores para facilitar el despliegue inmediato.

1. Clonar el repositorio:
   git clone <URL_DEL_REPO>
   cd wns-instancia
   2. Levantar los servicios:
   docker-compose up -d --build
   3. Acceder a la aplicación en: `http://localhost:8000`


## Decisiones Técnicas

### 1. Integridad de Datos y Atomicidad
Dada la naturaleza crítica de los precios, todas las operaciones de importación están envueltas en `transaction.atomic()`.
*   **Justificación:** Si un archivo de 100 recetas falla en la receta #99, el sistema hace rollback completo. Esto evita estados inconsistentes en la base de datos (ej. ingredientes creados sin recetas asociadas).

### 2. Lógica de Parsing (Regex vs. Librerías)
*   **PDFs:** Se utilizó `pdfplumber` por su precisión en la extracción de tablas basadas en texto.
*   **Excel:** Se optó por `pandas` debido a su robustez para manejar filas vacías y tipos de datos inconsistentes en las columnas de precios.
*   **Markdown:** Se implementó un parser basado en Expresiones Regulares (Regex) customizadas para detectar patrones de ingredientes (`cantidad unidad de ingrediente`), permitiendo flexibilidad en la redacción de las recetas.

### 3. Separación de Responsabilidades (Parsers vs Views)
La lógica de lectura de archivos se extrajo de las Vistas y se movió a `FileParser` y `ETLService`.
*   **Fortaleza:** Las Vistas solo se encargan de recibir la HTTP Request y devolver la Response. El "cómo" se procesa el archivo es transparente para la vista.
*   **Debilidad:** Agrega una capa extra de complejidad inicial, pero paga dividendos en mantenibilidad.

---

## Supuestos y Limitaciones

Para el correcto funcionamiento del sistema, se asume lo siguiente:

1.  **Estructura de Archivos:** Aunque el contenido (precios, nombres) puede cambiar, la estructura semántica de los archivos de entrada debe mantenerse (ej. los Excels de carne deben tener la columna de precio a la derecha del nombre del corte).
2.  **Normalización de Unidades:** El sistema normaliza internamente a Kilogramos (KG). Recetas en unidades no estandarizadas (ej. "una pizca") no son soportadas actualmente por el motor de cálculo automático.
3.  **Coincidencia de Nombres:** El matcheo entre ingredientes de recetas y listas de precios es por **coincidencia exacta de nombre**. "Cebolla" no matcheará automáticamente con "Cebolla Morada". De esta manera se evita que un ingrediente mal escrito sea incluido.

---

## Escalabilidad y Futuro

Si se deseara llevar esta solución a un entorno de producción masivo, implementaría los siguientes cambios:

1.  **Procesamiento Asíncrono (Celery + Redis):** Actualmente, el parsing se hace en el hilo de la request. Para archivos grandes (>10MB o cientos de páginas), esto bloquearía el servidor. La solución es mover el procesamiento a una cola de tareas background (Workers) y notificar al usuario cuando la carga finalice.

2.  **Strategy Pattern para Parsers:** Refactorizar la clase `FileParser` para implementar un patrón *Strategy* completo. Esto permitiría agregar nuevos "Proveedores" (con formatos de archivo distintos) simplemente creando una nueva clase estrategia sin modificar el código existente.

3.  **Caching:** Implementar caché (ej. Memcached/Redis) para los cálculos de recetas consultadas frecuentemente, invalidando la caché solo cuando se sube una nueva lista de precios que afecte a dicha receta.

4. **LLMs** En caso de hacer que la app escale sin restriccion abierta a todos los posibles usuarios, seria imposible mantener una clase ETL para cada empresa/usuario. En ese caso utilizaria un LLM con un output validado con pydantic para que el LLM extraiga la información y la devuelva normalizada.

5. **Profiles**: El funcionamiento actual es muy basico. Si se va a escalar la app para varias empresas/usuarios, habria que generar un perfil, o bien una empresa que contenga perfiles y estos tienen sus ingredientes, recetas y precios. Es decir que se debe generar nuevos modelos para dar soporte a esta estructura. Se debera impleentar un Login, logout, etc.

6. **Documentación Automática (OpenAPI/Swagger)**: Dado el alcance acotado del desafío, no se incluyó documentación interactiva. En un entorno productivo, integraría la librería **`drf-spectacular`** para generar automáticamente una especificación **OpenAPI 3.0**. Esto permitiría exponer una interfaz **Swagger UI** o **Redoc**, facilitando que los desarrolladores frontend o clientes externos prueben los endpoints y entiendan los esquemas de datos sin necesidad de leer el código fuente.


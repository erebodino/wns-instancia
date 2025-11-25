#!/bin/sh

set -e

echo "Aplicando migraciones de base de datos..."
cd wns_menues

python manage.py migrate

echo "Iniciando servidor de desarrollo..."
python manage.py runserver 0.0.0.0:8000


import os

# Se ejecuta antes de importar la app: los tests no deben depender del .env de cada
# desarrollador. Crear el engine no abre conexión, así que esta URL ficticia alcanza.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
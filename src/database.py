from peewee import SqliteDatabase
from pathlib import Path

# 1. Descobre o caminho absoluto da pasta raiz do projeto
# (__file__ é o database.py, o primeiro parent é a pasta 'src', o segundo é a raiz 'radar-solar')
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Aponta para o ficheiro da base de dados dentro da pasta data/
CAMINHO_DB = BASE_DIR / 'data' / 'radarsolar.db'

# 3. Cria a instância de ligação à base de dados SQLite
db = SqliteDatabase(CAMINHO_DB)
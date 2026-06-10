from peewee import SqliteDatabase
from pathlib import Path

from src.utils import log_info, log_ok

BASE_DIR = Path(__file__).resolve().parent.parent
CAMINHO_DB = BASE_DIR / 'data' / 'radarsolar.db'

log_info(f'Banco SQLite: {CAMINHO_DB}')
db = SqliteDatabase(CAMINHO_DB, pragmas={'foreign_keys': 1})
log_ok('Conexao SQLite estabelecida com foreign_keys=ON')

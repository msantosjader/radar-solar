import sys
from pathlib import Path

# Garante que o Python encontra a pasta 'src' independentemente de onde o script for executado
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from src.models import criar_tabelas
from src.database import CAMINHO_DB

def inicializar_banco():
    print(f"A tentar criar a base de dados em: {CAMINHO_DB}")
    try:
        criar_tabelas()
        print("✅ SUCESSO! As tabelas foram criadas fisicamente no ficheiro radarsolar.db")
    except Exception as e:
        print(f"❌ ERRO ao criar a base de dados: {e}")

if __name__ == '__main__':
    inicializar_banco()
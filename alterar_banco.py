import sqlite3
conn = sqlite3.connect("caza.db")
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE estoque ADD COLUMN sabor TEXT")
except sqlite3.OperationalError:
    print("Coluna sabor já existe ou tabela não existe")

conn.commit()
conn.close()

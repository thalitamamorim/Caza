import sqlite3
import streamlit as st


def main():
    st.title("🛠️ Ferramenta de Correção do Banco de Dados")

    st.warning(
        "Use esta ferramenta apenas se estiver tendo problemas com a estrutura do banco de dados")

    if st.button("Executar Verificação/Correção"):
        try:
            conn = sqlite3.connect('data/caza.db')
            cursor = conn.cursor()

            # Verificar e adicionar colunas faltantes
            alteracoes = [
                ("gastos_insumos", "quantidade", "REAL"),
                ("gastos_insumos", "tipo", "TEXT"),
                ("gastos_insumos", "unidade_medida", "TEXT"),
                ("estoque", "sabor", "TEXT")
            ]

            for tabela, coluna, tipo in alteracoes:
                try:
                    cursor.execute(
                        f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
                    st.success(
                        f"Coluna '{coluna}' adicionada à tabela {tabela}")
                except sqlite3.OperationalError as e:
                    st.warning(
                        f"Coluna '{coluna}' já existe ou erro: {str(e)}")

            conn.commit()
            st.success("✅ Banco de dados verificado e corrigido com sucesso!")

        except Exception as e:
            st.error(f"❌ Erro durante a correção: {str(e)}")
        finally:
            if conn:
                conn.close()


if __name__ == "__main__":
    main()

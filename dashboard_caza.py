import streamlit as st
import sqlite3
import pandas as pd
from fpdf import FPDF
from datetime import date, datetime, timedelta
import calendar
import os

# Configuração inicial
st.set_page_config(layout="wide")

# Conexão com banco SQLite
conn = sqlite3.connect("caza.db", check_same_thread=False)
cursor = conn.cursor()

# Funções auxiliares


def formatar_data(data_iso):
    try:
        dt = datetime.strptime(data_iso, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return data_iso

# Criar tabelas (se não existirem)


def criar_tabelas():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recebimentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        forma_pagamento TEXT,
        valor REAL,
        observacao TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        item TEXT,
        quantidade INTEGER
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sobras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        item TEXT,
        quantidade INTEGER
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gastos_insumos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        item TEXT,
        valor REAL,
        observacao TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gastos_fixos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        descricao TEXT,
        valor REAL,
        observacao TEXT
    )""")
    conn.commit()


criar_tabelas()

# Classe para gerar PDF com formatação profissional


class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Relatório Diário - CAZÁ', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')


def formatar_nome_coluna(nome):
    """Formata nomes de colunas para título com maiúsculas"""
    substituicoes = {
        'forma_pagamento': 'Forma de Pagamento',
        'observacao': 'Observação',
        'descricao': 'Descrição'
    }
    return substituicoes.get(nome, nome.replace('_', ' ').title())


def gerar_pdf(data):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    # Buscar dados do dia
    tabelas = {
        "Recebimentos": "recebimentos",
        "Produção": "producao",
        "Sobras": "sobras",
        "Gastos com Insumos": "gastos_insumos",
        "Gastos Fixos": "gastos_fixos"
    }

    for titulo, tabela in tabelas.items():
        df = pd.read_sql_query(f"SELECT * FROM {tabela} WHERE data = ?",
                               conn, params=(data,))
        if not df.empty:
            # Título da seção
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, titulo, ln=1)
            pdf.set_font("Arial", size=10)

            # Preparar colunas
            colunas = [col for col in df.columns if col not in ['id', 'data']]
            col_widths = [45 if col != 'valor' else 30 for col in colunas]

            # Cabeçalhos
            for col, width in zip(colunas, col_widths):
                pdf.cell(width, 8, formatar_nome_coluna(
                    col), border=1, align='C')
            pdf.ln()

            # Dados
            for _, row in df.iterrows():
                for col, width in zip(colunas, col_widths):
                    valor = str(row[col])
                    # Formatação especial para valores
                    if col == 'valor':
                        valor = f"R$ {float(valor):.2f}"
                    pdf.cell(width, 8, valor, border=1)
                pdf.ln()
            pdf.ln(5)

    # Salvar PDF
    if not os.path.exists('relatorios'):
        os.makedirs('relatorios')

    data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%Y%m%d")
    filename = f"relatorios/relatorio_{data_formatada}.pdf"
    pdf.output(filename)
    return filename


def gerar_pdf_mensal(data_inicio, data_fim, mes_nome, ano):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f'Relatório Mensal - {mes_nome}/{ano}', 0, 1, 'C')
    pdf.ln(10)

    # Dados financeiros
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Resumo Financeiro", ln=1)
    pdf.set_font("Arial", size=10)

    # Recebimentos totais
    recebimentos = pd.read_sql_query(
        "SELECT SUM(valor) as total FROM recebimentos WHERE data BETWEEN ? AND ?",
        conn, params=(data_inicio, data_fim))
    total_receb = recebimentos['total'].sum() if not recebimentos.empty else 0

    # Gastos totais
    gastos = pd.read_sql_query(
        "SELECT 'Insumos' as tipo, SUM(valor) as total FROM gastos_insumos WHERE data BETWEEN ? AND ? "
        "UNION ALL SELECT 'Fixos' as tipo, SUM(valor) as total FROM gastos_fixos WHERE data BETWEEN ? AND ?",
        conn, params=(data_inicio, data_fim, data_inicio, data_fim))
    total_gastos = gastos['total'].sum() if not gastos.empty else 0
    saldo = total_receb - total_gastos

    # Adiciona métricas ao PDF
    pdf.cell(0, 8, f"Total Recebido: R$ {total_receb:,.2f}", ln=1)
    pdf.cell(0, 8, f"Total Gastos: R$ {total_gastos:,.2f}", ln=1)
    pdf.cell(0, 8, f"Saldo Mensal: R$ {saldo:,.2f}", ln=1)
    pdf.ln(10)

    # Recebimentos por dia
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Recebimentos por Dia", ln=1)
    pdf.set_font("Arial", size=10)

    recebimentos_dia = pd.read_sql_query(
        "SELECT data, SUM(valor) as total FROM recebimentos WHERE data BETWEEN ? AND ? GROUP BY data",
        conn, params=(data_inicio, data_fim))

    if not recebimentos_dia.empty:
        recebimentos_dia['data'] = recebimentos_dia['data'].apply(
            lambda x: formatar_data(x)[:5])  # Mostra apenas dia/mês
        for _, row in recebimentos_dia.iterrows():
            pdf.cell(40, 8, row['data'], border=1)
            pdf.cell(40, 8, f"R$ {row['total']:,.2f}", border=1, ln=1)
    else:
        pdf.cell(0, 8, "Nenhum recebimento registrado neste período", ln=1)

    pdf.ln(10)

    # Gastos por categoria
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Gastos por Categoria", ln=1)
    pdf.set_font("Arial", size=10)

    if not gastos.empty:
        for _, row in gastos.iterrows():
            pdf.cell(40, 8, row['tipo'], border=1)
            pdf.cell(40, 8, f"R$ {row['total']:,.2f}", border=1, ln=1)
    else:
        pdf.cell(0, 8, "Nenhum gasto registrado neste período", ln=1)

    # Salvar PDF
    if not os.path.exists('relatorios_mensais'):
        os.makedirs('relatorios_mensais')

    filename = f"relatorios_mensais/relatorio_{mes_nome}_{ano}.pdf"
    pdf.output(filename)
    return filename


# Interface principal
st.image("IMG_5950.jpg", width=300)
st.title("CAZÁ - Controle Diário")

# Menu de navegação
menu = st.sidebar.selectbox("Menu", ["Registro Diário", "Relatório Mensal"])

if menu == "Registro Diário":
    hoje = st.date_input("Data do Registro", value=date.today())
    data_str = hoje.strftime("%d/%m/%Y")
    data_iso = hoje.isoformat()

    # Seções de cadastro
    with st.expander("💰 Registro de Recebimentos", expanded=True):
        with st.form("form_recebimento"):
            forma = st.selectbox("Forma de Pagamento", [
                                 "Pix", "Dinheiro", "Cartão"])
            valor_str = st.text_input(
                "Valor Recebido (R$)", placeholder="Ex: 100.00 ou 50,50")
            obs = st.text_input("Observação (opcional)")
            if st.form_submit_button("Salvar Recebimento"):
                try:
                    valor = float(valor_str.replace(",", "."))
                    cursor.execute(
                        "INSERT INTO recebimentos (data, forma_pagamento, valor, observacao) VALUES (?, ?, ?, ?)",
                        (data_iso, forma, valor, obs))
                    conn.commit()
                    st.success("Recebimento registrado!")
                except ValueError:
                    st.error(
                        "Valor inválido. Use números com . ou , como separador decimal")

    with st.expander("🍲 Registro de Produção", expanded=True):
        with st.form("form_producao"):
            item_prod = st.text_input("Item Produzido")
            qtd_prod = st.number_input("Quantidade Produzida", min_value=0)
            if st.form_submit_button("Salvar Produção") and item_prod:
                cursor.execute(
                    "INSERT INTO producao (data, item, quantidade) VALUES (?, ?, ?)",
                    (data_iso, item_prod, qtd_prod))
                conn.commit()
                st.success("Produção registrada!")

    with st.expander("🧊 Registro de Sobras", expanded=True):
        with st.form("form_sobra"):
            item_sobra = st.text_input("Item com Sobra")
            qtd_sobra = st.number_input("Quantidade Sobrando", min_value=0)
            if st.form_submit_button("Salvar Sobra") and item_sobra:
                cursor.execute(
                    "INSERT INTO sobras (data, item, quantidade) VALUES (?, ?, ?)",
                    (data_iso, item_sobra, qtd_sobra))
                conn.commit()
                st.success("Sobra registrada!")

    with st.expander("🛒 Gastos com Insumos", expanded=True):
        with st.form("form_insumos"):
            item_gasto = st.text_input("Item do Insumo")
            valor_gasto = st.number_input(
                "Valor Gasto (R$)", min_value=0.0, format="%.2f")
            obs_gasto = st.text_input("Observação (opcional)")
            if st.form_submit_button("Salvar Gasto") and item_gasto:
                cursor.execute(
                    "INSERT INTO gastos_insumos (data, item, valor, observacao) VALUES (?, ?, ?, ?)",
                    (data_iso, item_gasto, valor_gasto, obs_gasto))
                conn.commit()
                st.success("Gasto registrado!")

    with st.expander("🏠 Gastos Fixos", expanded=True):
        with st.form("form_fixos"):
            desc_gasto = st.text_input("Descrição do Gasto")
            valor_fixo = st.number_input(
                "Valor (R$)", min_value=0.0, format="%.2f")
            obs_fixo = st.text_input("Observação (opcional)")
            if st.form_submit_button("Salvar Gasto Fixo") and desc_gasto:
                cursor.execute(
                    "INSERT INTO gastos_fixos (data, descricao, valor, observacao) VALUES (?, ?, ?, ?)",
                    (data_iso, desc_gasto, valor_fixo, obs_fixo))
                conn.commit()
                st.success("Gasto fixo registrado!")

    # Visualização dos dados do dia
    st.subheader("📋 Resumo do Dia")

    def mostrar_tabela(tabela, nome):
        df = pd.read_sql_query(
            f"SELECT * FROM {tabela} WHERE data = ?", conn, params=(data_iso,))
        if not df.empty:
            st.write(f"**{nome}**")
            st.dataframe(df.drop(columns=['id', 'data']), width=800)

    mostrar_tabela("recebimentos", "Recebimentos")
    mostrar_tabela("producao", "Produção")
    mostrar_tabela("sobras", "Sobras")
    mostrar_tabela("gastos_insumos", "Gastos com Insumos")
    mostrar_tabela("gastos_fixos", "Gastos Fixos")

    # Botão para gerar PDF
    if st.button("📥 Gerar Relatório em PDF"):
        with st.spinner("Gerando PDF..."):
            filename = gerar_pdf(data_iso)
            with open(filename, "rb") as pdf_file:
                st.download_button(
                    label="⬇️ Baixar Relatório Completo",
                    data=pdf_file,
                    file_name=f"Relatorio_CAZA_{data_str.replace('/', '-')}.pdf",
                    mime="application/pdf"
                )
            os.remove(filename)  # Remove o arquivo após o download

elif menu == "Relatório Mensal":
    st.subheader("📈 Relatório Mensal")

    col1, col2 = st.columns(2)
    with col1:
        mes = st.selectbox("Mês", list(calendar.month_name)[
                           1:], index=datetime.now().month-1)
    with col2:
        ano = st.number_input("Ano", min_value=2020,
                              max_value=2030, value=datetime.now().year)

    mes_num = list(calendar.month_name).index(mes)
    primeiro_dia = date(ano, mes_num, 1).isoformat()
    ultimo_dia = date(ano, mes_num, calendar.monthrange(
        ano, mes_num)[1]).isoformat()

    if st.button("Gerar Relatório"):
        # Dados financeiros
        recebimentos = pd.read_sql_query(
            "SELECT data, SUM(valor) as total FROM recebimentos WHERE data BETWEEN ? AND ? GROUP BY data",
            conn, params=(primeiro_dia, ultimo_dia))

        gastos = pd.read_sql_query(
            "SELECT 'Insumos' as tipo, SUM(valor) as total FROM gastos_insumos WHERE data BETWEEN ? AND ? "
            "UNION ALL SELECT 'Fixos' as tipo, SUM(valor) as total FROM gastos_fixos WHERE data BETWEEN ? AND ?",
            conn, params=(primeiro_dia, ultimo_dia, primeiro_dia, ultimo_dia))

        # Exibir métricas
        total_receb = recebimentos['total'].sum(
        ) if not recebimentos.empty else 0
        total_gastos = gastos['total'].sum() if not gastos.empty else 0
        saldo = total_receb - total_gastos

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Recebido", f"R$ {total_receb:,.2f}")
        with col2:
            st.metric("Total Gastos", f"R$ {total_gastos:,.2f}")
        with col3:
            st.metric("Saldo Mensal", f"R$ {saldo:,.2f}")

        # Gráfico de recebimentos por dia
        if not recebimentos.empty:
            st.subheader("Recebimentos por Dia")
            recebimentos['data'] = recebimentos['data'].apply(
                lambda x: formatar_data(x)[:5])  # Mostra apenas dia/mês
            st.bar_chart(recebimentos.set_index('data'))

        # Tabelas detalhadas
        if not recebimentos.empty:
            st.subheader("Detalhes dos Recebimentos")
            recebimentos['data'] = recebimentos['data'].apply(formatar_data)
            st.dataframe(recebimentos)

        if not gastos.empty:
            st.subheader("Gastos por Categoria")
            st.dataframe(gastos)

        # Botão para gerar PDF mensal
        if st.button("📥 Gerar Relatório Mensal em PDF"):
            with st.spinner("Gerando PDF..."):
                filename = gerar_pdf_mensal(primeiro_dia, ultimo_dia, mes, ano)
                with open(filename, "rb") as pdf_file:
                    st.download_button(
                        label="⬇️ Baixar Relatório Mensal Completo",
                        data=pdf_file,
                        file_name=f"Relatorio_Mensal_CAZA_{mes}_{ano}.pdf",
                        mime="application/pdf"
                    )
                os.remove(filename)  # Remove o arquivo após o download

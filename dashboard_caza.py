import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
from calendar import monthrange
from fpdf import FPDF
import io
import os
from PIL import Image
import atexit

# =============================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# =============================================


def configurar_banco_dados():
    """Configura a conexão com o banco de dados"""
    if not os.path.exists('data'):
        os.makedirs('data')

    conn = sqlite3.connect('data/caza.db', check_same_thread=False)
    cursor = conn.cursor()
    return conn, cursor


def verificar_estrutura_bd(cursor):
    """Verifica e corrige a estrutura do banco de dados"""
    alteracoes = [
        ("insumos", "estoque_atual", "REAL"),
        ("gastos_insumos", "quantidade", "REAL"),
        ("gastos_insumos", "tipo", "TEXT"),
        ("gastos_insumos", "unidade_medida", "TEXT"),
        ("estoque", "sabor", "TEXT")
    ]

    for tabela, coluna, tipo in alteracoes:
        try:
            cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            print(f"Coluna '{coluna}' adicionada à tabela {tabela}")
        except sqlite3.OperationalError:
            pass  # Coluna já existe


def criar_tabelas(cursor):
    """Cria todas as tabelas necessárias se não existirem"""
    tabelas = {
        'saldo_inicial': '''
            CREATE TABLE IF NOT EXISTS saldo_inicial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT UNIQUE,
                valor REAL,
                observacao TEXT
            )
        ''',
        'recebimentos': '''
            CREATE TABLE IF NOT EXISTS recebimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT,
                valor REAL,
                metodo TEXT,
                tipo TEXT,
                observacao TEXT,
                nome_cliente TEXT
            )
        ''',
        'consumo_clientes': '''
            CREATE TABLE IF NOT EXISTS consumo_clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT,
                nome_cliente TEXT,
                descricao TEXT,
                valor REAL,
                tipo TEXT,
                observacao TEXT
            )
        ''',
        'gastos_insumos': '''
            CREATE TABLE IF NOT EXISTS gastos_insumos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT,
                item TEXT,
                valor REAL,
                tipo TEXT,
                quantidade REAL,
                unidade_medida TEXT,
                observacao TEXT
            )
        ''',
        'gastos_fixos': '''
            CREATE TABLE IF NOT EXISTS gastos_fixos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT,
                descricao TEXT,
                valor REAL,
                tipo TEXT
            )
        ''',
        'insumos': '''
            CREATE TABLE IF NOT EXISTS insumos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE,
                unidade_medida TEXT,
                estoque_minimo REAL,
                observacao TEXT
            )
        ''',
        'estoque': '''
            CREATE TABLE IF NOT EXISTS estoque (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto TEXT,
                quantidade REAL,
                unidade TEXT,
                sabor TEXT,
                data_atualizacao TEXT
            )
        '''
    }

    for tabela, schema in tabelas.items():
        cursor.execute(schema)

    cursor.connection.commit()

# =============================================
# FUNÇÕES DE OPERAÇÕES NO BANCO DE DADOS
# =============================================


def adicionar_entrada(cursor, tabela, dados):
    """Adiciona um novo registro na tabela especificada"""
    try:
        colunas = ", ".join(dados.keys())
        placeholders = ", ".join("?" * len(dados))
        valores = tuple(dados.values())
        cursor.execute(
            f"INSERT INTO {tabela} ({colunas}) VALUES ({placeholders})", valores)
        cursor.connection.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar entrada: {str(e)}")
        return False


def editar_registro(cursor, tabela, id_, campos):
    """Edita um registro existente"""
    try:
        set_clause = ", ".join([f"{c} = ?" for c in campos.keys()])
        valores = tuple(campos.values()) + (id_,)
        cursor.execute(
            f"UPDATE {tabela} SET {set_clause} WHERE id = ?", valores)
        cursor.connection.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao editar registro: {str(e)}")
        return False


def deletar_registro(cursor, tabela, id_):
    """Remove um registro do banco de dados"""
    try:
        cursor.execute(f"DELETE FROM {tabela} WHERE id = ?", (id_,))
        cursor.connection.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao deletar registro: {str(e)}")
        return False


def obter_saldo_inicial(cursor, data):
    """Obtém o saldo inicial para uma data específica"""
    cursor.execute("SELECT valor FROM saldo_inicial WHERE data = ?", (data,))
    resultado = cursor.fetchone()
    return resultado[0] if resultado else 0.0

# =============================================
# FUNÇÕES PARA GERAÇÃO DE RELATÓRIOS
# =============================================


def gerar_pdf_resumo(data, saldo_inicial, totais, tipo='diario'):
    """Gera um PDF com o resumo financeiro"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)

    titulo = "Resumo Diário CAZÁ" if tipo == 'diario' else f"Resumo Mensal CAZÁ - {data}"
    pdf.cell(0, 10, titulo, ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Data: {data}", ln=True)
    pdf.ln(5)

    pdf.set_fill_color(255, 255, 255)

    linhas = [
        ("Saldo Inicial", saldo_inicial),
        ("Total Recebimentos", totais['recebimentos']),
        ("Total Consumo Clientes", totais['consumo']),
        ("Total Entrada", totais['entrada']),
        ("Total Gastos Insumos", totais['gastos_insumos']),
        ("Total Gastos Fixos", totais['gastos_fixos']),
        ("Total Gastos", totais['gastos']),
        ("Saldo Final", totais['saldo_final'])
    ]

    for desc, val in linhas:
        if val < 0:
            pdf.set_text_color(255, 0, 0)
        else:
            pdf.set_text_color(0, 0, 0)

        pdf.cell(130, 10, desc, 0, 0)
        pdf.cell(40, 10, f"R$ {val:.2f}", 0, 1, 'R')
        pdf.set_text_color(0, 0, 0)

    buffer = io.BytesIO()
    pdf_output = pdf.output(dest='S').encode('latin1')
    buffer.write(pdf_output)
    buffer.seek(0)
    return buffer


def gerar_excel_resumo(dados, nome_arquivo):
    """Gera um arquivo Excel com os dados consolidados"""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        for sheet_name, df in dados.items():
            if not df.empty:
                df.to_excel(writer, index=False, sheet_name=sheet_name[:31])

                workbook = writer.book
                worksheet = writer.sheets[sheet_name[:31]]
                format_negativo = workbook.add_format(
                    {'num_format': '[Red]R$ #,##0.00'})

                for col_num, col_name in enumerate(df.columns):
                    if pd.api.types.is_numeric_dtype(df[col_name]):
                        worksheet.set_column(
                            col_num, col_num, None, format_negativo)
    buffer.seek(0)
    return buffer

# =============================================
# INTERFACE DO USUÁRIO
# =============================================


def main():
    # Configuração inicial
    conn, cursor = configurar_banco_dados()
    criar_tabelas(cursor)
    verificar_estrutura_bd(cursor)
    hoje = datetime.now().strftime("%Y-%m-%d")

    # Carregar logo
    LOGO_PATH = "/Users/thalitaamorim/Desktop/CAZA/IMG_5950.jpg"
    try:
        logo = Image.open(LOGO_PATH)
        st.sidebar.image(logo, use_container_width=True)
    except:
        st.sidebar.warning("Logo não encontrada")

    # Interface principal
    st.title("🍽️ Sistema Financeiro CAZÁ")

    # Menu lateral
    with st.sidebar:
        st.header("Navegação")
        aba = st.radio(
            "Selecione a aba",
            ["📊 Caixa Diário", "📅 Relatório Mensal",
                "📦 Controle de Insumos", "❓ Ajuda"],
            index=0
        )

        st.markdown("---")
        st.caption(
            f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    # --- ABA AJUDA ---
    if aba == "❓ Ajuda":
        st.header("❓ Guia de Ajuda")

        with st.expander("📌 Como usar o sistema", expanded=True):
            st.markdown("""
            **1. Configuração Inicial:**
            - Comece cadastrando todos os insumos utilizados na aba 'Controle de Insumos'
            - No primeiro dia, defina seu saldo inicial (pode ser negativo se necessário)
            
            **2. Fluxo Diário:**
            - Registre todos os recebimentos e gastos na aba 'Caixa Diário'
            - Atualize o estoque na aba 'Controle de Insumos'
            - Saldos negativos são normais nos dias de compra (especialmente domingos)
            
            **3. Relatórios:**
            - Gere relatórios diários ou mensais quando precisar
            - Exporte para PDF ou Excel para compartilhar com sua equipe
            """)

        with st.expander("🔍 Dicas Rápidas"):
            st.markdown("""
            - **Saldos Negativos:** São esperados nos dias de compra (domingo)
            - **Controle de Insumos:** Atualize sempre após o uso dos ingredientes
            - **Atalhos:** Clique em um campo e pressione 'Tab' para navegar mais rápido
            - **Exportação:** Gere relatórios completos com um clique
            """)

        with st.expander("📞 Suporte"):
            st.markdown("""
            **Problemas ou dúvidas?**
            - WhatsApp: (98) 98110-4216
            - Email: thalita.muniz.amorim@gmail.com
            - Horário de atendimento: 9h às 17h (segunda a sexta)
            """)

    # --- ABA CONTROLE DE INSUMOS ---
    elif aba == "📦 Controle de Insumos":
        st.header("📦 Controle de Insumos")

        tab1, tab2, tab3 = st.tabs(
            ["📝 Cadastro", "📉 Baixa de Estoque", "📊 Estoque Atual"])

        with tab1:
            with st.form("form_insumo", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    nome = st.text_input(
                        "Nome do Insumo*", placeholder="Ex: Farinha, Açúcar")
                with col2:
                    unidade = st.selectbox(
                        "Unidade de Medida*", ["kg", "g", "L", "ml", "un", "cx", "pct"])
                estoque_minimo = st.number_input(
                    "Estoque Mínimo", min_value=0.0, step=0.1)
                estoque_atual = st.number_input(
                    "Estoque Atual", min_value=0.0, step=0.1)
                observacao = st.text_area("Observações")
                submitted = st.form_submit_button("💾 Cadastrar Insumo")
                if submitted:
                    if not nome.strip():
                        st.error("O nome do insumo é obrigatório!")
                    else:
                        if adicionar_entrada(cursor, "insumos", {
                            "nome": nome.strip(),
                            "unidade_medida": unidade,
                            "estoque_minimo": estoque_minimo,
                            "estoque_atual": estoque_atual,
                            "observacao": observacao.strip()
                        }):
                            st.success("✅ Insumo cadastrado com sucesso!")
                            st.rerun()

            st.markdown("---")
            st.subheader("🗂️ Insumos Cadastrados")

            df_insumos = pd.read_sql_query(
                "SELECT id, nome, unidade_medida, estoque_minimo, estoque_atual, observacao FROM insumos ORDER BY nome", conn)

            if not df_insumos.empty:
                for idx, row in df_insumos.iterrows():
                    col1, col2, col3 = st.columns([4, 1, 1])
                    with col1:
                        estoque_atual = row['estoque_atual'] if row['estoque_atual'] is not None else 0.0
                        estoque_minimo = row['estoque_minimo'] if row['estoque_minimo'] is not None else 0.0
                        st.write(
                            f"**{row['nome']}** ({row['unidade_medida']}) | Estoque Atual: {estoque_atual:.2f} | Mínimo: {estoque_minimo:.2f}")
                        if row['observacao']:
                            st.caption(f"Obs: {row['observacao']}")
                    with col2:
                        if st.button(f"✏️ Editar", key=f"edit_{row['id']}"):
                            novo_nome = st.text_input(
                                "Novo nome", value=row['nome'], key=f"novo_nome_{row['id']}")
                            nova_unidade = st.text_input(
                                "Nova unidade", value=row['unidade_medida'], key=f"nova_unidade_{row['id']}")
                            novo_minimo = st.number_input(
                                "Novo estoque mínimo", value=row['estoque_minimo'], key=f"novo_minimo_{row['id']}")
                            novo_atual = st.number_input(
                                "Novo estoque atual", value=row['estoque_atual'], key=f"novo_atual_{row['id']}")
                            nova_obs = st.text_input(
                                "Nova observação", value=row['observacao'], key=f"nova_obs_{row['id']}")
                            if st.button("Salvar alterações", key=f"salvar_{row['id']}"):
                                editar_registro(cursor, "insumos", row['id'], {
                                    "nome": novo_nome,
                                    "unidade_medida": nova_unidade,
                                    "estoque_minimo": novo_minimo,
                                    "estoque_atual": novo_atual,
                                    "observacao": nova_obs
                                })
                                st.success("✅ Insumo editado com sucesso!")
                                st.rerun()
                    with col3:
                        if st.button(f"🗑️ Excluir", key=f"del_{row['id']}"):
                            deletar_registro(cursor, "insumos", row['id'])
                            st.success("✅ Insumo excluído!")
                            st.rerun()
            else:
                st.info("Nenhum insumo cadastrado.")

        with tab2:
            st.subheader("Registrar Baixa de Estoque")
            df_insumos = pd.read_sql_query(
                "SELECT id, nome, unidade_medida FROM insumos ORDER BY nome", conn)

            if not df_insumos.empty:
                with st.form("form_baixa_estoque", clear_on_submit=True):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        insumo_selecionado = st.selectbox(
                            "Insumo*",
                            df_insumos['nome'],
                            format_func=lambda x: f"{x} ({df_insumos[df_insumos['nome'] == x]['unidade_medida'].iloc[0]})"
                        )
                        unidade = df_insumos[df_insumos['nome'] ==
                                             insumo_selecionado]['unidade_medida'].iloc[0]

                    with col2:
                        quantidade = st.number_input(
                            f"Quantidade ({unidade})*",
                            min_value=0.001,
                            step=0.001,
                            format="%.3f"
                        )

                    with col3:
                        data_baixa = st.date_input(
                            "Data da Baixa*", datetime.now())

                    motivo = st.text_input(
                        "Motivo (opcional)", placeholder="Ex: Produção diária")

                    if st.form_submit_button("📉 Registrar Baixa"):
                        if quantidade <= 0:
                            st.error("A quantidade deve ser maior que zero!")
                        else:
                            if adicionar_entrada(cursor, "gastos_insumos", {
                                "data": data_baixa.strftime("%Y-%m-%d"),
                                "item": insumo_selecionado,
                                "valor": 0,
                                "tipo": "baixa_estoque",
                                "quantidade": -abs(quantidade),
                                "unidade_medida": unidade,
                                "observacao": motivo.strip()
                            }):
                                # Atualiza o estoque atual do insumo
                                cursor.execute(
                                    "UPDATE insumos SET estoque_atual = estoque_atual - ? WHERE nome = ?",
                                    (quantidade, insumo_selecionado)
                                )
                                conn.commit()
                                st.success(
                                    f"✅ Baixa de {quantidade} {unidade} de {insumo_selecionado} registrada!")
                                st.rerun()
            else:
                st.warning("Cadastre insumos antes de registrar baixas")

        with tab3:
            st.subheader("Nível de Estoque Atual")

            try:
                df_estoque = pd.read_sql_query('''
                    SELECT 
                        i.nome AS Insumo,
                        i.unidade_medida AS Unidade,
                        i.estoque_atual AS Estoque_Atual,
                        i.estoque_minimo AS Estoque_Mínimo,
                        CASE 
                            WHEN i.estoque_atual <= i.estoque_minimo THEN '⚠️ Repor'
                            ELSE '✅ OK'
                        END AS Status
                    FROM insumos i
                    ORDER BY Status DESC, i.nome
                ''', conn)

                if not df_estoque.empty:
                    def color_status(val):
                        color = 'red' if val == '⚠️ Repor' else 'green'
                        return f'color: {color}'

                    styled_df = df_estoque.style.applymap(
                        color_status, subset=['Status'])

                    st.dataframe(
                        styled_df.format({
                            "Estoque_Atual": "{:.3f}",
                            "Estoque_Mínimo": "{:.3f}"
                        }),
                        use_container_width=True,
                        hide_index=True,
                        height=600
                    )

                    insumos_criticos = df_estoque[df_estoque['Status']
                                                  == '⚠️ Repor']
                    if not insumos_criticos.empty:
                        st.markdown("---")
                        st.subheader("🛑 Insumos para Reposição Urgente")
                        st.bar_chart(
                            insumos_criticos.set_index(
                                'Insumo')['Estoque_Atual'],
                            color="#FF4B4B"
                        )

                    st.markdown("---")
                    st.download_button(
                        label="📥 Exportar Relatório de Estoque (Excel)",
                        data=gerar_excel_resumo(
                            {"Estoque": df_estoque}, "estoque_atual.xlsx"),
                        file_name=f"estoque_caza_{hoje}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info(
                        "Nenhum insumo cadastrado ainda. Adicione insumos na aba 'Cadastro'")
            except Exception as e:
                st.error(f"Erro ao carregar estoque: {str(e)}")
                st.info(
                    "Execute o script de correção do banco de dados se o problema persistir")

    # --- ABA CAIXA DIÁRIO ---
    elif aba == "📊 Caixa Diário":
        st.header("📊 Caixa Diário")

        # Seção de Saldo Inicial
        with st.expander("💰 SALDO INICIAL DO DIA", expanded=True):
            saldo_existente = obter_saldo_inicial(cursor, hoje)

            col1, col2 = st.columns(2)
            with col1:
                saldo_inicial = st.number_input(
                    "Valor em Caixa (R$)*",
                    min_value=-100000.0,
                    step=0.01,
                    value=float(saldo_existente),
                    key="saldo_inicial"
                )

                if saldo_inicial < 0:
                    st.warning(
                        "💡 Saldo negativo é normal para dias de compra (como domingos)")

            with col2:
                obs_saldo = st.text_input(
                    "Observação (opcional)",
                    placeholder="Ex: Saldo da semana anterior, compras de domingo"
                )

            if st.button("💾 Salvar Saldo Inicial", key="btn_saldo_inicial"):
                try:
                    cursor.execute(
                        "INSERT OR REPLACE INTO saldo_inicial (data, valor, observacao) VALUES (?, ?, ?)",
                        (hoje, saldo_inicial, obs_saldo.strip())
                    )
                    conn.commit()
                    st.success("✅ Saldo inicial salvo com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao salvar: {str(e)}")

        # Seção de Lançamentos
        st.markdown("---")
        st.subheader("📝 Registrar Lançamentos")

        opcao_lancamento = st.radio(
            "Tipo de Lançamento:",
            ["💵 Recebimento", "👥 Consumo por Cliente",
                "🛒 Gasto com Insumos", "🏢 Gasto Fixo"],
            horizontal=True,
            label_visibility="collapsed"
        )

        if opcao_lancamento == "💵 Recebimento":
            with st.form("form_recebimento", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    metodo_pagamento = st.selectbox(
                        "Método de Pagamento*",
                        ["Dinheiro", "PIX", "Cartão", "Transferência"]
                    )
                with col2:
                    valor_recebimento = st.number_input(
                        "Valor Recebido (R$)*",
                        min_value=0.01,
                        step=0.01
                    )

                observacao = st.text_input(
                    "Observação (opcional)",
                    placeholder="Ex: Feirinha, Evento especial"
                )

                if st.form_submit_button("💾 Registrar Recebimento"):
                    if valor_recebimento <= 0:
                        st.error("❌ O valor deve ser maior que zero!")
                    else:
                        if adicionar_entrada(cursor, "recebimentos", {
                            "data": hoje,
                            "valor": valor_recebimento,
                            "metodo": metodo_pagamento,
                            "tipo": "recebimento",
                            "observacao": observacao.strip(),
                            "nome_cliente": ""
                        }):
                            st.success("✅ Recebimento registrado com sucesso!")
                            st.rerun()

        elif opcao_lancamento == "👥 Consumo por Cliente":
            with st.form("form_consumo", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    nome_cliente = st.text_input("Nome do Cliente*")
                with col2:
                    valor_consumo = st.number_input(
                        "Valor do Consumo (R$)*",
                        min_value=0.01,
                        step=0.01
                    )

                descricao_consumo = st.text_input(
                    "Descrição (opcional)",
                    placeholder="Ex: 2 porções de feijoada"
                )

                observacao = st.text_input(
                    "Observação (opcional)",
                    placeholder="Ex: Consumo no local"
                )

                if st.form_submit_button("💾 Registrar Consumo"):
                    if not nome_cliente.strip():
                        st.error("❌ Informe o nome do cliente!")
                    elif valor_consumo <= 0:
                        st.error("❌ O valor deve ser maior que zero!")
                    else:
                        if adicionar_entrada(cursor, "consumo_clientes", {
                            "data": hoje,
                            "nome_cliente": nome_cliente.strip(),
                            "descricao": descricao_consumo.strip(),
                            "valor": valor_consumo,
                            "tipo": "consumo",
                            "observacao": observacao.strip()
                        }):
                            st.success("✅ Consumo registrado com sucesso!")
                            st.rerun()

        elif opcao_lancamento == "🛒 Gasto com Insumos":
            df_insumos = pd.read_sql_query(
                "SELECT nome, unidade_medida FROM insumos ORDER BY nome", conn)

            with st.form("form_gasto_insumo", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    if not df_insumos.empty:
                        item_selecionado = st.selectbox(
                            "Insumo*",
                            df_insumos['nome'],
                            format_func=lambda x: f"{x} ({df_insumos[df_insumos['nome'] == x]['unidade_medida'].iloc[0]})"
                        )
                        unidade = df_insumos[df_insumos['nome'] ==
                                             item_selecionado]['unidade_medida'].iloc[0]
                    else:
                        item_selecionado = st.text_input(
                            "Insumo*", placeholder="Ex: Farinha, Açúcar")
                        unidade = st.text_input("Unidade*", value="kg")

                    quantidade = st.number_input(
                        f"Quantidade ({unidade})",
                        min_value=0.001,
                        step=0.001,
                        format="%.3f"
                    )

                with col2:
                    valor_insumo = st.number_input(
                        "Valor Total (R$)*", min_value=0.01, step=0.01)
                    tipo_evento = st.text_input(
                        "Tipo de Evento (opcional)", placeholder="Ex: Feirinha, Compra semanal")

                if st.form_submit_button("💾 Registrar Gasto"):
                    if not item_selecionado:
                        st.error("❌ Selecione ou informe um insumo!")
                    elif valor_insumo <= 0:
                        st.error("❌ O valor deve ser maior que zero!")
                    else:
                        if adicionar_entrada(cursor, "gastos_insumos", {
                            "data": hoje,
                            "item": item_selecionado.strip(),
                            "valor": valor_insumo,
                            "tipo": tipo_evento.strip(),
                            "quantidade": quantidade,
                            "unidade_medida": unidade.strip(),
                            "observacao": f"Compra: {tipo_evento.strip()}" if tipo_evento.strip() else "Compra"
                        }):
                            st.success(
                                "✅ Gasto com insumo registrado com sucesso!")
                            st.rerun()

        elif opcao_lancamento == "🏢 Gasto Fixo":
            with st.form("form_gasto_fixo", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    descricao_fixo = st.text_input(
                        "Descrição*",
                        placeholder="Ex: Aluguel, Luz, Internet"
                    )
                with col2:
                    valor_fixo = st.number_input(
                        "Valor (R$)*",
                        min_value=0.01,
                        step=0.01
                    )

                tipo_evento_fixo = st.text_input(
                    "Tipo de Evento (opcional)",
                    placeholder="Ex: Mensalidade, Conta de água"
                )

                if st.form_submit_button("💾 Registrar Gasto Fixo"):
                    if not descricao_fixo.strip():
                        st.error("❌ Informe a descrição do gasto fixo!")
                    elif valor_fixo <= 0:
                        st.error("❌ O valor deve ser maior que zero!")
                    else:
                        if adicionar_entrada(cursor, "gastos_fixos", {
                            "data": hoje,
                            "descricao": descricao_fixo.strip(),
                            "valor": valor_fixo,
                            "tipo": tipo_evento_fixo.strip() if tipo_evento_fixo.strip() else "fixo"
                        }):
                            st.success("✅ Gasto fixo registrado com sucesso!")
                            st.rerun()

        # Resumo financeiro do dia
        st.markdown("---")
        st.subheader("📊 Resumo do Dia")

        # Buscar dados do dia
        df_recebimentos = pd.read_sql_query(
            f"SELECT * FROM recebimentos WHERE data = '{hoje}'", conn)
        df_consumo = pd.read_sql_query(
            f"SELECT * FROM consumo_clientes WHERE data = '{hoje}'", conn)
        df_gastos_insumos = pd.read_sql_query(
            f"SELECT * FROM gastos_insumos WHERE data = '{hoje}'", conn)
        df_gastos_fixos = pd.read_sql_query(
            f"SELECT * FROM gastos_fixos WHERE data = '{hoje}'", conn)

        # Cálculo de totais
        totais = {
            'recebimentos': df_recebimentos["valor"].sum() if not df_recebimentos.empty else 0.0,
            'consumo': df_consumo["valor"].sum() if not df_consumo.empty else 0.0,
            'gastos_insumos': df_gastos_insumos["valor"].sum() if not df_gastos_insumos.empty else 0.0,
            'gastos_fixos': df_gastos_fixos["valor"].sum() if not df_gastos_fixos.empty else 0.0
        }

        totais['entrada'] = totais['recebimentos'] + totais['consumo']
        totais['gastos'] = totais['gastos_insumos'] + totais['gastos_fixos']
        totais['saldo_final'] = saldo_inicial + \
            totais['entrada'] - totais['gastos']

        # Exibição em colunas com cores condicionais
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Saldo Inicial",
                      f"R$ {saldo_inicial:.2f}", delta="Saldo inicial do dia")
            st.metric("Total Recebimentos",
                      f"R$ {totais['recebimentos']:.2f}", delta=f"R$ {totais['recebimentos']:.2f}")
            st.metric(
                "Total Consumo", f"R$ {totais['consumo']:.2f}", delta=f"R$ {totais['consumo']:.2f}")
            st.metric(
                "Total Entradas", f"R$ {totais['entrada']:.2f}", delta=f"R$ {totais['entrada']:.2f}")

        with col2:
            st.metric("Gastos com Insumos",
                      f"R$ {totais['gastos_insumos']:.2f}", delta=f"R$ {totais['gastos_insumos']:.2f}")
            st.metric(
                "Gastos Fixos", f"R$ {totais['gastos_fixos']:.2f}", delta=f"R$ {totais['gastos_fixos']:.2f}")
            st.metric(
                "Total Gastos", f"R$ {totais['gastos']:.2f}", delta=f"R$ {totais['gastos']:.2f}")

            saldo_delta = totais['saldo_final'] - saldo_inicial
            st.metric("Saldo Final",
                      f"R$ {totais['saldo_final']:.2f}",
                      delta=f"R$ {saldo_delta:.2f}",
                      delta_color="normal" if saldo_delta >= 0 else "inverse")

        # Seção de exportação
        st.markdown("---")
        st.subheader("📤 Exportar Relatório")

        col_exp1, col_exp2 = st.columns(2)

        with col_exp1:
            if st.button("📄 Gerar PDF do Resumo"):
                pdf_buffer = gerar_pdf_resumo(
                    hoje, saldo_inicial, totais, 'diario')
                st.download_button(
                    "⬇️ Baixar PDF",
                    data=pdf_buffer,
                    file_name=f"resumo_caixa_{hoje}.pdf",
                    mime="application/pdf"
                )

        with col_exp2:
            dados_excel = {
                "Resumo Diário": pd.DataFrame({
                    "Descrição": [
                        "Saldo Inicial",
                        "Total Recebimentos",
                        "Total Consumo",
                        "Total Entradas",
                        "Gastos com Insumos",
                        "Gastos Fixos",
                        "Total Gastos",
                        "Saldo Final"
                    ],
                    "Valor (R$)": [
                        saldo_inicial,
                        totais['recebimentos'],
                        totais['consumo'],
                        totais['entrada'],
                        totais['gastos_insumos'],
                        totais['gastos_fixos'],
                        totais['gastos'],
                        totais['saldo_final']
                    ]
                }),
                "Recebimentos": df_recebimentos,
                "Consumos": df_consumo,
                "Gastos Insumos": df_gastos_insumos,
                "Gastos Fixos": df_gastos_fixos
            }

            excel_buffer = gerar_excel_resumo(
                dados_excel, f"resumo_caixa_{hoje}.xlsx")
            st.download_button(
                label="⬇️ Baixar Excel Completo",
                data=excel_buffer,
                file_name=f"resumo_caixa_{hoje}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # --- ABA RELATÓRIO MENSAL ---
    elif aba == "📅 Relatório Mensal":
        st.header("📅 Relatório Mensal")

        # Seleção do período
        hoje = datetime.now()
        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mês", range(1, 13), index=hoje.month - 1)
        with col2:
            ano = st.selectbox("Ano", range(
                2020, hoje.year + 1), index=hoje.year - 2020)

        data_selecionada = f"{ano}-{mes:02d}"
        filtro_data = f"strftime('%Y-%m', data) = '{data_selecionada}'"

        # Buscar dados do mês
        df_recebimentos_mes = pd.read_sql_query(
            f"SELECT * FROM recebimentos WHERE {filtro_data}", conn)
        df_gastos_insumos_mes = pd.read_sql_query(
            f"SELECT * FROM gastos_insumos WHERE {filtro_data}", conn)
        df_gastos_fixos_mes = pd.read_sql_query(
            f"SELECT * FROM gastos_fixos WHERE {filtro_data}", conn)

        # Calcular saldo inicial do mês (primeiro dia)
        primeiro_dia = f"{ano}-{mes:02d}-01"
        saldo_inicial_mes = obter_saldo_inicial(cursor, primeiro_dia)

        # Cálculo de totais
        total_recebido = df_recebimentos_mes["valor"].sum(
        ) if not df_recebimentos_mes.empty else 0.0
        total_gasto_insumos = df_gastos_insumos_mes["valor"].sum(
        ) if not df_gastos_insumos_mes.empty else 0.0
        total_gasto_fixos = df_gastos_fixos_mes["valor"].sum(
        ) if not df_gastos_fixos_mes.empty else 0.0

        total_gastos = total_gasto_insumos + total_gasto_fixos
        saldo_final_mes = saldo_inicial_mes + total_recebido - total_gastos

        st.subheader(f"📊 Resumo Mensal - {mes:02d}/{ano}")

        col_res1, col_res2 = st.columns(2)

        with col_res1:
            st.metric("Saldo Inicial do Mês", f"R$ {saldo_inicial_mes:.2f}")
            st.metric(
                "Total Recebido", f"R$ {total_recebido:.2f}", delta=f"R$ {total_recebido:.2f}")
            st.metric("Gastos com Insumos",
                      f"R$ {total_gasto_insumos:.2f}", delta=f"R$ {total_gasto_insumos:.2f}")

        with col_res2:
            st.metric(
                "Gastos Fixos", f"R$ {total_gasto_fixos:.2f}", delta=f"R$ {total_gasto_fixos:.2f}")
            st.metric("Total Gastos",
                      f"R$ {total_gastos:.2f}", delta=f"R$ {total_gastos:.2f}")
            st.metric("Saldo Final do Mês",
                      f"R$ {saldo_final_mes:.2f}",
                      delta=f"R$ {saldo_final_mes - saldo_inicial_mes:.2f}",
                      delta_color="normal" if (saldo_final_mes - saldo_inicial_mes) >= 0 else "inverse")

        st.markdown("---")
        st.subheader("💳 Detalhamento por Forma de Pagamento")

        if not df_recebimentos_mes.empty:
            df_formas_pagamento = df_recebimentos_mes.groupby(
                'metodo')['valor'].sum().reset_index()
            df_formas_pagamento.columns = ['Forma de Pagamento', 'Total (R$)']

            col_det1, col_det2 = st.columns(2)

            with col_det1:
                st.dataframe(df_formas_pagamento,
                             use_container_width=True, hide_index=True)

            with col_det2:
                st.bar_chart(df_formas_pagamento.set_index(
                    'Forma de Pagamento'), color="#FF4B4B")
        else:
            st.info("ℹ️ Nenhum recebimento registrado neste período.")

        st.markdown("---")
        st.subheader("📤 Exportar Relatório Mensal")

        col_exp1, col_exp2 = st.columns(2)

        with col_exp1:
            if st.button("📄 Gerar PDF do Relatório"):
                pdf_buffer = gerar_pdf_resumo(f"{mes:02d}/{ano}", saldo_inicial_mes, {
                    'recebimentos': total_recebido,
                    'consumo': 0,
                    'entrada': total_recebido,
                    'gastos_insumos': total_gasto_insumos,
                    'gastos_fixos': total_gasto_fixos,
                    'gastos': total_gastos,
                    'saldo_final': saldo_final_mes
                }, 'mensal')

                st.download_button(
                    "⬇️ Baixar PDF Mensal",
                    data=pdf_buffer,
                    file_name=f"resumo_mensal_{mes:02d}_{ano}.pdf",
                    mime="application/pdf"
                )

        with col_exp2:
            dados_excel = {
                "Resumo Mensal": pd.DataFrame({
                    "Descrição": [
                        "Saldo Inicial",
                        "Total Recebido",
                        "Gastos com Insumos",
                        "Gastos Fixos",
                        "Total Gastos",
                        "Saldo Final"
                    ],
                    "Valor (R$)": [
                        saldo_inicial_mes,
                        total_recebido,
                        total_gasto_insumos,
                        total_gasto_fixos,
                        total_gastos,
                        saldo_final_mes
                    ]
                }),
                "Recebimentos": df_recebimentos_mes,
                "Gastos Insumos": df_gastos_insumos_mes,
                "Gastos Fixos": df_gastos_fixos_mes
            }

            if not df_recebimentos_mes.empty:
                dados_excel["Formas Pagamento"] = df_formas_pagamento

            excel_buffer = gerar_excel_resumo(
                dados_excel, f"resumo_mensal_{mes:02d}_{ano}.xlsx")
            st.download_button(
                label="⬇️ Baixar Excel Completo",
                data=excel_buffer,
                file_name=f"resumo_mensal_{mes:02d}_{ano}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # Fechar conexão quando o app for encerrado
    def fechar_conexao():
        if conn:
            conn.close()

    atexit.register(fechar_conexao)


if __name__ == "__main__":
    main()

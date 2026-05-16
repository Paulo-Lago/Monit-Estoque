import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURAÇÃO DE ÍCONE PERSONALIZADO ---
import base64
from pathlib import Path

# === CAMINHO SEGURO DA IMAGEM ===
BASE_DIR = Path(__file__).parent          # pasta onde está o app.py
LOGO_PATH = BASE_DIR / "assets" / "logomarca.png"


# 1. Função de Estilo Avançada (CSS Responsivo e Persistente)

def aplicar_estilo_customizado():
    # Tenta carregar a imagem em base64
    try:
        with open(LOGO_PATH, "rb") as img_file:
            logo_base64 = base64.b64encode(img_file.read()).decode()
    except:
        logo_base64 = ""  # Se não encontrar a imagem, não quebra o app

    st.markdown(f"""
    <style>
    .main-bg-container {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: -2;
        pointer-events: none;
        background-image: url("data:image/png;base64,{logo_base64}");
        background-size: contain;
        background-position: center;
        background-repeat: no-repeat;
        opacity: 0.13;
        filter: grayscale(12%);
    }}
    </style>

    <div class="main-bg-container"></div>
    """, unsafe_allow_html=True)


st.set_page_config(page_title="Estoque Ovos Pro", layout="wide")
aplicar_estilo_customizado()

# --- INICIALIZAÇÃO DO BANCO DE DADOS COM MIGRAÇÃO ---


def init_db():
    conn = sqlite3.connect('estoque_ovos.db')
    c = conn.cursor()

    # Tabela de usuários
    c.execute(
        'CREATE TABLE IF NOT EXISTS usuarios (username TEXT UNIQUE, password TEXT)')

    # Tabela de produção (ovos) - usando rowid implícito do SQLite
    c.execute('''CREATE TABLE IF NOT EXISTS producao (
        username TEXT,
        data DATE,
        quantidade INTEGER,
        tipo TEXT DEFAULT 'A',
        galpao TEXT DEFAULT 'Galpão 2',
        cor TEXT DEFAULT 'Branco'
    )''')

    # Tabela de aves
    c.execute('''CREATE TABLE IF NOT EXISTS aves (
        username TEXT,
        galpao TEXT,
        quantidade_total INTEGER,
        data_registro DATE
    )''')

    # Tabela de aves mortas
    c.execute('''CREATE TABLE IF NOT EXISTS aves_mortas (
        username TEXT,
        galpao TEXT,
        quantidade INTEGER,
        data DATE
    )''')

    # Tabela de ovos quebrados
    c.execute('''CREATE TABLE IF NOT EXISTS ovos_quebrados (
        username TEXT,
        galpao TEXT,
        quantidade INTEGER,
        data DATE
    )''')

    # Migração: Adicionar colunas se não existirem
    try:
        c.execute("ALTER TABLE producao ADD COLUMN tipo TEXT DEFAULT 'A'")
    except:
        pass

    try:
        c.execute("ALTER TABLE producao ADD COLUMN galpao TEXT DEFAULT 'Galpão 2'")
    except:
        pass

    try:
        c.execute("ALTER TABLE producao ADD COLUMN cor TEXT DEFAULT 'Branco'")
    except:
        pass

    conn.commit()
    conn.close()


init_db()

# --- INICIALIZAÇÃO DE SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""

# --- CONSTANTES ---
TIPOS_OVO = ["A", "B", "Jumbo", "Extra", "Trincado"]
GALPOES = ["Galpão 2", "Galpão 3"]
CORES = ["Branco", "Vermelho"]

# --- FUNÇÕES AUXILIARES ---


def get_total_aves_vivas(username, galpao):
    """Calcula total de aves vivas (registradas - mortas)"""
    conn = sqlite3.connect('estoque_ovos.db')
    c = conn.cursor()

    # Total registrado
    c.execute("SELECT COALESCE(SUM(quantidade_total), 0) FROM aves WHERE username=? AND galpao=?", (username, galpao))
    total_reg = c.fetchone()[0]

    # Total morto
    c.execute("SELECT COALESCE(SUM(quantidade), 0) FROM aves_mortas WHERE username=? AND galpao=?", (username, galpao))
    total_morto = c.fetchone()[0]

    conn.close()
    return max(0, total_reg - total_morto)


def get_aves_mortas_galpao(username, galpao):
    """Retorna total de aves mortas por galpão"""
    conn = sqlite3.connect('estoque_ovos.db')
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(quantidade), 0) FROM aves_mortas WHERE username=? AND galpao=?", (username, galpao))
    result = c.fetchone()[0]
    conn.close()
    return result


# --- INTERFACE DE LOGIN ---
if not st.session_state.logged_in:
    st.markdown("<h1>🐔 Estoque de Ovos Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-texto'>Sua produção organizada de forma profissional</p>",
                unsafe_allow_html=True)

    user = st.text_input("Nome de Usuário", placeholder="Digite seu usuário")
    pw = st.text_input("Senha", type="password",
                       placeholder="Digite sua senha")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Entrar", use_container_width=True):
            if user and pw:
                conn = sqlite3.connect('estoque_ovos.db')
                c = conn.cursor()
                c.execute(
                    "SELECT password FROM usuarios WHERE username = ?", (user,))
                result = c.fetchone()
                conn.close()
                if result and result[0] == pw:
                    st.session_state.logged_in = True
                    st.session_state.username = user
                    st.rerun()
                else:
                    st.error("Login ou senha inválidos.")
    with col2:
        if st.button("Criar Conta", use_container_width=True):
            if user and pw:
                try:
                    conn = sqlite3.connect('estoque_ovos.db')
                    c = conn.cursor()
                    c.execute("INSERT INTO usuarios VALUES (?, ?)", (user, pw))
                    conn.commit()
                    conn.close()
                    st.success("Conta criada com sucesso!")
                except:
                    st.error("Este usuário já existe.")
            else:
                st.error("Preencha usuário e senha.")

else:
    # --- PAINEL PRINCIPAL ---
    st.markdown(f"<h1>🐔 Painel de Gerenciamento</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<p class='sub-texto'>Bem-vindo, <b>{st.session_state.username}</b></p>", unsafe_allow_html=True)

    if st.sidebar.button("🚪 Sair / Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # --- ABAS PRINCIPAIS ---
    tabs = st.tabs([
        "📝 Nova Colheita",
        "🔍 Histórico & Edição",
        "📊 Monitoramento",
        "🐔 Registrar Aves",
        "📈 Gráficos",
        "🔨 Ovos Quebrados"
    ])

    # ======================== ABA 1: NOVA COLHEITA ========================
    with tabs[0]:
        st.markdown("### 📝 Registrar Nova Colheita")

        col1, col2 = st.columns(2)
        with col1:
            data_reg = st.date_input("📅 Data da Colheita", value=datetime.now(
            ).date(), format="DD/MM/YYYY", key="data_colheita")
            qtd_val = st.number_input(
                "🥚 Quantidade de Ovos", min_value=0, step=1, format="%d", key="qtd_colheita")

        with col2:
            tipo_ovo = st.selectbox(
                "🏷️ Tipo de Ovo", TIPOS_OVO, key="tipo_ovo")
            galpao = st.selectbox("🏠 Galpão", GALPOES, key="galpao_colheita")

        cor = st.selectbox("🎨 Cor do Ovo", CORES, key="cor_ovo")

        if st.button("✅ Salvar Colheita", use_container_width=True):
            if qtd_val > 0:
                conn = sqlite3.connect('estoque_ovos.db')
                c = conn.cursor()
                c.execute("INSERT INTO producao (username, data, quantidade, tipo, galpao, cor) VALUES (?, ?, ?, ?, ?, ?)",
                          (st.session_state.username, data_reg, qtd_val, tipo_ovo, galpao, cor))
                conn.commit()
                conn.close()
                st.balloons()
                st.success(
                    f"✅ {qtd_val} ovos ({tipo_ovo}, {cor}) do {galpao} registrados com sucesso!")
            else:
                st.error("Quantidade deve ser maior que zero.")

    # ======================== ABA 2: HISTÓRICO & EDIÇÃO ========================
    with tabs[1]:
        st.markdown("### 🔍 Gerenciar Histórico")

        conn = sqlite3.connect('estoque_ovos.db')
        df_edit = pd.read_sql(
            "SELECT rowid, data, quantidade, tipo, galpao, cor FROM producao WHERE username=? ORDER BY rowid DESC",
            conn,
            params=(st.session_state.username,)
        )
        conn.close()

        if not df_edit.empty:
            df_edit['data_fmt'] = pd.to_datetime(
                df_edit['data']).dt.strftime('%d/%m/%Y')

            opcoes = {
                row['rowid']: f"📅 {row['data_fmt']} | {row['quantidade']} ovos | {row['tipo']} | {row['cor']} | {row['galpao']}"
                for _, row in df_edit.iterrows()
            }

            selecao = st.selectbox(
                "Escolha um registro para corrigir:", list(opcoes.values()))
            rid = [k for k, v in opcoes.items() if v == selecao][0]

            registro = df_edit[df_edit['rowid'] == rid].iloc[0]

            col1, col2 = st.columns(2)
            with col1:
                novo_val = st.number_input(
                    "Corrigir quantidade:", min_value=0, step=1, value=int(registro['quantidade']))
                novo_tipo = st.selectbox(
                    "Corrigir tipo:", TIPOS_OVO, index=TIPOS_OVO.index(registro['tipo']))

            with col2:
                novo_galpao = st.selectbox(
                    "Corrigir galpão:", GALPOES, index=GALPOES.index(registro['galpao']))
                nova_cor = st.selectbox(
                    "Corrigir cor:", CORES, index=CORES.index(registro['cor']))

            if st.button("✅ Confirmar Alteração", use_container_width=True):
                conn = sqlite3.connect('estoque_ovos.db')
                c = conn.cursor()
                c.execute(
                    "UPDATE producao SET quantidade=?, tipo=?, galpao=?, cor=? WHERE rowid=?",
                    (novo_val, novo_tipo, novo_galpao, nova_cor, rid)
                )
                conn.commit()
                conn.close()
                st.success("✅ Registro atualizado!")
                st.rerun()
        else:
            st.info("📭 Nenhum registro de colheita encontrado.")

            # ======================== ABA 3: MONITORAMENTO ========================
    with tabs[2]:
        st.markdown("### 📊 Monitoramento de Produção")

        conn = sqlite3.connect('estoque_ovos.db')
        df_producao = pd.read_sql(
            "SELECT data, quantidade, tipo, galpao, cor FROM producao WHERE username=? ORDER BY data DESC",
            conn,
            params=(st.session_state.username,)
        )
        conn.close()

        if df_producao.empty:
            st.info("📭 Nenhum registro de colheita encontrado.")
        else:
            df_producao['data'] = pd.to_datetime(df_producao['data'])

            # === FILTRO POR DATA ===
            st.markdown("#### 📅 Selecione o Dia para Análise")
            col_f1, col_f2 = st.columns([3, 1])
            with col_f1:
                data_selecionada = st.date_input(
                    "Data",
                    value=datetime.now().date(),
                    format="DD/MM/YYYY",
                    key="data_monitor"
                )
            with col_f2:
                mostrar_todos = st.checkbox(
                    "Mostrar todos os dias", value=False, key="checkbox_todos_dias")

            # Aplicando filtro
            if mostrar_todos:
                df_filtrado = df_producao.copy()
                titulo_periodo = "Todo o Período"
            else:
                df_filtrado = df_producao[df_producao['data'].dt.date ==
                                          data_selecionada]
                titulo_periodo = f"Dia {data_selecionada.strftime('%d/%m/%Y')}"

            st.markdown(f"**{titulo_periodo}**")
            st.divider()

            if df_filtrado.empty:
                st.warning(
                    f"Nenhum registro encontrado para a data selecionada.")
            else:
                # ===================== DETALHES POR GALPÃO E TIPO =====================
                st.markdown("#### 📋 Detalhes por Galpão e Tipo")

                df_filtrado = df_filtrado.copy()
                df_filtrado['galpao_norm'] = df_filtrado['galpao'].astype(
                    str).str.strip()

                for galpao in sorted(df_filtrado['galpao_norm'].unique()):
                    st.markdown(f"**{galpao}**")

                    df_galpao = df_filtrado[df_filtrado['galpao_norm'] == galpao]

                    # Total de Ovos do Dia
                    total_galpao = df_galpao['quantidade'].sum()
                    st.info(f"**Total de Ovos do Dia:** {total_galpao} ovos")

                    # Por tipo (removendo tipos específicos por galpão)
                    tipos_para_mostrar = [t for t in TIPOS_OVO]

                    if galpao == "Galpão 2":
                        tipos_para_mostrar = [t for t in TIPOS_OVO if t != "B"]
                    elif galpao == "Galpão 3":
                        tipos_para_mostrar = [
                            t for t in TIPOS_OVO if t != "Jumbo"]

                    tipo_cols = st.columns(len(tipos_para_mostrar))

                    for idx, tipo in enumerate(tipos_para_mostrar):
                        with tipo_cols[idx]:
                            total_tipo = df_galpao[df_galpao['tipo']
                                                   == tipo]['quantidade'].sum()
                            st.info(f"**{tipo}**: {total_tipo} ovos")

                    # Por cor
                    cor_cols = st.columns(len(CORES))
                    for idx, cor in enumerate(CORES):
                        with cor_cols[idx]:
                            total_cor = df_galpao[df_galpao['cor']
                                                  == cor]['quantidade'].sum()
                            st.warning(f"**{cor}**: {total_cor} ovos")

                    st.divider()
          # ======================== ABA 4: REGISTRAR AVES ========================
    with tabs[3]:
        st.markdown("### 🐔 Gerenciamento de Aves")

        tab_reg_aves, tab_mortas, tab_historico = st.tabs([
            "➕ Registrar Aves",
            "⚠️ Aves Mortas",
            "📋 Histórico"
        ])

        # ===================== SUBABA 1: REGISTRAR AVES =====================
        with tab_reg_aves:
            st.markdown("#### ➕ Adicionar Novas Aves")

            col1, col2 = st.columns(2)
            with col1:
                data_aves = st.date_input("📅 Data", value=datetime.now().date(), format="DD/MM/YYYY",
                                          key="data_aves_reg_v2")
                galpao_aves = st.selectbox(
                    "🏠 Galpão", GALPOES, key="galpao_aves_reg_v2")

            with col2:
                qtd_aves = st.number_input("🐔 Quantidade de Aves", min_value=1, step=1, format="%d",
                                           key="qtd_aves_reg_v2")

            if st.button("✅ Registrar Aves", use_container_width=True, type="primary", key="btn_reg_aves_v2"):
                if qtd_aves > 0:
                    conn = sqlite3.connect('estoque_ovos.db')
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO aves (username, galpao, quantidade_total, data_registro) VALUES (?, ?, ?, ?)",
                        (st.session_state.username,
                         galpao_aves, qtd_aves, data_aves)
                    )
                    conn.commit()
                    conn.close()
                    st.success(
                        f"✅ {qtd_aves} aves registradas no {galpao_aves}!")
                    st.rerun()

        # ===================== SUBABA 2: AVES MORTAS =====================
        with tab_mortas:
            st.markdown("#### ⚠️ Registrar Aves Mortas")

            col1, col2 = st.columns(2)
            with col1:
                data_morta = st.date_input("📅 Data", value=datetime.now().date(), format="DD/MM/YYYY",
                                           key="data_morta_v2")
                galpao_morta = st.selectbox(
                    "🏠 Galpão", GALPOES, key="galpao_morta_v2")

            with col2:
                qtd_morta = st.number_input("🪦 Quantidade de Aves Mortas", min_value=1, step=1, format="%d",
                                            key="qtd_morta_v2")

            if st.button("✅ Registrar Morte", use_container_width=True, type="primary", key="btn_morta_v2"):
                conn = sqlite3.connect('estoque_ovos.db')
                c = conn.cursor()
                c.execute(
                    "INSERT INTO aves_mortas (username, galpao, quantidade, data) VALUES (?, ?, ?, ?)",
                    (st.session_state.username, galpao_morta, qtd_morta, data_morta)
                )
                conn.commit()
                conn.close()
                st.success(f"✅ {qtd_morta} aves mortas registradas!")
                st.rerun()

                # ===================== SUBABA 3: HISTÓRICO =====================
        with tab_historico:
            st.markdown("#### 📋 Histórico de Aves")

            conn = sqlite3.connect('estoque_ovos.db')

            df_aves = pd.read_sql("""
                SELECT data_registro as Data, galpao as Galpão, quantidade_total as 'Registradas'
                FROM aves WHERE username=? ORDER BY data_registro DESC
            """, conn, params=(st.session_state.username,))

            df_mortas = pd.read_sql("""
                SELECT data as Data, galpao as Galpão, quantidade as 'Mortas'
                FROM aves_mortas WHERE username=? ORDER BY data DESC
            """, conn, params=(st.session_state.username,))

            conn.close()

            # Formatação das datas
            if not df_aves.empty:
                df_aves['Data'] = pd.to_datetime(
                    df_aves['Data']).dt.strftime('%d/%m/%Y')

            if not df_mortas.empty:
                df_mortas['Data'] = pd.to_datetime(
                    df_mortas['Data']).dt.strftime('%d/%m/%Y')

            col_h1, col_h2 = st.columns(2)
            with col_h1:
                st.markdown("**Aves Registradas**")
                if not df_aves.empty:
                    st.dataframe(
                        df_aves, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhum registro encontrado.")

            with col_h2:
                st.markdown("**Aves Mortas**")
                if not df_mortas.empty:
                    st.dataframe(
                        df_mortas, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhum registro encontrado.")

        st.divider()

        # ===================== RESUMO ATUAL =====================
        st.markdown("#### 📊 Resumo Atual de Aves por Galpão")
        for galpao in GALPOES:
            conn = sqlite3.connect('estoque_ovos.db')
            c = conn.cursor()
            c.execute("SELECT COALESCE(SUM(quantidade_total), 0) FROM aves WHERE username=? AND galpao=?",
                      (st.session_state.username, galpao))
            total_reg = c.fetchone()[0]

            c.execute("SELECT COALESCE(SUM(quantidade), 0) FROM aves_mortas WHERE username=? AND galpao=?",
                      (st.session_state.username, galpao))
            total_morto = c.fetchone()[0]
            conn.close()

            total_vivo = max(0, total_reg - total_morto)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(f"{galpao} - Registradas", f"{total_reg} aves")
            with col2:
                st.metric(f"{galpao} - Mortas", f"{total_morto} aves")
            with col3:
                st.metric(f"{galpao} - Vivas", f"{total_vivo} aves")

                # ======================== ABA 5: GRÁFICOS ========================
    with tabs[4]:
        st.markdown("### 📈 Gráficos e Análises")

        # Carregando dados
        conn = sqlite3.connect('estoque_ovos.db')

        df_producao = pd.read_sql(
            "SELECT data, quantidade, tipo, galpao FROM producao WHERE username=? ORDER BY data",
            conn, params=(st.session_state.username,)
        )

        df_quebrados = pd.read_sql(
            "SELECT data, quantidade, galpao FROM ovos_quebrados WHERE username=? ORDER BY data",
            conn, params=(st.session_state.username,)
        )

        df_mortas = pd.read_sql(
            "SELECT data, quantidade, galpao FROM aves_mortas WHERE username=? ORDER BY data",
            conn, params=(st.session_state.username,)
        )

        conn.close()

        if df_producao.empty and df_quebrados.empty and df_mortas.empty:
            st.info("📭 Nenhum dado disponível para gerar gráficos.")
        else:
            if not df_producao.empty:
                df_producao['data'] = pd.to_datetime(df_producao['data'])
            if not df_quebrados.empty:
                df_quebrados['data'] = pd.to_datetime(df_quebrados['data'])
            if not df_mortas.empty:
                df_mortas['data'] = pd.to_datetime(df_mortas['data'])

            tab_prod, tab_quebrados, tab_mortas = st.tabs([
                "🥚 Produção de Ovos",
                "🔨 Ovos Quebrados",
                "🐔 Aves Mortas"
            ])

            # ===================== PRODUÇÃO DE OVOS =====================
            with tab_prod:
                st.markdown("#### Produção de Ovos por Período")

                if df_producao.empty:
                    st.info("Nenhum registro de produção.")
                else:
                    # Filtros de data
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        data_inicio = st.date_input(
                            "Data Inicial",
                            value=datetime.now().date() - pd.Timedelta(days=6),
                            format="DD/MM/YYYY",
                            key="data_inicio_prod"
                        )
                    with col_d2:
                        data_fim = st.date_input(
                            "Data Final",
                            value=datetime.now().date(),
                            format="DD/MM/YYYY",
                            key="data_fim_prod"
                        )

                    # Filtrando dados
                    df_filtrado = df_producao[
                        (df_producao['data'].dt.date >= data_inicio) &
                        (df_producao['data'].dt.date <= data_fim)
                    ].copy()

                    if df_filtrado.empty:
                        st.warning(
                            "Nenhum registro encontrado no período selecionado.")
                    else:
                        for galpao in sorted(df_filtrado['galpao'].unique()):
                            st.markdown(f"**{galpao}**")

                            df_g = df_filtrado[df_filtrado['galpao'] == galpao]
                            df_agg = df_g.groupby(['data', 'tipo'])[
                                'quantidade'].sum().reset_index()

                            df_pivot = df_agg.pivot(
                                index='data', columns='tipo', values='quantidade').fillna(0)
                            df_pivot = df_pivot.loc[:,
                                                    (df_pivot != 0).any(axis=0)]

                            if df_pivot.empty:
                                st.info(
                                    f"Nenhum registro para {galpao} no período selecionado.")
                            else:
                                fig = px.bar(
                                    df_pivot,
                                    x=df_pivot.index,
                                    y=df_pivot.columns,
                                    title=f"Produção - {galpao} ({data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')})",
                                    labels={
                                        'x': 'Data', 'value': 'Quantidade de Ovos', 'variable': 'Tipo'},
                                    text_auto=True,
                                    barmode='group'
                                )

                                fig.update_layout(
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font=dict(color="white", size=13),
                                    title_font=dict(color="white", size=16),
                                    legend_title_font=dict(color="white"),
                                    legend_font=dict(color="white"),
                                    xaxis=dict(
                                        title_font=dict(color="white"),
                                        tickfont=dict(color="white")
                                    ),
                                    yaxis=dict(
                                        title_font=dict(color="white"),
                                        tickfont=dict(color="white")
                                    )
                                )
                                fig.update_xaxes(tickformat='%d/%m')
                                st.plotly_chart(fig, use_container_width=True)

                            st.divider()
            # ===================== OVOS QUEBRADOS =====================
            with tab_quebrados:
                st.markdown("#### 🔨 Ovos Quebrados por Período")

                if df_quebrados.empty:
                    st.info("Nenhum registro de ovos quebrados.")
                else:
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        data_inicio_q = st.date_input(
                            "Data Inicial",
                            value=datetime.now().date() - pd.Timedelta(days=6),
                            format="DD/MM/YYYY",
                            key="data_inicio_quebrados"
                        )
                    with col_d2:
                        data_fim_q = st.date_input(
                            "Data Final",
                            value=datetime.now().date(),
                            format="DD/MM/YYYY",
                            key="data_fim_quebrados"
                        )

                    df_filtrado_q = df_quebrados[
                        (df_quebrados['data'].dt.date >= data_inicio_q) &
                        (df_quebrados['data'].dt.date <= data_fim_q)
                    ].copy()

                    if df_filtrado_q.empty:
                        st.warning(
                            "Nenhum registro encontrado no período selecionado.")
                    else:
                        for galpao in sorted(df_filtrado_q['galpao'].unique()):
                            st.markdown(f"**{galpao}**")

                            df_g = df_filtrado_q[df_filtrado_q['galpao'] == galpao]

                            # Agrupar por dia (total de ovos quebrados por dia)
                            df_agg = df_g.groupby(
                                'data')['quantidade'].sum().reset_index()
                            df_agg = df_agg.sort_values('data')

                            if df_agg.empty:
                                st.info(
                                    f"Nenhum registro para {galpao} no período selecionado.")
                            else:
                                fig = px.bar(
                                    df_agg,
                                    x='data',
                                    y='quantidade',
                                    title=f"Ovos Quebrados - {galpao} ({data_inicio_q.strftime('%d/%m/%Y')} a {data_fim_q.strftime('%d/%m/%Y')})",
                                    labels={
                                        'data': 'Data', 'quantidade': 'Quantidade de Ovos Quebrados'},
                                    text_auto=True,
                                    color_discrete_sequence=['#E74C3C']
                                )

                                fig.update_layout(
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font=dict(color="white", size=13),
                                    title_font=dict(color="white", size=16),
                                    xaxis=dict(title_font=dict(
                                        color="white"), tickfont=dict(color="white")),
                                    yaxis=dict(title_font=dict(
                                        color="white"), tickfont=dict(color="white"))
                                )
                                fig.update_xaxes(tickformat='%d/%m')
                                fig.update_traces(textposition='outside')
                                st.plotly_chart(fig, use_container_width=True)

                            st.divider()
            # ===================== AVES MORTAS =====================
            with tab_mortas:
                st.markdown("#### 🐔 Aves Mortas por Período")

                if df_mortas.empty:
                    st.info("Nenhum registro de aves mortas.")
                else:
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        data_inicio_m = st.date_input(
                            "Data Inicial",
                            value=datetime.now().date() - pd.Timedelta(days=6),
                            format="DD/MM/YYYY",
                            key="data_inicio_mortas"
                        )
                    with col_d2:
                        data_fim_m = st.date_input(
                            "Data Final",
                            value=datetime.now().date(),
                            format="DD/MM/YYYY",
                            key="data_fim_mortas"
                        )

                    df_filtrado_m = df_mortas[
                        (df_mortas['data'].dt.date >= data_inicio_m) &
                        (df_mortas['data'].dt.date <= data_fim_m)
                    ].copy()

                    if df_filtrado_m.empty:
                        st.warning(
                            "Nenhum registro encontrado no período selecionado.")
                    else:
                        for galpao in sorted(df_filtrado_m['galpao'].unique()):
                            st.markdown(f"**{galpao}**")

                            df_g = df_filtrado_m[df_filtrado_m['galpao'] == galpao]

                            # Agrupar por dia (total de aves mortas por dia)
                            df_agg = df_g.groupby(
                                'data')['quantidade'].sum().reset_index()
                            df_agg = df_agg.sort_values('data')

                            if df_agg.empty:
                                st.info(
                                    f"Nenhum registro para {galpao} no período selecionado.")
                            else:
                                fig = px.bar(
                                    df_agg,
                                    x='data',
                                    y='quantidade',
                                    title=f"Aves Mortas - {galpao} ({data_inicio_m.strftime('%d/%m/%Y')} a {data_fim_m.strftime('%d/%m/%Y')})",
                                    labels={
                                        'data': 'Data', 'quantidade': 'Quantidade de Aves Mortas'},
                                    text_auto=True,
                                    # Roxo para diferenciar
                                    color_discrete_sequence=['#8E44AD']
                                )

                                fig.update_layout(
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font=dict(color="white", size=13),
                                    title_font=dict(color="white", size=16),
                                    xaxis=dict(title_font=dict(
                                        color="white"), tickfont=dict(color="white")),
                                    yaxis=dict(title_font=dict(
                                        color="white"), tickfont=dict(color="white"))
                                )
                                fig.update_xaxes(tickformat='%d/%m')
                                fig.update_traces(textposition='outside')
                                st.plotly_chart(fig, use_container_width=True)

                            st.divider()

    # ======================== ABA 6: OVOS QUEBRADOS ========================
    with tabs[5]:
        st.markdown("### 🔨 Gerenciamento de Ovos Quebrados")

        # Formulário de registro
        st.markdown("#### 🔨 Registrar Ovos Quebrados")

        col1, col2 = st.columns(2)
        with col1:
            data_quebrados = st.date_input("📅 Data", value=datetime.now(
            ).date(), format="DD/MM/YYYY", key="data_quebrados")
            galpao_quebrados = st.selectbox(
                "🏠 Galpão", GALPOES, key="galpao_quebrados")

        with col2:
            qtd_quebrados = st.number_input(
                "🔨 Quantidade de Ovos Quebrados", min_value=1, step=1, format="%d", key="qtd_quebrados")

        if st.button("✅ Registrar Quebrados", use_container_width=True):
            conn = sqlite3.connect('estoque_ovos.db')
            c = conn.cursor()
            c.execute(
                "INSERT INTO ovos_quebrados (username, galpao, quantidade, data) VALUES (?, ?, ?, ?)",
                (st.session_state.username, galpao_quebrados,
                 qtd_quebrados, data_quebrados)
            )
            conn.commit()
            conn.close()
            st.success(
                f"✅ {qtd_quebrados} ovos quebrados registrados no {galpao_quebrados}!")
            st.rerun()

        st.divider()

        # Resumo por galpão
        st.markdown("#### 📊 Resumo de Ovos Quebrados por Galpão")

        conn = sqlite3.connect('estoque_ovos.db')

        total_quebrados_geral = 0
        cols_quebrados = st.columns(len(GALPOES))

        for idx, galpao in enumerate(GALPOES):
            c = conn.cursor()
            c.execute("SELECT COALESCE(SUM(quantidade), 0) FROM ovos_quebrados WHERE username=? AND galpao=?",
                      (st.session_state.username, galpao))
            total = c.fetchone()[0]
            total_quebrados_geral += total

            with cols_quebrados[idx]:
                st.metric(galpao, f"{total} ovos quebrados")

        conn.close()

        st.divider()

        # Histórico
        st.markdown("#### 📋 Histórico de Ovos Quebrados")

        conn = sqlite3.connect('estoque_ovos.db')
        df_quebrados = pd.read_sql(
            "SELECT data, galpao, quantidade FROM ovos_quebrados WHERE username=? ORDER BY data DESC",
            conn,
            params=(st.session_state.username,)
        )
        conn.close()

        if not df_quebrados.empty:
            df_quebrados['data'] = pd.to_datetime(
                df_quebrados['data']).dt.strftime('%d/%m/%Y')
            st.dataframe(df_quebrados.rename(columns={
                         'data': 'Data', 'galpao': 'Galpão', 'quantidade': 'Quantidade'}), use_container_width=True, hide_index=True)
        else:
            st.info("📭 Nenhum registro de ovos quebrados.")

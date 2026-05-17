import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import datetime
import base64
from pathlib import Path
import plotly.express as px

# ==================== CONEXÃO COM SUPABASE (POSTGRES) ====================


@st.cache_resource
def get_engine():
    """Cria conexão com o banco do Supabase"""
    try:
        database_url = st.secrets["supabase"]["DATABASE_URL"]
        engine = create_engine(
            database_url,
            pool_pre_ping=True,      # importante para Streamlit Cloud
            pool_recycle=3600
        )
        return engine
    except Exception as e:
        st.error(f"Erro ao conectar no banco de dados: {e}")
        st.stop()


engine = get_engine()
# =====================================================================

# --- CONFIGURAÇÃO DE ÍCONE PERSONALIZADO ---

# === CAMINHO SEGURO DA IMAGEM ===
BASE_DIR = Path(__file__).parent          # pasta onde está o app.py
LOGO_PATH = BASE_DIR / "assets" / "logomarca.png"


# 1. Função de Estilo Avançada (CSS Responsivo e Persistente)

def aplicar_estilo_customizado():
    try:
        with open(LOGO_PATH, "rb") as img_file:
            logo_base64 = base64.b64encode(img_file.read()).decode()
    except:
        logo_base64 = ""

    st.markdown(f"""
    <style>
    .stApp {{
        background-image: url("data:image/png;base64,{logo_base64}") !important;
        background-size: 35% !important;
        background-position: center !important;
        background-repeat: no-repeat !important;
        background-attachment: fixed !important;
    }}
    </style>
    """, unsafe_allow_html=True)


st.set_page_config(page_title="Estoque Ovos Pro", layout="wide")
aplicar_estilo_customizado()


# --- INICIALIZAÇÃO DE SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""

# --- CONSTANTES ---
TIPOS_OVO = ["A", "B", "Jumbo", "Extra",]
GALPOES = ["Galpão 2", "Galpão 3"]
CORES = ["Branco", "Vermelho"]


# ==================== LOGIN E CRIAÇÃO DE CONTA (SUPABASE) ====================
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
                try:
                    with engine.connect() as conn:
                        result = conn.execute(
                            text(
                                "SELECT password FROM usuarios WHERE username = :user"),
                            {"user": user}
                        ).fetchone()

                    if result and result[0] == pw:
                        st.session_state.logged_in = True
                        st.session_state.username = user
                        st.rerun()
                    else:
                        st.error("Login ou senha inválidos.")
                except Exception as e:
                    st.error(f"Erro ao fazer login: {e}")

    with col2:
        if st.button("Criar Conta", use_container_width=True):
            if user and pw:
                try:
                    with engine.connect() as conn:
                        conn.execute(
                            text(
                                "INSERT INTO usuarios (username, password) VALUES (:user, :pw)"),
                            {"user": user, "pw": pw}
                        )
                        conn.commit()
                    st.success("Conta criada com sucesso! Faça login.")
                except Exception as e:
                    if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                        st.error("Este usuário já existe.")
                    else:
                        st.error(f"Erro ao criar conta: {e}")
            else:
                st.error("Preencha usuário e senha.")

else:
    # ==================== PAINEL PRINCIPAL ====================
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
        data_reg = st.date_input("📅 Data da Colheita", value=datetime.now().date(),
                                 format="DD/MM/YYYY", key="data_colheita")
        qtd_val = st.number_input("🥚 Quantidade de Ovos", min_value=0, step=1,
                                  format="%d", key="qtd_colheita")
    with col2:
        tipo_ovo = st.selectbox("🏷️ Tipo de Ovo", TIPOS_OVO, key="tipo_ovo")
        galpao = st.selectbox("🏠 Galpão", GALPOES, key="galpao_colheita")

    cor = st.selectbox("🎨 Cor do Ovo", CORES, key="cor_ovo")

    if st.button("✅ Salvar Colheita", use_container_width=True):
        if qtd_val > 0:
            try:
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO producao (username, data, quantidade, tipo, galpao, cor)
                        VALUES (:username, :data, :quantidade, :tipo, :galpao, :cor)
                    """), {
                        "username": st.session_state.username,
                        "data": data_reg,
                        "quantidade": qtd_val,
                        "tipo": tipo_ovo,
                        "galpao": galpao,
                        "cor": cor
                    })
                    conn.commit()
                st.balloons()
                st.success(
                    f"✅ {qtd_val} ovos ({tipo_ovo}, {cor}) do {galpao} registrados com sucesso!")
            except Exception as e:
                st.error(f"Erro ao salvar colheita: {e}")
        else:
            st.error("Quantidade deve ser maior que zero.")

# ======================== ABA 2: HISTÓRICO & EDIÇÃO ========================
with tabs[1]:
    st.markdown("### 🔍 Gerenciar Histórico")

    try:
        df_edit = pd.read_sql(
            text("""
                SELECT id, data, quantidade, tipo, galpao, cor 
                FROM producao 
                WHERE username = :username 
                ORDER BY id DESC
            """),
            engine,
            params={"username": st.session_state.username}
        )

        if not df_edit.empty:
            df_edit['data_fmt'] = pd.to_datetime(
                df_edit['data']).dt.strftime('%d/%m/%Y')

            opcoes = {
                row['id']: f"📅 {row['data_fmt']} | {row['quantidade']} ovos | {row['tipo']} | {row['cor']} | {row['galpao']}"
                for _, row in df_edit.iterrows()
            }

            selecao = st.selectbox(
                "Escolha um registro para corrigir:", list(opcoes.values()))
            selected_id = [k for k, v in opcoes.items() if v == selecao][0]

            registro = df_edit[df_edit['id'] == selected_id].iloc[0]

            col1, col2 = st.columns(2)
            with col1:
                novo_val = st.number_input("Corrigir quantidade:", min_value=0, step=1,
                                           value=int(registro['quantidade']))
                novo_tipo = st.selectbox("Corrigir tipo:", TIPOS_OVO,
                                         index=TIPOS_OVO.index(registro['tipo']))
            with col2:
                novo_galpao = st.selectbox("Corrigir galpão:", GALPOES,
                                           index=GALPOES.index(registro['galpao']))
                nova_cor = st.selectbox("Corrigir cor:", CORES,
                                        index=CORES.index(registro['cor']))

            if st.button("✅ Confirmar Alteração", use_container_width=True):
                try:
                    with engine.connect() as conn:
                        conn.execute(text("""
                            UPDATE producao 
                            SET quantidade = :qtd, tipo = :tipo, galpao = :galpao, cor = :cor 
                            WHERE id = :id AND username = :username
                        """), {
                            "qtd": novo_val, "tipo": novo_tipo,
                            "galpao": novo_galpao, "cor": nova_cor,
                            "id": selected_id, "username": st.session_state.username
                        })
                        conn.commit()
                    st.success("✅ Registro atualizado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar: {e}")
        else:
            st.info("📭 Nenhum registro de colheita encontrado.")
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")

# ======================== ABA 3: MONITORAMENTO ========================
with tabs[2]:
    st.markdown("### 📊 Monitoramento de Produção")

    try:
        df_producao = pd.read_sql(
            text("""
                SELECT data, quantidade, tipo, galpao, cor 
                FROM producao 
                WHERE username = :username 
                ORDER BY data DESC
            """),
            engine,
            params={"username": st.session_state.username}
        )

        if df_producao.empty:
            st.info("📭 Nenhum registro de colheita encontrado.")
        else:
            df_producao['data'] = pd.to_datetime(df_producao['data'])

            st.markdown("#### 📅 Selecione o Dia para Análise")
            col_f1, col_f2 = st.columns([3, 1])
            with col_f1:
                data_selecionada = st.date_input("Data", value=datetime.now().date(),
                                                 format="DD/MM/YYYY", key="data_monitor")
            with col_f2:
                mostrar_todos = st.checkbox(
                    "Mostrar todos os dias", value=False, key="checkbox_todos_dias")

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
                    "Nenhum registro encontrado para a data selecionada.")
            else:
                st.markdown("#### 📋 Detalhes por Galpão e Tipo")
                df_filtrado = df_filtrado.copy()
                df_filtrado['galpao_norm'] = df_filtrado['galpao'].astype(
                    str).str.strip()

                for galpao in sorted(df_filtrado['galpao_norm'].unique()):
                    st.markdown(f"**{galpao}**")
                    df_galpao = df_filtrado[df_filtrado['galpao_norm'] == galpao]

                    total_galpao = df_galpao['quantidade'].sum()
                    st.info(f"**Total de Ovos do Dia:** {total_galpao} ovos")

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

                    cor_cols = st.columns(len(CORES))
                    for idx, cor in enumerate(CORES):
                        with cor_cols[idx]:
                            total_cor = df_galpao[df_galpao['cor']
                                                  == cor]['quantidade'].sum()
                            st.warning(f"**{cor}**: {total_cor} ovos")
                    st.divider()
    except Exception as e:
        st.error(f"Erro ao carregar monitoramento: {e}")

# ======================== ABA 4: REGISTRAR AVES ========================
with tabs[3]:
    st.markdown("### 🐔 Gerenciamento de Aves")

    tab_reg_aves, tab_mortas, tab_historico = st.tabs([
        "➕ Registrar Aves", "⚠️ Aves Mortas", "📋 Histórico"
    ])

    with tab_reg_aves:
        st.markdown("#### ➕ Adicionar Novas Aves")
        col1, col2 = st.columns(2)
        with col1:
            data_aves = st.date_input("📅 Data", value=datetime.now().date(),
                                      format="DD/MM/YYYY", key="data_aves_reg_v2")
            galpao_aves = st.selectbox(
                "🏠 Galpão", GALPOES, key="galpao_aves_reg_v2")
        with col2:
            qtd_aves = st.number_input("🐔 Quantidade de Aves", min_value=1, step=1,
                                       format="%d", key="qtd_aves_reg_v2")

        if st.button("✅ Registrar Aves", use_container_width=True, type="primary", key="btn_reg_aves_v2"):
            if qtd_aves > 0:
                try:
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO aves (username, galpao, quantidade_total, data_registro)
                            VALUES (:username, :galpao, :qtd, :data)
                        """), {
                            "username": st.session_state.username,
                            "galpao": galpao_aves,
                            "qtd": qtd_aves,
                            "data": data_aves
                        })
                        conn.commit()
                    st.success(
                        f"✅ {qtd_aves} aves registradas no {galpao_aves}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao registrar aves: {e}")

    with tab_mortas:
        st.markdown("#### ⚠️ Registrar Aves Mortas")
        col1, col2 = st.columns(2)
        with col1:
            data_morta = st.date_input("📅 Data", value=datetime.now().date(),
                                       format="DD/MM/YYYY", key="data_morta_v2")
            galpao_morta = st.selectbox(
                "🏠 Galpão", GALPOES, key="galpao_morta_v2")
        with col2:
            qtd_morta = st.number_input("🪦 Quantidade de Aves Mortas", min_value=1, step=1,
                                        format="%d", key="qtd_morta_v2")

        if st.button("✅ Registrar Morte", use_container_width=True, type="primary", key="btn_morta_v2"):
            try:
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO aves_mortas (username, galpao, quantidade, data)
                        VALUES (:username, :galpao, :qtd, :data)
                    """), {
                        "username": st.session_state.username,
                        "galpao": galpao_morta,
                        "qtd": qtd_morta,
                        "data": data_morta
                    })
                    conn.commit()
                st.success(f"✅ {qtd_morta} aves mortas registradas!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao registrar morte: {e}")

    with tab_historico:
        st.markdown("#### 📋 Histórico de Aves")
        col_h1, col_h2 = st.columns(2)

        with col_h1:
            st.markdown("**Aves Registradas**")
            try:
                df_aves = pd.read_sql(text("""
                    SELECT data_registro as Data, galpao as Galpão, quantidade_total as 'Registradas'
                    FROM aves WHERE username = :username ORDER BY data_registro DESC
                """), engine, params={"username": st.session_state.username})
                if not df_aves.empty:
                    df_aves['Data'] = pd.to_datetime(
                        df_aves['Data']).dt.strftime('%d/%m/%Y')
                    st.dataframe(
                        df_aves, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhum registro encontrado.")
            except Exception as e:
                st.error(f"Erro: {e}")

        with col_h2:
            st.markdown("**Aves Mortas**")
            try:
                df_mortas = pd.read_sql(text("""
                    SELECT data as Data, galpao as Galpão, quantidade as 'Mortas'
                    FROM aves_mortas WHERE username = :username ORDER BY data DESC
                """), engine, params={"username": st.session_state.username})
                if not df_mortas.empty:
                    df_mortas['Data'] = pd.to_datetime(
                        df_mortas['Data']).dt.strftime('%d/%m/%Y')
                    st.dataframe(
                        df_mortas, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhum registro encontrado.")
            except Exception as e:
                st.error(f"Erro: {e}")

    st.divider()
    st.markdown("#### 📊 Resumo Atual de Aves por Galpão")
    for galpao in GALPOES:
        try:
            with engine.connect() as conn:
                total_reg = conn.execute(text("""
                    SELECT COALESCE(SUM(quantidade_total), 0) FROM aves 
                    WHERE username = :u AND galpao = :g
                """), {"u": st.session_state.username, "g": galpao}).scalar()
                total_morto = conn.execute(text("""
                    SELECT COALESCE(SUM(quantidade), 0) FROM aves_mortas 
                    WHERE username = :u AND galpao = :g
                """), {"u": st.session_state.username, "g": galpao}).scalar()
            total_vivo = max(0, total_reg - total_morto)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(f"{galpao} - Registradas", f"{total_reg} aves")
            with col2:
                st.metric(f"{galpao} - Mortas", f"{total_morto} aves")
            with col3:
                st.metric(f"{galpao} - Vivas", f"{total_vivo} aves")
        except Exception as e:
            st.error(f"Erro ao calcular resumo: {e}")

# ======================== ABA 5: GRÁFICOS (SUPABASE) ========================
with tabs[4]:
    st.markdown("### 📈 Gráficos e Análises")

    try:
        # Carregando dados do Supabase
        df_producao = pd.read_sql(text("""
            SELECT data, quantidade, tipo, galpao 
            FROM producao 
            WHERE username = :username 
            ORDER BY data
        """), engine, params={"username": st.session_state.username})

        df_quebrados = pd.read_sql(text("""
            SELECT data, quantidade, galpao 
            FROM ovos_quebrados 
            WHERE username = :username 
            ORDER BY data
        """), engine, params={"username": st.session_state.username})

        df_mortas = pd.read_sql(text("""
            SELECT data, quantidade, galpao 
            FROM aves_mortas 
            WHERE username = :username 
            ORDER BY data
        """), engine, params={"username": st.session_state.username})

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
                "🥚 Produção de Ovos", "🔨 Ovos Quebrados", "🐔 Aves Mortas"
            ])

            # ===================== PRODUÇÃO DE OVOS =====================
            with tab_prod:
                st.markdown("#### Produção de Ovos por Período")

                if df_producao.empty:
                    st.info("Nenhum registro de produção.")
                else:
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        data_inicio = st.date_input("Data Inicial", value=datetime.now().date() - pd.Timedelta(days=6),
                                                    format="DD/MM/YYYY", key="data_inicio_prod")
                    with col_d2:
                        data_fim = st.date_input("Data Final", value=datetime.now().date(),
                                                 format="DD/MM/YYYY", key="data_fim_prod")

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

                            if not df_pivot.empty:
                                fig = px.bar(
                                    df_pivot, x=df_pivot.index, y=df_pivot.columns,
                                    title=f"Produção - {galpao}",
                                    labels={
                                        'x': 'Data', 'value': 'Quantidade', 'variable': 'Tipo'},
                                    text_auto=True, barmode='group'
                                )
                                fig.update_layout(
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font=dict(color="black", size=12),
                                    xaxis=dict(tickformat='%d/%m')
                                )
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
                        data_inicio_q = st.date_input("Data Inicial", value=datetime.now().date() - pd.Timedelta(days=6),
                                                      format="DD/MM/YYYY", key="data_inicio_quebrados")
                    with col_d2:
                        data_fim_q = st.date_input("Data Final", value=datetime.now().date(),
                                                   format="DD/MM/YYYY", key="data_fim_quebrados")

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
                            df_agg = df_g.groupby(
                                'data')['quantidade'].sum().reset_index()

                            if not df_agg.empty:
                                fig = px.bar(df_agg, x='data', y='quantidade',
                                             title=f"Ovos Quebrados - {galpao}",
                                             text_auto=True, color_discrete_sequence=['#E74C3C'])
                                fig.update_layout(
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font=dict(color="black", size=12),
                                    xaxis=dict(tickformat='%d/%m')
                                )
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
                        data_inicio_m = st.date_input("Data Inicial", value=datetime.now().date() - pd.Timedelta(days=6),
                                                      format="DD/MM/YYYY", key="data_inicio_mortas")
                    with col_d2:
                        data_fim_m = st.date_input("Data Final", value=datetime.now().date(),
                                                   format="DD/MM/YYYY", key="data_fim_mortas")

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
                            df_agg = df_g.groupby(
                                'data')['quantidade'].sum().reset_index()

                            if not df_agg.empty:
                                fig = px.bar(df_agg, x='data', y='quantidade',
                                             title=f"Aves Mortas - {galpao}",
                                             text_auto=True, color_discrete_sequence=['#8E44AD'])
                                fig.update_layout(
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font=dict(color="black", size=12),
                                    xaxis=dict(tickformat='%d/%m')
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            st.divider()

    except Exception as e:
        st.error(f"Erro ao carregar gráficos: {e}")

# ======================== ABA 6: OVOS QUEBRADOS (SUPABASE) ========================
with tabs[5]:
    st.markdown("### 🔨 Gerenciamento de Ovos Quebrados")

    # Formulário de registro
    st.markdown("#### 🔨 Registrar Ovos Quebrados")

    col1, col2 = st.columns(2)
    with col1:
        data_quebrados = st.date_input("📅 Data", value=datetime.now().date(),
                                       format="DD/MM/YYYY", key="data_quebrados")
        galpao_quebrados = st.selectbox(
            "🏠 Galpão", GALPOES, key="galpao_quebrados")
    with col2:
        qtd_quebrados = st.number_input("🔨 Quantidade de Ovos Quebrados", min_value=1, step=1,
                                        format="%d", key="qtd_quebrados")

    if st.button("✅ Registrar Quebrados", use_container_width=True):
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO ovos_quebrados (username, galpao, quantidade, data)
                    VALUES (:username, :galpao, :qtd, :data)
                """), {
                    "username": st.session_state.username,
                    "galpao": galpao_quebrados,
                    "qtd": qtd_quebrados,
                    "data": data_quebrados
                })
                conn.commit()
            st.success(
                f"✅ {qtd_quebrados} ovos quebrados registrados no {galpao_quebrados}!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao registrar: {e}")

    st.divider()

    # Resumo por galpão
    st.markdown("#### 📊 Resumo de Ovos Quebrados por Galpão")

    try:
        cols_quebrados = st.columns(len(GALPOES))
        for idx, galpao in enumerate(GALPOES):
            with engine.connect() as conn:
                total = conn.execute(text("""
                    SELECT COALESCE(SUM(quantidade), 0) 
                    FROM ovos_quebrados 
                    WHERE username = :u AND galpao = :g
                """), {"u": st.session_state.username, "g": galpao}).scalar()

            with cols_quebrados[idx]:
                st.metric(galpao, f"{total} ovos quebrados")
    except Exception as e:
        st.error(f"Erro ao carregar resumo: {e}")

    st.divider()

    # Histórico
    st.markdown("#### 📋 Histórico de Ovos Quebrados")

    try:
        df_quebrados = pd.read_sql(text("""
            SELECT data, galpao, quantidade 
            FROM ovos_quebrados 
            WHERE username = :username 
            ORDER BY data DESC
        """), engine, params={"username": st.session_state.username})

        if not df_quebrados.empty:
            df_quebrados['data'] = pd.to_datetime(
                df_quebrados['data']).dt.strftime('%d/%m/%Y')
            st.dataframe(df_quebrados.rename(columns={
                'data': 'Data', 'galpao': 'Galpão', 'quantidade': 'Quantidade'
            }), use_container_width=True, hide_index=True)
        else:
            st.info("📭 Nenhum registro de ovos quebrados.")
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")

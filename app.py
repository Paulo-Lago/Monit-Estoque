import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import datetime, date
import base64
from pathlib import Path
import plotly.express as px

# ==================== CONEXÃO COM SUPABASE ====================


@st.cache_resource
def get_engine():
    try:
        database_url = st.secrets["supabase"]["DATABASE_URL"]
        engine = create_engine(
            database_url, pool_pre_ping=True, pool_recycle=3600)
        return engine
    except Exception as e:
        st.error(f"Erro ao conectar no banco: {e}")
        st.stop()


engine = get_engine()

# ==================== ESTILO ====================
BASE_DIR = Path(__file__).parent
LOGO_PATH = BASE_DIR / "assets" / "logomarca.png"


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
        background-size: 26% !important;
        background-position: center !important;
        background-repeat: no-repeat !important;
        background-attachment: fixed !important;
        opacity: 0.92;
    }}
    </style>
    """, unsafe_allow_html=True)


st.set_page_config(page_title="Estoque Ovos Pro", layout="wide")
aplicar_estilo_customizado()

# ==================== SESSION STATE ====================
# Tenta restaurar sessão a partir da URL
if 'logged_in' not in st.session_state:
    user_from_url = st.query_params.get("user")
    if user_from_url:
        st.session_state.logged_in = True
        st.session_state.username = user_from_url
        st.session_state.modulo_atual = None
    else:
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.modulo_atual = None

# ==================== CONSTANTES ====================
TIPOS_OVO = ["A", "B", "Jumbo", "Extra"]
GALPOES = ["Galpão 2", "Galpão 3"]
CORES = ["Branco", "Vermelho"]

# ==================== LOGIN ====================
if not st.session_state.logged_in:
    st.markdown("<h1>🐔 Estoque de Ovos Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-texto'>Sua produção organizada de forma profissional</p>",
                unsafe_allow_html=True)

    user = st.text_input("Nome de Usuário", placeholder="Digite seu usuário")
    pw = st.text_input("Senha", type="password",
                       placeholder="Digite sua senha")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Entrar", width='stretch'):
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
                        st.query_params["user"] = user
                        st.rerun()
                    else:
                        st.error("Login ou senha inválidos.")
                except Exception as e:
                    st.error(f"Erro ao fazer login: {e}")

    with col2:
        if st.button("Criar Conta", width='stretch'):
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

    st.stop()

# ============================================================
# USUÁRIO LOGADO
# ============================================================

# CONTROLE DE MÓDULO
if st.session_state.modulo_atual is None:
    st.title("🐔 Bem-vindo ao Monit-Estoque")
    st.markdown("### Escolha a área que deseja acessar:")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🐔 **Monitoramento de Produção**", width='stretch', type="primary"):
            st.session_state.modulo_atual = "monitoramento"
            st.rerun()

    with col2:
        if st.button("💰 **Faturamento & Controle**", width='stretch', type="primary"):
            st.session_state.modulo_atual = "faturamento"
            st.rerun()

else:
    if st.sidebar.button("🔄 Trocar de Módulo", width='stretch'):
        st.session_state.modulo_atual = None
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.write(
        f"**Módulo atual:** {st.session_state.modulo_atual.capitalize()}")

    # ============================================================
    # MÓDULO: MONITORAMENTO DE PRODUÇÃO
    # ============================================================
    if st.session_state.modulo_atual == "monitoramento":

        st.header("🐔 Monitoramento de Produção")

        if st.sidebar.button("🚪 Sair / Logout"):
            st.session_state.logged_in = False
            st.session_state.modulo_atual = None
            st.query_params.clear()
            st.rerun()

        tabs = st.tabs([
            "📝 Nova Colheita",
            "📋 Produção & Histórico",
            "🐔 Registrar Aves",
            "📈 Gráficos",
            "🔨 Ovos Quebrados",
            "⚙️ Configurações"
        ])

        # ======================== ABA 0: NOVA COLHEITA ========================
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
                galpao = st.selectbox(
                    "🏠 Galpão", GALPOES, key="galpao_colheita")

            cor = st.selectbox("🎨 Cor do Ovo", CORES, key="cor_ovo")

            if st.button("✅ Salvar Colheita", width='stretch'):
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

        # ======================== ABA 1: PRODUÇÃO & HISTÓRICO ========================
        with tabs[1]:
            st.markdown("### 📋 Produção & Histórico")

            prod_tabs = st.tabs(
                ["📊 Monitoramento", "🔍 Histórico & Edição", "📦 Caixas de Ovos"])

            # ==================== SUB-ABA 1: MONITORAMENTO ====================
            with prod_tabs[0]:
                st.markdown("### 📊 Monitoramento de Produção")

                try:
                    df_producao = pd.read_sql(text("""
                        SELECT data, quantidade, tipo, galpao, cor
                        FROM producao
                        WHERE username = :username
                        ORDER BY data DESC
                    """), engine, params={"username": st.session_state.username})

                    if df_producao.empty:
                        st.info("📭 Nenhum registro de colheita encontrado.")
                    else:
                        df_producao['data'] = pd.to_datetime(
                            df_producao['data'])

                        st.markdown("#### 📅 Selecione o Período para Análise")
                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            data_inicio = st.date_input("Data Inicial", value=datetime.now().date() - pd.Timedelta(days=6),
                                                        format="DD/MM/YYYY", key="data_inicio_monitor")
                        with col_f2:
                            data_fim = st.date_input("Data Final", value=datetime.now().date(),
                                                     format="DD/MM/YYYY", key="data_fim_monitor")

                        df_filtrado = df_producao[
                            (df_producao['data'].dt.date >= data_inicio) &
                            (df_producao['data'].dt.date <= data_fim)
                        ].copy()

                        titulo_periodo = f"Período: {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}"
                        st.markdown(f"**{titulo_periodo}**")
                        st.divider()

                        if df_filtrado.empty:
                            st.warning(
                                "Nenhum registro encontrado para o período selecionado.")
                        else:
                            sub_tabs = st.tabs(
                                ["📋 Detalhes por Galpão e Tipo", "📦 Caixas de Ovos"])

                            with sub_tabs[0]:
                                st.markdown(
                                    "#### 📋 Detalhes por Galpão e Tipo")
                                df_temp = df_filtrado.copy()
                                df_temp['galpao_norm'] = df_temp['galpao'].astype(
                                    str).str.strip()

                                for galpao in sorted(df_temp['galpao_norm'].unique()):
                                    st.markdown(f"**{galpao}**")
                                    df_g = df_temp[df_temp['galpao_norm']
                                                   == galpao]
                                    total_galpao = df_g['quantidade'].sum()
                                    st.info(
                                        f"**Total de Ovos:** {total_galpao} ovos")

                                    tipos_para_mostrar = [t for t in TIPOS_OVO]
                                    if galpao == "Galpão 2":
                                        tipos_para_mostrar = [
                                            t for t in TIPOS_OVO if t != "B"]
                                    elif galpao == "Galpão 3":
                                        tipos_para_mostrar = [
                                            t for t in TIPOS_OVO if t != "Jumbo"]

                                    tipo_cols = st.columns(
                                        len(tipos_para_mostrar))
                                    for idx, tipo in enumerate(tipos_para_mostrar):
                                        with tipo_cols[idx]:
                                            total_tipo = df_g[df_g['tipo']
                                                              == tipo]['quantidade'].sum()
                                            st.info(
                                                f"**{tipo}**: {total_tipo} ovos")

                                    cor_cols = st.columns(len(CORES))
                                    for idx, cor in enumerate(CORES):
                                        with cor_cols[idx]:
                                            total_cor = df_g[df_g['cor']
                                                             == cor]['quantidade'].sum()
                                            st.warning(
                                                f"**{cor}**: {total_cor} ovos")
                                    st.divider()

                            with sub_tabs[1]:
                                st.markdown("#### 📦 Caixas de Ovos Fechadas")
                                st.caption("Cada caixa comporta **360 ovos**")

                                df_caixas = df_filtrado.copy()
                                df_caixas['galpao_norm'] = df_caixas['galpao'].astype(
                                    str).str.strip()

                                resumo = df_caixas.groupby(['galpao_norm', 'tipo', 'cor'])[
                                    'quantidade'].sum().reset_index()
                                resumo['caixas'] = resumo['quantidade'] // 360
                                resumo['ovos_restantes'] = resumo['quantidade'] % 360

                                for galpao in sorted(resumo['galpao_norm'].unique()):
                                    st.markdown(f"**{galpao}**")
                                    df_g = resumo[resumo['galpao_norm']
                                                  == galpao]
                                    if not df_g.empty:
                                        st.dataframe(
                                            df_g[['tipo', 'cor', 'quantidade', 'caixas', 'ovos_restantes']].rename(columns={
                                                'tipo': 'Tipo', 'cor': 'Cor', 'quantidade': 'Total de Ovos',
                                                'caixas': 'Caixas Completas (360)', 'ovos_restantes': 'Ovos Restantes'
                                            }),
                                            width='stretch', hide_index=True
                                        )
                                    else:
                                        st.info(
                                            "Nenhum registro neste galpão.")
                                    st.divider()

                except Exception as e:
                    st.error(f"Erro ao carregar monitoramento: {e}")

            # ==================== SUB-ABA 2: HISTÓRICO & EDIÇÃO ====================
            with prod_tabs[1]:
                st.markdown("### 🔍 Gerenciar Histórico")

                try:
                    df_edit = pd.read_sql(text("""
                        SELECT id, data, quantidade, tipo, galpao, cor
                        FROM producao
                        WHERE username = :username
                        ORDER BY id DESC
                    """), engine, params={"username": st.session_state.username})

                    if not df_edit.empty:
                        df_edit['data_fmt'] = pd.to_datetime(
                            df_edit['data']).dt.strftime('%d/%m/%Y')

                        opcoes = {
                            row['id']: f"📅 {row['data_fmt']} | {row['quantidade']} ovos | {row['tipo']} | {row['cor']} | {row['galpao']}"
                            for _, row in df_edit.iterrows()
                        }

                        selecao = st.selectbox(
                            "Escolha um registro para corrigir:", list(opcoes.values()))
                        selected_id = [
                            k for k, v in opcoes.items() if v == selecao][0]

                        registro = df_edit[df_edit['id']
                                           == selected_id].iloc[0]

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

                        if st.button("✅ Confirmar Alteração", width='stretch'):
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

             # ==================== CAIXAS DE OVOS ====================
                with prod_tabs[2]:
                    st.markdown(
                        "#### 📦 Caixas de Ovos Fechadas (Últimos 30 dias)")
                    if df_producao.empty:
                        st.info("Nenhum registro de produção.")
                    else:
                        data_limite = datetime.now().date() - pd.Timedelta(days=30)
                        df_recente = df_producao[df_producao['data'].dt.date >= data_limite].copy(
                        )

                        if df_recente.empty:
                            st.warning("Nenhum registro nos últimos 30 dias.")
                        else:
                            resumo = df_recente.groupby(['galpao', 'tipo', 'cor'])[
                                'quantidade'].sum().reset_index()
                            resumo['caixas'] = resumo['quantidade'] // 360
                            resumo['ovos_restantes'] = resumo['quantidade'] % 360

                            for galpao in sorted(resumo['galpao'].unique()):
                                st.markdown(f"**{galpao}**")
                                df_g = resumo[resumo['galpao'] == galpao]
                                st.dataframe(
                                    df_g[['tipo', 'cor', 'quantidade', 'caixas', 'ovos_restantes']].rename(columns={
                                        'tipo': 'Tipo', 'cor': 'Cor', 'quantidade': 'Total de Ovos',
                                        'caixas': 'Caixas Completas (360)', 'ovos_restantes': 'Ovos Restantes'
                                    }),
                                    width='stretch', hide_index=True
                                )
                                st.divider()

        # ======================== ABA 2: REGISTRAR AVES ========================
        with tabs[2]:
            st.markdown("### 🐔 Gerenciamento de Aves")

            tab_reg_aves, tab_mortas, tab_historico = st.tabs(
                ["➕ Registrar Aves", "⚠️ Aves Mortas", "📋 Histórico"])

            # ==================== REGISTRAR NOVAS AVES ====================
            with tab_reg_aves:
                st.markdown("#### ➕ Adicionar Novas Aves")
                col1, col2 = st.columns(2)
                with col1:
                    data_aves = st.date_input("📅 Data", value=datetime.now().date(),
                                              format="DD/MM/YYYY", key="data_aves_reg")
                    galpao_aves = st.selectbox(
                        "🏠 Galpão", GALPOES, key="galpao_aves_reg")
                with col2:
                    qtd_aves = st.number_input("🐔 Quantidade de Aves", min_value=1, step=1,
                                               format="%d", key="qtd_aves_reg")

                if st.button("✅ Registrar Aves", width='stretch', type="primary"):
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

            # ==================== AVES MORTAS ====================
            with tab_mortas:
                st.markdown("#### ⚠️ Registrar Aves Mortas")
                col1, col2 = st.columns(2)
                with col1:
                    data_morta = st.date_input("📅 Data", value=datetime.now().date(),
                                               format="DD/MM/YYYY", key="data_morta")
                    galpao_morta = st.selectbox(
                        "🏠 Galpão", GALPOES, key="galpao_morta")
                with col2:
                    qtd_morta = st.number_input("🪦 Quantidade de Aves Mortas", min_value=1, step=1,
                                                format="%d", key="qtd_morta")

                if st.button("✅ Registrar Morte", width='stretch', type="primary"):
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

            # ==================== HISTÓRICO + EDIÇÃO ====================
            with tab_historico:
                st.markdown("#### 📋 Histórico de Aves Registradas")

                try:
                    df_aves = pd.read_sql(text("""
                        SELECT id, data_registro, galpao, quantidade_total
                        FROM aves
                        WHERE username = :username
                        ORDER BY data_registro DESC
                    """), engine, params={"username": st.session_state.username})

                    if df_aves.empty:
                        st.info("Nenhum registro de aves encontrado.")
                    else:
                        df_aves = df_aves.rename(columns={
                            "data_registro": "Data",
                            "galpao": "Galpão",
                            "quantidade_total": "Quantidade"
                        })
                        df_aves['Data'] = pd.to_datetime(
                            df_aves['Data']).dt.strftime('%d/%m/%Y')

                        # Select para editar/excluir
                        opcoes = {
                            row['id']: f"📅 {row['Data']} | {row['Galpão']} | {row['Quantidade']} aves"
                            for _, row in df_aves.iterrows()
                        }

                        selecao = st.selectbox(
                            "Selecione um registro para editar ou excluir:", list(opcoes.values()))
                        selected_id = [
                            k for k, v in opcoes.items() if v == selecao][0]

                        registro = df_aves[df_aves['id']
                                           == selected_id].iloc[0]

                        st.markdown("---")
                        st.markdown("**Editar ou Excluir Registro**")

                        col1, col2 = st.columns(2)
                        with col1:
                            novo_galpao = st.selectbox("Galpão", GALPOES,
                                                       index=GALPOES.index(registro['Galpão']))
                            nova_qtd = st.number_input("Quantidade", min_value=1, step=1,
                                                       value=int(registro['Quantidade']))
                        with col2:
                            nova_data = st.date_input("Data", value=pd.to_datetime(registro['Data']).date(),
                                                      format="DD/MM/YYYY")

                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("✅ Salvar Alterações", width='stretch', type="primary"):
                                try:
                                    with engine.connect() as conn:
                                        conn.execute(text("""
                                            UPDATE aves
                                            SET galpao = :galpao, quantidade_total = :qtd, data_registro = :data
                                            WHERE id = :id AND username = :username
                                        """), {
                                            "galpao": novo_galpao,
                                            "qtd": nova_qtd,
                                            "data": nova_data,
                                            "id": selected_id,
                                            "username": st.session_state.username
                                        })
                                        conn.commit()
                                    st.success(
                                        "✅ Registro atualizado com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao atualizar: {e}")

                        with col_btn2:
                            st.warning("⚠️ Excluir este registro?")
                            if st.button("🗑️ Excluir Registro", type="primary"):
                                try:
                                    with engine.connect() as conn:
                                        conn.execute(text("""
                                            DELETE FROM aves
                                            WHERE id = :id AND username = :username
                                        """), {
                                            "id": selected_id,
                                            "username": st.session_state.username
                                        })
                                        conn.commit()
                                    st.success(
                                        "✅ Registro excluído com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir: {e}")

                        st.divider()
                        st.markdown("**Histórico Completo**")
                        st.dataframe(df_aves, width='stretch', hide_index=True)

                except Exception as e:
                    st.error(f"Erro ao carregar histórico: {e}")

            # ==================== RESUMO ATUAL ====================
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
                        st.metric(f"{galpao} - Registradas",
                                  f"{total_reg} aves")
                    with col2:
                        st.metric(f"{galpao} - Mortas", f"{total_morto} aves")
                    with col3:
                        st.metric(f"{galpao} - Vivas", f"{total_vivo} aves")

                except Exception as e:
                    st.error(f"Erro ao calcular resumo: {e}")

        # ======================== ABA 3: GRÁFICOS ========================
        with tabs[3]:
            st.markdown("### 📈 Gráficos e Análises")

            tab_prod, tab_quebrados, tab_mortas = st.tabs([
                "🥚 Produção de Ovos", "🔨 Ovos Quebrados", "🐔 Aves Mortas"
            ])

            try:
                df_producao = pd.read_sql(text("""
                    SELECT data, quantidade, tipo, galpao, cor
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

                if not df_producao.empty:
                    df_producao['data'] = pd.to_datetime(df_producao['data'])
                if not df_quebrados.empty:
                    df_quebrados['data'] = pd.to_datetime(df_quebrados['data'])
                if not df_mortas.empty:
                    df_mortas['data'] = pd.to_datetime(df_mortas['data'])

                # ==================== PRODUÇÃO DE OVOS ====================
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
                                    fig = px.line(
                                        df_pivot, x=df_pivot.index, y=df_pivot.columns,
                                        title=f"Produção - {galpao}",
                                        labels={
                                            'x': 'Data', 'value': 'Quantidade', 'variable': 'Tipo'},
                                        markers=True
                                    )
                                    fig.update_layout(
                                        plot_bgcolor='#ffffff',
                                        paper_bgcolor='#ffffff',
                                        font=dict(color="#000000", size=12),
                                        title_font=dict(color="#000000"),
                                        xaxis=dict(
                                            tickformat='%d/%m', color="#000000"),
                                        yaxis=dict(color="#000000")
                                    )
                                    st.plotly_chart(
                                        fig, use_container_width=True)
                                st.divider()

                # ==================== OVOS QUEBRADOS ====================
                with tab_quebrados:
                    st.markdown("#### 🔨 Ovos Quebrados por Período")
                    if df_quebrados.empty:
                        st.info("Nenhum registro de ovos quebrados.")
                    else:
                        col_d1, col_d2 = st.columns(2)
                        with col_d1:
                            data_inicio = st.date_input("Data Inicial", value=datetime.now().date() - pd.Timedelta(days=30),
                                                        format="DD/MM/YYYY", key="data_inicio_quebrados")
                        with col_d2:
                            data_fim = st.date_input("Data Final", value=datetime.now().date(),
                                                     format="DD/MM/YYYY", key="data_fim_quebrados")

                        df_filtrado = df_quebrados[
                            (df_quebrados['data'].dt.date >= data_inicio) &
                            (df_quebrados['data'].dt.date <= data_fim)
                        ].copy()

                        if df_filtrado.empty:
                            st.warning(
                                "Nenhum registro encontrado no período selecionado.")
                        else:
                            for galpao in sorted(df_filtrado['galpao'].unique()):
                                st.markdown(f"**{galpao}**")
                                df_g = df_filtrado[df_filtrado['galpao'] == galpao]
                                df_agg = df_g.groupby(
                                    'data')['quantidade'].sum().reset_index()

                                fig = px.line(
                                    df_agg, x='data', y='quantidade',
                                    title=f"Ovos Quebrados - {galpao}",
                                    labels={'data': 'Data',
                                            'quantidade': 'Quantidade'},
                                    markers=True
                                )
                                fig.update_layout(
                                    plot_bgcolor='#ffffff',
                                    paper_bgcolor='#ffffff',
                                    font=dict(color="#000000", size=12),
                                    title_font=dict(color="#000000"),
                                    xaxis=dict(tickformat='%d/%m',
                                               color="#000000"),
                                    yaxis=dict(color="#000000")
                                )
                                st.plotly_chart(fig, use_container_width=True)
                                st.divider()

                # ==================== AVES MORTAS ====================
                with tab_mortas:
                    st.markdown("#### 🐔 Aves Mortas por Período")
                    if df_mortas.empty:
                        st.info("Nenhum registro de aves mortas.")
                    else:
                        col_d1, col_d2 = st.columns(2)
                        with col_d1:
                            data_inicio = st.date_input("Data Inicial", value=datetime.now().date() - pd.Timedelta(days=30),
                                                        format="DD/MM/YYYY", key="data_inicio_mortas")
                        with col_d2:
                            data_fim = st.date_input("Data Final", value=datetime.now().date(),
                                                     format="DD/MM/YYYY", key="data_fim_mortas")

                        df_filtrado = df_mortas[
                            (df_mortas['data'].dt.date >= data_inicio) &
                            (df_mortas['data'].dt.date <= data_fim)
                        ].copy()

                        if df_filtrado.empty:
                            st.warning(
                                "Nenhum registro encontrado no período selecionado.")
                        else:
                            for galpao in sorted(df_filtrado['galpao'].unique()):
                                st.markdown(f"**{galpao}**")
                                df_g = df_filtrado[df_filtrado['galpao'] == galpao]
                                df_agg = df_g.groupby(
                                    'data')['quantidade'].sum().reset_index()

                                fig = px.line(
                                    df_agg, x='data', y='quantidade',
                                    title=f"Aves Mortas - {galpao}",
                                    labels={'data': 'Data',
                                            'quantidade': 'Quantidade'},
                                    markers=True
                                )
                                fig.update_layout(
                                    plot_bgcolor='#ffffff',
                                    paper_bgcolor='#ffffff',
                                    font=dict(color="#000000", size=12),
                                    title_font=dict(color="#000000"),
                                    xaxis=dict(tickformat='%d/%m',
                                               color="#000000"),
                                    yaxis=dict(color="#000000")
                                )
                                st.plotly_chart(fig, use_container_width=True)
                                st.divider()

            except Exception as e:
                st.error(f"Erro ao carregar gráficos: {e}")

        # ======================== ABA 4: OVOS QUEBRADOS ========================
        with tabs[4]:
            st.markdown("### 🔨 Gerenciamento de Ovos Quebrados")

            tab_registrar, tab_historico = st.tabs(
                ["➕ Registrar Ovos Quebrados", "📋 Histórico"])

            # ==================== REGISTRAR OVOS QUEBRADOS ====================
            with tab_registrar:
                st.markdown("#### ➕ Registrar Ovos Quebrados")

                col1, col2 = st.columns(2)
                with col1:
                    data_quebrados = st.date_input("📅 Data", value=datetime.now().date(),
                                                   format="DD/MM/YYYY", key="data_quebrados_reg")
                    galpao_quebrados = st.selectbox(
                        "🏠 Galpão", GALPOES, key="galpao_quebrados_reg")
                with col2:
                    qtd_quebrados = st.number_input("🔨 Quantidade de Ovos Quebrados", min_value=1, step=1,
                                                    format="%d", key="qtd_quebrados_reg")

                if st.button("✅ Registrar Ovos Quebrados", width='stretch', type="primary"):
                    if qtd_quebrados > 0:
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

            # ==================== HISTÓRICO ====================
            with tab_historico:
                st.markdown("#### 📋 Histórico de Ovos Quebrados")

                try:
                    df_quebrados_hist = pd.read_sql(text("""
                        SELECT id, data, galpao, quantidade
                        FROM ovos_quebrados
                        WHERE username = :username
                        ORDER BY data DESC
                    """), engine, params={"username": st.session_state.username})

                    if df_quebrados_hist.empty:
                        st.info("Nenhum registro de ovos quebrados encontrado.")
                    else:
                        # Renomeia primeiro
                        df_quebrados_hist = df_quebrados_hist.rename(columns={
                            "galpao": "Galpão",
                            "quantidade": "Quantidade"
                        })

                        # Depois formata a data e exibe
                        df_quebrados_hist['data'] = pd.to_datetime(
                            df_quebrados_hist['data']).dt.strftime('%d/%m/%Y')

                        st.dataframe(
                            df_quebrados_hist[["data", "Galpão", "Quantidade"]].rename(
                                columns={"data": "Data"}
                            ),
                            width='stretch',
                            hide_index=True
                        )

                except Exception as e:
                    st.error(f"Erro ao carregar histórico: {e}")

            # ==================== RESUMO ====================
            st.divider()
            st.markdown("#### 📊 Resumo de Ovos Quebrados por Galpão")

            for galpao in GALPOES:
                try:
                    with engine.connect() as conn:
                        total = conn.execute(text("""
                            SELECT COALESCE(SUM(quantidade), 0) FROM ovos_quebrados
                            WHERE username = :u AND galpao = :g
                        """), {"u": st.session_state.username, "g": galpao}).scalar()

                    st.metric(f"{galpao} - Total Quebrados", f"{total} ovos")
                except Exception as e:
                    st.error(f"Erro ao calcular resumo: {e}")

        # ======================== ABA 5: CONFIGURAÇÕES ========================
        with tabs[5]:
            st.markdown("### ⚙️ Configurações da Conta")
            st.markdown(f"**Usuário atual:** `{st.session_state.username}`")
            st.divider()
            st.markdown("#### 🔐 Alterar Senha")

            with st.form("change_password_form"):
                current_pw = st.text_input("Senha Atual", type="password")
                new_pw = st.text_input("Nova Senha", type="password")
                confirm_pw = st.text_input(
                    "Confirmar Nova Senha", type="password")

                submitted = st.form_submit_button("✅ Alterar Senha")

                if submitted:
                    if not current_pw or not new_pw or not confirm_pw:
                        st.error("Preencha todos os campos.")
                    elif new_pw != confirm_pw:
                        st.error("As senhas novas não coincidem.")
                    elif len(new_pw) < 4:
                        st.error(
                            "A nova senha deve ter pelo menos 4 caracteres.")
                    else:
                        try:
                            with engine.connect() as conn:
                                result = conn.execute(text("""
                                    SELECT password FROM usuarios
                                    WHERE username = :u
                                """), {"u": st.session_state.username}).fetchone()

                                if result and result[0] == current_pw:
                                    conn.execute(text("""
                                        UPDATE usuarios
                                        SET password = :new_pw
                                        WHERE username = :u
                                    """), {"new_pw": new_pw, "u": st.session_state.username})
                                    conn.commit()
                                    st.success("✅ Senha alterada com sucesso!")
                                else:
                                    st.error("Senha atual incorreta.")
                        except Exception as e:
                            st.error(f"Erro ao alterar senha: {e}")

    # ============================================================
    # MÓDULO: FATURAMENTO & CONTROLE
    # ============================================================
    else:
        st.header("💰 Faturamento & Controle de Estoque")

        # ----- FUNÇÃO AUXILIAR PARA ATUALIZAR ESTOQUE -----
        def atualizar_estoque(produto_id, delta):
            """Atualiza a quantidade em estoque (soma delta). delta pode ser negativo (venda) ou positivo (devolução)."""
            with engine.connect() as conn:
                produto_id_int = int(produto_id)
                # Verifica se já existe registro de estoque
                existe = conn.execute(text("""
                    SELECT 1 FROM estoque WHERE username = :u AND produto_id = :p
                """), {"u": st.session_state.username, "p": produto_id_int}).fetchone()

                if existe:
                    conn.execute(text("""
                        UPDATE estoque
                        SET quantidade = quantidade + :delta, data_atualizacao = CURRENT_TIMESTAMP
                        WHERE username = :u AND produto_id = :p
                    """), {"u": st.session_state.username, "p": produto_id_int, "delta": delta})
                else:
                    # Se não existe, cria com delta (se delta for positivo, senão lança erro)
                    if delta < 0:
                        raise Exception(
                            "Estoque insuficiente e sem registro inicial.")
                    conn.execute(text("""
                        INSERT INTO estoque (username, produto_id, quantidade)
                        VALUES (:u, :p, :qtd)
                    """), {"u": st.session_state.username, "p": produto_id_int, "qtd": delta})
                conn.commit()

        def verificar_estoque(produto_id, quantidade_necessaria):
            """Retorna True se há estoque suficiente."""
            with engine.connect() as conn:
                qtd_atual = conn.execute(text("""
                    SELECT COALESCE(quantidade, 0) FROM estoque
                    WHERE username = :u AND produto_id = :p
                """), {"u": st.session_state.username, "p": int(produto_id)}).scalar()
            return qtd_atual >= quantidade_necessaria

        fat_tabs = st.tabs([
            "🛒 Vendas",
            "📦 Estoque",
            "📝 Cadastros"
        ])

        # ============================================
        # ABA 0 → VENDAS
        # ============================================
        with fat_tabs[0]:
            st.subheader("🛒 Vendas")

            vendas_tabs = st.tabs([
                "🛒 Nova Venda",
                "📋 Registros de Vendas",
                "💰 Financeiro"
            ])

            # -------------------- NOVA VENDA (DESCONTO UNITÁRIO) --------------------
            with vendas_tabs[0]:
                st.markdown("""
                <style>
                .card-form {
                    background-color: #f9f9fb;
                    border-radius: 20px;
                    padding: 1.5rem;
                    border: 1px solid #e0e4e8;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
                    margin-bottom: 1rem;
                }
                .preco-unitario {
                    background-color: #eef2ff;
                    border-radius: 40px;
                    padding: 0.3rem 0.8rem;
                    display: inline-block;
                    font-size: 0.85rem;
                    color: #1e3a8a;
                    font-weight: 500;
                    margin-top: 1.8rem;
                }
                div.stButton > button:first-child {
                    border-radius: 40px;
                    font-weight: 600;
                    transition: all 0.2s ease;
                }
                div.stButton > button:first-child:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 12px rgba(0,0,0,0.1);
                }
                </style>
                """, unsafe_allow_html=True)

                st.markdown("### 🧾 Registrar Nova Venda")
                st.caption(
                    "Preencha os dados abaixo — a venda será revisada antes de salvar")

                if "venda_dados" not in st.session_state:
                    st.session_state.venda_dados = None
                if "mostrar_confirmacao" not in st.session_state:
                    st.session_state.mostrar_confirmacao = False

                try:
                    df_clientes = pd.read_sql(text("SELECT id, nome FROM clientes WHERE username = :u ORDER BY nome"), engine,
                                              params={"u": st.session_state.username})
                    df_produtos = pd.read_sql(text("SELECT id, nome, preco_atual FROM produtos WHERE username = :u ORDER BY nome"), engine,
                                              params={"u": st.session_state.username})
                    df_formas = pd.read_sql(text("SELECT id, nome FROM formas_pagamento WHERE (username = :u OR username IS NULL) AND ativo = TRUE ORDER BY nome"),
                                            engine, params={"u": st.session_state.username})

                    if df_clientes.empty or df_produtos.empty or df_formas.empty:
                        st.warning(
                            "⚠️ Cadastre pelo menos 1 Cliente, 1 Produto e 1 Forma de Pagamento ativa antes de registrar uma venda.")
                    else:
                        # ==================== MODO CONFIRMAÇÃO ====================
                        if st.session_state.mostrar_confirmacao and st.session_state.venda_dados:
                            dados = st.session_state.venda_dados
                            with st.container():
                                st.markdown("### ✅ Confirmar venda")
                                st.markdown(
                                    "Verifique os dados antes de finalizar")
                                st.divider()
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.markdown(
                                        f"**👤 Cliente**  \n{dados['cliente_nome']}")
                                    st.markdown(
                                        f"**📦 Produto**  \n{dados['produto_nome']}")
                                    st.markdown(
                                        f"**🔢 Quantidade**  \n{dados['quantidade']}")
                                    preco_original = dados['preco_unit']
                                    desconto_unit = dados['desconto_unit']
                                    preco_final = preco_original - desconto_unit
                                    st.markdown(
                                        f"**💰 Preço unitário original**  \nR$ {preco_original:.2f}")
                                    st.markdown(
                                        f"**🎁 Desconto por unidade**  \nR$ {desconto_unit:.2f}")
                                    st.markdown(
                                        f"**💵 Preço unitário com desconto**  \nR$ {preco_final:.2f}")
                                with col2:
                                    st.markdown(
                                        f"**💳 Pagamento**  \n{dados['forma_nome']}")
                                    st.markdown(
                                        f"**💰 Valor Pago agora**  \nR$ {dados['valor_pago']:.2f}")
                                    if dados.get('observacoes'):
                                        st.markdown(
                                            f"**📝 Observações**  \n{dados['observacoes']}")
                                st.divider()
                                col_r1, col_r2, col_r3 = st.columns(3)
                                with col_r1:
                                    st.metric("💰 Valor Total (com desconto)",
                                              f"R$ {dados['valor_total']:.2f}")
                                with col_r2:
                                    st.metric("💵 Valor Pago",
                                              f"R$ {dados['valor_pago']:.2f}")
                                with col_r3:
                                    st.metric("🔻 Ficará Devendo",
                                              f"R$ {dados['valor_devendo']:.2f}")
                                st.warning(
                                    "⚠️ Confirme os dados. Após salvar, não será possível editar diretamente.")
                                col_btn1, col_btn2 = st.columns(2)
                                with col_btn1:
                                    if st.button("✅ Confirmar e Registrar", type="primary", use_container_width=True):
                                        # Verificar estoque antes de vender
                                        if not verificar_estoque(dados['produto_id'], dados['quantidade']):
                                            st.error(
                                                f"❌ Estoque insuficiente para o produto '{dados['produto_nome']}'. Consulte a aba Estoque.")
                                        else:
                                            try:
                                                with engine.connect() as conn:
                                                    conn.execute(text("""
                                                        INSERT INTO vendas (username, cliente_id, data_venda, produto_id, quantidade,
                                                        preco_unitario, forma_pagamento_id, desconto, valor_total, valor_pago, observacoes)
                                                        VALUES (:u, :cliente_id, CURRENT_DATE, :produto_id, :qtd, :preco, :forma_id,
                                                                :desconto, :total, :valor_pago, :obs)
                                                    """), {
                                                        "u": st.session_state.username,
                                                        "cliente_id": dados['cliente_id'],
                                                        "produto_id": dados['produto_id'],
                                                        "qtd": dados['quantidade'],
                                                        "preco": dados['preco_unit'],
                                                        "forma_id": dados['forma_id'],
                                                        # desconto unitário
                                                        "desconto": dados['desconto_unit'],
                                                        "total": dados['valor_total'],
                                                        "valor_pago": dados['valor_pago'],
                                                        "obs": dados.get('observacoes')
                                                    })
                                                    conn.commit()
                                                # Atualizar estoque (subtrair quantidade vendida)
                                                atualizar_estoque(
                                                    dados['produto_id'], -dados['quantidade'])
                                                st.balloons()
                                                st.success(
                                                    "✅ Venda registrada com sucesso e estoque atualizado!")
                                                st.session_state.venda_dados = None
                                                st.session_state.mostrar_confirmacao = False
                                                st.rerun()
                                            except Exception as e:
                                                st.error(
                                                    f"Erro ao registrar venda: {e}")
                                with col_btn2:
                                    if st.button("✏️ Voltar e editar", use_container_width=True):
                                        st.session_state.mostrar_confirmacao = False
                                        st.rerun()

                        # ==================== MODO FORMULÁRIO ====================
                        else:
                            st.markdown('<div class="card-form">',
                                        unsafe_allow_html=True)
                            col_prod, col_preco_chip = st.columns([2, 1])
                            with col_prod:
                                produto_nome = st.selectbox(
                                    "📦 Produto *", df_produtos['nome'].tolist(), key="produto_select_fora")
                            with col_preco_chip:
                                produto_row = df_produtos[df_produtos['nome']
                                                          == produto_nome].iloc[0]
                                preco_unit = float(produto_row['preco_atual'])
                                st.markdown(
                                    f'<div class="preco-unitario">💰 Preço unitário: R$ {preco_unit:.2f}</div>', unsafe_allow_html=True)

                            with st.form("form_nova_venda", clear_on_submit=True):
                                col1, col2 = st.columns(2, gap="medium")
                                with col1:
                                    cliente_nome = st.selectbox(
                                        "👤 Cliente *", df_clientes['nome'].tolist(), key="venda_cliente")
                                    cliente_id = int(
                                        df_clientes[df_clientes['nome'] == cliente_nome].iloc[0]['id'])
                                    forma_nome = st.selectbox(
                                        "💳 Forma de Pagamento *", df_formas['nome'].tolist(), key="venda_forma")
                                    forma_id = int(
                                        df_formas[df_formas['nome'] == forma_nome].iloc[0]['id'])
                                with col2:
                                    quantidade = st.number_input(
                                        "🔢 Quantidade *", min_value=1, step=1, value=1, key="venda_qtd")
                                    valor_pago = st.number_input(
                                        "💰 Valor Pago agora (R$)", min_value=0.0, step=0.01, value=0.0, format="%.2f", key="venda_valor_pago")
                                    desconto_unit = st.number_input(
                                        "🎁 Desconto por unidade (R$)", min_value=0.0, step=0.01, value=0.0, format="%.2f", key="venda_desconto_unit")
                                observacoes = st.text_area(
                                    "📝 Observações (opcional)", key="venda_obs", placeholder="Ex: Entrega agendada, troco, etc.")
                                submitted = st.form_submit_button(
                                    "💸 Registrar Venda", type="primary", use_container_width=True)
                            st.markdown('</div>', unsafe_allow_html=True)

                            if submitted:
                                # Cálculo correto com desconto unitário
                                preco_com_desconto = max(
                                    0, preco_unit - desconto_unit)
                                valor_total = quantidade * preco_com_desconto
                                valor_devendo = max(
                                    0, valor_total - valor_pago)

                                produto_row_final = df_produtos[df_produtos['nome']
                                                                == produto_nome].iloc[0]
                                produto_id_final = int(produto_row_final['id'])
                                preco_unit_final = float(
                                    produto_row_final['preco_atual'])

                                st.session_state.venda_dados = {
                                    "cliente_id": cliente_id,
                                    "cliente_nome": cliente_nome,
                                    "produto_id": produto_id_final,
                                    "produto_nome": produto_nome,
                                    "quantidade": quantidade,
                                    "preco_unit": preco_unit_final,
                                    "desconto_unit": desconto_unit,      # guarda desconto unitário
                                    "forma_id": forma_id,
                                    "forma_nome": forma_nome,
                                    "valor_pago": valor_pago,
                                    "valor_total": valor_total,
                                    "valor_devendo": valor_devendo,
                                    "observacoes": observacoes
                                }
                                st.session_state.mostrar_confirmacao = True
                                st.rerun()

                except Exception as e:
                    st.error(f"Erro ao carregar dados: {e}")

           # -------------------- REGISTROS DE VENDAS --------------------
            with vendas_tabs[1]:
                st.markdown("#### 📋 Histórico de Vendas")
                # Filtros
                st.markdown("#### Filtros")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    data_inicio = st.date_input("Data Inicial", value=datetime.now().date() - pd.Timedelta(days=30),
                                                format="DD/MM/YYYY", key="reg_data_inicio")
                with col2:
                    data_fim = st.date_input("Data Final", value=datetime.now().date(),
                                             format="DD/MM/YYYY", key="reg_data_fim")
                with col3:
                    try:
                        df_clientes_reg = pd.read_sql(text("SELECT DISTINCT c.nome FROM vendas v JOIN clientes c ON v.cliente_id = c.id WHERE v.username = :u"),
                                                      engine, params={"u": st.session_state.username})
                        clientes_lista = ["Todos"] + \
                            df_clientes_reg['nome'].tolist()
                    except:
                        clientes_lista = ["Todos"]
                    cliente_filtro = st.selectbox(
                        "Cliente", clientes_lista, key="reg_cliente")
                with col4:
                    status_filtro = st.selectbox(
                        "Status", ["Todas", "Quitadas", "Com Pendência"], key="reg_status")
                busca = st.text_input(
                    "Buscar por nome do cliente ou produto", key="reg_busca")

                st.markdown("#### Resumo do Período")
                try:
                    with engine.connect() as conn:
                        resumo = conn.execute(text("""
                            SELECT COUNT(*), COALESCE(SUM(valor_total),0), COALESCE(SUM(valor_pago),0), COALESCE(SUM(valor_total - valor_pago),0)
                            FROM vendas WHERE username = :u AND data_venda BETWEEN :inicio AND :fim
                        """), {"u": st.session_state.username, "inicio": data_inicio, "fim": data_fim}).fetchone()
                    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                    with col_r1:
                        st.metric("Total de Vendas", resumo[0])
                    with col_r2:
                        st.metric("Valor Total", f"R$ {resumo[1]:,.2f}")
                    with col_r3:
                        st.metric("Valor Recebido", f"R$ {resumo[2]:,.2f}")
                    with col_r4:
                        st.metric("Valor Pendente",
                                  f"R$ {resumo[3]:,.2f}", delta_color="inverse")
                except Exception as e:
                    st.error(f"Erro ao carregar resumo: {e}")

                st.divider()
                st.markdown("#### Histórico de Vendas")
                try:
                    query = """
                        SELECT v.id, v.data_venda, c.nome as cliente, p.nome as produto, v.quantidade,
                               v.valor_total, v.valor_pago, v.produto_id, (v.valor_total - v.valor_pago) as valor_devendo, v.observacoes
                        FROM vendas v
                        JOIN clientes c ON v.cliente_id = c.id
                        JOIN produtos p ON v.produto_id = p.id
                        WHERE v.username = :u AND v.data_venda BETWEEN :inicio AND :fim
                    """
                    params = {"u": st.session_state.username,
                              "inicio": data_inicio, "fim": data_fim}
                    if cliente_filtro != "Todos":
                        query += " AND c.nome = :cliente"
                        params["cliente"] = cliente_filtro
                    if status_filtro == "Quitadas":
                        query += " AND (v.valor_total - v.valor_pago) <= 0"
                    elif status_filtro == "Com Pendência":
                        query += " AND (v.valor_total - v.valor_pago) > 0"
                    if busca:
                        query += " AND (c.nome ILIKE :busca OR p.nome ILIKE :busca)"
                        params["busca"] = f"%{busca}%"
                    query += " ORDER BY v.data_venda DESC"

                    df_vendas = pd.read_sql(text(query), engine, params=params)
                    if df_vendas.empty:
                        st.info("Nenhuma venda encontrada.")
                    else:
                        # Exibição da tabela com gramática melhorada
                        df_display = df_vendas.copy()
                        df_display = df_display.rename(columns={
                            "data_venda": "Data",
                            "cliente": "Cliente",
                            "produto": "Produto",
                            "quantidade": "Quantidade",
                            "valor_total": "Valor Total",
                            "valor_pago": "Valor Pago",
                            "valor_devendo": "Saldo Devedor",
                            "observacoes": "Observações"
                        })

                        # Formatar datas e valores
                        df_display['Data'] = pd.to_datetime(
                            df_display['Data']).dt.strftime('%d/%m/%Y')
                        df_display['Valor Total'] = df_display['Valor Total'].apply(
                            lambda x: f"R$ {x:,.2f}")
                        df_display['Valor Pago'] = df_display['Valor Pago'].apply(
                            lambda x: f"R$ {x:,.2f}")
                        df_display['Saldo Devedor'] = df_display['Saldo Devedor'].apply(
                            lambda x: f"R$ {max(0, x):,.2f}")

                        st.dataframe(
                            df_display[["Data", "Cliente", "Produto", "Quantidade",
                                        "Valor Total", "Valor Pago", "Saldo Devedor"]],
                            width='stretch',
                            hide_index=True,
                            column_config={
                                "Data": st.column_config.TextColumn("📅 Data", width="small"),
                                "Cliente": st.column_config.TextColumn("👤 Cliente", width="medium"),
                                "Produto": st.column_config.TextColumn("📦 Produto", width="medium"),
                                "Quantidade": st.column_config.NumberColumn("🔢 Quantidade", width="small"),
                                "Valor Total": st.column_config.TextColumn("💰 Valor Total", width="small"),
                                "Valor Pago": st.column_config.TextColumn("💵 Valor Pago", width="small"),
                                "Saldo Devedor": st.column_config.TextColumn("⚠️ Saldo Devedor", width="small")
                            }
                        )
                except Exception as e:
                    st.error(f"Erro: {e}")

            # -------------------- FINANCEIRO --------------------
            with vendas_tabs[2]:
                st.markdown("#### 💰 Financeiro - Controle de Pagamentos")
                st.markdown("#### Filtros")
                col_f1, col_f2, col_f3 = st.columns([1.3, 1.3, 2])
                with col_f1:
                    data_inicio = st.date_input("Data Inicial", value=datetime.now().date(
                    )-pd.Timedelta(days=30), format="DD/MM/YYYY", key="fin_data_inicio")
                with col_f2:
                    data_fim = st.date_input("Data Final", value=datetime.now(
                    ).date(), format="DD/MM/YYYY", key="fin_data_fim")
                with col_f3:
                    try:
                        df_cf = pd.read_sql(text("SELECT DISTINCT c.nome FROM vendas v JOIN clientes c ON v.cliente_id=c.id WHERE v.username=:u"), engine, params={
                                            "u": st.session_state.username})
                        clientes_lista = ["Todos"]+df_cf['nome'].tolist()
                    except:
                        clientes_lista = ["Todos"]
                    cliente_filtro = st.selectbox(
                        "Cliente", clientes_lista, key="fin_cliente_filtro")

                st.markdown("#### Resumo de Pendências")
                try:
                    with engine.connect() as conn:
                        resumo = conn.execute(text("""
                            SELECT COUNT(*), COALESCE(SUM(valor_total - valor_pago),0)
                            FROM vendas WHERE username=:u AND (valor_total - valor_pago)>0 AND data_venda BETWEEN :inicio AND :fim
                        """), {"u": st.session_state.username, "inicio": data_inicio, "fim": data_fim}).fetchone()
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        st.metric("Vendas com Pendência", resumo[0])
                    with col_m2:
                        st.metric("Total em Aberto",
                                  f"R$ {resumo[1]:,.2f}", delta_color="inverse")
                except Exception as e:
                    st.error(f"Erro: {e}")

                st.divider()
                st.markdown("#### Todas as Vendas do Período")
                try:
                    query = """
                        SELECT v.id, v.data_venda, c.nome as cliente, p.nome as produto, v.quantidade,
                               v.preco_unitario, v.valor_total, v.valor_pago, (v.valor_total - v.valor_pago) as valor_devendo
                        FROM vendas v
                        JOIN clientes c ON v.cliente_id = c.id
                        JOIN produtos p ON v.produto_id = p.id
                        WHERE v.username = :u AND v.data_venda BETWEEN :inicio AND :fim
                    """
                    params = {"u": st.session_state.username,
                              "inicio": data_inicio, "fim": data_fim}
                    if cliente_filtro != "Todos":
                        query += " AND c.nome = :cliente"
                        params["cliente"] = cliente_filtro
                    query += " ORDER BY v.data_venda DESC"
                    df_vendas = pd.read_sql(text(query), engine, params=params)
                    if df_vendas.empty:
                        st.info("Nenhuma venda no período.")
                    else:
                        df_display = df_vendas.copy()
                        df_display = df_display.rename(columns={
                            "data_venda": "Data",
                            "cliente": "Cliente",
                            "produto": "Produto",
                            "quantidade": "Quantidade",
                            "valor_total": "Valor Total",
                            "valor_pago": "Valor Pago",
                            "valor_devendo": "Saldo Pendente"
                        })
                        df_display['Data'] = pd.to_datetime(
                            df_display['Data']).dt.strftime('%d/%m/%Y')
                        df_display['Valor Total'] = df_display['Valor Total'].apply(
                            lambda x: f"R$ {x:,.2f}")
                        df_display['Valor Pago'] = df_display['Valor Pago'].apply(
                            lambda x: f"R$ {x:,.2f}")
                        df_display['Saldo Pendente'] = df_display['Saldo Pendente'].apply(
                            lambda x: f"R$ {max(0, x):,.2f}")

                        st.dataframe(
                            df_display[["Data", "Cliente", "Produto", "Quantidade",
                                        "Valor Total", "Valor Pago", "Saldo Pendente"]],
                            width='stretch',
                            hide_index=True,
                            column_config={
                                "Data": st.column_config.TextColumn("📅 Data", width="small"),
                                "Cliente": st.column_config.TextColumn("👤 Cliente", width="medium"),
                                "Produto": st.column_config.TextColumn("📦 Produto", width="medium"),
                                "Quantidade": st.column_config.NumberColumn("🔢 Quantidade", width="small"),
                                "Valor Total": st.column_config.TextColumn("💰 Valor Total", width="small"),
                                "Valor Pago": st.column_config.TextColumn("💵 Valor Pago", width="small"),
                                "Saldo Pendente": st.column_config.TextColumn("⚠️ Saldo Pendente", width="small")
                            }
                        )

                        st.markdown("---")
                        st.markdown("**Selecionar Venda para Gerenciar**")

                        def fmt_venda(x):
                            row = df_vendas[df_vendas['id'] == x].iloc[0]
                            data_str = pd.to_datetime(
                                row['data_venda']).strftime('%d/%m/%Y')
                            valor_total = row['valor_total']
                            valor_devendo = max(0, row['valor_devendo'])
                            return f"#{x} | {data_str} | {row['cliente']} | Total: R$ {valor_total:,.2f} | Devendo: R$ {valor_devendo:,.2f}"
                        venda_id = st.selectbox("Escolha uma venda:", options=df_vendas['id'].tolist(
                        ), format_func=fmt_venda, key="fin_select_venda")
                        venda = df_vendas[df_vendas['id'] == venda_id].iloc[0]
                        valor_devendo_atual = max(
                            0, float(venda['valor_devendo']))
                        valor_pago_atual = float(venda['valor_pago'])

                        tab_pag, tab_edit, tab_del = st.tabs(
                            ["💰 Registrar Pagamento", "✏️ Editar Venda", "🗑️ Excluir Venda"])
                        with tab_pag:
                            with st.form("form_receber_pagamento"):
                                valor_recebido = st.number_input(
                                    "Valor Recebido agora (R$)",
                                    min_value=0.0,
                                    max_value=float(valor_devendo_atual),
                                    step=0.01,
                                    format="%.2f",
                                    value=min(50.0, float(valor_devendo_atual))
                                )
                                if st.form_submit_button("Confirmar Recebimento"):
                                    novo_pago = valor_pago_atual + valor_recebido
                                    with engine.connect() as conn:
                                        conn.execute(text("UPDATE vendas SET valor_pago = :novo WHERE id = :id"), {
                                                     "novo": novo_pago, "id": venda_id})
                                        conn.commit()
                                    st.success(
                                        f"Pagamento de R$ {valor_recebido:.2f} registrado!")
                                    st.rerun()
                        with tab_edit:
                            st.warning(
                                "Atenção: Editar a quantidade afetará o estoque. O valor do desconto e observações não alteram o estoque.")
                            with st.form("form_editar_venda"):
                                nova_qtd = st.number_input(
                                    "Quantidade", min_value=1, value=int(venda['quantidade']), step=1)
                                novo_desconto = st.number_input("Desconto (R$)", min_value=0.0, value=float(
                                    venda.get('desconto', 0)), step=0.01, format="%.2f")
                                novas_obs = st.text_area(
                                    "Observações", value=venda.get('observacoes', '') or "")
                                if st.form_submit_button("Salvar Alterações"):
                                    # Calcular diferença na quantidade
                                    quantidade_original = int(
                                        venda['quantidade'])
                                    diferenca = nova_qtd - quantidade_original

                                    # Verificar estoque se for aumentar a quantidade (diferenca > 0)
                                    if diferenca > 0:
                                        if not verificar_estoque(venda['produto_id'], diferenca):
                                            st.error(
                                                f"Estoque insuficiente para aumentar a quantidade em {diferenca}. Disponível? Consulte a aba Estoque.")
                                            st.stop()

                                    # Atualizar a venda
                                    novo_valor_total = (
                                        nova_qtd * float(venda['preco_unitario'])) - novo_desconto
                                    try:
                                        with engine.connect() as conn:
                                            conn.execute(text("""
                                                UPDATE vendas 
                                                SET quantidade = :qtd, desconto = :desc, valor_total = :total, observacoes = :obs 
                                                WHERE id = :id
                                            """), {"qtd": nova_qtd, "desc": novo_desconto, "total": novo_valor_total, "obs": novas_obs, "id": venda_id})
                                            conn.commit()

                                        # Atualizar estoque: subtrair a diferença (se positiva) ou somar (se negativa)
                                        # Ajuste: delta = -diferenca (porque se aumentou a venda, estoque diminui; se diminuiu, estoque aumenta)
                                        atualizar_estoque(
                                            venda['produto_id'], -diferenca)

                                        st.success(
                                            "Venda atualizada e estoque ajustado com sucesso!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao editar venda: {e}")
                        with tab_del:
                            if valor_pago_atual > 0:
                                st.warning(
                                    f"⚠️ Esta venda já possui R$ {valor_pago_atual:,.2f} em pagamentos.")
                            st.markdown(
                                "**Tem certeza que deseja excluir esta venda?**")
                            st.error("Esta ação não pode ser desfeita.")
                            confirm = st.checkbox(
                                "Entendo que é irreversível", key=f"confirm_del_{venda_id}")
                            if st.button("🗑️ Excluir Venda Permanentemente", type="primary", disabled=not confirm):
                                try:
                                    # Obter produto_id e quantidade da venda antes de excluir
                                    with engine.connect() as conn:
                                        venda_dados = conn.execute(text("""
                                            SELECT produto_id, quantidade FROM vendas WHERE id = :id
                                        """), {"id": venda_id}).fetchone()
                                        if venda_dados:
                                            produto_id_excluir = venda_dados[0]
                                            qtd_excluir = venda_dados[1]
                                            # Devolver ao estoque
                                            atualizar_estoque(
                                                produto_id_excluir, qtd_excluir)
                                            # Excluir a venda
                                            conn.execute(text("DELETE FROM vendas WHERE id = :id"), {
                                                         "id": venda_id})
                                            conn.commit()
                                    st.success(
                                        "Venda excluída e estoque restaurado com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir venda: {e}")
                except Exception as e:
                    st.error(f"Erro: {e}")

        # ============================================
        # ABA 1 → ESTOQUE (INCREMENTO DIÁRIO)
        # ============================================
        with fat_tabs[1]:
            st.subheader("📦 Gestão de Estoque")

            # ----- Criar tabela de estoque se não existir -----
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS estoque (
                        id SERIAL PRIMARY KEY,
                        username TEXT NOT NULL,
                        produto_id INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
                        quantidade INTEGER NOT NULL DEFAULT 0,
                        data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(username, produto_id)
                    )
                """))
                conn.commit()

            # ----- Funções auxiliares (banco) -----
            def obter_estoque():
                query = """
                    SELECT p.id, p.nome, p.unidade, p.preco_atual, 
                           COALESCE(e.quantidade, 0) as quantidade
                    FROM produtos p
                    LEFT JOIN estoque e ON p.id = e.produto_id AND e.username = :username
                    WHERE p.username = :username
                    ORDER BY p.nome
                """
                return pd.read_sql(text(query), engine, params={"username": st.session_state.username})

            def incrementar_estoque(produto_id, quantidade_adicionar):
                """Soma quantidade_adicionar ao estoque existente do produto"""
                with engine.connect() as conn:
                    produto_id_int = int(produto_id)
                    # Verifica se já existe registro
                    existe = conn.execute(text("""
                        SELECT 1 FROM estoque WHERE username = :u AND produto_id = :p
                    """), {"u": st.session_state.username, "p": produto_id_int}).fetchone()

                    if existe:
                        # Atualiza somando
                        conn.execute(text("""
                            UPDATE estoque 
                            SET quantidade = quantidade + :qtd, data_atualizacao = CURRENT_TIMESTAMP
                            WHERE username = :u AND produto_id = :p
                        """), {"u": st.session_state.username, "p": produto_id_int, "qtd": quantidade_adicionar})
                    else:
                        # Insere com a quantidade informada
                        conn.execute(text("""
                            INSERT INTO estoque (username, produto_id, quantidade)
                            VALUES (:u, :p, :qtd)
                        """), {"u": st.session_state.username, "p": produto_id_int, "qtd": quantidade_adicionar})
                    conn.commit()

            def definir_estoque(produto_id, quantidade_total):
                """Substitui o estoque pelo valor informado (usado na edição)"""
                with engine.connect() as conn:
                    produto_id_int = int(produto_id)
                    conn.execute(text("""
                        INSERT INTO estoque (username, produto_id, quantidade)
                        VALUES (:u, :p, :qtd)
                        ON CONFLICT (username, produto_id) 
                        DO UPDATE SET quantidade = EXCLUDED.quantidade, data_atualizacao = CURRENT_TIMESTAMP
                    """), {"u": st.session_state.username, "p": produto_id_int, "qtd": quantidade_total})
                    conn.commit()

            def excluir_estoque(produto_id):
                with engine.connect() as conn:
                    conn.execute(text("""
                        DELETE FROM estoque WHERE username = :u AND produto_id = :p
                    """), {"u": st.session_state.username, "p": int(produto_id)})
                    conn.commit()

            # ----- Formulário para ADICIONAR ao estoque (incremento) -----
            with st.expander("➕ Adicionar Quantidade ao Estoque (Registro Diário)", expanded=True):
                st.markdown(
                    "Informe a **quantidade produzida/comercializada HOJE** para somar ao estoque.")

                df_produtos_estoque = pd.read_sql(
                    text(
                        "SELECT id, nome, preco_atual FROM produtos WHERE username = :u ORDER BY nome"),
                    engine, params={"u": st.session_state.username}
                )

                if df_produtos_estoque.empty:
                    st.warning(
                        "⚠️ Nenhum produto cadastrado. Cadastre produtos na aba 'Cadastros' primeiro.")
                else:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        produto_selecionado = st.selectbox(
                            "📦 Produto",
                            df_produtos_estoque['nome'].tolist(),
                            key="estoque_produto_add"
                        )
                        produto_id = df_produtos_estoque[df_produtos_estoque['nome']
                                                         == produto_selecionado].iloc[0]['id']

                    with col2:
                        quantidade_hoje = st.number_input(
                            "➕ Quantidade a adicionar (hoje)",
                            min_value=1, step=1, value=1,
                            key="estoque_qtd_add"
                        )

                    if st.button("➕ Adicionar ao Estoque", type="primary", use_container_width=True):
                        if quantidade_hoje > 0:
                            incrementar_estoque(produto_id, quantidade_hoje)
                            st.success(
                                f"✅ {quantidade_hoje} unidade(s) de '{produto_selecionado}' adicionadas ao estoque.")
                            st.rerun()
                        else:
                            st.error("A quantidade deve ser maior que zero.")

            st.divider()

            # ----- Visualização do Estoque Atual (total acumulado) -----
            st.markdown("### 📋 Estoque Atual (Total Acumulado)")
            df_estoque = obter_estoque()

            if df_estoque.empty:
                st.info(
                    "Nenhum produto cadastrado. Cadastre produtos na aba 'Cadastros'.")
            else:
                # Calcular valor total do estoque
                df_estoque['valor_total'] = df_estoque['quantidade'] * \
                    df_estoque['preco_atual']
                total_produtos = df_estoque['quantidade'].sum()
                valor_total_estoque = df_estoque['valor_total'].sum()

                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.metric("📦 Total de Unidades em Estoque",
                              f"{total_produtos:,}")
                with col_res2:
                    st.metric("💰 Valor Total do Estoque",
                              f"R$ {valor_total_estoque:,.2f}")

                st.divider()

                # Tabela de estoque
                st.markdown("**Produtos em Estoque**")
                df_display = df_estoque.copy()
                df_display = df_display.rename(columns={
                    "nome": "Produto",
                    "unidade": "Unidade",
                    "preco_atual": "Preço Unitário",
                    "quantidade": "Quantidade Total",
                    "valor_total": "Valor Total"
                })
                df_display["Preço Unitário"] = df_display["Preço Unitário"].apply(
                    lambda x: f"R$ {x:.2f}")
                df_display["Valor Total"] = df_display["Valor Total"].apply(
                    lambda x: f"R$ {x:,.2f}")

                st.dataframe(
                    df_display[["Produto", "Unidade", "Preço Unitário",
                                "Quantidade Total", "Valor Total"]],
                    width='stretch',
                    hide_index=True
                )

                st.divider()

                # ----- Editar ou Excluir Estoque (correção manual) -----
                st.markdown("### ✏️ Editar ou 🗑️ Excluir Estoque")
                st.caption(
                    "Caso tenha registrado um valor incorreto, você pode **substituir a quantidade total** ou remover o produto do estoque.")

                produtos_com_estoque = df_estoque[df_estoque['quantidade'] > 0]['nome'].tolist(
                )
                if not produtos_com_estoque:
                    st.info(
                        "Nenhum produto com estoque positivo. Adicione estoque para algum produto primeiro.")
                else:
                    produto_editar = st.selectbox(
                        "Selecione o produto",
                        produtos_com_estoque,
                        key="estoque_editar_produto"
                    )

                    linha = df_estoque[df_estoque['nome']
                                       == produto_editar].iloc[0]
                    produto_id_edit = int(linha['id'])  # já converte
                    qtd_atual_edit = int(linha['quantidade'])

                    col_edit1, col_edit2, col_edit3 = st.columns([2, 1, 1])
                    with col_edit1:
                        nova_qtd_total = st.number_input(
                            "Nova quantidade total (substitui o valor atual)",
                            min_value=0,
                            step=1,
                            value=qtd_atual_edit,
                            key="estoque_nova_qtd"
                        )
                    with col_edit2:
                        if st.button("✅ Substituir", use_container_width=True, key="btn_atualizar_estoque"):
                            definir_estoque(produto_id_edit, nova_qtd_total)
                            st.success(
                                f"Estoque do produto '{produto_editar}' atualizado para {nova_qtd_total} unidades.")
                            st.rerun()
                    with col_edit3:
                        with st.popover("🗑️ Excluir", use_container_width=True):
                            st.warning(
                                f"Tem certeza que deseja remover o produto '{produto_editar}' do estoque?")
                            st.caption(
                                "Isso não exclui o produto cadastrado, apenas remove sua contagem do estoque.")
                            if st.button("Sim, excluir permanentemente", type="primary", key="btn_excluir_estoque"):
                                excluir_estoque(produto_id_edit)
                                st.success(
                                    f"Registro de estoque para '{produto_editar}' removido.")
                                st.rerun()
        # ============================================
        # ABA 2 → CADASTROS
        # ============================================
        with fat_tabs[2]:
            st.subheader("📝 Cadastros")
            cadastros_tabs = st.tabs(
                ["👥 Clientes", "📦 Produtos & Preços", "💳 Formas de Pagamento"])

            # --- CLIENTES ---
            with cadastros_tabs[0]:
                st.markdown("#### 👥 Gestão de Clientes")
                with st.expander("➕ Cadastrar Novo Cliente", expanded=False):
                    with st.form("form_novo_cliente", clear_on_submit=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            nome = st.text_input(
                                "Nome / Razão Social *", key="cli_nome_novo")
                            cpf_cnpj = st.text_input(
                                "CPF ou CNPJ", key="cli_cpf_novo")
                            telefone = st.text_input(
                                "Telefone / WhatsApp", key="cli_tel_novo")
                        with col2:
                            email = st.text_input(
                                "E-mail", key="cli_email_novo")
                            endereco = st.text_area(
                                "Endereço", key="cli_end_novo")
                        if st.form_submit_button("Cadastrar Cliente"):
                            if nome:
                                try:
                                    with engine.connect() as conn:
                                        conn.execute(text("""
                                            INSERT INTO clientes (username, nome, cpf_cnpj, telefone, email, endereco)
                                            VALUES (:u, :nome, :cpf, :tel, :email, :end)
                                        """), {"u": st.session_state.username, "nome": nome, "cpf": cpf_cnpj or None,
                                               "tel": telefone or None, "email": email or None, "end": endereco or None})
                                        conn.commit()
                                    st.success("✅ Cliente cadastrado!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro: {e}")
                            else:
                                st.error("Nome é obrigatório.")
                st.markdown("**Clientes Cadastrados**")
                try:
                    df_cli = pd.read_sql(text("SELECT id, nome, cpf_cnpj, telefone, email, endereco FROM clientes WHERE username = :u ORDER BY data_cadastro DESC"),
                                         engine, params={"u": st.session_state.username})
                    if df_cli.empty:
                        st.info("Nenhum cliente cadastrado.")
                    else:
                        st.dataframe(df_cli[['nome', 'cpf_cnpj', 'telefone', 'email', 'endereco']].rename(
                            columns={'nome': 'Nome', 'cpf_cnpj': 'CPF/CNPJ'}), width='stretch', hide_index=True)
                        cliente_nome = st.selectbox(
                            "Selecione um cliente para editar/excluir:", df_cli['nome'].tolist(), key="sel_cliente")
                        cliente = df_cli[df_cli['nome'] ==
                                         cliente_nome].iloc[0].to_dict()
                        with st.expander("✏️ Editar Cliente"):
                            with st.form("form_editar_cliente"):
                                n_nome = st.text_input(
                                    "Nome", value=cliente['nome'])
                                n_cpf = st.text_input(
                                    "CPF/CNPJ", value=cliente.get('cpf_cnpj', ''))
                                n_tel = st.text_input(
                                    "Telefone", value=cliente.get('telefone', ''))
                                n_email = st.text_input(
                                    "Email", value=cliente.get('email', ''))
                                n_end = st.text_area(
                                    "Endereço", value=cliente.get('endereco', ''))
                                if st.form_submit_button("Salvar Alterações"):
                                    with engine.connect() as conn:
                                        conn.execute(text("UPDATE clientes SET nome=:nome, cpf_cnpj=:cpf, telefone=:tel, email=:email, endereco=:end WHERE id=:id"),
                                                     {"nome": n_nome, "cpf": n_cpf or None, "tel": n_tel or None, "email": n_email or None, "end": n_end or None, "id": cliente['id']})
                                        conn.commit()
                                    st.success("Cliente atualizado!")
                                    st.rerun()
                        with st.expander("🗑️ Excluir Cliente"):
                            st.warning("⚠️ Esta ação não pode ser desfeita!")
                            if st.button("Excluir Cliente", type="primary"):
                                with engine.connect() as conn:
                                    conn.execute(text("DELETE FROM clientes WHERE id = :id"), {
                                                 "id": cliente['id']})
                                    conn.commit()
                                st.success("Cliente excluído!")
                                st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

                    # --- PRODUTOS & PREÇOS (COM EDIÇÃO E EXCLUSÃO) ---
            with cadastros_tabs[1]:
                st.markdown("#### 📦 Produtos & Preços")

                # Expansor para cadastrar novo produto
                with st.expander("➕ Cadastrar Novo Produto", expanded=False):
                    with st.form("form_novo_produto", clear_on_submit=True):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            nome_prod = st.text_input(
                                "Nome do Produto *", key="prod_nome_novo")
                            descricao = st.text_area(
                                "Descrição", key="prod_desc_novo")
                        with col2:
                            unidade = st.text_input(
                                "Unidade de Medida", value="unidade", key="prod_un_novo")
                            preco = st.number_input(
                                "Preço Atual (R$)", min_value=0.0, step=0.01, format="%.2f", key="prod_preco_novo")
                        if st.form_submit_button("Cadastrar Produto"):
                            if nome_prod:
                                try:
                                    with engine.connect() as conn:
                                        conn.execute(text("""
                                            INSERT INTO produtos (username, nome, descricao, unidade, preco_atual)
                                            VALUES (:u, :nome, :desc, :un, :preco)
                                        """), {"u": st.session_state.username, "nome": nome_prod,
                                               "desc": descricao or None, "un": unidade, "preco": preco})
                                        conn.commit()
                                    st.success(
                                        "✅ Produto cadastrado com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao cadastrar: {e}")
                            else:
                                st.error("Nome do produto é obrigatório.")

                st.divider()

                # Listagem de produtos cadastrados
                st.markdown("**Produtos Cadastrados**")
                try:
                    df_produtos_lista = pd.read_sql(text("""
                        SELECT id, nome, descricao, unidade, preco_atual 
                        FROM produtos 
                        WHERE username = :u 
                        ORDER BY data_cadastro DESC
                    """), engine, params={"u": st.session_state.username})

                    if df_produtos_lista.empty:
                        st.info("Nenhum produto cadastrado ainda.")
                    else:
                        # Tabela de produtos
                        df_display = df_produtos_lista.copy()
                        df_display['preco_atual'] = df_display['preco_atual'].apply(
                            lambda x: f"R$ {x:.2f}")
                        st.dataframe(
                            df_display[['nome', 'unidade', 'preco_atual']].rename(
                                columns={
                                    'nome': 'Produto', 'unidade': 'Unidade', 'preco_atual': 'Preço Atual'}
                            ),
                            width='stretch',
                            hide_index=True
                        )

                        st.divider()
                        st.markdown("### ✏️ Editar ou 🗑️ Excluir Produto")
                        st.caption(
                            "Selecione um produto abaixo para editar seus dados ou excluí-lo permanentemente.")

                        # Select para escolher o produto
                        produto_selecionado = st.selectbox(
                            "Selecione o produto",
                            df_produtos_lista['nome'].tolist(),
                            key="select_produto_edit"
                        )
                        produto_row = df_produtos_lista[df_produtos_lista['nome']
                                                        == produto_selecionado].iloc[0]
                        produto_id = int(produto_row['id'])

                        col_edit, col_del = st.columns(2)

                        # --- Editar produto ---
                        with col_edit:
                            with st.expander("✏️ Editar Produto", expanded=False):
                                with st.form("form_editar_produto"):
                                    novo_nome = st.text_input(
                                        "Nome do Produto", value=produto_row['nome'], key="edit_prod_nome")
                                    nova_desc = st.text_area("Descrição", value=produto_row.get(
                                        'descricao', '') or '', key="edit_prod_desc")
                                    nova_unidade = st.text_input(
                                        "Unidade de Medida", value=produto_row['unidade'], key="edit_prod_un")
                                    novo_preco = st.number_input("Preço (R$)", value=float(
                                        produto_row['preco_atual']), step=0.01, format="%.2f", key="edit_prod_preco")

                                    if st.form_submit_button("✅ Salvar Alterações"):
                                        if novo_nome:
                                            try:
                                                with engine.connect() as conn:
                                                    conn.execute(text("""
                                                        UPDATE produtos 
                                                        SET nome = :nome, descricao = :desc, unidade = :un, preco_atual = :preco
                                                        WHERE id = :id AND username = :u
                                                    """), {
                                                        "nome": novo_nome,
                                                        "desc": nova_desc or None,
                                                        "un": nova_unidade,
                                                        "preco": novo_preco,
                                                        "id": produto_id,
                                                        "u": st.session_state.username
                                                    })
                                                    conn.commit()
                                                st.success(
                                                    "✅ Produto atualizado com sucesso!")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(
                                                    f"Erro ao atualizar: {e}")
                                        else:
                                            st.error(
                                                "O nome do produto é obrigatório.")

                        # --- Excluir produto ---
                        with col_del:
                            with st.expander("🗑️ Excluir Produto", expanded=False):
                                st.warning(
                                    f"⚠️ Tem certeza que deseja excluir o produto **'{produto_selecionado}'**?")
                                st.caption(
                                    "Esta ação **não pode ser desfeita** e também afetará:\n- Registros de vendas (tornará o produto inválido)\n- Registros de estoque (serão removidos)")

                                confirm_excluir = st.checkbox(
                                    "Sim, entendo que esta ação é irreversível", key="confirm_excluir_produto")
                                if st.button("🗑️ Excluir Permanentemente", type="primary", disabled=not confirm_excluir):
                                    try:
                                        with engine.connect() as conn:
                                            # Inicia transação para garantir consistência
                                            with conn.begin():
                                                # Remove registros de estoque relacionados
                                                conn.execute(text("DELETE FROM estoque WHERE username = :u AND produto_id = :p"),
                                                             {"u": st.session_state.username, "p": produto_id})
                                                # Remove o produto (cascade para vendas se configurado, senão pode dar erro)
                                                # Se a tabela vendas tiver ON DELETE RESTRICT, será impedido.
                                                # Tentamos excluir o produto; se houver vendas, o banco pode barrar.
                                                conn.execute(text("DELETE FROM produtos WHERE id = :id AND username = :u"),
                                                             {"id": produto_id, "u": st.session_state.username})
                                        st.success(
                                            f"✅ Produto '{produto_selecionado}' e seus registros de estoque foram removidos.")
                                        st.rerun()
                                    except Exception as e:
                                        if "foreign key constraint" in str(e).lower():
                                            st.error(
                                                "❌ Não é possível excluir o produto porque existem vendas associadas a ele. Primeiro exclua as vendas ou cancele essa operação.")
                                        else:
                                            st.error(f"Erro ao excluir: {e}")

                except Exception as e:
                    st.error(f"Erro ao carregar produtos: {e}")

            # --- FORMAS DE PAGAMENTO ---
            with cadastros_tabs[2]:
                st.markdown("#### 💳 Formas de Pagamento Aceitas")
                with st.expander("➕ Adicionar Nova Forma de Pagamento", expanded=False):
                    with st.form("form_nova_forma", clear_on_submit=True):
                        nome_forma = st.text_input(
                            "Nome da Forma de Pagamento *", key="forma_nome_novo")
                        if st.form_submit_button("Adicionar"):
                            if nome_forma:
                                with engine.connect() as conn:
                                    conn.execute(text("INSERT INTO formas_pagamento (username, nome, ativo) VALUES (:u, :nome, TRUE)"),
                                                 {"u": st.session_state.username, "nome": nome_forma})
                                    conn.commit()
                                st.success("Forma de pagamento adicionada!")
                                st.rerun()
                st.markdown("**Formas de Pagamento Cadastradas**")
                try:
                    df_fp = pd.read_sql(text("SELECT id, nome, ativo, username FROM formas_pagamento WHERE username = :u OR username IS NULL ORDER BY nome"),
                                        engine, params={"u": st.session_state.username})
                    if df_fp.empty:
                        st.info("Nenhuma forma de pagamento.")
                    else:
                        for _, row in df_fp.iterrows():
                            col1, col2, col3 = st.columns([3, 1.5, 1])
                            with col1:
                                st.write(
                                    f"**{row['nome']}**" + (" (Padrão)" if row['username'] is None else ""))
                            with col2:
                                if row['username'] is not None:
                                    ativo = st.checkbox("Ativa", value=bool(
                                        row['ativo']), key=f"fp_ativa_{row['id']}")
                            with col3:
                                if row['username'] is not None:
                                    if st.button("Salvar", key=f"fp_salvar_{row['id']}"):
                                        with engine.connect() as conn:
                                            conn.execute(text("UPDATE formas_pagamento SET ativo = :ativo WHERE id = :id"), {
                                                         "ativo": ativo, "id": row['id']})
                                            conn.commit()
                                        st.success("Atualizado!")
                                        st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURAÇÃO DE ÍCONE PERSONALIZADO ---
URL_ICONE = "https://preview.redd.it/d7ajx3csqpzg1.jpeg?width=640&crop=smart&auto=webp&s=52f986fe2c31fe8b67d7502f4b1a02f9646cba1d"

# 1. Função de Estilo Avançada (CSS Responsivo e Persistente)
def aplicar_estilo_customizado():
    st.markdown(f"""
    <style>
    /* Configurações Gerais - Removendo cores de fundo de todas as camadas */
    .stApp, .stMain, .stHeader, .stAppHeader, .block-container {{
        background-color: transparent !important;
        color: black !important;
    }}

    /* Forçando o fundo do body para branco para que a transparência funcione sobre ele */
    body {{
        background-color: white !important;
    }}

    /* Container de Fundo Persistente */
    .main-bg-container {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        display: flex !important;
        justify-content: center;
        align-items: center;
        z-index: -2 !important;
        pointer-events: none;
        overflow: hidden;
    }}

    .egg-icon-bg-persistent {{
        width: 85vw;
        max-width: 650px;
        opacity: 0.15 !important;
        filter: grayscale(10%);
    }}

    /* Ajustes de Layout */
    .block-container {{
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 1000px !important;
    }}

    h1, h2, h3, p, span, label, .stMarkdown {{
        color: #000000 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }}

    h1 {{ font-size: calc(1.6rem + 1vw) !important; text-align: center; margin-bottom: 0.5rem; }}

    .sub-texto {{
        text-align: center;
        margin-bottom: 2rem;
        font-size: 1.1rem;
        opacity: 0.7;
    }}

    /* Botões Modernos */
    div.stButton > button {{
        background-color: #5CE65C !important;
        color: white !important;
        border-radius: 15px !important;
        font-weight: bold !important;
        width: 100% !important;
        padding: 0.6rem !important;
        border: none !important;
        transition: 0.3s transform ease;
    }}

    div.stButton > button:hover {{ transform: scale(1.03); opacity: 0.95; }}

    /* Inputs com fundo semi-transparente para não sumirem no branco */
    .stTextInput, .stNumberInput, .stDateInput, .stSelectbox {{
        background-color: rgba(255, 255, 255, 0.9) !important;
        border-radius: 12px;
        border: 1px solid #ddd !important;
    }}

    /* Métrica cards */
    .metric-card {{
        background: linear-gradient(135deg, #5CE65C 0%, #3db82e 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin: 10px 0;
    }}

    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    </style>

    <div class="main-bg-container">
        <img src="{URL_ICONE}" class="egg-icon-bg-persistent">
    </div>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Estoque Ovos Pro", layout="wide")
aplicar_estilo_customizado()

# --- INICIALIZAÇÃO DO BANCO DE DADOS COM MIGRAÇÃO ---
def init_db():
    conn = sqlite3.connect('estoque_ovos.db')
    c = conn.cursor()
    
    # Tabela de usuários
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT UNIQUE, password TEXT)')
    
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
    st.markdown("<p class='sub-texto'>Sua produção organizada de forma profissional</p>", unsafe_allow_html=True)
    
    user = st.text_input("Nome de Usuário", placeholder="Digite seu usuário")
    pw = st.text_input("Senha", type="password", placeholder="Digite sua senha")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Entrar", use_container_width=True):
            if user and pw:
                conn = sqlite3.connect('estoque_ovos.db')
                c = conn.cursor()
                c.execute("SELECT password FROM usuarios WHERE username = ?", (user,))
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
    st.markdown(f"<p class='sub-texto'>Bem-vindo, <b>{st.session_state.username}</b></p>", unsafe_allow_html=True)
    
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
            data_reg = st.date_input("📅 Data da Colheita", value=datetime.now().date(), format="DD/MM/YYYY", key="data_colheita")
            qtd_val = st.number_input("🥚 Quantidade de Ovos", min_value=0, step=1, format="%d", key="qtd_colheita")
        
        with col2:
            tipo_ovo = st.selectbox("🏷️ Tipo de Ovo", TIPOS_OVO, key="tipo_ovo")
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
                st.success(f"✅ {qtd_val} ovos ({tipo_ovo}, {cor}) do {galpao} registrados com sucesso!")
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
            df_edit['data_fmt'] = pd.to_datetime(df_edit['data']).dt.strftime('%d/%m/%Y')
            
            opcoes = {
                row['rowid']: f"📅 {row['data_fmt']} | {row['quantidade']} ovos | {row['tipo']} | {row['cor']} | {row['galpao']}"
                for _, row in df_edit.iterrows()
            }
            
            selecao = st.selectbox("Escolha um registro para corrigir:", list(opcoes.values()))
            rid = [k for k, v in opcoes.items() if v == selecao][0]
            
            registro = df_edit[df_edit['rowid'] == rid].iloc[0]
            
            col1, col2 = st.columns(2)
            with col1:
                novo_val = st.number_input("Corrigir quantidade:", min_value=0, step=1, value=int(registro['quantidade']))
                novo_tipo = st.selectbox("Corrigir tipo:", TIPOS_OVO, index=TIPOS_OVO.index(registro['tipo']))
            
            with col2:
                novo_galpao = st.selectbox("Corrigir galpão:", GALPOES, index=GALPOES.index(registro['galpao']))
                nova_cor = st.selectbox("Corrigir cor:", CORES, index=CORES.index(registro['cor']))
            
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
        
        if not df_producao.empty:
            # Total geral
            total_geral = df_producao['quantidade'].sum()
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🥚 Total de Ovos", f"{total_geral:,}")
            with col2:
                st.metric("📅 Registros", len(df_producao))
            with col3:
                st.metric("📊 Média por Registro", f"{total_geral / len(df_producao):.0f}")
            
            st.divider()
            
            # Total por galpão
            st.markdown("#### 🏠 Ovos por Galpão")
            galpao_totais = df_producao.groupby('galpao')['quantidade'].sum().sort_values(ascending=False)
            col_g1, col_g2 = st.columns(len(galpao_totais))
            for idx, (galpao, total) in enumerate(galpao_totais.items()):
                with st.columns(len(galpao_totais))[idx]:
                    st.metric(galpao, f"{total:,} ovos")
            
            st.divider()
            
            # Total por tipo
            st.markdown("#### 🏷️ Ovos por Tipo")
            tipo_totais = df_producao.groupby('tipo')['quantidade'].sum().sort_values(ascending=False)
            cols_tipo = st.columns(len(tipo_totais))
            for idx, (tipo, total) in enumerate(tipo_totais.items()):
                with cols_tipo[idx]:
                    st.metric(tipo, f"{total:,} ovos")
            
            st.divider()
            
            # Total por cor
            st.markdown("#### 🎨 Ovos por Cor")
            cor_totais = df_producao.groupby('cor')['quantidade'].sum().sort_values(ascending=False)
            cols_cor = st.columns(len(cor_totais))
            for idx, (cor, total) in enumerate(cor_totais.items()):
                with cols_cor[idx]:
                    st.metric(cor, f"{total:,} ovos")
            
            st.divider()
            
            # Tabela detalhada
            st.markdown("#### 📋 Detalhes por Galpão e Tipo")
            
            for galpao in sorted(df_producao['galpao'].unique()):
                st.markdown(f"**{galpao}**")
                
                df_galpao = df_producao[df_producao['galpao'] == galpao]
                
                # Por tipo
                tipo_cols = st.columns(len(TIPOS_OVO))
                for idx, tipo in enumerate(TIPOS_OVO):
                    with tipo_cols[idx]:
                        total_tipo = df_galpao[df_galpao['tipo'] == tipo]['quantidade'].sum()
                        st.info(f"**{tipo}**: {total_tipo} ovos")
                
                # Por cor
                cor_cols = st.columns(len(CORES))
                for idx, cor in enumerate(CORES):
                    with cor_cols[idx]:
                        total_cor = df_galpao[df_galpao['cor'] == cor]['quantidade'].sum()
                        st.warning(f"**{cor}**: {total_cor} ovos")
                
                st.divider()
        else:
            st.info("📭 Nenhum registro de colheita encontrado.")

    # ======================== ABA 4: REGISTRAR AVES ========================
    with tabs[3]:
        st.markdown("### 🐔 Gerenciamento de Aves")
        
        tab_reg_aves, tab_mortas = st.tabs(["➕ Registrar Aves", "⚠️ Aves Mortas"])
        
        # Subaba: Registrar Aves
        with tab_reg_aves:
            st.markdown("#### ➕ Adicionar Novas Aves")
            
            col1, col2 = st.columns(2)
            with col1:
                data_aves = st.date_input("📅 Data", value=datetime.now().date(), format="DD/MM/YYYY", key="data_aves")
                galpao_aves = st.selectbox("🏠 Galpão", GALPOES, key="galpao_aves_reg")
            
            with col2:
                qtd_aves = st.number_input("🐔 Quantidade de Aves", min_value=1, step=1, format="%d", key="qtd_aves")
            
            if st.button("✅ Registrar Aves", use_container_width=True):
                conn = sqlite3.connect('estoque_ovos.db')
                c = conn.cursor()
                c.execute(
                    "INSERT INTO aves (username, galpao, quantidade_total, data_registro) VALUES (?, ?, ?, ?)",
                    (st.session_state.username, galpao_aves, qtd_aves, data_aves)
                )
                conn.commit()
                conn.close()
                st.success(f"✅ {qtd_aves} aves registradas no {galpao_aves}!")
                st.rerun()
        
        # Subaba: Aves Mortas
        with tab_mortas:
            st.markdown("#### ⚠️ Registrar Aves Mortas")
            
            col1, col2 = st.columns(2)
            with col1:
                data_morta = st.date_input("📅 Data", value=datetime.now().date(), format="DD/MM/YYYY", key="data_morta")
                galpao_morta = st.selectbox("🏠 Galpão", GALPOES, key="galpao_aves_morta")
            
            with col2:
                qtd_morta = st.number_input("🪦 Quantidade de Aves Mortas", min_value=1, step=1, format="%d", key="qtd_morta")
            
            if st.button("✅ Registrar Morte", use_container_width=True):
                conn = sqlite3.connect('estoque_ovos.db')
                c = conn.cursor()
                c.execute(
                    "INSERT INTO aves_mortas (username, galpao, quantidade, data) VALUES (?, ?, ?, ?)",
                    (st.session_state.username, galpao_morta, qtd_morta, data_morta)
                )
                conn.commit()
                conn.close()
                st.success(f"✅ {qtd_morta} aves mortas registradas no {galpao_morta}.")
                st.rerun()
        
        st.divider()
        
        # Resumo de aves por galpão
        st.markdown("#### 📊 Resumo de Aves por Galpão")
        
        for galpao in GALPOES:
            col1, col2, col3 = st.columns(3)
            
            # Total registrado
            conn = sqlite3.connect('estoque_ovos.db')
            c = conn.cursor()
            c.execute("SELECT COALESCE(SUM(quantidade_total), 0) FROM aves WHERE username=? AND galpao=?",
                     (st.session_state.username, galpao))
            total_reg = c.fetchone()[0]
            
            # Total morto
            c.execute("SELECT COALESCE(SUM(quantidade), 0) FROM aves_mortas WHERE username=? AND galpao=?",
                     (st.session_state.username, galpao))
            total_morto = c.fetchone()[0]
            conn.close()
            
            total_vivo = max(0, total_reg - total_morto)
            
            with col1:
                st.metric(f"{galpao} - Registradas", f"{total_reg} aves")
            with col2:
                st.metric(f"{galpao} - Mortas", f"{total_morto} aves")
            with col3:
                st.metric(f"{galpao} - Vivas", f"{total_vivo} aves", delta=None)

    # ======================== ABA 5: GRÁFICOS ========================
    with tabs[4]:
        st.markdown("### 📈 Gráficos e Análises")
        
        conn = sqlite3.connect('estoque_ovos.db')
        df_graficos = pd.read_sql(
            "SELECT data, quantidade, tipo, galpao, cor FROM producao WHERE username=? ORDER BY data",
            conn,
            params=(st.session_state.username,)
        )
        conn.close()
        
        if not df_graficos.empty:
            df_graficos['data'] = pd.to_datetime(df_graficos['data'])
            
            # Gráfico 1: Evolução temporal
            st.markdown("#### 📉 Evolução Temporal de Produção")
            df_tempo = df_graficos.groupby('data')['quantidade'].sum().reset_index()
            fig_tempo = px.line(
                df_tempo,
                x='data',
                y='quantidade',
                markers=True,
                labels={'data': 'Data', 'quantidade': 'Quantidade de Ovos'},
                title="Produção ao Longo do Tempo"
            )
            fig_tempo.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color="black", size=12),
                hovermode='x unified'
            )
            st.plotly_chart(fig_tempo, use_container_width=True)
            
            # Gráfico 2: Produção por galpão
            st.markdown("#### 🏠 Produção por Galpão")
            df_galpao = df_graficos.groupby('galpao')['quantidade'].sum().reset_index()
            fig_galpao = px.bar(
                df_galpao,
                x='galpao',
                y='quantidade',
                color='galpao',
                labels={'galpao': 'Galpão', 'quantidade': 'Total de Ovos'},
                title="Total de Ovos por Galpão"
            )
            fig_galpao.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color="black", size=12),
                showlegend=False
            )
            st.plotly_chart(fig_galpao, use_container_width=True)
            
            # Gráfico 3: Tipo de ovo
            st.markdown("#### 🏷️ Distribuição por Tipo")
            df_tipo = df_graficos.groupby('tipo')['quantidade'].sum().reset_index()
            fig_tipo = px.pie(
                df_tipo,
                names='tipo',
                values='quantidade',
                title="Ovos por Tipo"
            )
            fig_tipo.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color="black", size=12)
            )
            st.plotly_chart(fig_tipo, use_container_width=True)
            
            # Gráfico 4: Cor de ovo
            st.markdown("#### 🎨 Distribuição por Cor")
            df_cor = df_graficos.groupby('cor')['quantidade'].sum().reset_index()
            fig_cor = px.pie(
                df_cor,
                names='cor',
                values='quantidade',
                title="Ovos por Cor"
            )
            fig_cor.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color="black", size=12)
            )
            st.plotly_chart(fig_cor, use_container_width=True)
            
            # Gráfico 5: Heatmap Galpão x Tipo
            st.markdown("#### 🔥 Heatmap: Galpão vs Tipo")
            df_heatmap = df_graficos.groupby(['galpao', 'tipo'])['quantidade'].sum().reset_index()
            df_pivot = df_heatmap.pivot(index='galpao', columns='tipo', values='quantidade').fillna(0)
            
            fig_heat = px.imshow(
                df_pivot,
                labels=dict(x='Tipo', y='Galpão', color='Quantidade'),
                title="Produção por Galpão e Tipo",
                color_continuous_scale='Greens'
            )
            fig_heat.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color="black", size=12)
            )
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.info("📭 Nenhum dado disponível para gráficos.")

    # ======================== ABA 6: OVOS QUEBRADOS ========================
    with tabs[5]:
        st.markdown("### 🔨 Gerenciamento de Ovos Quebrados")
        
        # Formulário de registro
        st.markdown("#### 🔨 Registrar Ovos Quebrados")
        
        col1, col2 = st.columns(2)
        with col1:
            data_quebrados = st.date_input("📅 Data", value=datetime.now().date(), format="DD/MM/YYYY", key="data_quebrados")
            galpao_quebrados = st.selectbox("🏠 Galpão", GALPOES, key="galpao_quebrados")
        
        with col2:
            qtd_quebrados = st.number_input("🔨 Quantidade de Ovos Quebrados", min_value=1, step=1, format="%d", key="qtd_quebrados")
        
        if st.button("✅ Registrar Quebrados", use_container_width=True):
            conn = sqlite3.connect('estoque_ovos.db')
            c = conn.cursor()
            c.execute(
                "INSERT INTO ovos_quebrados (username, galpao, quantidade, data) VALUES (?, ?, ?, ?)",
                (st.session_state.username, galpao_quebrados, qtd_quebrados, data_quebrados)
            )
            conn.commit()
            conn.close()
            st.success(f"✅ {qtd_quebrados} ovos quebrados registrados no {galpao_quebrados}!")
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
            df_quebrados['data'] = pd.to_datetime(df_quebrados['data']).dt.strftime('%d/%m/%Y')
            st.dataframe(df_quebrados.rename(columns={'data': 'Data', 'galpao': 'Galpão', 'quantidade': 'Quantidade'}), use_container_width=True, hide_index=True)
        else:
            st.info("📭 Nenhum registro de ovos quebrados.")

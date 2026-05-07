import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURAÇÃO DE ÍCONE PERSONALIZADO ---
URL_ICONE = "https://preview.redd.it/d7ajx3csqpzg1.jpeg?width=640&crop=smart&auto=webp&s=52f986fe2c31fe8b67d7502f4b1a02f9646cba1d"

# 1. Função de Estilo Avançada (CSS Responsivo e Persistente)
def aplicar_estilo_customizado():
    st.markdown(f"""
    <style>
    /* Configurações Gerais */
    .stApp {{ 
        background-color: white; 
        color: black; 
    }}

    /* Container de Fundo Persistente (Aparece em todas as telas) */
    .main-bg-container {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: -1;
        pointer-events: none;
        overflow: hidden;
    }}

    .egg-icon-bg-persistent {{
        width: 80vw;
        max-width: 600px;
        opacity: 0.10;
        filter: grayscale(10%);
    }}

    /* Ajustes de Layout Responsivo */
    .block-container {{
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 800px !important;
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

    /* Botões Modernos e Responsivos */
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

    /* Estilização de Cards e Inputs */
    .stTextInput, .stNumberInput, .stDateInput, .stSelectbox {{
        background-color: rgba(255, 255, 255, 0.8);
        border-radius: 12px;
    }}

    /* Esconder Menu Streamlit */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    </style>

    <div class="main-bg-container">
        <img src="{URL_ICONE}" class="egg-icon-bg-persistent">
    </div>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Estoque Ovos Pro", layout="centered")
aplicar_estilo_customizado()

def init_db():
    conn = sqlite3.connect('estoque_ovos.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT UNIQUE, password TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS producao (username TEXT, data DATE, quantidade INTEGER)')
    conn.commit()
    conn.close()

init_db()

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'username' not in st.session_state: st.session_state.username = ""

# --- TELA DE LOGIN ---
if not st.session_state.logged_in:
    st.markdown("<h1>Estoque de Ovos Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-texto'>Sua produção organizada de forma profissional</p>", unsafe_allow_html=True)

    with st.container():
        user = st.text_input("Nome de Usuário", placeholder="Digite seu usuário")
        pw = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        
        st.write("")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Entrar"):
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
                    else: st.error("Login ou senha inválidos.")
        with col2:
            if st.button("Criar Conta"):
                if user and pw:
                    try:
                        conn = sqlite3.connect('estoque_ovos.db')
                        c = conn.cursor()
                        c.execute("INSERT INTO usuarios VALUES (?, ?)", (user, pw))
                        conn.commit()
                        conn.close()
                        st.success("Conta criada com sucesso!")
                    except: st.error("Este usuário já existe.")

# --- INTERFACE PRINCIPAL ---
else:
    st.markdown(f"<h1>Painel de Gerenciamento</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='sub-texto'>Bem-vindo, <b>{st.session_state.username}</b></p>", unsafe_allow_html=True)

    if st.sidebar.button("Sair / Logout"): 
        st.session_state.logged_in = False
        st.rerun()

    tab1, tab2 = st.tabs(["📝 Nova Colheita", "🔍 Histórico & Edição"])

    with tab1:
        st.markdown("### Registrar Produção")
        # Ajuste visual e formato da data (DD/MM/YYYY)
        data_reg = st.date_input("📅 Data da Colheita", value=datetime.now().date(), format="DD/MM/YYYY")
        qtd_val = st.number_input("🥚 Quantidade de Ovos", min_value=0, step=1, format="%d")
        
        st.write("")
        if st.button("Salvar no Banco de Dados"):
            conn = sqlite3.connect('estoque_ovos.db')
            c = conn.cursor()
            c.execute("INSERT INTO producao VALUES (?, ?, ?)", (st.session_state.username, data_reg, qtd_val))
            conn.commit()
            conn.close()
            st.balloons()
            st.success("Produção registrada com sucesso!")

    with tab2:
        st.markdown("### Gerenciar Histórico")
        conn = sqlite3.connect('estoque_ovos.db')
        df_edit = pd.read_sql(f"SELECT rowid, data, quantidade FROM producao WHERE username='{st.session_state.username}' ORDER BY data DESC", conn)
        
        if not df_edit.empty:
            df_edit['data_fmt'] = pd.to_datetime(df_edit['data']).dt.strftime('%d/%m/%Y')
            opcoes = {row['rowid']: f"📅 {row['data_fmt']} — {row['quantidade']} ovos" for _, row in df_edit.iterrows()}
            selecao = st.selectbox("Escolha um registro para corrigir:", list(opcoes.values()))
            
            rid = [k for k, v in opcoes.items() if v == selecao][0]
            novo_val = st.number_input("Corrigir para esta quantidade:", min_value=0, step=1)
            
            if st.button("Confirmar Alteração"):
                c = conn.cursor()
                c.execute("UPDATE producao SET quantidade = ? WHERE rowid = ?", (novo_val, rid))
                conn.commit()
                conn.close()
                st.success("Registro atualizado!")
                st.rerun()
        else:
            conn.close()
            st.info("Nenhum registro encontrado para este usuário.")

    st.divider()
    st.markdown("### Desempenho Recente")
    conn = sqlite3.connect('estoque_ovos.db')
    df = pd.read_sql(f"SELECT data, quantidade FROM producao WHERE username='{st.session_state.username}' ORDER BY data DESC LIMIT 15", conn)
    conn.close()

    if not df.empty:
        df['data'] = pd.to_datetime(df['data'])
        df = df.sort_values("data")
        df['data_br'] = df['data'].dt.strftime('%d/%m/%Y')
        
        fig = px.bar(df, x='data_br', y='quantidade', 
                     labels={'data_br': 'Data', 'quantidade': 'Ovos'},
                     color_discrete_sequence=['#5CE65C'])
        
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)', 
            font=dict(color="black"),
            margin=dict(l=0, r=0, t=10, b=0),
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)

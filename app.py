import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# 1. Função de Estilo (CSS)
def aplicar_estilo_customizado():
    st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    div.stButton > button:first-child {
        background-color: #FF8C00;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        border: none;
    }
    div.stButton > button:first-child:hover {
        background-color: #e07b00;
    }
    h1 { color: #2e4053; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# 2. Configurações Iniciais
st.set_page_config(page_title="Estoque de Ovos Pro", layout="centered")
aplicar_estilo_customizado()

def init_db():
    conn = sqlite3.connect('estoque_ovos.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT UNIQUE, password TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS producao (username TEXT, data DATE, quantidade INTEGER)')
    conn.commit()
    conn.close()

init_db()

st.title("🥚 Controle e Monitoramento de Estoque")

# 3. Lógica de Login e Interface (Simplificada)
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

with st.sidebar:
    st.header("🔒 Acesso")
    user = st.text_input("Usuário")
    pw = st.text_input("Senha", type="password")
    if st.button("Entrar / Cadastrar"):
        conn = sqlite3.connect('estoque_ovos.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO usuarios VALUES (?, ?)", (user, pw))
        conn.commit()
        st.session_state.logged_in = True
        st.session_state.username = user

if st.session_state.logged_in:
    st.success(f"Usuário: {st.session_state.username}")
    qtd = st.number_input("Ovos produzidos hoje:", min_value=0)
    if st.button("Registrar agora"):
        conn = sqlite3.connect('estoque_ovos.db')
        c = conn.cursor()
        c.execute("INSERT INTO producao VALUES (?, ?, ?)", (st.session_state.username, datetime.now().date(), qtd))
        conn.commit()
        st.balloons()

    # Gráfico
    conn = sqlite3.connect('estoque_ovos.db')
    df = pd.read_sql(f"SELECT data, quantidade FROM producao WHERE username='{st.session_state.username}' ORDER BY data DESC LIMIT 30", conn)
    if not df.empty:
        st.line_chart(df.sort_values('data').set_index('data'))
else:
    st.info("Acesse o painel lateral para começar.")
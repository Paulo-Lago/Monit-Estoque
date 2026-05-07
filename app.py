import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# 1. Função de Estilo Avançada (CSS)
def aplicar_estilo_customizado():
    st.markdown("""
    <style>
    /* Configurações Gerais */
    .stApp { background-color: white; }
    
    /* Estilização de Títulos e Textos */
    h1, h2, h3 { color: #2e4053; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .sub-texto { color: #666; text-align: center; margin-bottom: 2rem; font-size: 1.1rem; }
    
    /* Botões Simétricos e Estilizados (#5CE65C) */
    div.stButton > button:first-child {
        background-color: #5CE65C;
        color: white;
        border-radius: 20px;
        font-weight: bold;
        border: none;
        width: 100%;
        height: 45px;
        transition: all 0.3s ease;
        text-transform: uppercase;
    }
    div.stButton > button:first-child:hover {
        background-color: #4dc24d;
        box-shadow: 0 4px 10px rgba(92, 230, 92, 0.4);
    }
    
    /* Estilização de Inputs */
    .stTextInput input {
        border-radius: 10px !important;
    }
    
    /* Customização das Abas */
    .stTabs [data-baseweb="tab-list"] button {
        font-weight: bold;
        color: #2e4053;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        background-color: #5CE65C !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. Configurações e Banco de Dados
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

# Estado da Sessão
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'username' not in st.session_state: st.session_state.username = ""

# --- TELA DE LOGIN ---
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🥚 Estoque de Ovos Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-texto'>Comece agora a controlar seu estoque de maneira eficiente</p>", unsafe_allow_html=True)

    with st.container():
        user = st.text_input("Nome de Usuário", placeholder="Insira seu usuário")
        pw = st.text_input("Senha", type="password", placeholder="Insira sua senha")
        
        st.write("") # Espaço em branco
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
                    else:
                        st.error("Usuário ou senha incorretos.")
                else:
                    st.warning("Preencha os campos de acesso.")

        with col2:
            if st.button("Criar Conta"):
                if user and pw:
                    try:
                        conn = sqlite3.connect('estoque_ovos.db')
                        c = conn.cursor()
                        c.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (user, pw))
                        conn.commit()
                        conn.close()
                        st.success("Usuário criado com sucesso! Clique em Entrar.")
                    except sqlite3.IntegrityError:
                        st.error("Este usuário já existe.")
                else:
                    st.warning("Preencha os campos para cadastrar.")

# --- INTERFACE PRINCIPAL ---
else:
    st.title("📈 Painel de Gerenciamento")
    st.subheader(f"Bem-vindo, {st.session_state.username}!")

    if st.sidebar.button("Sair / Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    tab1, tab2 = st.tabs(["📝 Novo Registro", "🔍 Histórico e Edição"])

    with tab1:
        data_reg = st.date_input("Data da Colheita", datetime.now().date())
        qtd_val = st.text_input("Quantidade de Ovos", placeholder="Insira a quantidade de Ovos")

        if st.button("Salvar no Estoque"):
            if qtd_val.isdigit():
                conn = sqlite3.connect('estoque_ovos.db')
                c = conn.cursor()
                c.execute("INSERT INTO producao (username, data, quantidade) VALUES (?, ?, ?)",
                          (st.session_state.username, data_reg, int(qtd_val)))
                conn.commit()
                conn.close()
                st.balloons()
                st.success(f"Registro de {qtd_val} ovos salvo!")
            else:
                st.error("Insira apenas números inteiros.")

    with tab2:
        conn = sqlite3.connect('estoque_ovos.db')
        df_edit = pd.read_sql(f"SELECT rowid, data, quantidade FROM producao WHERE username='{st.session_state.username}' ORDER BY data DESC", conn)
        
        if not df_edit.empty:
            opcoes = df_edit.apply(lambda x: f"ID: {x['rowid']} | Data: {x['data']} | Qtd: {x['quantidade']}", axis=1).tolist()
            selecao = st.selectbox("Escolha o registro para alterar:", opcoes)
            novo_num = st.number_input("Corrigir para quanto?", min_value=0, step=1)

            if st.button("Confirmar Alteração"):
                rid = int(selecao.split('|')[0].replace('ID: ', '').strip())
                c = conn.cursor()
                c.execute("UPDATE producao SET quantidade = ? WHERE rowid = ?", (novo_num, rid))
                conn.commit()
                conn.close()
                st.success("Registro atualizado!")
                st.rerun()
        else:
            conn.close()
            st.info("Nenhum dado registrado para este usuário.")

    st.divider()
    st.subheader("Gráfico de Produção")
    conn = sqlite3.connect('estoque_ovos.db')
    df = pd.read_sql(f"SELECT data, quantidade FROM producao WHERE username='{st.session_state.username}' ORDER BY data DESC LIMIT 30", conn)
    conn.close()
    if not df.empty:
        st.line_chart(df.sort_values('data').set_index('data'), color="#5CE65C")

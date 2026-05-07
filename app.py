import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURAÇÃO DE ÍCONE PERSONALIZADO ---
URL_ICONE = "https://preview.redd.it/d7ajx3csqpzg1.jpeg?width=640&crop=smart&auto=webp&s=52f986fe2c31fe8b67d7502f4b1a02f9646cba1d"

# 1. Função de Estilo Avançada (CSS)
def aplicar_estilo_customizado():
    st.markdown(f"""
    <style>
    /* Configurações Gerais */
    .stApp {{ background-color: white; color: black; }}

    /* Estilização do Ícone de Ovo como Fundo */
    .egg-background-container {{
        position: relative;
        width: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 50px 0;
    }}

    .egg-icon-bg {{
        position: absolute;
        width: 280px;
        opacity: 0.15;
        z-index: 0;
        pointer-events: none;
    }}

    /* Títulos e Formulário sobrepostos ao fundo */
    .login-content {{
        position: relative;
        z-index: 1;
        width: 100%;
    }}

    h1, h2, h3, p, span, label, .stMarkdown {{
        color: #000000 !important;
        font-family: 'Segoe UI', sans-serif;
    }}

    .sub-texto {{
        color: #000000 !important;
        text-align: center;
        margin-bottom: 2rem;
        font-size: 1.1rem;
        font-weight: 500;
    }}

    /* Botões */
    div.stButton > button:first-child {{
        background-color: #5CE65C;
        color: white !important;
        border-radius: 20px;
        font-weight: bold;
        border: none;
        width: 100%;
        height: 45px;
        text-transform: uppercase;
    }}
    div.stButton > button:first-child:hover {{
        background-color: #4dc24d;
        box-shadow: 0 4px 10px rgba(92, 230, 92, 0.4);
    }}

    .stTextInput label, .stDateInput label, .stNumberInput label, .stSelectbox label {{
        color: black !important;
    }}
    </style>
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
    st.markdown(f'''
        <div class="egg-background-container">
            <img src="{URL_ICONE}" class="egg-icon-bg">
            <div class="login-content">
                <h1 style="text-align:center;">Estoque de Ovos Pro</h1>
                <p class="sub-texto">Comece agora a controlar seu estoque de maneira eficiente</p>
            </div>
        </div>
    ''', unsafe_allow_html=True)

    with st.container():
        user = st.text_input("Nome de Usuário", placeholder="Insira seu usuário")
        pw = st.text_input("Senha", type="password", placeholder="Insira sua senha")

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
                    else:
                        st.error("Usuário ou senha incorretos.")

        with col2:
            if st.button("Criar Conta"):
                if user and pw:
                    try:
                        conn = sqlite3.connect('estoque_ovos.db')
                        c = conn.cursor()
                        c.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (user, pw))
                        conn.commit()
                        conn.close()
                        st.success("Usuário criado! Faça login.")
                    except sqlite3.IntegrityError:
                        st.error("Este usuário já existe. Tente outro nome ou faça login.")
                else:
                    st.warning("Preencha usuário e senha para cadastrar.")

# --- INTERFACE PRINCIPAL ---
else:
    st.markdown(f'<img src="{URL_ICONE}" style="width:50px; display:block; margin:auto;">', unsafe_allow_html=True)
    st.markdown("<h1>Painel de Gerenciamento</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align: center;'>Bem-vindo, {st.session_state.username}!</h3>", unsafe_allow_html=True)

    if st.sidebar.button("Sair / Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    tab1, tab2 = st.tabs(["📝 Novo Registro", "🔍 Histórico e Edição"])

    with tab1:
        st.markdown("### Registrar Colheita")
        data_reg = st.date_input("Data da Colheita", datetime.now().date())
        qtd_val = st.text_input("Quantidade de Ovos", placeholder="Ex: 12")

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
                st.error("Por favor, insira um número válido.")

    with tab2:
        st.markdown("### Gerenciar Histórico")
        conn = sqlite3.connect('estoque_ovos.db')
        df_edit = pd.read_sql(f"SELECT rowid, data, quantidade FROM producao WHERE username='{st.session_state.username}' ORDER BY data DESC", conn)

        if not df_edit.empty:
            opcoes = df_edit.apply(lambda x: f"ID: {x['rowid']} | Data: {x['data']} | Qtd: {x['quantidade']}", axis=1).tolist()
            selecao = st.selectbox("Escolha o registro para alterar:", opcoes)
            novo_num = st.number_input("Corrigir quantidade:", min_value=0, step=1)

            if st.button("Confirmar Alteração"):
                rid = int(selecao.split("|")[0].replace("ID: ", "").strip())
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
    st.markdown("### Gráfico de Produção")
    conn = sqlite3.connect('estoque_ovos.db')
    df = pd.read_sql(f"SELECT data, quantidade FROM producao WHERE username='{st.session_state.username}' ORDER BY data DESC LIMIT 30", conn)
    conn.close()
    
    if not df.empty:
        df = df.sort_values("data")
        fig = px.bar(df, x='data', y='quantidade', 
                     title='Produção dos Últimos 30 Registros',
                     labels={'data': 'Data', 'quantidade': 'Ovos'},
                     color_discrete_sequence=['#5CE65C'])
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis_title="Data",
            yaxis_title="Quantidade",
            title_x=0.5
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Ainda não há dados para mostrar o gráfico.")

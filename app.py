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
        width: 100%;
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

# Gerenciamento de Estado da Sessão
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""

# --- TELA DE LOGIN (Somente aparece se não estiver logado) ---
if not st.session_state.logged_in:
    st.title("🔐 Acesso ao Sistema")
    
    # Container centralizado para login
    with st.container():
        user = st.text_input("Usuário", key="login_user")
        pw = st.text_input("Senha", type="password", key="login_pw")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Entrar"):
                if user and pw:
                    conn = sqlite3.connect('estoque_ovos.db')
                    c = conn.cursor()
                    c.execute("SELECT password FROM usuarios WHERE username = ?", (user,))
                    result = c.fetchone()
                    conn.close()
                    
                    if result:
                        if result[0] == pw:
                            st.session_state.logged_in = True
                            st.session_state.username = user
                            st.rerun()
                        else:
                            st.error("Senha incorreta! Verifique e tente novamente.")
                    else:
                        st.error("Usuário não encontrado. Deseja criar uma conta?")
                else:
                    st.warning("Por favor, preencha o usuário e a senha.")

        with col2:
            if st.button("Criar Conta"):
                if user and pw:
                    try:
                        conn = sqlite3.connect('estoque_ovos.db')
                        c = conn.cursor()
                        c.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (user, pw))
                        conn.commit()
                        conn.close()
                        st.success("Usuário criado com sucesso! Agora você pode entrar.")
                    except sqlite3.IntegrityError:
                        st.error("Este nome de usuário já está em uso.")
                else:
                    st.warning("Preencha os campos para cadastrar um novo usuário.")

# --- INTERFACE PRINCIPAL (Aparece somente após o sucesso do login) ---
else:
    st.title("🥚 Controle de Estoque")
    st.subheader(f"Bem-vindo, {st.session_state.username}!")

    # Botão de Logout na Barra Lateral
    if st.sidebar.button("Sair / Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    tab1, tab2 = st.tabs(["Registrar Produção", "Editar Histórico"])

    with tab1:
        data_selecionada = st.date_input("Selecione a Data:", datetime.now().date())
        qtd_str = st.text_input("Quantidade de ovos:", placeholder="Insira a quantidade de Ovos")

        if st.button("Registrar agora"):
            if qtd_str.isdigit():
                qtd = int(qtd_str)
                conn = sqlite3.connect('estoque_ovos.db')
                c = conn.cursor()
                c.execute("INSERT INTO producao (username, data, quantidade) VALUES (?, ?, ?)",
                          (st.session_state.username, data_selecionada, qtd))
                conn.commit()
                conn.close()
                st.balloons()
                st.success(f"Registrado {qtd} ovos em {data_selecionada}!")
            else:
                st.error("Por favor, insira um número inteiro válido.")

    with tab2:
        st.subheader("Gerenciar Registros")
        conn = sqlite3.connect('estoque_ovos.db')
        df_edit = pd.read_sql(f"SELECT rowid, data, quantidade FROM producao WHERE username='{st.session_state.username}' ORDER BY data DESC", conn)

        if not df_edit.empty:
            opcoes = df_edit.apply(lambda x: f"ID: {x['rowid']} | Data: {x['data']} | Qtd: {x['quantidade']}", axis=1).tolist()
            selecionado = st.selectbox("Selecione o registro para alterar:", opcoes)
            novo_valor = st.number_input("Nova quantidade de ovos:", min_value=0, step=1)

            if st.button("Salvar Alteração"):
                row_id_real = int(selecionado.split('|')[0].replace('ID: ', '').strip())
                c = conn.cursor()
                c.execute("UPDATE producao SET quantidade = ? WHERE rowid = ?", (novo_valor, row_id_real))
                conn.commit()
                conn.close()
                st.success("Registro atualizado com sucesso!")
                st.rerun()
        else:
            conn.close()
            st.info("Ainda não há registros para editar.")

    st.divider()
    st.subheader("Tendência de Produção")
    conn = sqlite3.connect('estoque_ovos.db')
    df = pd.read_sql(f"SELECT data, quantidade FROM producao WHERE username='{st.session_state.username}' ORDER BY data DESC LIMIT 30", conn)
    conn.close()
    if not df.empty:
        st.line_chart(df.sort_values('data').set_index('data'))

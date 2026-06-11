import streamlit as st
from sqlalchemy import create_engine, text
import base64
from pathlib import Path
import requests
import time

from recibo_pdf import gerar_pdf_recibo_reportlab
from modulo_producao import render_modulo_producao
from modulo_faturamento import render_modulo_faturamento

# ==================== EVOLUTION API ====================
def get_evolution_config():
    return {
        "url": st.secrets.get("evolution", {}).get("url", "http://localhost:8080"),
        "api_key": st.secrets.get("evolution", {}).get("api_key", ""),
        "instance": st.secrets.get("evolution", {}).get("instance", "default")
    }

def enviar_pdf_whatsapp(telefone_cliente, pdf_bytes, nome_cliente, numero_recibo):
    """
    Envia PDF pelo WhatsApp usando Evolution API.
    telefone_cliente: string com DDD e número (pode conter espaços, traços)
    Retorna (sucesso, mensagem)
    """
    if not telefone_cliente:
        return False, "Cliente sem telefone cadastrado."
    
    # Limpa o número: só dígitos
    numero_limpo = ''.join(filter(str.isdigit, telefone_cliente))
    if not numero_limpo.startswith('55'):
        numero_limpo = '55' + numero_limpo
    
    config = get_evolution_config()
    if not config["api_key"]:
        return False, "Evolution API não configurada (api_key ausente)"

    url_base = config["url"].rstrip("/")
    instancia = config["instance"].strip()
    if not url_base or not instancia:
        return False, "Evolution API não configurada (URL ou instância ausente)"

    try:
        url = f"{url_base}/message/sendMedia/{instancia}"
        headers = {
            "apikey": config["api_key"],
            "Content-Type": "application/json"
        }

        caption = f"""Olá {nome_cliente}, segue o recibo da sua compra.
Nº do recibo: {numero_recibo}
Obrigado pela preferência! 🐔"""

        nome_arquivo = f"recibo_{numero_recibo or 'venda'}.pdf"
        payload = {
            "number": numero_limpo,
            "mediatype": "document",
            "mimetype": "application/pdf",
            "caption": caption,
            "media": base64.b64encode(pdf_bytes).decode("ascii"),
            "fileName": nome_arquivo,
            "delay": 1200
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60
        )
        if response.status_code in (200, 201):
            return True, "Recibo enviado com sucesso!"
        detalhe = response.text.strip().replace("\n", " ")[:300]
        if response.status_code == 404:
            return False, (
                f"Evolution API retornou 404 na rota /message/sendMedia/{instancia}. "
                "Confira se a URL configurada aponta para a raiz da API e se o nome da instância está correto."
            )
        return False, f"Evolution API retornou {response.status_code}: {detalhe or 'sem detalhes'}"
    except Exception as e:
        return False, f"Erro ao enviar: {str(e)}"

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

# ==================== ESTRUTURA DO BANCO ====================
@st.cache_resource
def inicializar_estrutura_banco(_engine):
    with _engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS logs_acoes (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                acao TEXT NOT NULL,
                tabela TEXT NOT NULL,
                registro_id INTEGER,
                detalhes TEXT,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_logs_acoes_usuario_data
            ON logs_acoes (username, data_hora DESC)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_logs_acoes_usuario_acao_tabela
            ON logs_acoes (username, acao, tabela)
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ovos_geral_galpao (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                data DATE NOT NULL,
                galpao TEXT NOT NULL,
                quantidade INTEGER NOT NULL CHECK (quantidade >= 0),
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (username, data, galpao)
            )
        """))
        conn.commit()
    return True


inicializar_estrutura_banco(engine)

def registrar_log(acao, tabela, registro_id=None, detalhes=None):
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO logs_acoes (username, acao, tabela, registro_id, detalhes)
                VALUES (:u, :a, :t, :rid, :d)
            """), {
                "u": st.session_state.username,
                "a": acao,
                "t": tabela,
                "rid": registro_id,
                "d": detalhes
            })
            conn.commit()
        return True
    except Exception:
        st.warning(
            "A operação foi concluída, mas não foi possível registrá-la no histórico de ações.")
        return False

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


def acao_repetida(chave, payload=None, intervalo=8):
    """Evita que o mesmo envio seja processado duas vezes em poucos segundos."""
    agora = time.time()
    assinatura = repr(payload)
    cache = st.session_state.setdefault("_acoes_recentes", {})
    ultima = cache.get(chave)

    if ultima and ultima["assinatura"] == assinatura and agora - ultima["quando"] < intervalo:
        st.warning("Essa ação já foi enviada. Aguarde alguns segundos antes de tentar novamente.")
        return True

    cache[chave] = {"assinatura": assinatura, "quando": agora}
    return False


def liberar_acao(chave):
    st.session_state.get("_acoes_recentes", {}).pop(chave, None)

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
                chave_acao = "criar_conta"
                payload_acao = (user,)
                if acao_repetida(chave_acao, payload_acao):
                    st.stop()
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
                        liberar_acao(chave_acao)
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


    if st.session_state.modulo_atual == "monitoramento":
        render_modulo_producao(
            engine=engine,
            base_dir=BASE_DIR,
            tipos_ovo=TIPOS_OVO,
            galpoes=GALPOES,
            cores=CORES,
            registrar_log=registrar_log,
            acao_repetida=acao_repetida,
            liberar_acao=liberar_acao,
        )
    else:
        render_modulo_faturamento(
            engine=engine,
            registrar_log=registrar_log,
            acao_repetida=acao_repetida,
            liberar_acao=liberar_acao,
            gerar_pdf_recibo_reportlab=gerar_pdf_recibo_reportlab,
            enviar_pdf_whatsapp=enviar_pdf_whatsapp,
        )

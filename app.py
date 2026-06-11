import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import datetime, date
import base64
from pathlib import Path
import plotly.express as px


from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from pathlib import Path

import requests
import time

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

# ==================== FUNÇÃO DE GERAR PDF (REPORTLAB) ====================
def gerar_pdf_recibo_reportlab(dados_venda, itens, numero_recibo):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle(name='Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16, spaceAfter=10)
    style_subtitle = ParagraphStyle(name='Subtitle', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12, textColor=colors.grey)
    
    elements = []
    
    # --- Logo (se existir) ---
    logo_path = Path(__file__).parent / "assets" / "logomarca.png"
    if logo_path.exists():
        try:
            img = Image(str(logo_path), width=4*cm, height=4*cm, hAlign='CENTER')
            elements.append(img)
            elements.append(Spacer(1, 0.3*cm))
        except:
            pass  # se falhar ao carregar, ignora
    
    # Cabeçalho
    elements.append(Paragraph("Estoque Ovos Pro", style_title))
    elements.append(Paragraph("RECIBO DE VENDA", style_subtitle))
    elements.append(Spacer(1, 0.5*cm))
    
    # Dados da venda
    info_data = [
        ["Nº Recibo:", numero_recibo],
        ["Data:", dados_venda['data_venda'].strftime('%d/%m/%Y')],
        ["Cliente:", dados_venda['cliente_nome']],
        ["Observações:", dados_venda.get('observacoes', '')]
    ]
    table_info = Table(info_data, colWidths=[3.5*cm, 10*cm])
    table_info.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10)]))
    elements.append(table_info)
    elements.append(Spacer(1, 0.5*cm))
    
    # Tabela de produtos
    data = [["Produto", "Qtd", "Preço Unit. (R$)", "Desc. Unit. (R$)", "Subtotal (R$)"]]
    for item in itens:
        data.append([
            item['produto_nome'],
            f"{item['quantidade']:.2f}".replace('.', ','),
            f"{item['preco_unit']:.2f}".replace('.', ','),
            f"{item['desconto_unit']:.2f}".replace('.', ','),
            f"{item['subtotal']:.2f}".replace('.', ',')
        ])
    table_prod = Table(data, colWidths=[6*cm, 1.8*cm, 2.5*cm, 2.5*cm, 2.5*cm])
    table_prod.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
    ]))
    elements.append(table_prod)
    elements.append(Spacer(1, 0.5*cm))
    
    # Totais
    valor_bruto = sum(item['subtotal'] + item['desconto_unit'] * item['quantidade'] for item in itens)
    desconto_total = sum(item['desconto_unit'] * item['quantidade'] for item in itens)
    
    def fmt_br(valor):
        return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    totais_data = [
        ["Valor Bruto:", fmt_br(valor_bruto)],
        ["Desconto Total:", fmt_br(desconto_total)],
        ["Valor Final:", fmt_br(dados_venda['valor_total'])],
        ["Valor Pago:", fmt_br(dados_venda['valor_pago'])],
        ["Saldo Devedor:", fmt_br(dados_venda['valor_devendo'])]
    ]
    table_totais = Table(totais_data, colWidths=[4.5*cm, 4.5*cm])
    table_totais.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('BACKGROUND', (0,2), (1,2), colors.lightblue)
    ]))
    wrapper = Table([[table_totais]], colWidths=[16*cm])
    wrapper.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'RIGHT')]))
    elements.append(wrapper)
    elements.append(Spacer(1, 0.5*cm))
    
    # Mensagem final
    elements.append(Paragraph("Obrigado pela preferência!", ParagraphStyle(name='Thanks', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10, textColor=colors.grey)))
    elements.append(Paragraph("Documento emitido eletronicamente – não é necessária assinatura.", ParagraphStyle(name='Footer', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8, textColor=colors.grey)))
    
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

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

# ==================== TABELA DE LOGS ====================
with engine.connect() as conn:
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
    conn.commit()

def registrar_log(acao, tabela, registro_id=None, detalhes=None):
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

            with st.form("form_salvar_colheita", clear_on_submit=True):
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
                salvar_colheita = st.form_submit_button("✅ Salvar Colheita", use_container_width=True)

            if salvar_colheita:
                if qtd_val > 0:
                    chave_acao = "salvar_colheita"
                    payload_acao = (st.session_state.username, data_reg, qtd_val, tipo_ovo, galpao, cor)
                    if acao_repetida(chave_acao, payload_acao):
                        st.stop()
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
                        liberar_acao(chave_acao)
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

           
             # ==================== SUB-ABA 2: HISTÓRICO & EDIÇÃO (COM FILTRO E TABELA) ====================
            with prod_tabs[1]:
                st.markdown("### 🔍 Histórico e Edição de Colheitas")

                # ----- FILTRO DE PERÍODO -----
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    data_inicio_hist = st.date_input(
                        "📅 Data Inicial",
                        value=datetime.now().date() - pd.Timedelta(days=30),
                        format="DD/MM/YYYY",
                        key="hist_data_inicio"
                    )
                with col_f2:
                    data_fim_hist = st.date_input(
                        "📅 Data Final",
                        value=datetime.now().date(),
                        format="DD/MM/YYYY",
                        key="hist_data_fim"
                    )

                if data_inicio_hist > data_fim_hist:
                    st.error("⚠️ Data inicial não pode ser maior que a data final.")
                else:
                    # ----- TABELA HISTÓRICA (período filtrado) -----
                    try:
                        query_hist = text("""
                            SELECT id, data, quantidade, tipo, galpao, cor
                            FROM producao
                            WHERE username = :username
                                AND data BETWEEN :inicio AND :fim
                            ORDER BY data DESC, id DESC
                        """)
                        df_hist = pd.read_sql(
                            query_hist,
                            engine,
                            params={
                                "username": st.session_state.username,
                                "inicio": data_inicio_hist,
                                "fim": data_fim_hist
                            }
                        )

                        if df_hist.empty:
                            st.info("📭 Nenhum registro de colheita encontrado no período selecionado.")
                        else:
                            # Formatar para exibição
                            df_display = df_hist.copy()
                            df_display['data'] = pd.to_datetime(df_display['data']).dt.strftime('%d/%m/%Y')
                            df_display = df_display.rename(columns={
                                'data': 'Data',
                                'quantidade': 'Quantidade',
                                'tipo': 'Tipo',
                                'galpao': 'Galpão',
                                'cor': 'Cor'
                            })
                            st.markdown("#### 📋 Registros do Período")
                            st.dataframe(
                                df_display[['Data', 'Quantidade', 'Tipo', 'Galpão', 'Cor']],
                                use_container_width=True,
                                hide_index=True
                            )
                    except Exception as e:
                        st.error(f"Erro ao carregar histórico: {e}")

                    st.divider()

                    # ----- EDIÇÃO/EXCLUSÃO (selecionar um registro) -----
                    st.markdown("#### ✏️ Editar ou Excluir Registro")

                    # Carregar todos os registros (ou apenas do período? Vou manter todos para não perder a funcionalidade)
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

                        if df_edit.empty:
                            st.info("Nenhum registro disponível para edição/exclusão.")
                        else:
                            df_edit['data_fmt'] = pd.to_datetime(df_edit['data']).dt.strftime('%d/%m/%Y')
                            opcoes = {
                                row['id']: f"📅 {row['data_fmt']} | {row['quantidade']} ovos | {row['tipo']} | {row['cor']} | {row['galpao']}"
                                for _, row in df_edit.iterrows()
                            }
                            selected_id = st.selectbox(
                                "Escolha um registro para corrigir:",
                                options=list(opcoes.keys()),
                                format_func=lambda x: opcoes[x],
                                index=None,
                                placeholder="Selecione um registro",
                                key="edit_select"
                            )
                            mensagem_editar_colheita = st.empty()
                            area_editar_colheita = st.empty()
                            with area_editar_colheita.container(), st.form("form_editar_colheita", clear_on_submit=True):
                                if selected_id is not None:
                                    registro = df_edit[df_edit['id'] == selected_id].iloc[0]
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        novo_val = st.number_input(
                                            "Corrigir quantidade:", min_value=0, step=1,
                                            value=int(registro['quantidade']), key="edit_qtd")
                                        novo_tipo = st.selectbox(
                                            "Corrigir tipo:", TIPOS_OVO,
                                            index=TIPOS_OVO.index(registro['tipo']), key="edit_tipo")
                                        nova_data = st.date_input(
                                            "📅 Data da Colheita", value=pd.to_datetime(registro['data']).date(),
                                            format="DD/MM/YYYY", key="edit_data")
                                    with col2:
                                        novo_galpao = st.selectbox(
                                            "Corrigir galpão:", GALPOES,
                                            index=GALPOES.index(registro['galpao']), key="edit_galpao")
                                        nova_cor = st.selectbox(
                                            "Corrigir cor:", CORES,
                                            index=CORES.index(registro['cor']), key="edit_cor")
                                    salvar_colheita_editada = st.form_submit_button(
                                        "✅ Confirmar Alteração", type="primary", use_container_width=True)
                                else:
                                    salvar_colheita_editada = st.form_submit_button(
                                        "✅ Confirmar Alteração", type="primary", use_container_width=True, disabled=True)

                            if salvar_colheita_editada and selected_id is not None:
                                try:
                                    with engine.connect() as conn:
                                        conn.execute(
                                            text("""
                                                UPDATE producao
                                                SET quantidade = :qtd,
                                                    tipo = :tipo,
                                                    galpao = :galpao,
                                                    cor = :cor,
                                                    data = :data
                                                WHERE id = :id AND username = :username
                                            """),
                                            {
                                                "qtd": novo_val,
                                                "tipo": novo_tipo,
                                                "galpao": novo_galpao,
                                                "cor": nova_cor,
                                                "data": nova_data,
                                                "id": selected_id,
                                                "username": st.session_state.username
                                            }
                                        )
                                        conn.commit()
                                    area_editar_colheita.empty()
                                    mensagem_editar_colheita.success("✅ Registro atualizado com sucesso!")
                                except Exception as e:
                                    st.error(f"Erro ao atualizar: {e}")

                            st.divider()

                            # Exclusão
                            st.markdown("#### 🗑️ Excluir Registro")
                            st.caption("Esta ação é irreversível e removerá permanentemente o registro do histórico.")
                            selected_id_excluir = st.selectbox(
                                "Escolha um registro para excluir:",
                                options=list(opcoes.keys()),
                                format_func=lambda x: opcoes[x],
                                index=None,
                                placeholder="Selecione um registro",
                                key="delete_select_colheita"
                            )
                            mensagem_excluir_colheita = st.empty()
                            area_excluir_colheita = st.empty()
                            with area_excluir_colheita.container(), st.form("form_excluir_colheita", clear_on_submit=True):
                                if selected_id_excluir is not None:
                                    registro_excluir = df_edit[df_edit['id'] == selected_id_excluir].iloc[0]
                                    st.warning(
                                        f"Tem certeza que deseja excluir o registro de {registro_excluir['quantidade']} ovos "
                                        f"({registro_excluir['tipo']}, {registro_excluir['cor']}) do {registro_excluir['galpao']}?")
                                    confirmar = st.checkbox("Sim, quero excluir permanentemente este registro.")
                                else:
                                    registro_excluir = None
                                    confirmar = False
                                excluir_colheita = st.form_submit_button(
                                    "Excluir agora", type="primary", disabled=not confirmar)

                                if excluir_colheita and selected_id_excluir is not None:
                                    try:
                                        registrar_log("DELETE", "producao", selected_id_excluir, f"Excluiu colheita de {registro_excluir['quantidade']} ovos")
                                        with engine.connect() as conn:
                                            conn.execute(
                                                text("DELETE FROM producao WHERE id = :id AND username = :username"),
                                                {"id": selected_id_excluir, "username": st.session_state.username}
                                            )
                                            conn.commit()
                                        area_excluir_colheita.empty()
                                        mensagem_excluir_colheita.success("✅ Registro excluído com sucesso!")
                                    except Exception as e:
                                        st.error(f"Erro ao excluir: {e}")

                    except Exception as e:
                        st.error(f"Erro ao carregar registros para edição: {e}")

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
                with st.form("form_registrar_aves", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        data_aves = st.date_input("📅 Data", value=datetime.now().date(),
                                                  format="DD/MM/YYYY", key="data_aves_reg")
                        galpao_aves = st.selectbox(
                            "🏠 Galpão", GALPOES, key="galpao_aves_reg")
                    with col2:
                        qtd_aves = st.number_input("🐔 Quantidade de Aves", min_value=1, step=1,
                                                   format="%d", key="qtd_aves_reg")

                    registrar_aves = st.form_submit_button(
                        "✅ Registrar Aves", type="primary", use_container_width=True)

                if registrar_aves:
                    if qtd_aves > 0:
                        chave_acao = "registrar_aves"
                        payload_acao = (st.session_state.username, data_aves, galpao_aves, qtd_aves)
                        if acao_repetida(chave_acao, payload_acao):
                            st.stop()
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
                        except Exception as e:
                            liberar_acao(chave_acao)
                            st.error(f"Erro ao registrar aves: {e}")

            # ==================== AVES MORTAS ====================
            with tab_mortas:
                # Título com imagem
                img_icone = BASE_DIR / "assets" / "galinhamorta.png"
                if img_icone.exists():
                    with open(img_icone, "rb") as f:
                        img_base64 = base64.b64encode(f.read()).decode()
                    st.markdown(
                        f'<h4 style="font-size: 1.8rem;"><img src="data:image/png;base64,{img_base64}" width="44" style="vertical-align: middle; margin-right: 6px;"> Registrar Aves Mortas</h4>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown("#### ⚠️ Registrar Aves Mortas")
                
                with st.form("form_registrar_morte", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        data_morta = st.date_input("📅 Data", value=datetime.now().date(),
                                                   format="DD/MM/YYYY", key="data_morta")
                        galpao_morta = st.selectbox(
                            "🏠 Galpão", GALPOES, key="galpao_morta")
                    with col2:
                        qtd_morta = st.number_input("🪦 Quantidade de Aves Mortas", min_value=1, step=1,
                                                    format="%d", key="qtd_morta")

                    registrar_morte = st.form_submit_button(
                        "✅ Registrar Morte", type="primary", use_container_width=True)

                if registrar_morte:
                    chave_acao = "registrar_morte"
                    payload_acao = (st.session_state.username, data_morta, galpao_morta, qtd_morta)
                    if acao_repetida(chave_acao, payload_acao):
                        st.stop()
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
                    except Exception as e:
                        liberar_acao(chave_acao)
                        st.error(f"Erro ao registrar morte: {e}")

            # ==================== HISTÓRICO + EDIÇÃO (AVES VIVAS E MORTAS) ====================
            with tab_historico:
                st.markdown("#### 📋 Histórico de Aves")

                # Filtro de período
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    data_inicio_aves = st.date_input(
                        "Data Inicial",
                        value=datetime.now().date() - pd.Timedelta(days=30),
                        format="DD/MM/YYYY",
                        key="aves_data_inicio"
                    )
                with col_f2:
                    data_fim_aves = st.date_input(
                        "Data Final",
                        value=datetime.now().date(),
                        format="DD/MM/YYYY",
                        key="aves_data_fim"
                    )

                if data_inicio_aves > data_fim_aves:
                    st.error("⚠️ Data inicial não pode ser maior que a data final.")
                else:
                    # ---- HISTÓRICO DE AVES VIVAS (REGISTRADAS) ----
                    st.markdown("### 🐔 Aves Registradas (Vivas)")
                    try:
                        df_aves = pd.read_sql(text("""
                            SELECT id, data_registro, galpao, quantidade_total
                            FROM aves
                            WHERE username = :username
                                AND data_registro BETWEEN :inicio AND :fim
                            ORDER BY data_registro DESC
                        """), engine, params={
                            "username": st.session_state.username,
                            "inicio": data_inicio_aves,
                            "fim": data_fim_aves
                        })

                        if df_aves.empty:
                            st.info("Nenhum registro de aves vivas no período.")
                        else:
                            df_aves = df_aves.rename(columns={
                                "data_registro": "Data",
                                "galpao": "Galpão",
                                "quantidade_total": "Quantidade"
                            })
                            df_aves['Data'] = pd.to_datetime(df_aves['Data']).dt.strftime('%d/%m/%Y')
                            st.dataframe(df_aves[['Data', 'Galpão', 'Quantidade']], use_container_width=True, hide_index=True)

                            # ---- Edição/Exclusão de Aves Vivas (como já existia) ----
                            st.markdown("#### ✏️ Editar ou Excluir Registro de Aves Vivas")
                            opcoes = {
                                row['id']: f"📅 {row['Data']} | {row['Galpão']} | {row['Quantidade']} aves"
                                for _, row in df_aves.iterrows()
                            }
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                selected_id = st.selectbox(
                                    "Selecione um registro para editar:",
                                    options=list(opcoes.keys()),
                                    format_func=lambda x: opcoes[x],
                                    index=None,
                                    placeholder="Selecione um registro",
                                    key="select_ave_viva"
                                )
                                mensagem_editar_ave = st.empty()
                                area_editar_ave = st.empty()
                                with area_editar_ave.container(), st.form("form_editar_ave", clear_on_submit=True):
                                    if selected_id is not None:
                                        registro = pd.read_sql(text("""
                                            SELECT data_registro, galpao, quantidade_total
                                            FROM aves WHERE id = :id
                                        """), engine, params={"id": selected_id}).iloc[0]
                                        novo_galpao = st.selectbox(
                                            "Galpão", GALPOES,
                                            index=GALPOES.index(registro['galpao']), key="edit_galpao_ave")
                                        nova_qtd = st.number_input(
                                            "Quantidade", min_value=1, step=1,
                                            value=int(registro['quantidade_total']), key="edit_qtd_ave")
                                        nova_data = st.date_input(
                                            "Data", value=pd.to_datetime(registro['data_registro']).date(),
                                            format="DD/MM/YYYY", key="edit_data_ave")
                                        salvar_ave = st.form_submit_button(
                                            "✅ Salvar Alterações", use_container_width=True, type="primary")
                                    else:
                                        salvar_ave = st.form_submit_button(
                                            "✅ Salvar Alterações", use_container_width=True, type="primary", disabled=True)

                                if salvar_ave and selected_id is not None:
                                    try:
                                        with engine.connect() as conn:
                                            conn.execute(text("""
                                                UPDATE aves
                                                SET galpao = :galpao,
                                                    quantidade_total = :qtd,
                                                    data_registro = :data
                                                WHERE id = :id AND username = :username
                                            """), {
                                                "galpao": novo_galpao,
                                                "qtd": nova_qtd,
                                                "data": nova_data,
                                                "id": selected_id,
                                                "username": st.session_state.username
                                            })
                                            conn.commit()
                                        area_editar_ave.empty()
                                        mensagem_editar_ave.success("✅ Registro atualizado com sucesso!")
                                    except Exception as e:
                                        st.error(f"Erro ao atualizar: {e}")
                            with col_btn2:
                                selected_id_excluir = st.selectbox(
                                    "Selecione um registro para excluir:",
                                    options=list(opcoes.keys()),
                                    format_func=lambda x: opcoes[x],
                                    index=None,
                                    placeholder="Selecione um registro",
                                    key="delete_ave_viva"
                                )
                                mensagem_excluir_ave = st.empty()
                                area_excluir_ave = st.empty()
                                with area_excluir_ave.container(), st.form("form_excluir_ave", clear_on_submit=True):
                                    if selected_id_excluir is not None:
                                        st.warning("⚠️ Esta ação não pode ser desfeita!")
                                        confirmar_ave = st.checkbox("Confirmo que quero excluir este registro")
                                    else:
                                        confirmar_ave = False
                                    excluir_ave = st.form_submit_button(
                                        "Sim, excluir permanentemente", type="primary", disabled=not confirmar_ave)

                                    if excluir_ave and selected_id_excluir is not None:
                                        try:
                                            with engine.connect() as conn:
                                                conn.execute(text("""
                                                    DELETE FROM aves
                                                    WHERE id = :id AND username = :username
                                                """), {"id": selected_id_excluir, "username": st.session_state.username})
                                                conn.commit()
                                            area_excluir_ave.empty()
                                            mensagem_excluir_ave.success("Registro excluído!")
                                        except Exception as e:
                                            st.error(f"Erro ao excluir: {e}")
                    except Exception as e:
                        st.error(f"Erro ao carregar aves vivas: {e}")

                    st.divider()

                    # ---- HISTÓRICO DE AVES MORTAS ----
                   # --- Título com imagem personalizada ---
                    img_icone = BASE_DIR / "assets" / "galinhamorta.png"  # ou outro nome de arquivo
                    if img_icone.exists():
                        with open(img_icone, "rb") as f:
                            img_base64 = base64.b64encode(f.read()).decode()
                        st.markdown(
                            f'<h3 style="font-size: 1.8rem;"><img src="data:image/png;base64,{img_base64}" width="44" style="vertical-align: middle; margin-right: 8px;"> Aves Mortas</h3>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown("### 🪦 Aves Mortas")  # fallback com emoji
                    try:
                        df_mortas = pd.read_sql(text("""
                            SELECT id, data, galpao, quantidade
                            FROM aves_mortas
                            WHERE username = :username
                                AND data BETWEEN :inicio AND :fim
                            ORDER BY data DESC
                        """), engine, params={
                            "username": st.session_state.username,
                            "inicio": data_inicio_aves,
                            "fim": data_fim_aves
                        })

                        if df_mortas.empty:
                            st.info("Nenhum registro de aves mortas no período.")
                        else:
                            df_mortas = df_mortas.rename(columns={
                                "data": "Data",
                                "galpao": "Galpão",
                                "quantidade": "Quantidade"
                            })
                            df_mortas['Data'] = pd.to_datetime(df_mortas['Data']).dt.strftime('%d/%m/%Y')
                            st.dataframe(df_mortas[['Data', 'Galpão', 'Quantidade']], use_container_width=True, hide_index=True)

                            # Opcional: permitir excluir registros de mortes (sem edição)
                            st.markdown("#### 🗑️ Excluir Registro de Aves Mortas")
                            opcoes_mortas = {
                                row['id']: f"📅 {row['Data']} | {row['Galpão']} | {row['Quantidade']} aves"
                                for _, row in df_mortas.iterrows()
                            }
                            selected_id_morta = st.selectbox(
                                "Selecione um registro para excluir:",
                                options=list(opcoes_mortas.keys()),
                                format_func=lambda x: opcoes_mortas[x],
                                index=None,
                                placeholder="Selecione um registro",
                                key="select_ave_morta"
                            )
                            mensagem_excluir_ave_morta = st.empty()
                            area_excluir_ave_morta = st.empty()
                            with area_excluir_ave_morta.container(), st.form("form_excluir_ave_morta", clear_on_submit=True):
                                if selected_id_morta is not None:
                                    st.warning("⚠️ Esta ação é irreversível e removerá permanentemente o registro de morte.")
                                    confirmar_morta = st.checkbox(
                                        "Sim, quero excluir permanentemente este registro.")
                                else:
                                    confirmar_morta = False
                                excluir_ave_morta = st.form_submit_button(
                                    "Excluir agora", type="primary", disabled=not confirmar_morta)

                                if excluir_ave_morta and selected_id_morta is not None:
                                    try:
                                        registrar_log("DELETE", "aves_mortas", selected_id_morta,
                                                    f"Excluiu registro de morte de {df_mortas[df_mortas['id']==selected_id_morta].iloc[0]['Quantidade']} aves")
                                        with engine.connect() as conn:
                                            conn.execute(text("""
                                                DELETE FROM aves_mortas
                                                WHERE id = :id AND username = :username
                                            """), {"id": selected_id_morta, "username": st.session_state.username})
                                            conn.commit()
                                        area_excluir_ave_morta.empty()
                                        mensagem_excluir_ave_morta.success("✅ Registro de morte excluído com sucesso!")
                                    except Exception as e:
                                        st.error(f"Erro ao excluir: {e}")
                    except Exception as e:
                        st.error(f"Erro ao carregar aves mortas: {e}")

                    # ==================== RESUMO ATUAL ====================
            st.divider()
            st.markdown("#### 📊 Resumo Atual de Aves por Galpão")

            total_aves_vivas = 0
            consumo_por_ave_kg = 0.115

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
                    total_aves_vivas += total_vivo
                    consumo_galpao_kg = total_vivo * consumo_por_ave_kg

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(f"{galpao} - Registradas", f"{total_reg} aves")
                    with col2:
                        st.metric(f"{galpao} - Mortas", f"{total_morto} aves")
                    with col3:
                        st.metric(f"{galpao} - Vivas", f"{total_vivo} aves")
                    with col4:
                        st.metric(f"{galpao} - Ração/dia", f"{consumo_galpao_kg:,.2f} kg", 
                                  help=f"Baseado em {consumo_por_ave_kg} kg/ave")

                except Exception as e:
                    st.error(f"Erro ao calcular resumo: {e}")

            # ----- Consumo total (opcional, mas útil) -----
            if total_aves_vivas > 0:
                consumo_total_kg = total_aves_vivas * consumo_por_ave_kg
                st.markdown("---")
                col_total1, col_total2 = st.columns(2)
                with col_total1:
                    st.metric("🐔 Total Geral de Aves Vivas", f"{total_aves_vivas} aves")
                with col_total2:
                    st.metric("🍽️ Consumo Total de Ração/dia", f"{consumo_total_kg:,.2f} kg")
            else:
                st.info("Nenhuma ave viva registrada no momento.")

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

                with st.form("form_registrar_ovos_quebrados", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        data_quebrados = st.date_input("📅 Data", value=datetime.now().date(),
                                                       format="DD/MM/YYYY", key="data_quebrados_reg")
                        galpao_quebrados = st.selectbox(
                            "🏠 Galpão", GALPOES, key="galpao_quebrados_reg")
                    with col2:
                        qtd_quebrados = st.number_input("🔨 Quantidade de Ovos Quebrados", min_value=1, step=1,
                                                        format="%d", key="qtd_quebrados_reg")

                    registrar_ovos_quebrados = st.form_submit_button(
                        "✅ Registrar Ovos Quebrados", type="primary", use_container_width=True)

                if registrar_ovos_quebrados:
                    if qtd_quebrados > 0:
                        chave_acao = "registrar_ovos_quebrados"
                        payload_acao = (st.session_state.username, data_quebrados, galpao_quebrados, qtd_quebrados)
                        if acao_repetida(chave_acao, payload_acao):
                            st.stop()
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
                        except Exception as e:
                            liberar_acao(chave_acao)
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

        # Converter colunas de quantidade para NUMERIC (aceitar decimais)
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE estoque ALTER COLUMN quantidade TYPE NUMERIC"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE venda_itens ALTER COLUMN quantidade TYPE NUMERIC"))
                conn.commit()
            except Exception:
                pass

        # Adicionar coluna numero_recibo se não existir
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE vendas ADD COLUMN numero_recibo TEXT"))
                conn.commit()
            except Exception:
                pass

        # ----- FUNÇÃO AUXILIAR PARA FORMATAÇÃO BR -----
        def fmt_br(valor):
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # ----- FUNÇÃO AUXILIAR PARA ATUALIZAR ESTOQUE (com tratamento None) -----
        def atualizar_estoque(produto_id, delta):
            """Atualiza a quantidade em estoque (soma delta). delta pode ser negativo (venda) ou positivo (devolução)."""
            with engine.connect() as conn:
                produto_id_int = int(produto_id)
                delta_float = float(delta) if delta is not None else 0.0

                existe = conn.execute(text("""
                    SELECT 1 FROM estoque WHERE username = :u AND produto_id = :p
                """), {"u": st.session_state.username, "p": produto_id_int}).fetchone()

                if existe:
                    conn.execute(text("""
                        UPDATE estoque 
                        SET quantidade = quantidade + :delta, data_atualizacao = CURRENT_TIMESTAMP
                        WHERE username = :u AND produto_id = :p
                    """), {"u": st.session_state.username, "p": produto_id_int, "delta": delta_float})
                else:
                    if delta_float < 0:
                        raise Exception("Estoque insuficiente e sem registro inicial.")
                    conn.execute(text("""
                        INSERT INTO estoque (username, produto_id, quantidade)
                        VALUES (:u, :p, :qtd)
                    """), {"u": st.session_state.username, "p": produto_id_int, "qtd": delta_float})
                conn.commit()

        # ----- FUNÇÃO AUXILIAR PARA VERIFICAR ESTOQUE (com tratamento None) -----
        def verificar_estoque(produto_id, quantidade_necessaria):
            try:
                with engine.connect() as conn:
                    qtd_atual = conn.execute(text("""
                        SELECT COALESCE(quantidade, 0) FROM estoque 
                        WHERE username = :u AND produto_id = :p
                    """), {"u": st.session_state.username, "p": int(produto_id)}).scalar()
                    qtd_atual = float(qtd_atual) if qtd_atual is not None else 0.0
                    quantidade_necessaria = float(quantidade_necessaria) if quantidade_necessaria is not None else 0.0
                    return qtd_atual >= quantidade_necessaria
            except Exception as e:
                st.error(f"Erro ao verificar estoque: {e}")
                return False

        fat_tabs = st.tabs([
            "🛒 Vendas",
            "📦 Estoque",
            "📝 Cadastros",
            "💰 Faturamento",
            "📋 Logs"
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

            # -------------------- NOVA VENDA COM CARRINHO --------------------
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
                .cart-item {
                    background-color: #ffffff;
                    border-radius: 12px;
                    padding: 0.8rem;
                    margin-bottom: 0.5rem;
                    border: 1px solid #e0e4e8;
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

                st.markdown("### 🛒 Registrar Nova Venda (Múltiplos Produtos)")
                st.caption("Adicione os produtos ao carrinho e finalize a venda")

                # Inicializar carrinho no session_state
                if "carrinho" not in st.session_state:
                    st.session_state.carrinho = []
                if "mostrar_confirmacao" not in st.session_state:
                    st.session_state.mostrar_confirmacao = False

                # Carregar dados
                df_clientes = pd.read_sql(text("SELECT id, nome FROM clientes WHERE username = :u ORDER BY nome"), engine,
                                          params={"u": st.session_state.username})
                df_produtos = pd.read_sql(text("SELECT id, nome, preco_atual FROM produtos WHERE username = :u ORDER BY nome"), engine,
                                          params={"u": st.session_state.username})
                df_formas = pd.read_sql(text("SELECT id, nome FROM formas_pagamento WHERE (username = :u OR username IS NULL) AND ativo = TRUE ORDER BY nome"),
                                        engine, params={"u": st.session_state.username})

                # ==================== MODO CONFIRMAÇÃO ====================
                if st.session_state.get("mostrar_confirmacao", False):
                    with st.container():
                        st.markdown("### ✅ Confirmar Venda")
                        st.markdown("Verifique os dados da venda e os itens abaixo")
                        st.divider()

                        dados_venda = st.session_state.get("dados_venda", {})
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**📅 Data da Venda**  \n{dados_venda.get('data_venda', '').strftime('%d/%m/%Y') if dados_venda.get('data_venda') else ''}")
                            st.markdown(f"**🧾 N° Recibo**  \n{dados_venda.get('numero_recibo', 'Não informado')}")
                            st.markdown(f"**👤 Cliente**  \n{dados_venda.get('cliente_nome', '')}")
                            st.markdown(f"**💳 Pagamento**  \n{dados_venda.get('forma_nome', '')}")
                        with col2:
                            st.markdown(f"**💰 Valor Total**  \n{fmt_br(dados_venda.get('valor_total', 0))}")
                            st.markdown(f"**💵 Valor Pago**  \n{fmt_br(dados_venda.get('valor_pago', 0))}")
                            st.markdown(f"**🔻 Ficará Devendo**  \n{fmt_br(dados_venda.get('valor_devendo', 0))}")

                        st.divider()
                        st.markdown("#### 🛒 Itens da Venda")
                        for item in st.session_state.get("carrinho", []):
                            st.markdown(f"- **{item['produto_nome']}** | Qtd: {item['quantidade']} | Preço unit.: {fmt_br(item['preco_unit'])} | Desc. unit.: {fmt_br(item['desconto_unit'])} | Subtotal: {fmt_br(item['subtotal'])}")

                        if dados_venda.get('observacoes'):
                            st.info(f"**📝 Observações:** {dados_venda['observacoes']}")

                        st.divider()
                        st.warning("⚠️ Confirme os dados. Após salvar, não será possível editar diretamente.")

                        col_btn1, col_btn2 = st.columns(2)
                        
                        with col_btn1:
                            if st.button("✅ Confirmar e Registrar", type="primary", use_container_width=True):
                                chave_acao = "confirmar_venda"
                                payload_acao = (
                                    st.session_state.username,
                                    dados_venda.get("cliente_id"),
                                    dados_venda.get("data_venda"),
                                    dados_venda.get("forma_id"),
                                    dados_venda.get("valor_total"),
                                    dados_venda.get("valor_pago"),
                                    dados_venda.get("numero_recibo"),
                                    tuple(
                                        (item.get("produto_id"), item.get("quantidade"), item.get("preco_unit"), item.get("desconto_unit"))
                                        for item in st.session_state.get("carrinho", [])
                                    )
                                )
                                if acao_repetida(chave_acao, payload_acao, intervalo=20):
                                    st.stop()
                                try:
                                    with engine.connect() as conn:
                                        with conn.begin():
                                            venda_result = conn.execute(text("""
                                                INSERT INTO vendas (username, cliente_id, data_venda, forma_pagamento_id, valor_total, valor_pago, observacoes, numero_recibo)
                                                VALUES (:u, :cliente_id, :data_venda, :forma_id, :valor_total, :valor_pago, :obs, :recibo)
                                                RETURNING id
                                            """), {
                                                "u": st.session_state.username,
                                                "cliente_id": dados_venda['cliente_id'],
                                                "data_venda": dados_venda['data_venda'],
                                                "forma_id": dados_venda['forma_id'],
                                                "valor_total": dados_venda['valor_total'],
                                                "valor_pago": dados_venda['valor_pago'],
                                                "obs": dados_venda.get('observacoes', ''),
                                                "recibo": dados_venda.get('numero_recibo', '')
                                            })
                                            venda_id = venda_result.fetchone()[0]
                                            registrar_log("INSERT", "vendas", venda_id, f"Nova venda para {dados_venda['cliente_nome']} no valor de {fmt_br(dados_venda['valor_total'])}")

                                            for item in st.session_state.get("carrinho", []):
                                                conn.execute(text("""
                                                    INSERT INTO venda_itens (venda_id, produto_id, quantidade, preco_unitario, desconto_unitario, subtotal)
                                                    VALUES (:venda_id, :produto_id, :qtd, :preco, :desconto, :subtotal)
                                                """), {
                                                    "venda_id": venda_id,
                                                    "produto_id": item['produto_id'],
                                                    "qtd": item['quantidade'],
                                                    "preco": item['preco_unit'],
                                                    "desconto": item['desconto_unit'],
                                                    "subtotal": item['subtotal']
                                                })
                                                atualizar_estoque(item['produto_id'], -item['quantidade'])

                                    # Gerar o PDF do recibo
                                    pdf_bytes = gerar_pdf_recibo_reportlab(
                                        dados_venda=dados_venda,
                                        itens=st.session_state.get("carrinho", []),
                                        numero_recibo=dados_venda.get('numero_recibo', 'N/A')
                                    )

                                    # Envio automático por WhatsApp
                                    if dados_venda.get('enviar_whatsapp', False):
                                        with engine.connect() as conn:
                                            telefone = conn.execute(
                                                text("SELECT telefone FROM clientes WHERE id = :id"),
                                                {"id": dados_venda['cliente_id']}
                                            ).scalar()
                                        if telefone:
                                            sucesso, msg = enviar_pdf_whatsapp(
                                                telefone_cliente=telefone,
                                                pdf_bytes=pdf_bytes,
                                                nome_cliente=dados_venda['cliente_nome'],
                                                numero_recibo=dados_venda.get('numero_recibo', 'N/A')
                                            )
                                            if sucesso:
                                                st.success(f"✅ {msg}")
                                            else:
                                                st.warning(f"⚠️ WhatsApp: {msg}")
                                        else:
                                            st.info("ℹ️ Cliente sem telefone cadastrado. Recibo não enviado.")

                                    # Armazena dados para pós-venda
                                    st.session_state.venda_finalizada = True
                                    st.session_state.pdf_bytes = pdf_bytes
                                    st.session_state.dados_venda_pos = dados_venda
                                    
                                    st.balloons()
                                    st.success("✅ Venda registrada com sucesso e estoque atualizado!")
                                    
                                    # Limpa o estado de confirmação e carrinho
                                    st.session_state.mostrar_confirmacao = False
                                    st.session_state.carrinho = []

                                except Exception as e:
                                    liberar_acao(chave_acao)
                                    st.error(f"Erro ao registrar venda: {e}")
                        
                        with col_btn2:
                            if st.button("✏️ Voltar e editar", use_container_width=True):
                                st.session_state.mostrar_confirmacao = False
                                st.rerun()

                # ==================== MODO CARRINHO (NOVA VENDA) ====================
                elif not st.session_state.get("venda_finalizada", False):
                    st.markdown('<div class="card-form">', unsafe_allow_html=True)

                    col1, col2 = st.columns(2)
                    with col1:
                        data_venda = st.date_input("📅 Data da Venda", value=datetime.now().date(), format="DD/MM/YYYY", key="data_venda")
                        cliente_nome = st.selectbox("👤 Cliente *", df_clientes['nome'].tolist(), key="venda_cliente")
                        cliente_id = int(df_clientes[df_clientes['nome'] == cliente_nome].iloc[0]['id'])
                    with col2:
                        forma_nome = st.selectbox("💳 Forma de Pagamento *", df_formas['nome'].tolist(), key="venda_forma")
                        forma_id = int(df_formas[df_formas['nome'] == forma_nome].iloc[0]['id'])
                        valor_pago = st.number_input("💰 Valor Pago agora (R$)", min_value=0.0, step=0.01, value=0.0, format="%.2f", key="venda_valor_pago")

                    st.divider()
                    st.markdown("#### ➕ Adicionar Produto ao Carrinho")
                    col_add1, col_add2, col_add3, col_add4 = st.columns([2, 1, 1, 1])
                    with col_add1:
                        produto_nome = st.selectbox("Produto", df_produtos['nome'].tolist(), key="produto_carrinho")
                        produto_row = df_produtos[df_produtos['nome'] == produto_nome].iloc[0]
                        produto_id = int(produto_row['id'])
                        preco_unit = float(produto_row['preco_atual'])
                    with col_add2:
                        quantidade = st.number_input("Quantidade", min_value=0.1, step=0.1, value=1.0, format="%.2f", key="qtd_carrinho")
                    with col_add3:
                        desconto_unit = st.number_input("Desconto (R$)", min_value=0.0, step=0.01, value=0.0, format="%.2f", key="desc_carrinho")
                    with col_add4:
                        if st.button("➕ Adicionar ao Carrinho", use_container_width=True):
                            preco_com_desconto = max(0.0, preco_unit - desconto_unit)
                            subtotal = quantidade * preco_com_desconto
                            st.session_state.carrinho.append({
                                "produto_id": produto_id,
                                "produto_nome": produto_nome,
                                "quantidade": quantidade,
                                "preco_unit": preco_unit,
                                "desconto_unit": desconto_unit,
                                "subtotal": subtotal
                            })

                    st.markdown(f'<div class="preco-unitario" style="margin-top: 0;">💰 Preço unitário: {fmt_br(preco_unit)}</div>', unsafe_allow_html=True)

                    st.divider()
                    st.markdown("#### 🛒 Carrinho de Produtos")
                    if not st.session_state.get("carrinho", []):
                        st.info("Nenhum produto adicionado. Adicione produtos ao carrinho.")
                    else:
                        df_carrinho = pd.DataFrame(st.session_state.carrinho)
                        df_display = df_carrinho[["produto_nome", "quantidade", "preco_unit", "desconto_unit", "subtotal"]].copy()
                        df_display = df_display.rename(columns={
                            "produto_nome": "Produto",
                            "quantidade": "Qtd",
                            "preco_unit": "Preço Unit.",
                            "desconto_unit": "Desc. Unit.",
                            "subtotal": "Subtotal"
                        })
                        df_display["Preço Unit."] = df_display["Preço Unit."].apply(fmt_br)
                        df_display["Desc. Unit."] = df_display["Desc. Unit."].apply(fmt_br)
                        df_display["Subtotal"] = df_display["Subtotal"].apply(fmt_br)
                        st.dataframe(df_display, use_container_width=True, hide_index=True)

                        st.markdown("**Remover item do carrinho:**")
                        item_remover = st.selectbox("Selecione o produto para remover", df_carrinho["produto_nome"].tolist(), key="remover_item")
                        if st.button("🗑️ Remover Produto", use_container_width=True):
                            st.session_state.carrinho = [item for item in st.session_state.carrinho if item["produto_nome"] != item_remover]
                            st.rerun()

                    st.divider()
                    valor_total_carrinho = sum(item["subtotal"] for item in st.session_state.get("carrinho", []))
                    valor_devendo = max(0, valor_total_carrinho - valor_pago)

                    col_r1, col_r2, col_r3 = st.columns(3)
                    with col_r1:
                        st.metric("💰 Total do Carrinho", fmt_br(valor_total_carrinho))
                    with col_r2:
                        st.metric("💵 Valor Pago", fmt_br(valor_pago))
                    with col_r3:
                        st.metric("🔻 Ficará Devendo", fmt_br(valor_devendo))

                    numero_recibo = st.text_input("🧾 N° do Recibo (opcional)", key="venda_recibo")
                    observacoes = st.text_area("📝 Observações (opcional)", key="venda_obs", placeholder="Ex: Entrega agendada, troco, etc.")
                    enviar_whatsapp = st.checkbox("📱 Enviar recibo por WhatsApp", value=True, key="envia_whats")

                    st.markdown('</div>', unsafe_allow_html=True)

                    if st.button("💸 Finalizar Venda", type="primary", use_container_width=True, disabled=len(st.session_state.get("carrinho", [])) == 0):
                        st.session_state.dados_venda = {
                            "cliente_id": cliente_id,
                            "cliente_nome": cliente_nome,
                            "data_venda": data_venda,
                            "forma_id": forma_id,
                            "forma_nome": forma_nome,
                            "valor_pago": valor_pago,
                            "valor_total": valor_total_carrinho,
                            "valor_devendo": valor_devendo,
                            "observacoes": observacoes,
                            "numero_recibo": numero_recibo,
                            "enviar_whatsapp": enviar_whatsapp
                        }
                        st.session_state.mostrar_confirmacao = True
                        st.rerun()

                # ==================== BOTÕES DE PÓS-VENDA ====================
                if st.session_state.get("venda_finalizada", False):
                    st.divider()
                    st.markdown("### ✅ Venda concluída com sucesso!")
                    
                    col_download, col_finalizar = st.columns(2)
                    with col_download:
                        st.download_button(
                            label="📄 Baixar Recibo PDF",
                            data=st.session_state.pdf_bytes,
                            file_name=f"recibo_{st.session_state.dados_venda_pos.get('numero_recibo', 'venda')}.pdf",
                            mime="application/pdf"
                        )
                    with col_finalizar:
                        if st.button("✅ Finalizar e fazer nova venda", type="primary", use_container_width=True):
                            # Limpa tudo
                            st.session_state.carrinho = []
                            st.session_state.mostrar_confirmacao = False
                            st.session_state.venda_finalizada = False
                            st.session_state.pop("pdf_bytes", None)
                            st.session_state.pop("dados_venda", None)
                            st.session_state.pop("dados_venda_pos", None)
                            st.rerun()

            # -------------------- REGISTROS DE VENDAS --------------------
            with vendas_tabs[1]:
                st.markdown("#### 📋 Histórico de Vendas")
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
                        clientes_lista = ["Todos"] + df_clientes_reg['nome'].tolist()
                    except:
                        clientes_lista = ["Todos"]
                    cliente_filtro = st.selectbox("Cliente", clientes_lista, key="reg_cliente")
                with col4:
                    status_filtro = st.selectbox("Status", ["Todas", "Quitadas", "Com Pendência"], key="reg_status")
                busca = st.text_input("Buscar por nome do cliente ou produto", key="reg_busca")

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
                        st.metric("Valor Total", fmt_br(resumo[1]))
                    with col_r3:
                        st.metric("Valor Recebido", fmt_br(resumo[2]))
                    with col_r4:
                        st.metric("Valor Pendente", fmt_br(resumo[3]), delta_color="inverse")
                except Exception as e:
                    st.error(f"Erro ao carregar resumo: {e}")

                st.divider()
                st.markdown("#### Histórico de Vendas")
                try:
                    query = """
                        SELECT
                            v.id,
                            v.data_venda,
                            v.numero_recibo,
                            c.nome as cliente,
                            COALESCE(
                                STRING_AGG(
                                    CONCAT(
                                        COALESCE(p.nome, 'Produto sem nome'),
                                        ' (',
                                        ROUND(vi.quantidade::numeric, 2),
                                        ' un)'
                                    ),
                                    ', ' ORDER BY p.nome
                                ),
                                'Sem produtos'
                            ) as produtos,
                            COALESCE(SUM(vi.subtotal), 0) as valor_total,
                            v.valor_pago,
                            (COALESCE(SUM(vi.subtotal), 0) - v.valor_pago) as valor_devendo,
                            v.observacoes
                        FROM vendas v
                        JOIN clientes c ON v.cliente_id = c.id
                        LEFT JOIN venda_itens vi ON v.id = vi.venda_id
                        LEFT JOIN produtos p ON vi.produto_id = p.id
                        WHERE v.username = :u
                            AND v.data_venda BETWEEN :inicio AND :fim
                    """
                    params = {"u": st.session_state.username, "inicio": data_inicio, "fim": data_fim}

                    if cliente_filtro != "Todos":
                        query += " AND c.nome = :cliente"
                        params["cliente"] = cliente_filtro

                    having_clause = ""
                    if status_filtro == "Quitadas":
                        having_clause = " HAVING (COALESCE(SUM(vi.subtotal), 0) - v.valor_pago) <= 0"
                    elif status_filtro == "Com Pendência":
                        having_clause = " HAVING (COALESCE(SUM(vi.subtotal), 0) - v.valor_pago) > 0"

                    if busca:
                        query += " AND (c.nome ILIKE :busca OR p.nome ILIKE :busca)"
                        params["busca"] = f"%{busca}%"

                    query += f"""
                        GROUP BY v.id, v.data_venda, v.numero_recibo, c.nome, v.valor_pago, v.observacoes
                        {having_clause}
                        ORDER BY v.data_venda DESC
                    """
                    df_vendas = pd.read_sql(text(query), engine, params=params)

                    if df_vendas.empty:
                        st.info("Nenhuma venda encontrada.")
                    else:
                        df_display = df_vendas.copy()
                        df_display = df_display.rename(columns={
                            "data_venda": "Data",
                            "numero_recibo": "N° Recibo",
                            "cliente": "Cliente",
                            "produtos": "Produtos",
                            "valor_total": "Valor Total",
                            "valor_pago": "Valor Pago",
                            "valor_devendo": "Saldo Devedor",
                            "observacoes": "Observações"
                        })
                        df_display['Data'] = pd.to_datetime(df_display['Data']).dt.strftime('%d/%m/%Y')
                        df_display['Valor Total'] = df_display['Valor Total'].apply(fmt_br)
                        df_display['Valor Pago'] = df_display['Valor Pago'].apply(fmt_br)
                        df_display['Saldo Devedor'] = df_display['Saldo Devedor'].apply(lambda x: fmt_br(max(0, x)))

                        st.dataframe(
                            df_display[["Data", "Cliente", "N° Recibo", "Produtos", "Valor Total", "Valor Pago", "Saldo Devedor"]],
                            width='stretch', hide_index=True,
                            column_config={
                                "Data": st.column_config.TextColumn("📅 Data", width="small"),
                                "Cliente": st.column_config.TextColumn("👤 Cliente", width="medium"),
                                "N° Recibo": st.column_config.TextColumn("🧾 N° Recibo", width="small"),
                                "Produtos": st.column_config.TextColumn("📦 Produtos", width="medium"),
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
                    data_inicio = st.date_input("Data Inicial", value=datetime.now().date() - pd.Timedelta(days=30),
                                                format="DD/MM/YYYY", key="fin_data_inicio")
                with col_f2:
                    data_fim = st.date_input("Data Final", value=datetime.now().date(),
                                             format="DD/MM/YYYY", key="fin_data_fim")
                with col_f3:
                    try:
                        df_cf = pd.read_sql(text("SELECT DISTINCT c.nome FROM vendas v JOIN clientes c ON v.cliente_id=c.id WHERE v.username=:u"),
                                            engine, params={"u": st.session_state.username})
                        clientes_lista = ["Todos"] + df_cf['nome'].tolist()
                    except:
                        clientes_lista = ["Todos"]
                    cliente_filtro = st.selectbox("Cliente", clientes_lista, key="fin_cliente_filtro")

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
                        st.metric("Total em Aberto", fmt_br(resumo[1]), delta_color="inverse")
                except Exception as e:
                    st.error(f"Erro: {e}")

                st.divider()
                st.markdown("#### Todas as Vendas do Período")
                try:
                    query = """
                        SELECT
                            v.id,
                            v.data_venda,
                            v.numero_recibo,
                            c.nome as cliente,
                            COALESCE(
                                STRING_AGG(
                                    CONCAT(
                                        COALESCE(p.nome, 'Produto sem nome'),
                                        ' (',
                                        ROUND(vi.quantidade::numeric, 2),
                                        ' un)'
                                    ),
                                    ', ' ORDER BY p.nome
                                ),
                                'Sem produtos'
                            ) as produtos,
                            COALESCE(SUM(vi.subtotal), 0) as valor_total,
                            v.valor_pago,
                            (COALESCE(SUM(vi.subtotal), 0) - v.valor_pago) as valor_devendo,
                            v.observacoes
                        FROM vendas v
                        JOIN clientes c ON v.cliente_id = c.id
                        LEFT JOIN venda_itens vi ON v.id = vi.venda_id
                        LEFT JOIN produtos p ON vi.produto_id = p.id
                        WHERE v.username = :u
                            AND v.data_venda BETWEEN :inicio AND :fim
                    """
                    params = {"u": st.session_state.username, "inicio": data_inicio, "fim": data_fim}
                    if cliente_filtro != "Todos":
                        query += " AND c.nome = :cliente"
                        params["cliente"] = cliente_filtro
                    query += """
                        GROUP BY v.id, v.data_venda, c.nome, v.numero_recibo, v.valor_pago, v.observacoes
                        ORDER BY v.data_venda DESC
                    """
                    df_vendas = pd.read_sql(text(query), engine, params=params)

                    if df_vendas.empty:
                        st.info("Nenhuma venda no período.")
                    else:
                        df_display = df_vendas.copy()
                        df_display = df_display.rename(columns={
                            "data_venda": "Data",
                            "cliente": "Cliente",
                            "produtos": "Produtos",
                            "valor_total": "Valor Total",
                            "valor_pago": "Valor Pago",
                            "valor_devendo": "Saldo Pendente",
                            "numero_recibo": "N° Recibo"
                        })
                        df_display['Data'] = pd.to_datetime(df_display['Data']).dt.strftime('%d/%m/%Y')
                        df_display['Valor Total'] = df_display['Valor Total'].apply(fmt_br)
                        df_display['Valor Pago'] = df_display['Valor Pago'].apply(fmt_br)
                        df_display['Saldo Pendente'] = df_display['Saldo Pendente'].apply(lambda x: fmt_br(max(0, x)))

                        st.dataframe(
                            df_display[["Data", "Cliente", "Produtos", "N° Recibo", "Valor Total", "Valor Pago", "Saldo Pendente"]],
                            width='stretch', hide_index=True,
                            column_config={
                                "Data": st.column_config.TextColumn("📅 Data", width="small"),
                                "Cliente": st.column_config.TextColumn("👤 Cliente", width="medium"),
                                "N° Recibo": st.column_config.TextColumn("🧾 N° do Recibo", width="small"),
                                "Produtos": st.column_config.TextColumn("📦 Produtos", width="medium"),
                                "Valor Total": st.column_config.TextColumn("💰 Valor Total", width="small"),
                                "Valor Pago": st.column_config.TextColumn("💵 Valor Pago", width="small"),
                                "Saldo Pendente": st.column_config.TextColumn("⚠️ Saldo Pendente", width="small")
                            }
                        )

                        st.markdown("---")
                        st.markdown("**Selecionar Venda para Gerenciar**")

                        def fmt_venda(x):
                            row = df_vendas[df_vendas['id'] == x].iloc[0]
                            data_str = pd.to_datetime(row['data_venda']).strftime('%d/%m/%Y')
                            valor_total = row['valor_total']
                            valor_devendo = max(0, row['valor_devendo'])
                            return f"#{x} | {data_str} | {row['cliente']} | Total: {fmt_br(valor_total)} | Devendo: {fmt_br(valor_devendo)}"
                        venda_id = st.selectbox("Escolha uma venda:", options=df_vendas['id'].tolist(),
                                                format_func=fmt_venda, key="fin_select_venda")
                        venda = df_vendas[df_vendas['id'] == venda_id].iloc[0]
                        valor_devendo_atual = max(0, float(venda['valor_devendo']))
                        valor_pago_atual = float(venda['valor_pago'])

                        tab_pag, tab_edit, tab_del = st.tabs(["💰 Registrar Pagamento", "✏️ Editar Venda", "🗑️ Excluir Venda"])

                        with tab_pag:
                            valor_pendente_br = fmt_br(valor_devendo_atual)
                            st.info(f"💰 **Valor pendente:** {valor_pendente_br}")
                            with st.form("form_receber_pagamento", clear_on_submit=True):
                                
                                valor_recebido = st.number_input(
                                    "Valor Recebido agora (R$)",
                                    min_value=0.0,
                                    max_value=float(valor_devendo_atual),
                                    step=0.01,
                                    format="%.2f",
                                    value=0.0
                                )
                                if st.form_submit_button("Confirmar Recebimento"):
                                    if valor_recebido <= 0:
                                        st.error("Informe um valor maior que zero.")
                                    else:
                                        chave_acao = "registrar_pagamento_venda"
                                        payload_acao = (st.session_state.username, venda_id, valor_recebido)
                                        if not acao_repetida(chave_acao, payload_acao):
                                            try:
                                                novo_pago = valor_pago_atual + valor_recebido
                                                with engine.connect() as conn:
                                                    conn.execute(text("UPDATE vendas SET valor_pago = :novo WHERE id = :id"),
                                                                 {"novo": novo_pago, "id": venda_id})
                                                    conn.commit()
                                                st.success(f"Pagamento de {fmt_br(valor_recebido)} registrado!")
                                            except Exception as e:
                                                liberar_acao(chave_acao)
                                                st.error(f"Erro ao registrar pagamento: {e}")

                        with tab_edit:
                            st.warning("⚠️ Editar uma venda afetará o estoque. Você pode modificar produtos, quantidades, descontos e outros dados.")

                            venda_atual = pd.read_sql(
                                text("SELECT cliente_id, data_venda, forma_pagamento_id, valor_pago, observacoes, numero_recibo FROM vendas WHERE id = :id"),
                                engine, params={"id": venda_id}
                            ).iloc[0]

                            itens_atuais = pd.read_sql(
                                text("""
                                    SELECT vi.id as item_id, vi.produto_id, p.nome as produto_nome, 
                                        vi.quantidade, vi.preco_unitario, vi.desconto_unitario, vi.subtotal
                                    FROM venda_itens vi
                                    JOIN produtos p ON vi.produto_id = p.id
                                    WHERE vi.venda_id = :vid
                                """), engine, params={"vid": venda_id}
                            ).to_dict('records')

                            df_clientes_edit = pd.read_sql(text("SELECT id, nome FROM clientes WHERE username = :u ORDER BY nome"),
                                                           engine, params={"u": st.session_state.username})
                            df_produtos_edit = pd.read_sql(text("SELECT id, nome, preco_atual FROM produtos WHERE username = :u ORDER BY nome"),
                                                           engine, params={"u": st.session_state.username})
                            df_formas_edit = pd.read_sql(text("SELECT id, nome FROM formas_pagamento WHERE (username = :u OR username IS NULL) AND ativo = TRUE ORDER BY nome"),
                                                         engine, params={"u": st.session_state.username})

                            if f"edit_items_{venda_id}" not in st.session_state:
                                st.session_state[f"edit_items_{venda_id}"] = itens_atuais.copy()
                                st.session_state[f"edit_removed_{venda_id}"] = []

                            items_edit = st.session_state[f"edit_items_{venda_id}"]

                            st.markdown("#### 📋 Dados da Venda")
                            col1, col2 = st.columns(2)
                            with col1:
                                nova_data = st.date_input("📅 Data da Venda", value=venda_atual['data_venda'], format="DD/MM/YYYY")
                                novo_cliente_id = st.selectbox(
                                    "👤 Cliente",
                                    options=df_clientes_edit['id'].tolist(),
                                    format_func=lambda x: df_clientes_edit[df_clientes_edit['id'] == x].iloc[0]['nome'],
                                    index=df_clientes_edit[df_clientes_edit['id'] == venda_atual['cliente_id']].index[0] if venda_atual['cliente_id'] in df_clientes_edit['id'].values else 0
                                )
                            with col2:
                                nova_forma_id = st.selectbox(
                                    "💳 Forma de Pagamento",
                                    options=df_formas_edit['id'].tolist(),
                                    format_func=lambda x: df_formas_edit[df_formas_edit['id'] == x].iloc[0]['nome'],
                                    index=df_formas_edit[df_formas_edit['id'] == venda_atual['forma_pagamento_id']].index[0] if venda_atual['forma_pagamento_id'] in df_formas_edit['id'].values else 0
                                )
                                st.caption("Use **ponto** como separador decimal (ex: 100.50)")
                                novo_valor_pago = st.number_input("💰 Valor Pago (R$)", min_value=0.0, value=float(venda_atual['valor_pago']), step=0.01, format="%.2f")
                                novo_recibo = st.text_input("🧾 N° Recibo", value=venda_atual.get('numero_recibo', ''))

                            novas_obs = st.text_area("📝 Observações", value=venda_atual.get('observacoes', '') or '')

                            st.divider()
                            st.markdown("#### 🛒 Itens da Venda")
                            st.caption("Você pode editar os itens existentes, remover ou adicionar novos produtos.")

                            for idx, item in enumerate(items_edit):
                                with st.container():
                                    st.markdown(f"**Item {idx+1}**")
                                    col_a, col_b, col_c, col_d, col_e = st.columns([2, 1, 1, 1, 0.5])
                                    with col_a:
                                        novo_produto_nome = st.selectbox(
                                            "Produto",
                                            options=df_produtos_edit['nome'].tolist(),
                                            index=df_produtos_edit[df_produtos_edit['id'] == item['produto_id']].index[0] if item['produto_id'] in df_produtos_edit['id'].values else 0,
                                            key=f"edit_prod_{venda_id}_{idx}"
                                        )
                                        novo_produto_id = int(df_produtos_edit[df_produtos_edit['nome'] == novo_produto_nome].iloc[0]['id'])
                                        novo_preco_unit = float(df_produtos_edit[df_produtos_edit['id'] == novo_produto_id].iloc[0]['preco_atual'])
                                    with col_b:
                                        nova_qtd = st.number_input("Qtd", min_value=0.1, value=float(item['quantidade']), step=0.1, format="%.2f", key=f"edit_qtd_{venda_id}_{idx}")
                                    with col_c:
                                        novo_desc_unit = st.number_input("Desc. unit. (R$)", min_value=0.0, value=float(item.get('desconto_unitario', 0)), step=0.01, format="%.2f", key=f"edit_desc_{venda_id}_{idx}")
                                    with col_d:
                                        preco_final = novo_preco_unit - novo_desc_unit
                                        subtotal = nova_qtd * max(0, preco_final)
                                        st.metric("Subtotal", fmt_br(subtotal))
                                    with col_e:
                                        if st.button("🗑️", key=f"remove_item_{venda_id}_{idx}"):
                                            st.session_state[f"edit_removed_{venda_id}"].append(items_edit.pop(idx))
                                            st.rerun()

                                    item['produto_id'] = novo_produto_id
                                    item['produto_nome'] = novo_produto_nome
                                    item['quantidade'] = nova_qtd
                                    item['preco_unitario'] = novo_preco_unit
                                    item['desconto_unitario'] = novo_desc_unit
                                    item['subtotal'] = subtotal
                                    st.markdown("---")

                            st.markdown("#### ➕ Adicionar novo produto")
                            col_add1, col_add2, col_add3, col_add4 = st.columns([2, 1, 1, 1])
                            with col_add1:
                                novo_produto_nome = st.selectbox("Produto", df_produtos_edit['nome'].tolist(), key="add_prod_edit")
                                novo_produto_row = df_produtos_edit[df_produtos_edit['nome'] == novo_produto_nome].iloc[0]
                                novo_produto_id = int(novo_produto_row['id'])
                                novo_preco_unit = float(novo_produto_row['preco_atual'])
                            with col_add2:
                                nova_qtd = st.number_input("Quantidade", min_value=0.1, step=0.1, value=1.0, format="%.2f", key="add_qtd_edit")
                            with col_add3:
                                novo_desc_unit = st.number_input("Desconto unit. (R$)", min_value=0.0, step=0.01, value=0.0, format="%.2f", key="add_desc_edit")
                            with col_add4:
                                if st.button("➕ Adicionar", key="add_item_btn_edit", use_container_width=True):
                                    preco_final = novo_preco_unit - novo_desc_unit
                                    subtotal = nova_qtd * max(0, preco_final)
                                    items_edit.append({
                                        "item_id": None,
                                        "produto_id": novo_produto_id,
                                        "produto_nome": novo_produto_nome,
                                        "quantidade": nova_qtd,
                                        "preco_unitario": novo_preco_unit,
                                        "desconto_unitario": novo_desc_unit,
                                        "subtotal": subtotal
                                    })
                                    st.rerun()

                            st.divider()
                            total_carrinho = sum(item['subtotal'] for item in items_edit)
                            novo_valor_devendo = max(0, total_carrinho - novo_valor_pago)

                            colr1, colr2, colr3 = st.columns(3)
                            with colr1:
                                st.metric("💰 Novo Valor Total", fmt_br(total_carrinho))
                            with colr2:
                                st.metric("💵 Valor Pago", fmt_br(novo_valor_pago))
                            with colr3:
                                st.metric("⚠️ Novo Saldo Devedor", fmt_br(novo_valor_devendo))

                            if st.button("💾 Salvar Todas as Alterações", type="primary", use_container_width=True):
                                try:
                                    with engine.connect() as conn:
                                        with conn.begin():
                                            for item_removido in st.session_state[f"edit_removed_{venda_id}"]:
                                                atualizar_estoque(item_removido['produto_id'], item_removido['quantidade'])

                                            itens_antigos_dict = {item['item_id']: item for item in itens_atuais if item.get('item_id')}
                                            for item_novo in items_edit:
                                                if item_novo.get('item_id') is not None:
                                                    item_antigo = itens_antigos_dict.get(item_novo['item_id'])
                                                    if item_antigo:
                                                        diff_qtd = item_novo['quantidade'] - item_antigo['quantidade']
                                                        if diff_qtd != 0:
                                                            if diff_qtd > 0:
                                                                if not verificar_estoque(item_novo['produto_id'], diff_qtd):
                                                                    raise Exception(f"Estoque insuficiente para o produto {item_novo['produto_nome']} (necessário: {diff_qtd})")
                                                                atualizar_estoque(item_novo['produto_id'], -diff_qtd)
                                                            else:
                                                                atualizar_estoque(item_novo['produto_id'], -diff_qtd)
                                                else:
                                                    if not verificar_estoque(item_novo['produto_id'], item_novo['quantidade']):
                                                        raise Exception(f"Estoque insuficiente para o produto {item_novo['produto_nome']} (necessário: {item_novo['quantidade']})")
                                                    atualizar_estoque(item_novo['produto_id'], -item_novo['quantidade'])

                                            conn.execute(text("""
                                                UPDATE vendas
                                                SET data_venda = :data,
                                                    cliente_id = :cliente_id,
                                                    forma_pagamento_id = :forma_id,
                                                    valor_total = :total,
                                                    valor_pago = :valor_pago,
                                                    observacoes = :obs,
                                                    numero_recibo = :recibo
                                                WHERE id = :id
                                            """), {
                                                "data": nova_data,
                                                "cliente_id": novo_cliente_id,
                                                "forma_id": nova_forma_id,
                                                "total": total_carrinho,
                                                "valor_pago": novo_valor_pago,
                                                "obs": novas_obs,
                                                "recibo": novo_recibo,
                                                "id": venda_id
                                            })

                                            conn.execute(text("DELETE FROM venda_itens WHERE venda_id = :vid"), {"vid": venda_id})
                                            for item in items_edit:
                                                conn.execute(text("""
                                                    INSERT INTO venda_itens (venda_id, produto_id, quantidade, preco_unitario, desconto_unitario, subtotal)
                                                    VALUES (:vid, :prod_id, :qtd, :preco, :desc, :subtotal)
                                                """), {
                                                    "vid": venda_id,
                                                    "prod_id": item['produto_id'],
                                                    "qtd": item['quantidade'],
                                                    "preco": item['preco_unitario'],
                                                    "desc": item['desconto_unitario'],
                                                    "subtotal": item['subtotal']
                                                })

                                    del st.session_state[f"edit_items_{venda_id}"]
                                    del st.session_state[f"edit_removed_{venda_id}"]

                                    st.success("✅ Venda atualizada e estoque ajustado com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao editar venda: {e}")

                        with tab_del:
                            if valor_pago_atual > 0:
                                st.warning(f"⚠️ Esta venda já possui {fmt_br(valor_pago_atual)} em pagamentos.")
                            st.markdown("**Tem certeza que deseja excluir esta venda?**")
                            st.error("Esta ação não pode ser desfeita.")
                            confirm = st.checkbox("Entendo que é irreversível", key=f"confirm_del_{venda_id}")

                            if st.button("🗑️ Excluir Venda Permanentemente", type="primary", disabled=not confirm):
                                try:
                                    registrar_log("DELETE", "vendas", venda_id, f"Excluiu venda do cliente {venda['cliente']} no valor de {fmt_br(venda['valor_total'])}")
                                    with engine.connect() as conn:
                                        with conn.begin():
                                            itens = conn.execute(text("SELECT produto_id, quantidade FROM venda_itens WHERE venda_id = :vid"), {"vid": venda_id}).fetchall()
                                            for item in itens:
                                                atualizar_estoque(item[0], item[1])
                                            conn.execute(text("DELETE FROM venda_itens WHERE venda_id = :vid"), {"vid": venda_id})
                                            conn.execute(text("DELETE FROM vendas WHERE id = :id"), {"id": venda_id})
                                    st.success("Venda excluída e estoque restaurado com sucesso!")
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
                with engine.connect() as conn:
                    produto_id_int = int(produto_id)
                    existe = conn.execute(text("""
                        SELECT 1 FROM estoque WHERE username = :u AND produto_id = :p
                    """), {"u": st.session_state.username, "p": produto_id_int}).fetchone()
                    if existe:
                        conn.execute(text("""
                            UPDATE estoque 
                            SET quantidade = quantidade + :qtd, data_atualizacao = CURRENT_TIMESTAMP
                            WHERE username = :u AND produto_id = :p
                        """), {"u": st.session_state.username, "p": produto_id_int, "qtd": quantidade_adicionar})
                    else:
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
                    with st.form("form_adicionar_estoque", clear_on_submit=True):
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
                                min_value=0.0, step=0.1, value=0.0, format="%.2f",
                                key="estoque_qtd_add"
                            )

                        adicionar_estoque = st.form_submit_button(
                            "➕ Adicionar ao Estoque", type="primary", use_container_width=True)

                    if adicionar_estoque:
                        if quantidade_hoje <= 0:
                            st.error("A quantidade deve ser maior que zero.")
                        else:
                            chave_acao = "adicionar_estoque"
                            payload_acao = (st.session_state.username, produto_id, quantidade_hoje)
                            if not acao_repetida(chave_acao, payload_acao):
                                try:
                                    incrementar_estoque(produto_id, quantidade_hoje)
                                    st.success(
                                        f"✅ {quantidade_hoje} unidade(s) de '{produto_selecionado}' adicionadas ao estoque.")
                                except Exception as e:
                                    liberar_acao(chave_acao)
                                    st.error(f"Erro ao adicionar estoque: {e}")

            st.divider()

            # ----- Visualização do Estoque Atual (total acumulado) -----
            st.markdown("### 📋 Estoque Atual (Total Acumulado)")
            df_estoque = obter_estoque()

            if df_estoque.empty:
                st.info(
                    "Nenhum produto cadastrado. Cadastre produtos na aba 'Cadastros'.")
            else:
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
                    placeholder_estoque = "Selecione um produto"
                    opcoes_estoque = [placeholder_estoque] + produtos_com_estoque

                    col_edit, col_del = st.columns(2)
                    with col_edit:
                        area_editar_estoque = st.empty()
                        mensagem_estoque_editado = None
                        with area_editar_estoque.container():
                            produto_editar = st.selectbox(
                                "Produto para editar",
                                opcoes_estoque,
                                key="estoque_editar_produto"
                            )

                            if produto_editar != placeholder_estoque:
                                linha = df_estoque[df_estoque['nome']
                                                   == produto_editar].iloc[0]
                                produto_id_edit = int(linha['id'])
                                qtd_atual_edit = int(linha['quantidade'])
                                with st.form("form_editar_estoque", clear_on_submit=True):
                                    nova_qtd_total = st.number_input(
                                        "Nova quantidade total",
                                        min_value=0,
                                        step=1,
                                        value=qtd_atual_edit,
                                        key="estoque_nova_qtd"
                                    )
                                    substituir_estoque = st.form_submit_button(
                                        "✅ Substituir", type="primary", use_container_width=True)
                            else:
                                produto_id_edit = None
                                nova_qtd_total = 0
                                substituir_estoque = False

                            if substituir_estoque and produto_id_edit is not None:
                                chave_acao = "substituir_estoque"
                                payload_acao = (st.session_state.username, produto_id_edit, nova_qtd_total)
                                if not acao_repetida(chave_acao, payload_acao):
                                    try:
                                        definir_estoque(produto_id_edit, nova_qtd_total)
                                        mensagem_estoque_editado = (
                                            f"Estoque do produto '{produto_editar}' atualizado para {nova_qtd_total} unidades.")
                                        df_estoque = obter_estoque()
                                    except Exception as e:
                                        liberar_acao(chave_acao)
                                        st.error(f"Erro ao atualizar estoque: {e}")

                        if mensagem_estoque_editado:
                            area_editar_estoque.empty()
                            st.success(mensagem_estoque_editado)

                    with col_del:
                        area_excluir_estoque = st.empty()
                        mensagem_estoque_excluido = None
                        with area_excluir_estoque.container():
                            produto_excluir = st.selectbox(
                                "Produto para excluir do estoque",
                                opcoes_estoque,
                                key="estoque_excluir_produto"
                            )
                            if produto_excluir != placeholder_estoque:
                                linha_excluir = df_estoque[df_estoque['nome']
                                                          == produto_excluir].iloc[0]
                                produto_id_excluir = int(linha_excluir['id'])
                                with st.form("form_excluir_estoque", clear_on_submit=True):
                                    st.warning(
                                        f"Tem certeza que deseja remover o produto '{produto_excluir}' do estoque?")
                                    st.caption(
                                        "Isso não exclui o produto cadastrado, apenas remove sua contagem do estoque.")
                                    confirmar_exclusao_estoque = st.checkbox(
                                        "Confirmo que quero excluir", key="confirmar_exclusao_estoque")
                                    excluir_estoque_submit = st.form_submit_button(
                                        "🗑️ Excluir estoque", type="primary", use_container_width=True,
                                        disabled=not confirmar_exclusao_estoque
                                    )
                            else:
                                produto_id_excluir = None
                                excluir_estoque_submit = False

                            if excluir_estoque_submit and produto_id_excluir is not None:
                                chave_acao = "excluir_estoque"
                                payload_acao = (st.session_state.username, produto_id_excluir)
                                if not acao_repetida(chave_acao, payload_acao):
                                    try:
                                        excluir_estoque(produto_id_excluir)
                                        mensagem_estoque_excluido = (
                                            f"Registro de estoque para '{produto_excluir}' removido.")
                                        df_estoque = obter_estoque()
                                    except Exception as e:
                                        liberar_acao(chave_acao)
                                        st.error(f"Erro ao excluir estoque: {e}")

                        if mensagem_estoque_excluido:
                            area_excluir_estoque.empty()
                            st.success(mensagem_estoque_excluido)

                st.divider()

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
                df_display["Quantidade Total"] = df_display["Quantidade Total"].apply(
                    lambda x: f"{x:,.2f}")          # <-- ADICIONE ESTA LINHA
                df_display["Valor Total"] = df_display["Valor Total"].apply(
                    lambda x: f"R$ {x:,.2f}")

                st.dataframe(
                    df_display[["Produto", "Unidade", "Preço Unitário",
                                "Quantidade Total", "Valor Total"]],
                    width='stretch',
                    hide_index=True
                )
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
                                chave_acao = "cadastrar_cliente"
                                payload_acao = (st.session_state.username, nome, cpf_cnpj, telefone, email, endereco)
                                if acao_repetida(chave_acao, payload_acao):
                                    st.stop()
                                try:
                                    with engine.connect() as conn:
                                        conn.execute(text("""
                                            INSERT INTO clientes (username, nome, cpf_cnpj, telefone, email, endereco)
                                            VALUES (:u, :nome, :cpf, :tel, :email, :end)
                                        """), {"u": st.session_state.username, "nome": nome, "cpf": cpf_cnpj or None,
                                               "tel": telefone or None, "email": email or None, "end": endereco or None})
                                        conn.commit()
                                    st.success("✅ Cliente cadastrado!")
                                except Exception as e:
                                    liberar_acao(chave_acao)
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
                        opcoes_clientes = {
                            int(row['id']): row['nome'] for _, row in df_cli.iterrows()
                        }
                        mensagem_editar_cliente = st.empty()
                        area_editar_cliente = st.empty()
                        with area_editar_cliente.container(), st.expander("✏️ Editar Cliente"):
                            cliente_id_editar = st.selectbox(
                                "Selecione um cliente",
                                options=list(opcoes_clientes.keys()),
                                format_func=lambda x: opcoes_clientes[x],
                                index=None,
                                placeholder="Selecione um cliente",
                                key="sel_cliente_editar"
                            )
                            with st.form("form_editar_cliente", clear_on_submit=True):
                                if cliente_id_editar is not None:
                                    cliente = df_cli[df_cli['id'] == cliente_id_editar].iloc[0].to_dict()
                                    n_nome = st.text_input("Nome", value=cliente['nome'])
                                    n_cpf = st.text_input("CPF/CNPJ", value=cliente.get('cpf_cnpj', '') or '')
                                    n_tel = st.text_input("Telefone", value=cliente.get('telefone', '') or '')
                                    n_email = st.text_input("Email", value=cliente.get('email', '') or '')
                                    n_end = st.text_area("Endereço", value=cliente.get('endereco', '') or '')
                                    salvar_cliente = st.form_submit_button("Salvar Alterações", type="primary")
                                else:
                                    salvar_cliente = st.form_submit_button("Salvar Alterações", type="primary", disabled=True)

                                if salvar_cliente and cliente_id_editar is not None:
                                    chave_acao = "atualizar_cliente"
                                    payload_acao = (st.session_state.username, cliente_id_editar, n_nome, n_cpf, n_tel, n_email, n_end)
                                    if not acao_repetida(chave_acao, payload_acao):
                                        try:
                                            with engine.connect() as conn:
                                                conn.execute(text("UPDATE clientes SET nome=:nome, cpf_cnpj=:cpf, telefone=:tel, email=:email, endereco=:end WHERE id=:id"),
                                                             {"nome": n_nome, "cpf": n_cpf or None, "tel": n_tel or None, "email": n_email or None, "end": n_end or None, "id": cliente_id_editar})
                                                conn.commit()
                                            area_editar_cliente.empty()
                                            mensagem_editar_cliente.success("Cliente atualizado!")
                                        except Exception as e:
                                            liberar_acao(chave_acao)
                                            st.error(f"Erro ao atualizar cliente: {e}")
                        mensagem_excluir_cliente = st.empty()
                        area_excluir_cliente = st.empty()
                        with area_excluir_cliente.container(), st.expander("🗑️ Excluir Cliente"):
                            cliente_id_excluir = st.selectbox(
                                "Selecione um cliente",
                                options=list(opcoes_clientes.keys()),
                                format_func=lambda x: opcoes_clientes[x],
                                index=None,
                                placeholder="Selecione um cliente",
                                key="sel_cliente_excluir"
                            )
                            with st.form("form_excluir_cliente", clear_on_submit=True):
                                if cliente_id_excluir is not None:
                                    st.warning("⚠️ Esta ação não pode ser desfeita!")
                                    confirmar_cliente = st.checkbox("Confirmo que quero excluir este cliente")
                                else:
                                    confirmar_cliente = False
                                excluir_cliente = st.form_submit_button(
                                    "Excluir Cliente", type="primary", disabled=not confirmar_cliente)

                                if excluir_cliente and cliente_id_excluir is not None:
                                    try:
                                        registrar_log("DELETE", "clientes", cliente_id_excluir, f"Excluiu cliente '{opcoes_clientes[cliente_id_excluir]}'")
                                        with engine.connect() as conn:
                                            conn.execute(text("DELETE FROM clientes WHERE id = :id"), {
                                                         "id": cliente_id_excluir})
                                            conn.commit()
                                        area_excluir_cliente.empty()
                                        mensagem_excluir_cliente.success("Cliente excluído!")
                                    except Exception as e:
                                        st.error(f"Erro ao excluir cliente: {e}")
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
                                chave_acao = "cadastrar_produto"
                                payload_acao = (st.session_state.username, nome_prod, descricao, unidade, preco)
                                if acao_repetida(chave_acao, payload_acao):
                                    st.stop()
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
                                except Exception as e:
                                    liberar_acao(chave_acao)
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

                        opcoes_produtos = {
                            int(row['id']): row['nome'] for _, row in df_produtos_lista.iterrows()
                        }

                        col_edit, col_del = st.columns(2)

                        # --- Editar produto ---
                        with col_edit:
                            mensagem_editar_produto = st.empty()
                            area_editar_produto = st.empty()
                            with area_editar_produto.container(), st.expander("✏️ Editar Produto", expanded=False):
                                produto_id_editar = st.selectbox(
                                    "Selecione o produto",
                                    options=list(opcoes_produtos.keys()),
                                    format_func=lambda x: opcoes_produtos[x],
                                    index=None,
                                    placeholder="Selecione um produto",
                                    key="select_produto_editar"
                                )
                                with st.form("form_editar_produto", clear_on_submit=True):
                                    if produto_id_editar is not None:
                                        produto_row = df_produtos_lista[df_produtos_lista['id'] == produto_id_editar].iloc[0]
                                        novo_nome = st.text_input(
                                            "Nome do Produto", value=produto_row['nome'], key="edit_prod_nome")
                                        nova_desc = st.text_area("Descrição", value=produto_row.get(
                                            'descricao', '') or '', key="edit_prod_desc")
                                        nova_unidade = st.text_input(
                                            "Unidade de Medida", value=produto_row['unidade'], key="edit_prod_un")
                                        novo_preco = st.number_input("Preço (R$)", value=float(
                                            produto_row['preco_atual']), step=0.01, format="%.2f", key="edit_prod_preco")
                                        salvar_produto = st.form_submit_button("✅ Salvar Alterações", type="primary")
                                    else:
                                        salvar_produto = st.form_submit_button("✅ Salvar Alterações", type="primary", disabled=True)

                                    if salvar_produto and produto_id_editar is not None:
                                        if novo_nome:
                                            chave_acao = "atualizar_produto"
                                            payload_acao = (st.session_state.username, produto_id_editar, novo_nome, nova_desc, nova_unidade, novo_preco)
                                            if not acao_repetida(chave_acao, payload_acao):
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
                                                            "id": produto_id_editar,
                                                            "u": st.session_state.username
                                                        })
                                                        conn.commit()
                                                    area_editar_produto.empty()
                                                    mensagem_editar_produto.success("✅ Produto atualizado com sucesso!")
                                                except Exception as e:
                                                    liberar_acao(chave_acao)
                                                    st.error(f"Erro ao atualizar: {e}")
                                        else:
                                            st.error("O nome do produto é obrigatório.")

                        # --- Excluir produto ---
                        with col_del:
                            mensagem_excluir_produto = st.empty()
                            area_excluir_produto = st.empty()
                            with area_excluir_produto.container(), st.expander("🗑️ Excluir Produto", expanded=False):
                                produto_id_excluir = st.selectbox(
                                    "Selecione o produto",
                                    options=list(opcoes_produtos.keys()),
                                    format_func=lambda x: opcoes_produtos[x],
                                    index=None,
                                    placeholder="Selecione um produto",
                                    key="select_produto_excluir"
                                )
                                with st.form("form_excluir_produto", clear_on_submit=True):
                                    if produto_id_excluir is not None:
                                        produto_excluir_nome = opcoes_produtos[produto_id_excluir]
                                        st.warning(
                                            f"⚠️ Tem certeza que deseja excluir o produto **'{produto_excluir_nome}'**?")
                                        st.caption(
                                            "Esta ação **não pode ser desfeita** e também removerá seus registros de estoque.")
                                        confirm_excluir = st.checkbox(
                                            "Sim, entendo que esta ação é irreversível", key="confirm_excluir_produto")
                                    else:
                                        produto_excluir_nome = ""
                                        confirm_excluir = False

                                    excluir_produto = st.form_submit_button(
                                        "🗑️ Excluir Permanentemente", type="primary", disabled=not confirm_excluir)

                                    if excluir_produto and produto_id_excluir is not None:
                                        try:
                                            registrar_log("DELETE", "produtos", produto_id_excluir, f"Excluiu produto '{produto_excluir_nome}'")
                                            with engine.connect() as conn:
                                                with conn.begin():
                                                    conn.execute(text("DELETE FROM estoque WHERE username = :u AND produto_id = :p"),
                                                                 {"u": st.session_state.username, "p": produto_id_excluir})
                                                    conn.execute(text("DELETE FROM produtos WHERE id = :id AND username = :u"),
                                                                 {"id": produto_id_excluir, "u": st.session_state.username})
                                            area_excluir_produto.empty()
                                            mensagem_excluir_produto.success(
                                                f"✅ Produto '{produto_excluir_nome}' e seus registros de estoque foram removidos.")
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
                                chave_acao = "adicionar_forma_pagamento"
                                payload_acao = (st.session_state.username, nome_forma)
                                if acao_repetida(chave_acao, payload_acao):
                                    st.stop()
                                try:
                                    with engine.connect() as conn:
                                        conn.execute(text("INSERT INTO formas_pagamento (username, nome, ativo) VALUES (:u, :nome, TRUE)"),
                                                     {"u": st.session_state.username, "nome": nome_forma})
                                        conn.commit()
                                    st.success("Forma de pagamento adicionada!")
                                except Exception as e:
                                    liberar_acao(chave_acao)
                                    st.error(f"Erro ao adicionar: {e}")
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
                except Exception as e:
                    st.error(f"Erro: {e}")

        # ============================================
        # ABA 3 → FATURAMENTO (COM DESPESAS) - FORMATADO BR
        # ============================================
        with fat_tabs[3]:
            st.subheader("💰 Gestão de Faturamento")

            # Função de formatação BR (já definida no início do módulo, mas garantindo aqui)
            def fmt_br(valor):
                return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            # Subabas internas
            fat_interno = st.tabs(
                ["📉 Despesas", "📊 Receita de Vendas", "📈 Faturamento"])

            # ---------- SUBABA: DESPESAS (CORRIGIDA) ----------
            with fat_interno[0]:
                st.markdown("### 📉 Controle de Despesas")

                # Criar tabelas se não existirem
                with engine.connect() as conn:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS tipos_despesas (
                            id SERIAL PRIMARY KEY,
                            username TEXT NOT NULL,
                            nome TEXT NOT NULL,
                            descricao TEXT,
                            UNIQUE(username, nome)
                        )
                    """))
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS despesas (
                            id SERIAL PRIMARY KEY,
                            username TEXT NOT NULL,
                            data DATE NOT NULL,
                            tipo_id INTEGER NOT NULL REFERENCES tipos_despesas(id) ON DELETE RESTRICT,
                            valor NUMERIC NOT NULL CHECK (valor > 0),
                            observacao TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.commit()

                def obter_tipos_despesas():
                    return pd.read_sql(text("SELECT id, nome, descricao FROM tipos_despesas WHERE username = :u ORDER BY nome"),
                                       engine, params={"u": st.session_state.username})

                def adicionar_tipo_despesa(nome, descricao):
                    with engine.connect() as conn:
                        conn.execute(text("INSERT INTO tipos_despesas (username, nome, descricao) VALUES (:u, :n, :d)"),
                                     {"u": st.session_state.username, "n": nome, "d": descricao})
                        conn.commit()

                def atualizar_tipo_despesa(tipo_id, nome, descricao):
                    with engine.connect() as conn:
                        conn.execute(text("UPDATE tipos_despesas SET nome = :n, descricao = :d WHERE id = :id AND username = :u"),
                                     {"n": nome, "d": descricao, "id": tipo_id, "u": st.session_state.username})
                        conn.commit()

                def excluir_tipo_despesa(tipo_id):
                    with engine.connect() as conn:
                        count = conn.execute(text("SELECT COUNT(*) FROM despesas WHERE tipo_id = :tid"), {"tid": tipo_id}).scalar()
                        if count > 0:
                            raise Exception("Não é possível excluir este tipo, pois existem despesas associadas.")
                        conn.execute(text("DELETE FROM tipos_despesas WHERE id = :id AND username = :u"),
                                     {"id": tipo_id, "u": st.session_state.username})
                        conn.commit()

                def registrar_despesa(data, tipo_id, valor, observacao):
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO despesas (username, data, tipo_id, valor, observacao)
                            VALUES (:u, :d, :tid, :v, :obs)
                        """), {"u": st.session_state.username, "d": data, "tid": tipo_id, "v": valor, "obs": observacao})
                        conn.commit()

                def obter_despesas(data_inicio, data_fim):
                    query = """
                        SELECT d.id, d.data, d.tipo_id, t.nome as tipo, d.valor, d.observacao
                        FROM despesas d
                        JOIN tipos_despesas t ON d.tipo_id = t.id
                        WHERE d.username = :u AND d.data BETWEEN :inicio AND :fim
                        ORDER BY d.data DESC
                    """
                    return pd.read_sql(text(query), engine, params={"u": st.session_state.username,
                                                                    "inicio": data_inicio,
                                                                    "fim": data_fim})

                sub_tabs = st.tabs(["🏷️ Tipos de Despesa", "➕ Nova Despesa", "📋 Histórico"])

                # Tipos de Despesa
                with sub_tabs[0]:
                    st.markdown("#### Tipos de Despesa Cadastrados")
                    with st.expander("➕ Adicionar novo tipo", expanded=False):
                        with st.form("form_novo_tipo", clear_on_submit=True):
                            nome_tipo = st.text_input("Nome *")
                            desc_tipo = st.text_area("Descrição (opcional)")
                            if st.form_submit_button("Salvar"):
                                if nome_tipo:
                                    chave_acao = "adicionar_tipo_despesa"
                                    payload_acao = (st.session_state.username, nome_tipo, desc_tipo)
                                    if acao_repetida(chave_acao, payload_acao):
                                        st.stop()
                                    try:
                                        adicionar_tipo_despesa(nome_tipo, desc_tipo)
                                        st.success("Tipo adicionado!")
                                    except Exception as e:
                                        liberar_acao(chave_acao)
                                        st.error(f"Erro: {e}")
                                else:
                                    st.error("Nome é obrigatório.")
                    df_tipos = obter_tipos_despesas()
                    if df_tipos.empty:
                        st.info("Nenhum tipo cadastrado ainda.")
                    else:
                        st.dataframe(df_tipos[['nome', 'descricao']], use_container_width=True, hide_index=True)
                        st.markdown("---")
                        st.markdown("#### ✏️ Editar ou 🗑️ Excluir Tipo")
                        opcoes_tipos = {
                            int(row['id']): row['nome'] for _, row in df_tipos.iterrows()
                        }
                        col_edit, col_del = st.columns(2)
                        with col_edit:
                            mensagem_editar_tipo = st.empty()
                            area_editar_tipo = st.empty()
                            with area_editar_tipo.container(), st.expander("✏️ Editar"):
                                tipo_id_editar = st.selectbox(
                                    "Selecione um tipo",
                                    options=list(opcoes_tipos.keys()),
                                    format_func=lambda x: opcoes_tipos[x],
                                    index=None,
                                    placeholder="Selecione um tipo",
                                    key="tipo_editar_select"
                                )
                                with st.form("form_edit_tipo", clear_on_submit=True):
                                    if tipo_id_editar is not None:
                                        tipo_row = df_tipos[df_tipos['id'] == tipo_id_editar].iloc[0]
                                        novo_nome = st.text_input("Nome", value=tipo_row['nome'])
                                        nova_desc = st.text_area("Descrição", value=tipo_row.get('descricao', '') or '')
                                        salvar_tipo = st.form_submit_button("Salvar alterações", type="primary")
                                    else:
                                        salvar_tipo = st.form_submit_button("Salvar alterações", type="primary", disabled=True)

                                    if salvar_tipo and tipo_id_editar is not None:
                                        chave_acao = "atualizar_tipo_despesa"
                                        payload_acao = (st.session_state.username, tipo_id_editar, novo_nome, nova_desc)
                                        if not acao_repetida(chave_acao, payload_acao):
                                            try:
                                                atualizar_tipo_despesa(tipo_id_editar, novo_nome, nova_desc)
                                                area_editar_tipo.empty()
                                                mensagem_editar_tipo.success("Tipo atualizado!")
                                            except Exception as e:
                                                liberar_acao(chave_acao)
                                                st.error(f"Erro ao atualizar tipo: {e}")
                        with col_del:
                            mensagem_excluir_tipo = st.empty()
                            area_excluir_tipo = st.empty()
                            with area_excluir_tipo.container(), st.expander("🗑️ Excluir"):
                                tipo_id_excluir = st.selectbox(
                                    "Selecione um tipo",
                                    options=list(opcoes_tipos.keys()),
                                    format_func=lambda x: opcoes_tipos[x],
                                    index=None,
                                    placeholder="Selecione um tipo",
                                    key="tipo_excluir_select"
                                )
                                with st.form("form_excluir_tipo", clear_on_submit=True):
                                    if tipo_id_excluir is not None:
                                        st.warning(f"Excluir permanentemente o tipo '{opcoes_tipos[tipo_id_excluir]}'?")
                                        confirmar_tipo = st.checkbox("Confirmo que quero excluir este tipo")
                                    else:
                                        confirmar_tipo = False
                                    excluir_tipo = st.form_submit_button(
                                        "Sim, excluir", type="primary", disabled=not confirmar_tipo)

                                    if excluir_tipo and tipo_id_excluir is not None:
                                        try:
                                            excluir_tipo_despesa(tipo_id_excluir)
                                            area_excluir_tipo.empty()
                                            mensagem_excluir_tipo.success("Tipo excluído!")
                                        except Exception as e:
                                            st.error(str(e))

                # Nova Despesa
                with sub_tabs[1]:
                    st.markdown("#### Registrar Despesa")
                    df_tipos = obter_tipos_despesas()
                    if df_tipos.empty:
                        st.warning("Cadastre pelo menos um tipo de despesa antes de registrar.")
                    else:
                        with st.form("form_nova_despesa", clear_on_submit=True):
                            col1, col2 = st.columns(2)
                            with col1:
                                data_despesa = st.date_input("Data", value=datetime.now().date(), format="DD/MM/YYYY")
                                tipo_despesa = st.selectbox("Tipo de despesa", df_tipos['nome'].tolist())
                                tipo_id = int(df_tipos[df_tipos['nome'] == tipo_despesa].iloc[0]['id'])
                            with col2:
                                valor_despesa = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
                                observacao = st.text_area("Observação (opcional)")
                            if st.form_submit_button("Registrar Despesa"):
                                chave_acao = "registrar_despesa"
                                payload_acao = (st.session_state.username, data_despesa, tipo_id, valor_despesa, observacao)
                                if acao_repetida(chave_acao, payload_acao):
                                    st.stop()
                                try:
                                    registrar_despesa(data_despesa, tipo_id, valor_despesa, observacao)
                                    st.success("Despesa registrada!")
                                except Exception as e:
                                    liberar_acao(chave_acao)
                                    st.error(f"Erro ao registrar despesa: {e}")

                # Histórico de Despesas (com edição/exclusão)
                with sub_tabs[2]:
                    st.markdown("#### Histórico de Despesas")
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        data_inicio = st.date_input("Data Inicial", value=datetime.now().date() - pd.Timedelta(days=30),
                                                    format="DD/MM/YYYY", key="desp_inicio")
                    with col_f2:
                        data_fim = st.date_input("Data Final", value=datetime.now().date(),
                                                 format="DD/MM/YYYY", key="desp_fim")

                    df_despesas = obter_despesas(data_inicio, data_fim)
                    if df_despesas.empty:
                        st.info("Nenhuma despesa encontrada no período.")
                    else:
                        total_geral = df_despesas['valor'].sum()
                        st.metric("💰 Total de Despesas no Período", fmt_br(total_geral))
                        st.divider()

                        st.markdown("#### Totais por Tipo de Despesa")
                        df_totais = df_despesas.groupby('tipo')['valor'].sum().reset_index().sort_values('valor', ascending=False)
                        df_totais = df_totais.rename(columns={'tipo': 'Tipo de Despesa', 'valor': 'Total (R$)'})
                        df_totais['Total (R$)'] = df_totais['Total (R$)'].apply(fmt_br)
                        st.dataframe(df_totais, use_container_width=True, hide_index=True)

                        st.markdown("#### Lista de Despesas")
                        df_display = df_despesas.copy()
                        df_display['data'] = pd.to_datetime(df_display['data']).dt.strftime('%d/%m/%Y')
                        df_display['valor'] = df_display['valor'].apply(fmt_br)
                        df_display = df_display.rename(columns={'data': 'Data', 'tipo': 'Tipo', 'valor': 'Valor', 'observacao': 'Observação'})
                        st.dataframe(df_display[['Data', 'Tipo', 'Valor', 'Observação']], use_container_width=True, hide_index=True)

                        st.markdown("---")
                        st.markdown("#### ✏️ Editar Despesa")
                        opcoes = {row['id']: f"{row['Data']} - {row['Tipo']} - {row['Valor']}" for _, row in df_display.iterrows()}
                        despesa_id = st.selectbox(
                            "Selecione a despesa para editar",
                            options=list(opcoes.keys()),
                            format_func=lambda x: opcoes[x],
                            index=None,
                            placeholder="Selecione uma despesa",
                            key="edit_despesa_select"
                        )
                        area_editar_despesa = st.empty()
                        mensagem_despesa_editada = None
                        with area_editar_despesa.container():
                            with st.form("form_editar_despesa", clear_on_submit=True):

                                if despesa_id is not None:
                                    despesa_edit = df_despesas[df_despesas['id'] == despesa_id].iloc[0]
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        nova_data = st.date_input("Data", value=despesa_edit['data'], format="DD/MM/YYYY")
                                        df_tipos_edit = obter_tipos_despesas()
                                        tipo_atual_nome = df_tipos_edit[df_tipos_edit['id'] == despesa_edit['tipo_id']].iloc[0]['nome']
                                        novo_tipo = st.selectbox("Tipo", df_tipos_edit['nome'].tolist(),
                                                                 index=df_tipos_edit['nome'].tolist().index(tipo_atual_nome))
                                        novo_tipo_id = int(df_tipos_edit[df_tipos_edit['nome'] == novo_tipo].iloc[0]['id'])
                                    with col2:
                                        novo_valor = st.number_input("Valor (R$)", min_value=0.01, step=0.01,
                                                                      value=float(despesa_edit['valor']), format="%.2f")
                                        nova_obs = st.text_area("Observação", value=despesa_edit.get('observacao', ''))
                                    salvar_despesa = st.form_submit_button("Salvar alterações", type="primary")
                                else:
                                    nova_data = None
                                    novo_tipo_id = None
                                    novo_valor = 0
                                    nova_obs = ""
                                    salvar_despesa = st.form_submit_button("Salvar alterações", type="primary", disabled=True)

                                if salvar_despesa and despesa_id is not None:
                                    chave_acao = "atualizar_despesa"
                                    payload_acao = (st.session_state.username, despesa_id, nova_data, novo_tipo_id, novo_valor, nova_obs)
                                    if acao_repetida(chave_acao, payload_acao):
                                        st.stop()
                                    try:
                                        with engine.connect() as conn:
                                            conn.execute(text("""
                                                UPDATE despesas
                                                SET data = :data, tipo_id = :tipo_id, valor = :valor, observacao = :obs
                                                WHERE id = :id AND username = :u
                                            """), {
                                                "data": nova_data,
                                                "tipo_id": novo_tipo_id,
                                                "valor": novo_valor,
                                                "obs": nova_obs,
                                                "id": despesa_id,
                                                "u": st.session_state.username
                                            })
                                            conn.commit()
                                        registrar_log("UPDATE", "despesas", despesa_id, f"Editou despesa para R$ {novo_valor:.2f}")
                                        mensagem_despesa_editada = "Despesa atualizada!"
                                    except Exception as e:
                                        liberar_acao(chave_acao)
                                        st.error(f"Erro ao atualizar: {e}")

                        if mensagem_despesa_editada:
                            area_editar_despesa.empty()
                            st.success(mensagem_despesa_editada)

                        st.markdown("---")
                        st.markdown("#### 🗑️ Excluir Despesa")
                        despesa_excluir_id = st.selectbox(
                            "Selecione a despesa para excluir",
                            options=list(opcoes.keys()),
                            format_func=lambda x: opcoes[x],
                            index=None,
                            placeholder="Selecione uma despesa",
                            key="excluir_despesa_select"
                        )
                        area_excluir_despesa = st.empty()
                        mensagem_despesa_excluida = None
                        with area_excluir_despesa.container():
                            with st.form("form_excluir_despesa", clear_on_submit=True):
                                if despesa_excluir_id is not None:
                                    despesa_excluir = df_despesas[df_despesas['id'] == despesa_excluir_id].iloc[0]
                                    st.warning(f"Excluir permanentemente a despesa de {despesa_excluir['tipo']} no valor de {fmt_br(despesa_excluir['valor'])}?")
                                    confirm_excluir = st.checkbox("Confirmo que quero excluir", key="confirma_excluir_despesa")
                                else:
                                    despesa_excluir = None
                                    confirm_excluir = False

                                excluir_despesa = st.form_submit_button(
                                    "Excluir agora", type="primary", disabled=not confirm_excluir)

                                if excluir_despesa and despesa_excluir_id is not None:
                                    try:
                                        with engine.connect() as conn:
                                            conn.execute(text("DELETE FROM despesas WHERE id = :id AND username = :u"),
                                                         {"id": despesa_excluir_id, "u": st.session_state.username})
                                            conn.commit()
                                        registrar_log("DELETE", "despesas", despesa_excluir_id, f"Excluiu despesa de {despesa_excluir['tipo']} - R$ {despesa_excluir['valor']:.2f}")
                                        mensagem_despesa_excluida = "Despesa excluída com sucesso!"
                                    except Exception as e:
                                        st.error(f"Erro ao excluir: {e}")

                        if mensagem_despesa_excluida:
                            area_excluir_despesa.empty()
                            st.success(mensagem_despesa_excluida)

            # ---------- SUBABA: RECEITA DE VENDAS (FORMATADA BR) ----------
            with fat_interno[1]:
                st.markdown("### 📊 Receita de Vendas por Período")

                # Filtros de data
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    data_inicio_vendas = st.date_input("Data Inicial", value=datetime.now().date() - pd.Timedelta(days=30),
                                                       format="DD/MM/YYYY", key="receita_inicio")
                with col_f2:
                    data_fim_vendas = st.date_input("Data Final", value=datetime.now().date(),
                                                    format="DD/MM/YYYY", key="receita_fim")

                # Query para obter receita por produto no período
                query_receita = """
                    SELECT
                        p.nome as produto,
                        SUM(vi.quantidade) as total_unidades,
                        SUM(vi.subtotal) as valor_total
                    FROM vendas v
                    JOIN venda_itens vi ON v.id = vi.venda_id
                    JOIN produtos p ON vi.produto_id = p.id
                    WHERE v.username = :u
                        AND v.data_venda BETWEEN :inicio AND :fim
                    GROUP BY p.nome
                    ORDER BY valor_total DESC
                """
                df_receita = pd.read_sql(text(query_receita), engine, params={
                    "u": st.session_state.username,
                    "inicio": data_inicio_vendas,
                    "fim": data_fim_vendas
                })

                if df_receita.empty:
                    st.info("Nenhuma venda encontrada no período selecionado.")
                else:
                    # Totais gerais (formatados BR)
                    total_geral_valor = df_receita['valor_total'].sum()
                    total_geral_unidades = df_receita['total_unidades'].sum()

                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        st.metric("💰 Receita Total", fmt_br(total_geral_valor))
                    with col_c2:
                        st.metric("📦 Total de Itens Vendidos", f"{total_geral_unidades:,.0f}")

                    st.divider()

                    # Tabela de receita por produto (formatada BR)
                    st.markdown("#### Receita por Tipo de Produto")
                    df_display = df_receita.copy()
                    df_display['valor_total'] = df_display['valor_total'].apply(fmt_br)
                    df_display = df_display.rename(columns={
                        'produto': 'Produto',
                        'total_unidades': 'Unidades Vendidas',
                        'valor_total': 'Valor Total (R$)'
                    })
                    st.dataframe(df_display, use_container_width=True, hide_index=True)

                    st.divider()

                    # Gráfico de linha: evolução diária dos produtos (valores no eixo Y continuam numéricos)
                    st.markdown("#### Evolução do Valor Vendido por Produto (Gráfico de Linha)")
                    query_evolucao = """
                        SELECT
                            v.data_venda,
                            p.nome as produto,
                            SUM(vi.subtotal) as valor_dia
                        FROM vendas v
                        JOIN venda_itens vi ON v.id = vi.venda_id
                        JOIN produtos p ON vi.produto_id = p.id
                        WHERE v.username = :u
                            AND v.data_venda BETWEEN :inicio AND :fim
                        GROUP BY v.data_venda, p.nome
                        ORDER BY v.data_venda, p.nome
                    """
                    df_evolucao = pd.read_sql(text(query_evolucao), engine, params={
                        "u": st.session_state.username,
                        "inicio": data_inicio_vendas,
                        "fim": data_fim_vendas
                    })
                    if not df_evolucao.empty:
                        df_pivot = df_evolucao.pivot(index='data_venda', columns='produto', values='valor_dia').fillna(0)
                        fig = px.line(df_pivot, x=df_pivot.index, y=df_pivot.columns,
                                      title="Receita Diária por Produto",
                                      labels={'value': 'Receita (R$)', 'variable': 'Produto'},
                                      markers=True)
                        fig.update_layout(
                            plot_bgcolor='#ffffff',
                            paper_bgcolor='#ffffff',
                            font=dict(color="#000000", size=12),
                            title_font=dict(color="#000000"),
                            xaxis=dict(tickformat='%d/%m', color="#000000"),
                            yaxis=dict(color="#000000")
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Dados insuficientes para gráfico de linha.")

                    # Gráfico de barras horizontal com ranking (formatado BR no eixo X)
                    st.markdown("#### Ranking de Vendas por Produto")
                    fig_rank = px.bar(df_receita, x='valor_total', y='produto', orientation='h',
                                      title="Total Vendido por Produto (R$)",
                                      labels={'valor_total': 'Receita (R$)', 'produto': 'Produto'},
                                      text_auto=True, color='valor_total', color_continuous_scale='Blues')
                    fig_rank.update_layout(
                        plot_bgcolor='#ffffff',
                        paper_bgcolor='#ffffff',
                        font=dict(color="#000000", size=12),
                        title_font=dict(color="#000000"),
                        xaxis=dict(color="#000000", tickformat=",.2f", title="Receita (R$)"),
                        yaxis=dict(color="#000000")
                    )
                    # Ajusta os valores no texto das barras para formato BR (opcional)
                    fig_rank.update_traces(texttemplate='%{x:,.2f}', textposition='outside')
                    st.plotly_chart(fig_rank, use_container_width=True)

            # ---------- SUBABA: FATURAMENTO (PROFISSIONAL) - FORMATADO BR ----------
            with fat_interno[2]:
                st.markdown("## 📊 Dashboard Financeiro")
                st.markdown("---")

                # Filtro de período
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    data_inicio_fat = st.date_input("📅 Data Inicial", value=datetime.now().date() - pd.Timedelta(days=30),
                                                    format="DD/MM/YYYY", key="fat_inicio")
                with col_f2:
                    data_fim_fat = st.date_input("📅 Data Final", value=datetime.now().date(),
                                                 format="DD/MM/YYYY", key="fat_fim")
                if data_inicio_fat > data_fim_fat:
                    st.error("⚠️ Data inicial não pode ser maior que a data final.")
                    st.stop()

                @st.cache_data(ttl=60)
                def carregar_dados_faturamento(inicio, fim, username):
                    with engine.connect() as conn:
                        rec = conn.execute(text("""
                            SELECT COALESCE(SUM(vi.subtotal), 0) FROM vendas v
                            JOIN venda_itens vi ON v.id = vi.venda_id
                            WHERE v.username = :u AND v.data_venda BETWEEN :inicio AND :fim
                        """), {"u": username, "inicio": inicio, "fim": fim}).scalar()
                        desp = conn.execute(text("""
                            SELECT COALESCE(SUM(valor), 0) FROM despesas
                            WHERE username = :u AND data BETWEEN :inicio AND :fim
                        """), {"u": username, "inicio": inicio, "fim": fim}).scalar()
                        rec_diaria = pd.read_sql(text("""
                            SELECT v.data_venda as data, SUM(vi.subtotal) as valor
                            FROM vendas v JOIN venda_itens vi ON v.id = vi.venda_id
                            WHERE v.username = :u AND v.data_venda BETWEEN :inicio AND :fim
                            GROUP BY v.data_venda ORDER BY v.data_venda
                        """), conn, params={"u": username, "inicio": inicio, "fim": fim})
                        desp_diaria = pd.read_sql(text("""
                            SELECT data, SUM(valor) as valor
                            FROM despesas
                            WHERE username = :u AND data BETWEEN :inicio AND :fim
                            GROUP BY data ORDER BY data
                        """), conn, params={"u": username, "inicio": inicio, "fim": fim})
                        top_desp = pd.read_sql(text("""
                            SELECT t.nome as tipo, SUM(d.valor) as total
                            FROM despesas d JOIN tipos_despesas t ON d.tipo_id = t.id
                            WHERE d.username = :u AND d.data BETWEEN :inicio AND :fim
                            GROUP BY t.nome ORDER BY total DESC LIMIT 5
                        """), conn, params={"u": username, "inicio": inicio, "fim": fim})
                        top_prod = pd.read_sql(text("""
                            SELECT p.nome as produto, SUM(vi.subtotal) as receita
                            FROM vendas v JOIN venda_itens vi ON v.id = vi.venda_id
                            JOIN produtos p ON vi.produto_id = p.id
                            WHERE v.username = :u AND v.data_venda BETWEEN :inicio AND :fim
                            GROUP BY p.nome ORDER BY receita DESC LIMIT 5
                        """), conn, params={"u": username, "inicio": inicio, "fim": fim})
                    return rec, desp, rec_diaria, desp_diaria, top_desp, top_prod

                receita_total, despesa_total, df_rec_diaria, df_desp_diaria, df_top_desp, df_top_prod = carregar_dados_faturamento(
                    data_inicio_fat, data_fim_fat, st.session_state.username)

                lucro_liquido = receita_total - despesa_total
                margem_lucro = (lucro_liquido / receita_total * 100) if receita_total > 0 else 0

                # Cards com formatação BR
                st.markdown("### 📈 Indicadores do Período")
                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    st.metric("💰 **Receita Total**", fmt_br(receita_total))
                with col_b:
                    st.metric("📉 **Despesas Totais**", fmt_br(despesa_total), delta_color="inverse")
                with col_c:
                    st.metric("💎 **Lucro Líquido**", fmt_br(lucro_liquido),
                              delta=f"{fmt_br(lucro_liquido)}" if lucro_liquido >= 0 else f"-{fmt_br(abs(lucro_liquido))}",
                              delta_color="normal")
                with col_d:
                    st.metric("📊 **Margem de Lucro**", f"{margem_lucro:.1f}%")

                st.markdown("---")

                # Gráficos (evolução diária e lucro acumulado) – valores nos eixos permanecem numéricos, sem formatação BR
                if not df_rec_diaria.empty or not df_desp_diaria.empty:
                    datas = pd.date_range(data_inicio_fat, data_fim_fat, freq='D')
                    df_combinado = pd.DataFrame({'data': datas})
                    if not df_rec_diaria.empty:
                        df_rec_diaria['data'] = pd.to_datetime(df_rec_diaria['data'])
                        df_rec_diaria = df_rec_diaria.rename(columns={'valor': 'Receita'})
                        df_combinado = df_combinado.merge(df_rec_diaria[['data', 'Receita']], on='data', how='left')
                    else:
                        df_combinado['Receita'] = 0
                    if not df_desp_diaria.empty:
                        df_desp_diaria['data'] = pd.to_datetime(df_desp_diaria['data'])
                        df_desp_diaria = df_desp_diaria.rename(columns={'valor': 'Despesa'})
                        df_combinado = df_combinado.merge(df_desp_diaria[['data', 'Despesa']], on='data', how='left')
                    else:
                        df_combinado['Despesa'] = 0
                    df_combinado.fillna(0, inplace=True)
                    df_combinado['Lucro Diário'] = df_combinado['Receita'] - df_combinado['Despesa']
                    df_combinado['Lucro Acumulado'] = df_combinado['Lucro Diário'].cumsum()

                    col_left, col_right = st.columns(2)
                    with col_left:
                        st.markdown("#### 📈 Evolução Diária")
                        fig_evolucao = px.line(df_combinado, x='data', y=['Receita', 'Despesa'],
                                               title="Receita vs Despesa (Diário)",
                                               labels={'value': 'Valor (R$)', 'variable': 'Categoria'},
                                               markers=True,
                                               color_discrete_map={'Receita': '#2ecc71', 'Despesa': '#e74c3c'})
                        fig_evolucao.update_layout(plot_bgcolor='#f8f9fa', paper_bgcolor='#ffffff',
                                                   font=dict(color="#2c3e50", size=12), title_font=dict(color="#2c3e50", size=14),
                                                   xaxis=dict(tickformat='%d/%m', color="#2c3e50"), yaxis=dict(color="#2c3e50"),
                                                   legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
                        st.plotly_chart(fig_evolucao, use_container_width=True)
                    with col_right:
                        st.markdown("#### 📊 Lucro Acumulado")
                        fig_lucro = px.area(df_combinado, x='data', y='Lucro Acumulado',
                                            title="Lucro Líquido Acumulado",
                                            labels={'Lucro Acumulado': 'Lucro (R$)'},
                                            color_discrete_sequence=['#3498db'])
                        fig_lucro.update_layout(plot_bgcolor='#f8f9fa', paper_bgcolor='#ffffff',
                                                font=dict(color="#2c3e50", size=12), title_font=dict(color="#2c3e50", size=14),
                                                xaxis=dict(tickformat='%d/%m', color="#2c3e50"), yaxis=dict(color="#2c3e50"))
                        st.plotly_chart(fig_lucro, use_container_width=True)
                else:
                    st.info("📭 Não há dados de receita ou despesa no período selecionado.")

                st.markdown("---")

                # Tabelas de Top Despesas e Top Produtos (formatadas BR)
                col_tab1, col_tab2 = st.columns(2)
                with col_tab1:
                    st.markdown("#### 🔝 Principais Despesas")
                    if not df_top_desp.empty:
                        df_top_desp['total'] = df_top_desp['total'].apply(fmt_br)
                        st.dataframe(df_top_desp.rename(columns={'tipo': 'Tipo', 'total': 'Valor'}),
                                     use_container_width=True, hide_index=True,
                                     column_config={"Tipo": st.column_config.TextColumn("Tipo de Despesa")})
                    else:
                        st.info("Nenhuma despesa registrada no período.")
                with col_tab2:
                    st.markdown("#### 🔝 Produtos com Maior Receita")
                    if not df_top_prod.empty:
                        df_top_prod['receita'] = df_top_prod['receita'].apply(fmt_br)
                        st.dataframe(df_top_prod.rename(columns={'produto': 'Produto', 'receita': 'Receita'}),
                                     use_container_width=True, hide_index=True,
                                     column_config={"Produto": st.column_config.TextColumn("Produto")})
                    else:
                        st.info("Nenhuma venda registrada no período.")

                st.markdown("---")
                st.caption(f"📆 Período analisado: {data_inicio_fat.strftime('%d/%m/%Y')} a {data_fim_fat.strftime('%d/%m/%Y')}")


        # ============================================
        # ABA 4 → LOGS
        # ============================================
        with fat_tabs[4]:
            st.subheader("📋 Registro de Ações (Logs)")
            st.caption("Histórico de alterações, exclusões e inserções feitas pelos usuários.")

            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            with col_f1:
                data_log_inicio = st.date_input("Data Inicial", value=datetime.now().date() - pd.Timedelta(days=30),
                                                format="DD/MM/YYYY", key="log_inicio")
            with col_f2:
                data_log_fim = st.date_input("Data Final", value=datetime.now().date(),
                                             format="DD/MM/YYYY", key="log_fim")
            with col_f3:
                acoes = ["Todas", "INSERT", "UPDATE", "DELETE"]
                filtro_acao = st.selectbox("Ação", acoes)
            with col_f4:
                tabelas = ["Todas", "vendas", "produtos", "clientes", "despesas", "aves", "producao", "tipos_despesas", "venda_itens"]
                filtro_tabela = st.selectbox("Tabela", tabelas)

            query_logs = """
                SELECT id, username, acao, tabela, registro_id, detalhes, data_hora
                FROM logs_acoes
                WHERE username = :u
                AND data_hora BETWEEN :inicio AND :fim
            """
            params = {
                "u": st.session_state.username,
                "inicio": data_log_inicio,
                "fim": data_log_fim
            }
            if filtro_acao != "Todas":
                query_logs += " AND acao = :acao"
                params["acao"] = filtro_acao
            if filtro_tabela != "Todas":
                query_logs += " AND tabela = :tabela"
                params["tabela"] = filtro_tabela
            query_logs += " ORDER BY data_hora DESC"

            try:
                df_logs = pd.read_sql(text(query_logs), engine, params=params)
                if df_logs.empty:
                    st.info("Nenhum registro de log encontrado no período.")
                else:
                    df_display = df_logs.copy()
                    df_display['data_hora'] = pd.to_datetime(df_display['data_hora']).dt.strftime('%d/%m/%Y %H:%M:%S')
                    df_display = df_display.rename(columns={
                        'username': 'Usuário',
                        'acao': 'Ação',
                        'tabela': 'Tabela',
                        'registro_id': 'ID Registro',
                        'detalhes': 'Detalhes',
                        'data_hora': 'Data/Hora'
                    })
                    st.dataframe(df_display[['Data/Hora', 'Usuário', 'Ação', 'Tabela', 'ID Registro', 'Detalhes']],
                                 use_container_width=True, hide_index=True)
                    st.caption(f"Mostrando {len(df_logs)} registros.")
            except Exception as e:
                st.error(f"Erro ao carregar logs: {e}")

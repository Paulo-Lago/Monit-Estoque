import pandas as pd
import streamlit as st
from sqlalchemy import text


CATEGORIAS = {
    "galpao": {"titulo": "Galpões", "singular": "galpão", "padroes": ["Galpão 2", "Galpão 3", "Galpão 4"]},
    "tipo_ovo": {"titulo": "Tipos de ovo", "singular": "tipo de ovo", "padroes": ["A", "B", "Jumbo", "Extra"]},
    "cor_ovo": {"titulo": "Cores de ovo", "singular": "cor de ovo", "padroes": ["Branco", "Vermelho"]},
}


@st.cache_resource
def inicializar_catalogo_producao(_engine):
    with _engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS catalogo_producao (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                categoria TEXT NOT NULL CHECK (categoria IN ('galpao', 'tipo_ovo', 'cor_ovo')),
                nome TEXT NOT NULL,
                ativo BOOLEAN NOT NULL DEFAULT TRUE,
                ordem INTEGER NOT NULL DEFAULT 0,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (username, categoria, nome)
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_catalogo_producao_usuario_categoria
            ON catalogo_producao (username, categoria, ativo, ordem, nome)
        """))
        conn.commit()


def garantir_catalogo_usuario(engine, username):
    with engine.connect() as conn:
        with conn.begin():
            for categoria, dados in CATEGORIAS.items():
                for ordem, nome in enumerate(dados["padroes"], start=1):
                    conn.execute(text("""
                        INSERT INTO catalogo_producao (username, categoria, nome, ativo, ordem)
                        SELECT :username, :categoria, :nome, TRUE, :ordem
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM catalogo_producao
                            WHERE username = :username
                              AND categoria = :categoria
                              AND LOWER(nome) = LOWER(:nome)
                        )
                    """), {
                        "username": username,
                        "categoria": categoria,
                        "nome": nome,
                        "ordem": ordem,
                    })


def obter_catalogo_ativo(engine, username):
    with engine.connect() as conn:
        linhas = conn.execute(text("""
            SELECT categoria, nome
            FROM catalogo_producao
            WHERE username = :username AND ativo = TRUE
            ORDER BY categoria, ordem, nome
        """), {"username": username}).mappings().all()

    resultado = {categoria: [] for categoria in CATEGORIAS}
    for linha in linhas:
        resultado[linha["categoria"]].append(linha["nome"])
    return resultado


def render_gerenciamento_catalogo(engine, registrar_log, acao_repetida, liberar_acao):
    username = st.session_state.username
    st.markdown("#### Gerenciamento de Produção")
    st.caption(
        "As opções ativas aparecem nos novos registros. Desativar uma opção não altera dados já registrados."
    )

    abas = st.tabs(["Galpões", "Tipos de ovo", "Cores de ovo"])
    for aba, categoria in zip(abas, CATEGORIAS):
        dados_categoria = CATEGORIAS[categoria]
        with aba:
            df = pd.read_sql(text("""
                SELECT id, nome, ativo, ordem
                FROM catalogo_producao
                WHERE username = :username AND categoria = :categoria
                ORDER BY ordem, nome
            """), engine, params={"username": username, "categoria": categoria})

            with st.form(f"adicionar_{categoria}", clear_on_submit=True):
                col_nome, col_ordem, col_botao = st.columns([3, 1, 1])
                with col_nome:
                    nome = st.text_input(f"Novo {dados_categoria['singular']}", key=f"novo_{categoria}")
                with col_ordem:
                    ordem = st.number_input("Ordem", min_value=1, value=max(len(df) + 1, 1), step=1, key=f"ordem_{categoria}")
                with col_botao:
                    st.write("")
                    salvar = st.form_submit_button("Adicionar", width="stretch")

            if salvar:
                nome = nome.strip()
                if not nome:
                    st.error("Informe um nome.")
                else:
                    chave = f"adicionar_catalogo_{categoria}"
                    if not acao_repetida(chave, (username, categoria, nome, ordem)):
                        try:
                            with engine.connect() as conn:
                                with conn.begin():
                                    existe = conn.execute(text("""
                                        SELECT 1 FROM catalogo_producao
                                        WHERE username = :username
                                          AND categoria = :categoria
                                          AND LOWER(nome) = LOWER(:nome)
                                    """), {"username": username, "categoria": categoria, "nome": nome}).scalar()
                                    if existe:
                                        raise ValueError("Já existe uma opção com esse nome.")
                                    conn.execute(text("""
                                        INSERT INTO catalogo_producao (username, categoria, nome, ativo, ordem)
                                        VALUES (:username, :categoria, :nome, TRUE, :ordem)
                                    """), {"username": username, "categoria": categoria, "nome": nome, "ordem": ordem})
                            registrar_log("INSERT", "catalogo_producao", detalhes=f"Adicionou {dados_categoria['singular']} '{nome}'")
                            st.success("Opção adicionada com sucesso.")
                            st.rerun()
                        except Exception as exc:
                            liberar_acao(chave)
                            st.error(str(exc))

            if df.empty:
                st.info("Nenhuma opção cadastrada.")
                continue

            tabela = df.rename(columns={"nome": "Nome", "ativo": "Ativo", "ordem": "Ordem"})
            st.dataframe(tabela[["Nome", "Ativo", "Ordem"]], hide_index=True, width="stretch")

            opcoes = {
                int(linha["id"]): f"{linha['nome']} ({'ativo' if linha['ativo'] else 'inativo'})"
                for _, linha in df.iterrows()
            }
            selecionado = st.selectbox(
                f"{dados_categoria['singular'].capitalize()} para ativar ou desativar",
                options=list(opcoes),
                format_func=lambda opcao_id: opcoes[opcao_id],
                key=f"selecionar_{categoria}",
            )
            registro = df[df["id"] == selecionado].iloc[0]
            acao = "Desativar" if bool(registro["ativo"]) else "Ativar"
            if st.button(f"{acao} {dados_categoria['singular']}", key=f"alternar_{categoria}", width="stretch"):
                ativos = int(df["ativo"].sum())
                if bool(registro["ativo"]) and ativos <= 1:
                    st.error("Mantenha pelo menos uma opção ativa nesta categoria.")
                else:
                    chave = f"alternar_catalogo_{categoria}"
                    novo_status = not bool(registro["ativo"])
                    if not acao_repetida(chave, (username, int(registro["id"]), novo_status)):
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("""
                                    UPDATE catalogo_producao
                                    SET ativo = :ativo
                                    WHERE id = :id AND username = :username
                                """), {"ativo": novo_status, "id": int(registro["id"]), "username": username})
                                conn.commit()
                            registrar_log("UPDATE", "catalogo_producao", int(registro["id"]), f"{acao} {dados_categoria['singular']} '{registro['nome']}'")
                            st.success("Status atualizado.")
                            st.rerun()
                        except Exception as exc:
                            liberar_acao(chave)
                            st.error(f"Não foi possível atualizar: {exc}")

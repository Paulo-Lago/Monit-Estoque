from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text


DESTINO_PADRAO = "Galpão 4"
STATUS_ATIVOS = ("ativo", "pronto_transferencia")
ROTULOS_STATUS_LOTE = {
    "ativo": "Ativo",
    "pronto_transferencia": "Pronto para transferência",
    "transferido": "Transferido",
    "encerrado": "Encerrado",
}
ROTULOS_STATUS_VACINA = {
    "prevista": "Prevista",
    "aplicada": "Aplicada",
    "atrasada": "Atrasada",
    "cancelada": "Cancelada",
}


def calcular_aves_vivas(quantidade_inicial, mortes_acumuladas, quantidade_transferida=0):
    """Centraliza o calculo de aves vivas para evitar totais divergentes."""
    return max(
        0,
        int(quantidade_inicial or 0)
        - int(mortes_acumuladas or 0)
        - int(quantidade_transferida or 0),
    )


def status_exibicao_vacina(status, data_prevista, hoje=None):
    hoje = hoje or date.today()
    if status == "prevista" and pd.to_datetime(data_prevista).date() < hoje:
        return "atrasada"
    return status


def rotulo_status_lote(status):
    return ROTULOS_STATUS_LOTE.get(status, str(status).replace("_", " ").title())


def rotulo_status_vacina(status):
    return ROTULOS_STATUS_VACINA.get(status, str(status).replace("_", " ").title())


def _formatar_inteiro(valor):
    return f"{int(round(float(valor or 0))):,}".replace(",", ".")


def _formatar_kg(valor):
    return f"{float(valor or 0):,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")


def render_area_pinteiro(engine, registrar_log, acao_repetida, liberar_acao):
    usuario = st.session_state.username
    hoje = date.today()

    def carregar_lotes():
        return pd.read_sql(text("""
            SELECT
                l.id,
                l.nome,
                l.data_chegada,
                l.quantidade_inicial,
                l.fornecedor,
                l.linhagem,
                l.status,
                l.data_prevista_transferencia,
                l.destino_previsto,
                l.observacoes,
                l.quantidade_transferida,
                l.data_transferencia,
                COALESCE(m.mortes_acumuladas, 0) AS mortes_acumuladas
            FROM pinteiro_lotes l
            LEFT JOIN (
                SELECT username, lote_id, SUM(mortes) AS mortes_acumuladas
                FROM pinteiro_registros_mortalidade
                GROUP BY username, lote_id
            ) m ON m.lote_id = l.id AND m.username = l.username
            WHERE l.username = :username
            ORDER BY l.data_chegada DESC, l.id DESC
        """), engine, params={"username": usuario})

    def enriquecer_lotes(df_lotes):
        if df_lotes.empty:
            return df_lotes
        resultado = df_lotes.copy()
        resultado["data_chegada"] = pd.to_datetime(resultado["data_chegada"])
        resultado["idade_dias"] = resultado["data_chegada"].apply(
            lambda valor: max(0, (hoje - valor.date()).days)
        )
        resultado["aves_vivas"] = resultado.apply(
            lambda linha: calcular_aves_vivas(
                linha["quantidade_inicial"],
                linha["mortes_acumuladas"],
                linha["quantidade_transferida"],
            ),
            axis=1,
        )
        return resultado

    def carregar_registros_racao():
        return pd.read_sql(text("""
            SELECT r.*, l.nome AS lote
            FROM pinteiro_registros_racao r
            JOIN pinteiro_lotes l ON l.id = r.lote_id
            WHERE r.username = :username
            ORDER BY r.data DESC, r.id DESC
        """), engine, params={"username": usuario})

    def expandir_consumo_racao(registros):
        if registros.empty:
            return pd.DataFrame(columns=["data", "lote_id", "racao_consumida"])

        consumo_diario = []
        for registro in registros.itertuples():
            data_inicio = pd.to_datetime(registro.data).date()
            data_fim = pd.to_datetime(registro.data_fim).date()
            for data_consumo in pd.date_range(data_inicio, data_fim, freq="D"):
                consumo_diario.append({
                    "data": data_consumo,
                    "lote_id": int(registro.lote_id),
                    "racao_consumida": float(registro.racao_consumida),
                })
        return pd.DataFrame(consumo_diario)

    def periodo_racao_conflitante(conn, lote_id, data_inicio, data_fim, excluir_id=None):
        parametros = {
            "username": usuario,
            "lote_id": int(lote_id),
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        }
        filtro_id = ""
        if excluir_id is not None:
            filtro_id = " AND id <> :excluir_id"
            parametros["excluir_id"] = int(excluir_id)
        return conn.execute(text(f"""
            SELECT id
            FROM pinteiro_registros_racao
            WHERE username = :username
                AND lote_id = :lote_id
                AND data <= :data_fim
                AND COALESCE(data_fim, data) >= :data_inicio
                {filtro_id}
            LIMIT 1
        """), parametros).scalar()

    def bloquear_periodo_racao(conn, lote_id):
        chave = f"pinteiro_racao|{usuario}|{int(lote_id)}"
        conn.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:chave))"),
            {"chave": chave},
        )

    def carregar_registros_mortalidade():
        return pd.read_sql(text("""
            SELECT r.*, l.nome AS lote
            FROM pinteiro_registros_mortalidade r
            JOIN pinteiro_lotes l ON l.id = r.lote_id
            WHERE r.username = :username
            ORDER BY r.data DESC, r.id DESC
        """), engine, params={"username": usuario})

    def carregar_vacinas():
        return pd.read_sql(text("""
            SELECT v.*, l.nome AS lote
            FROM pinteiro_vacinacoes v
            JOIN pinteiro_lotes l ON l.id = v.lote_id
            WHERE v.username = :username
            ORDER BY v.data_prevista, v.id
        """), engine, params={"username": usuario})

    def destino_disponivel():
        with engine.connect() as conn:
            return bool(conn.execute(text("""
                SELECT ativo
                FROM pinteiro_destinos
                WHERE username = :username AND galpao = :galpao
            """), {"username": usuario, "galpao": DESTINO_PADRAO}).scalar() or False)

    def exibir_grafico(figura, chave):
        figura.update_xaxes(type="date", tickformat="%d/%m/%Y")
        figura.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(figura, width="stretch", key=chave)

    st.markdown("### Pinteiro")
    st.caption(
        "Controle isolado de pintos. Os dados desta área não entram nos indicadores "
        "dos Galpões 2 e 3."
    )

    abas = st.tabs([
        "Dashboard",
        "Lotes",
        "Controle Diário",
        "Vacinação",
        "Transferência",
    ])

    with abas[0]:
        lotes = enriquecer_lotes(carregar_lotes())
        registros_racao = carregar_registros_racao()
        registros_mortalidade = carregar_registros_mortalidade()
        vacinas = carregar_vacinas()

        if lotes.empty:
            st.info("Cadastre o primeiro lote para acompanhar o Pinteiro.")
        else:
            opcoes_lotes = {int(linha.id): linha.nome for linha in lotes.itertuples()}
            lote_selecionado = st.selectbox(
                "Lote",
                options=[0, *opcoes_lotes.keys()],
                format_func=lambda lote_id: "Todos os lotes" if lote_id == 0 else opcoes_lotes[lote_id],
                key="pinteiro_dashboard_lote",
            )
            data_minima = lotes["data_chegada"].min().date()
            col_inicio, col_fim = st.columns(2)
            with col_inicio:
                data_inicio = st.date_input(
                    "Período Inicial",
                    value=data_minima,
                    min_value=data_minima,
                    max_value=hoje,
                    format="DD/MM/YYYY",
                    key="pinteiro_dashboard_inicio",
                )
            with col_fim:
                data_fim = st.date_input(
                    "Período Final",
                    value=hoje,
                    min_value=data_minima,
                    max_value=hoje,
                    format="DD/MM/YYYY",
                    key="pinteiro_dashboard_fim",
                )

            if data_inicio > data_fim:
                st.error("A data inicial não pode ser posterior à data final.")
            else:
                if lote_selecionado:
                    lotes = lotes[lotes["id"] == lote_selecionado].copy()
                    registros_racao = registros_racao[
                        registros_racao["lote_id"] == lote_selecionado
                    ].copy()
                    registros_mortalidade = registros_mortalidade[
                        registros_mortalidade["lote_id"] == lote_selecionado
                    ].copy()
                    vacinas = vacinas[vacinas["lote_id"] == lote_selecionado].copy()

                racao_diaria_registrada = expandir_consumo_racao(registros_racao)
                if not racao_diaria_registrada.empty:
                    racao_diaria_registrada["data"] = pd.to_datetime(
                        racao_diaria_registrada["data"]
                    )
                    racao_periodo = racao_diaria_registrada[
                        (racao_diaria_registrada["data"].dt.date >= data_inicio)
                        & (racao_diaria_registrada["data"].dt.date <= data_fim)
                    ].copy()
                else:
                    racao_periodo = racao_diaria_registrada

                if not registros_mortalidade.empty:
                    registros_mortalidade["data"] = pd.to_datetime(
                        registros_mortalidade["data"]
                    )
                    mortalidade_periodo = registros_mortalidade[
                        (registros_mortalidade["data"].dt.date >= data_inicio)
                        & (registros_mortalidade["data"].dt.date <= data_fim)
                    ].copy()
                else:
                    mortalidade_periodo = registros_mortalidade

                vacinas["status_exibicao"] = vacinas.apply(
                    lambda linha: status_exibicao_vacina(
                        linha["status"], linha["data_prevista"], hoje
                    ),
                    axis=1,
                ) if not vacinas.empty else pd.Series(dtype="object")

                mortes_no_dia = 0
                if not registros_mortalidade.empty:
                    mortes_no_dia = int(registros_mortalidade.loc[
                        registros_mortalidade["data"].dt.date == data_fim, "mortes"
                    ].sum())
                quantidade_inicial = int(lotes["quantidade_inicial"].sum())
                aves_vivas = int(lotes["aves_vivas"].sum())
                mortes_acumuladas = int(lotes["mortes_acumuladas"].sum())
                consumo_periodo = float(racao_periodo["racao_consumida"].sum()) if not racao_periodo.empty else 0
                consumo_acumulado = float(racao_diaria_registrada["racao_consumida"].sum()) if not racao_diaria_registrada.empty else 0
                percentual_mortalidade = (mortes_acumuladas / quantidade_inicial * 100) if quantidade_inicial else 0
                consumo_por_ave = consumo_periodo / aves_vivas if aves_vivas else 0

                metricas_linha_1 = st.columns(5)
                metricas_linha_1[0].metric("Quantidade Inicial", _formatar_inteiro(quantidade_inicial))
                metricas_linha_1[1].metric("Aves Vivas", _formatar_inteiro(aves_vivas))
                metricas_linha_1[2].metric("Mortalidade no Dia", _formatar_inteiro(mortes_no_dia))
                metricas_linha_1[3].metric("Mortalidade Acumulada", _formatar_inteiro(mortes_acumuladas))
                metricas_linha_1[4].metric("Mortalidade", f"{percentual_mortalidade:.2f}%")

                metricas_linha_2 = st.columns(4)
                metricas_linha_2[0].metric("Ração no Período", f"{_formatar_kg(consumo_periodo)} kg")
                metricas_linha_2[1].metric("Ração Acumulada", f"{_formatar_kg(consumo_acumulado)} kg")
                metricas_linha_2[2].metric("Média por Ave Viva", f"{_formatar_kg(consumo_por_ave)} kg")
                idade_media = int(lotes["idade_dias"].mean()) if not lotes.empty else 0
                metricas_linha_2[3].metric("Idade Atual", f"{idade_media} dias")
                previstas = int((vacinas["status_exibicao"] == "prevista").sum()) if not vacinas.empty else 0
                atrasadas = int((vacinas["status_exibicao"] == "atrasada").sum()) if not vacinas.empty else 0
                aplicadas = int((vacinas["status_exibicao"] == "aplicada").sum()) if not vacinas.empty else 0
                metricas_vacinas = st.columns(3)
                metricas_vacinas[0].metric("Vacinas Pendentes", previstas)
                metricas_vacinas[1].metric("Vacinas Aplicadas", aplicadas)
                metricas_vacinas[2].metric("Vacinas Atrasadas", atrasadas)

                previsoes = lotes["data_prevista_transferencia"].dropna()
                if not previsoes.empty:
                    st.caption(
                        "Previsão de transferência mais próxima: "
                        f"{pd.to_datetime(previsoes.min()).strftime('%d/%m/%Y')} para {DESTINO_PADRAO}."
                    )

                if racao_periodo.empty and mortalidade_periodo.empty:
                    st.info("Não há registros de ração ou mortalidade no período selecionado.")
                else:
                    racao_diaria = racao_periodo.groupby("data", as_index=False).agg(
                        racao_consumida=("racao_consumida", "sum")
                    ) if not racao_periodo.empty else pd.DataFrame({
                        "data": pd.Series(dtype="datetime64[ns]"),
                        "racao_consumida": pd.Series(dtype="float"),
                    })
                    mortalidade_diaria = mortalidade_periodo.groupby("data", as_index=False).agg(
                        mortes=("mortes", "sum")
                    ) if not mortalidade_periodo.empty else pd.DataFrame({
                        "data": pd.Series(dtype="datetime64[ns]"),
                        "mortes": pd.Series(dtype="float"),
                    })
                    diario = pd.merge(
                        racao_diaria,
                        mortalidade_diaria,
                        on="data",
                        how="outer",
                    ).sort_values("data")
                    diario["data"] = pd.to_datetime(diario["data"], errors="coerce")
                    diario = diario.dropna(subset=["data"])
                    diario[["racao_consumida", "mortes"]] = diario[
                        ["racao_consumida", "mortes"]
                    ].fillna(0)
                    diario["racao_acumulada"] = diario["racao_consumida"].cumsum()
                    diario["mortes_acumuladas"] = diario["mortes"].cumsum()
                    diario["aves_vivas_periodo"] = aves_vivas + diario["mortes"].sum() - diario["mortes_acumuladas"]
                    diario["racao_por_ave"] = diario.apply(
                        lambda linha: linha["racao_consumida"] / linha["aves_vivas_periodo"]
                        if linha["aves_vivas_periodo"] else 0,
                        axis=1,
                    )

                    tem_consumo = diario["racao_consumida"].sum() > 0
                    tem_mortalidade = diario["mortes"].sum() > 0
                    if not tem_consumo and not tem_mortalidade:
                        st.info("Não há consumo de ração ou mortes no período para exibir em gráficos.")
                    elif tem_consumo and tem_mortalidade:
                        grafico_coluna_1, grafico_coluna_2 = st.columns(2)
                        with grafico_coluna_1:
                            exibir_grafico(px.bar(diario, x="data", y="racao_consumida", title="Consumo Diário de Ração"), "pinteiro_grafico_consumo_diario")
                            exibir_grafico(px.line(diario, x="data", y="mortes", markers=True, title="Mortalidade Diária"), "pinteiro_grafico_mortes_diarias")
                            exibir_grafico(px.line(diario, x="data", y="aves_vivas_periodo", markers=True, title="Evolução de Aves Vivas"), "pinteiro_grafico_aves_vivas")
                        with grafico_coluna_2:
                            exibir_grafico(px.line(diario, x="data", y="racao_acumulada", markers=True, title="Consumo Acumulado de Ração"), "pinteiro_grafico_consumo_acumulado")
                            exibir_grafico(px.line(diario, x="data", y="mortes_acumuladas", markers=True, title="Mortalidade Acumulada"), "pinteiro_grafico_mortes_acumuladas")
                            exibir_grafico(px.line(diario, x="data", y="racao_por_ave", markers=True, title="Consumo Médio por Ave"), "pinteiro_grafico_consumo_por_ave")
                    elif tem_consumo:
                        coluna_1, coluna_2 = st.columns(2)
                        with coluna_1:
                            exibir_grafico(px.bar(diario, x="data", y="racao_consumida", title="Consumo Diário de Ração"), "pinteiro_grafico_consumo_diario")
                            exibir_grafico(px.line(diario, x="data", y="racao_por_ave", markers=True, title="Consumo Médio por Ave"), "pinteiro_grafico_consumo_por_ave")
                        with coluna_2:
                            exibir_grafico(px.line(diario, x="data", y="racao_acumulada", markers=True, title="Consumo Acumulado de Ração"), "pinteiro_grafico_consumo_acumulado")
                    else:
                        coluna_1, coluna_2 = st.columns(2)
                        with coluna_1:
                            exibir_grafico(px.line(diario, x="data", y="mortes", markers=True, title="Mortalidade Diária"), "pinteiro_grafico_mortes_diarias")
                            exibir_grafico(px.line(diario, x="data", y="aves_vivas_periodo", markers=True, title="Evolução de Aves Vivas"), "pinteiro_grafico_aves_vivas")
                        with coluna_2:
                            exibir_grafico(px.line(diario, x="data", y="mortes_acumuladas", markers=True, title="Mortalidade Acumulada"), "pinteiro_grafico_mortes_acumuladas")

                if not vacinas.empty:
                    vacinas_grafico = vacinas.copy()
                    vacinas_grafico["data"] = pd.to_datetime(vacinas_grafico["data_aplicacao"].fillna(vacinas_grafico["data_prevista"]))
                    vacinas_grafico["status_exibicao"] = vacinas_grafico[
                        "status_exibicao"
                    ].map(rotulo_status_vacina)
                    fig_vacinas = px.scatter(
                        vacinas_grafico,
                        x="data",
                        y="lote",
                        color="status_exibicao",
                        hover_data=["vacina", "dose", "responsavel"],
                        title="Linha do tempo de vacinação",
                        labels={"status_exibicao": "Status"},
                    )
                    st.plotly_chart(fig_vacinas, width="stretch", key="pinteiro_grafico_vacinas")

    with abas[1]:
        st.markdown("#### Cadastrar Lote")
        with st.form("pinteiro_form_lote", clear_on_submit=True):
            coluna_1, coluna_2 = st.columns(2)
            with coluna_1:
                nome = st.text_input("Identificação do lote")
                data_chegada = st.date_input(
                    "Data de chegada", value=hoje, max_value=hoje, format="DD/MM/YYYY"
                )
                quantidade_inicial = st.number_input("Quantidade inicial de pintos", min_value=1, step=1)
                fornecedor = st.text_input("Fornecedor ou origem")
            with coluna_2:
                linhagem = st.text_input("Linhagem")
                data_prevista = st.date_input(
                    "Data prevista de transferência",
                    value=hoje + timedelta(days=120),
                    min_value=data_chegada,
                    format="DD/MM/YYYY",
                )
                st.text_input("Destino previsto", value=DESTINO_PADRAO, disabled=True)
                observacoes = st.text_area("Observações")
            salvar_lote = st.form_submit_button("Salvar Lote", type="primary", width="stretch")

        if salvar_lote:
            nome = nome.strip()
            if not nome:
                st.error("Informe a identificação do lote.")
            else:
                chave = "pinteiro_salvar_lote"
                payload = (usuario, nome, data_chegada, int(quantidade_inicial))
                if not acao_repetida(chave, payload):
                    try:
                        with engine.connect() as conn:
                            with conn.begin():
                                novo_id = conn.execute(text("""
                                    INSERT INTO pinteiro_lotes (
                                        username, nome, data_chegada, quantidade_inicial,
                                        fornecedor, linhagem, data_prevista_transferencia,
                                        destino_previsto, observacoes
                                    ) VALUES (
                                        :username, :nome, :data_chegada, :quantidade_inicial,
                                        :fornecedor, :linhagem, :data_prevista, :destino, :observacoes
                                    ) RETURNING id
                                """), {
                                    "username": usuario,
                                    "nome": nome,
                                    "data_chegada": data_chegada,
                                    "quantidade_inicial": int(quantidade_inicial),
                                    "fornecedor": fornecedor.strip() or None,
                                    "linhagem": linhagem.strip() or None,
                                    "data_prevista": data_prevista,
                                    "destino": DESTINO_PADRAO,
                                    "observacoes": observacoes.strip() or None,
                                }).scalar_one()
                        registrar_log("INSERT", "pinteiro_lotes", novo_id, f"Cadastrou o lote {nome} no Pinteiro.")
                        st.success("Lote cadastrado com sucesso.")
                    except Exception as erro:
                        liberar_acao(chave)
                        if "unique" in str(erro).lower():
                            st.error("Já existe um lote com essa identificação.")
                        else:
                            st.error(f"Erro ao cadastrar lote: {erro}")

        lotes = enriquecer_lotes(carregar_lotes())
        st.divider()
        st.markdown("#### Lotes Cadastrados")
        if lotes.empty:
            st.info("Nenhum lote cadastrado.")
        else:
            exibicao = lotes[[
                "nome", "data_chegada", "idade_dias", "quantidade_inicial", "mortes_acumuladas",
                "aves_vivas", "status", "data_prevista_transferencia", "destino_previsto",
            ]].rename(columns={
                "nome": "Lote", "data_chegada": "Chegada", "idade_dias": "Idade (dias)",
                "quantidade_inicial": "Inicial", "mortes_acumuladas": "Mortes",
                "aves_vivas": "Aves Vivas", "status": "Status",
                "data_prevista_transferencia": "Previsão", "destino_previsto": "Destino",
            })
            exibicao["Status"] = exibicao["Status"].map(rotulo_status_lote)
            st.dataframe(
                exibicao,
                width="stretch",
                hide_index=True,
                height=min(420, 74 + len(exibicao) * 35),
                column_config={
                    "Chegada": st.column_config.DateColumn(
                        "Chegada", format="DD/MM/YYYY"
                    ),
                    "Previsão": st.column_config.DateColumn(
                        "Previsão", format="DD/MM/YYYY"
                    ),
                },
            )

            lotes_encerraveis = lotes[lotes["status"].isin(STATUS_ATIVOS)]
            if not lotes_encerraveis.empty:
                opcoes_encerramento = {
                    int(linha.id): linha.nome for linha in lotes_encerraveis.itertuples()
                }
                with st.expander("Encerrar Lote", expanded=False):
                    with st.form("pinteiro_form_encerrar_lote", clear_on_submit=True):
                        lote_encerrar_id = st.selectbox(
                            "Lote para Encerrar",
                            options=list(opcoes_encerramento),
                            format_func=lambda valor: opcoes_encerramento[valor],
                        )
                        confirmar_encerramento = st.checkbox("Confirmo o encerramento deste lote")
                        encerrar_lote = st.form_submit_button("Encerrar Lote", width="stretch")
                    if encerrar_lote:
                        if not confirmar_encerramento:
                            st.error("Marque a confirmação antes de encerrar o lote.")
                        else:
                            try:
                                with engine.connect() as conn:
                                    with conn.begin():
                                        conn.execute(text("""
                                            UPDATE pinteiro_lotes
                                            SET status = 'encerrado'
                                            WHERE id = :id AND username = :username
                                                AND status IN ('ativo', 'pronto_transferencia')
                                        """), {"id": int(lote_encerrar_id), "username": usuario})
                                registrar_log("UPDATE", "pinteiro_lotes", int(lote_encerrar_id), "Lote encerrado no Pinteiro.")
                                st.success("Lote encerrado com sucesso.")
                            except Exception as erro:
                                st.error(f"Erro ao encerrar lote: {erro}")

    with abas[2]:
        lotes = enriquecer_lotes(carregar_lotes())
        lotes_ativos = lotes[lotes["status"].isin(STATUS_ATIVOS)].copy() if not lotes.empty else lotes
        tab_racao, tab_mortalidade = st.tabs(["Ração", "Mortalidade"])

        with tab_racao:
            if lotes_ativos.empty:
                st.info("Cadastre um lote ativo antes de lançar registros de ração.")
            else:
                opcoes_lotes = {
                    int(linha.id): f"{linha.nome} - {int(linha.aves_vivas)} aves vivas"
                    for linha in lotes_ativos.itertuples()
                }
                with st.form("pinteiro_form_racao", clear_on_submit=True):
                    lote_id = st.selectbox("Lote", options=list(opcoes_lotes), format_func=lambda valor: opcoes_lotes[valor])
                    coluna_1, coluna_2 = st.columns(2)
                    with coluna_1:
                        periodo_racao = st.date_input(
                            "Período do Consumo",
                            value=(hoje, hoje),
                            max_value=hoje,
                            format="DD/MM/YYYY",
                        )
                        racao_consumida = st.number_input("Consumo por Dia (kg)", min_value=0.0, step=0.1, format="%.3f")
                    with coluna_2:
                        entrada_racao = st.number_input("Entrada de Ração no Período (kg)", min_value=0.0, step=0.1, format="%.3f")
                        responsavel = st.text_input("Responsável pelo Registro")
                    observacoes = st.text_area("Observações")
                    salvar_racao = st.form_submit_button("Salvar Registro de Ração", type="primary", width="stretch")

                if salvar_racao:
                    if not isinstance(periodo_racao, tuple) or len(periodo_racao) != 2:
                        st.error("Selecione a data inicial e a data final do período.")
                    elif racao_consumida <= 0 and entrada_racao <= 0:
                        st.error("Informe uma quantidade consumida ou uma entrada de ração.")
                    else:
                        data_registro, data_fim_registro = periodo_racao
                        total_consumo = float(racao_consumida) * (
                            (data_fim_registro - data_registro).days + 1
                        )
                        chave = "pinteiro_salvar_racao"
                        payload = (usuario, lote_id, data_registro, data_fim_registro, float(racao_consumida), float(entrada_racao))
                        if not acao_repetida(chave, payload):
                            try:
                                conflito = False
                                with engine.connect() as conn:
                                    with conn.begin():
                                        bloquear_periodo_racao(conn, lote_id)
                                        conflito = bool(periodo_racao_conflitante(
                                            conn, lote_id, data_registro, data_fim_registro
                                        ))
                                        if not conflito:
                                            conn.execute(text("""
                                                INSERT INTO pinteiro_registros_racao (
                                                    username, lote_id, data, data_fim, racao_consumida,
                                                    entrada_racao, observacoes, responsavel
                                                ) VALUES (
                                                    :username, :lote_id, :data, :data_fim, :racao_consumida,
                                                    :entrada_racao, :observacoes, :responsavel
                                                )
                                            """), {
                                                "username": usuario, "lote_id": int(lote_id), "data": data_registro,
                                                "data_fim": data_fim_registro, "racao_consumida": float(racao_consumida),
                                                "entrada_racao": float(entrada_racao),
                                                "observacoes": observacoes.strip() or None,
                                                "responsavel": responsavel.strip() or None,
                                            })
                                if conflito:
                                    liberar_acao(chave)
                                    st.warning("Já existe um registro de ração que se sobrepõe a esse período.")
                                else:
                                    registrar_log("INSERT", "pinteiro_registros_racao", detalhes=f"Lançou ração do lote {opcoes_lotes[lote_id].split(' - ')[0]} de {data_registro.strftime('%d/%m/%Y')} a {data_fim_registro.strftime('%d/%m/%Y')}.")
                                    st.success(f"Registro salvo: {_formatar_kg(racao_consumida)} kg por dia, total de {_formatar_kg(total_consumo)} kg no período.")
                            except Exception as erro:
                                liberar_acao(chave)
                                if "unique" in str(erro).lower():
                                    st.warning("Já existe um registro de ração para este lote nesta data. Edite o registro existente.")
                                else:
                                    st.error(f"Erro ao salvar registro de ração: {erro}")

            registros_racao = carregar_registros_racao()
            st.divider()
            st.markdown("#### Histórico de Ração")
            if registros_racao.empty:
                st.info("Nenhum registro de ração cadastrado.")
            else:
                registros_racao = registros_racao.sort_values(["lote", "data", "id"]).copy()
                registros_racao["data"] = pd.to_datetime(registros_racao["data"])
                registros_racao["data_fim"] = pd.to_datetime(registros_racao["data_fim"])
                registros_racao["dias_periodo"] = (
                    registros_racao["data_fim"] - registros_racao["data"]
                ).dt.days + 1
                registros_racao["consumo_total"] = (
                    registros_racao["racao_consumida"] * registros_racao["dias_periodo"]
                )
                saldo_periodo = registros_racao["entrada_racao"] - registros_racao["consumo_total"]
                registros_racao["saldo_racao_lote"] = saldo_periodo.groupby(registros_racao["lote"]).cumsum()
                registros_racao["periodo"] = registros_racao.apply(
                    lambda linha: (
                        f"{linha['data'].strftime('%d/%m/%Y')} a "
                        f"{linha['data_fim'].strftime('%d/%m/%Y')}"
                    ),
                    axis=1,
                )
                exibicao = registros_racao[["periodo", "lote", "racao_consumida", "consumo_total", "entrada_racao", "saldo_racao_lote", "responsavel"]].rename(columns={
                    "periodo": "Período", "lote": "Lote", "racao_consumida": "Consumo por Dia (kg)",
                    "consumo_total": "Consumo Total (kg)", "entrada_racao": "Entrada no Período (kg)",
                    "saldo_racao_lote": "Saldo de Ração (kg)",
                    "responsavel": "Responsável",
                })
                st.dataframe(
                    exibicao, width="stretch", hide_index=True,
                    height=min(420, 74 + len(exibicao) * 35),
                )

                opcoes_racao = {
                    int(linha.id): (
                        f"{linha.lote} | {pd.to_datetime(linha.data).strftime('%d/%m/%Y')} "
                        f"a {pd.to_datetime(linha.data_fim).strftime('%d/%m/%Y')}"
                    )
                    for linha in registros_racao.itertuples()
                }
                with st.expander("Editar ou Excluir Registro de Ração", expanded=False):
                    registro_id = st.selectbox("Registro de Ração", [None, *opcoes_racao], format_func=lambda valor: "Selecione um registro" if valor is None else opcoes_racao[valor])
                    if registro_id is not None:
                        registro = registros_racao[registros_racao["id"] == registro_id].iloc[0]
                        aba_editar, aba_excluir = st.tabs(["Editar", "Excluir"])
                        with aba_editar:
                            with st.form(f"pinteiro_editar_racao_{registro_id}"):
                                novo_periodo = st.date_input(
                                    "Período do Consumo",
                                    value=(pd.to_datetime(registro["data"]).date(), pd.to_datetime(registro["data_fim"]).date()),
                                    max_value=hoje,
                                    format="DD/MM/YYYY",
                                )
                                nova_consumida = st.number_input("Consumo por Dia (kg)", min_value=0.0, value=float(registro["racao_consumida"]), step=0.1, format="%.3f")
                                nova_entrada = st.number_input("Entrada de Ração no Período (kg)", min_value=0.0, value=float(registro["entrada_racao"]), step=0.1, format="%.3f")
                                novo_responsavel = st.text_input("Responsável", value=registro["responsavel"] or "")
                                novas_observacoes = st.text_area("Observações", value=registro["observacoes"] or "")
                                salvar_edicao = st.form_submit_button("Salvar Alterações", type="primary", width="stretch")
                            if salvar_edicao:
                                if not isinstance(novo_periodo, tuple) or len(novo_periodo) != 2:
                                    st.error("Selecione a data inicial e a data final do período.")
                                elif nova_consumida <= 0 and nova_entrada <= 0:
                                    st.error("Informe uma quantidade consumida ou uma entrada de ração.")
                                else:
                                    try:
                                        nova_data, nova_data_fim = novo_periodo
                                        conflito = False
                                        with engine.connect() as conn:
                                            with conn.begin():
                                                bloquear_periodo_racao(conn, registro["lote_id"])
                                                conflito = bool(periodo_racao_conflitante(
                                                    conn, registro["lote_id"], nova_data, nova_data_fim, registro_id
                                                ))
                                                if not conflito:
                                                    conn.execute(text("""
                                                        UPDATE pinteiro_registros_racao
                                                        SET data = :data, data_fim = :data_fim,
                                                            racao_consumida = :consumida, entrada_racao = :entrada,
                                                            responsavel = :responsavel, observacoes = :observacoes
                                                        WHERE id = :id AND username = :username
                                                    """), {"data": nova_data, "data_fim": nova_data_fim, "consumida": float(nova_consumida), "entrada": float(nova_entrada), "responsavel": novo_responsavel.strip() or None, "observacoes": novas_observacoes.strip() or None, "id": int(registro_id), "username": usuario})
                                        if conflito:
                                            st.warning("Já existe um registro de ração que se sobrepõe a esse período.")
                                        else:
                                            registrar_log("UPDATE", "pinteiro_registros_racao", int(registro_id), "Editou um registro de ração.")
                                            st.success("Registro de ração atualizado com sucesso.")
                                    except Exception as erro:
                                        if "unique" in str(erro).lower():
                                            st.warning("Já existe um registro de ração para este lote nessa data.")
                                        else:
                                            st.error(f"Erro ao atualizar registro de ração: {erro}")
                        with aba_excluir:
                            with st.form(f"pinteiro_excluir_racao_{registro_id}"):
                                confirmar_exclusao = st.checkbox("Confirmo a exclusão deste registro de ração")
                                excluir_racao = st.form_submit_button("Excluir Registro", type="primary", width="stretch")
                            if excluir_racao:
                                if not confirmar_exclusao:
                                    st.error("Marque a confirmação antes de excluir o registro.")
                                else:
                                    try:
                                        with engine.connect() as conn:
                                            with conn.begin():
                                                conn.execute(text("DELETE FROM pinteiro_registros_racao WHERE id = :id AND username = :username"), {"id": int(registro_id), "username": usuario})
                                        registrar_log("DELETE", "pinteiro_registros_racao", int(registro_id), "Excluiu um registro de ração.")
                                        st.success("Registro de ração excluído com sucesso.")
                                    except Exception as erro:
                                        st.error(f"Erro ao excluir registro de ração: {erro}")

        with tab_mortalidade:
            if lotes_ativos.empty:
                st.info("Cadastre um lote ativo antes de lançar registros de mortalidade.")
            else:
                opcoes_lotes = {
                    int(linha.id): f"{linha.nome} - {int(linha.aves_vivas)} aves vivas"
                    for linha in lotes_ativos.itertuples()
                }
                with st.form("pinteiro_form_mortalidade", clear_on_submit=True):
                    lote_id = st.selectbox("Lote", options=list(opcoes_lotes), format_func=lambda valor: opcoes_lotes[valor])
                    coluna_1, coluna_2 = st.columns(2)
                    with coluna_1:
                        data_registro = st.date_input("Data", value=hoje, max_value=hoje, format="DD/MM/YYYY")
                        mortes = st.number_input("Quantidade de Mortes", min_value=1, step=1)
                    with coluna_2:
                        causa = st.text_input("Causa da Mortalidade")
                        responsavel = st.text_input("Responsável pelo Registro")
                    observacoes = st.text_area("Observações")
                    salvar_mortalidade = st.form_submit_button("Salvar Registro de Mortalidade", type="primary", width="stretch")

                if salvar_mortalidade:
                    lote = lotes_ativos[lotes_ativos["id"] == lote_id].iloc[0]
                    if mortes > int(lote["aves_vivas"]):
                        st.error("A quantidade de mortes não pode ser maior que a quantidade de aves vivas do lote.")
                    else:
                        chave = "pinteiro_salvar_mortalidade"
                        payload = (usuario, lote_id, data_registro, int(mortes))
                        if not acao_repetida(chave, payload):
                            try:
                                with engine.connect() as conn:
                                    with conn.begin():
                                        conn.execute(text("""
                                            INSERT INTO pinteiro_registros_mortalidade (
                                                username, lote_id, data, mortes, causa_mortalidade,
                                                observacoes, responsavel
                                            ) VALUES (
                                                :username, :lote_id, :data, :mortes, :causa,
                                                :observacoes, :responsavel
                                            )
                                        """), {"username": usuario, "lote_id": int(lote_id), "data": data_registro, "mortes": int(mortes), "causa": causa.strip() or None, "observacoes": observacoes.strip() or None, "responsavel": responsavel.strip() or None})
                                registrar_log("INSERT", "pinteiro_registros_mortalidade", detalhes=f"Lançou mortalidade do lote {lote.nome} em {data_registro.strftime('%d/%m/%Y')}.")
                                st.success("Registro de mortalidade salvo com sucesso.")
                            except Exception as erro:
                                liberar_acao(chave)
                                if "unique" in str(erro).lower():
                                    st.warning("Já existe um registro de mortalidade para este lote nesta data. Edite o registro existente.")
                                else:
                                    st.error(f"Erro ao salvar registro de mortalidade: {erro}")

            registros_mortalidade = carregar_registros_mortalidade()
            st.divider()
            st.markdown("#### Histórico de Mortalidade")
            if registros_mortalidade.empty:
                st.info("Nenhum registro de mortalidade cadastrado.")
            else:
                exibicao = registros_mortalidade[["data", "lote", "mortes", "causa_mortalidade", "responsavel"]].rename(columns={
                    "data": "Data", "lote": "Lote", "mortes": "Mortes",
                    "causa_mortalidade": "Causa da Mortalidade", "responsavel": "Responsável",
                })
                st.dataframe(
                    exibicao, width="stretch", hide_index=True,
                    height=min(420, 74 + len(exibicao) * 35),
                    column_config={"Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")},
                )

                opcoes_mortalidade = {
                    int(linha.id): f"{linha.lote} | {pd.to_datetime(linha.data).strftime('%d/%m/%Y')} | {int(linha.mortes)} morte(s)"
                    for linha in registros_mortalidade.itertuples()
                }
                with st.expander("Editar ou Excluir Registro de Mortalidade", expanded=False):
                    registro_id = st.selectbox("Registro de Mortalidade", [None, *opcoes_mortalidade], format_func=lambda valor: "Selecione um registro" if valor is None else opcoes_mortalidade[valor])
                    if registro_id is not None:
                        registro = registros_mortalidade[registros_mortalidade["id"] == registro_id].iloc[0]
                        lote = lotes[lotes["id"] == registro["lote_id"]].iloc[0]
                        limite_mortes = int(lote["aves_vivas"]) + int(registro["mortes"])
                        aba_editar, aba_excluir = st.tabs(["Editar", "Excluir"])
                        with aba_editar:
                            with st.form(f"pinteiro_editar_mortalidade_{registro_id}"):
                                nova_data = st.date_input("Data", value=pd.to_datetime(registro["data"]).date(), max_value=hoje, format="DD/MM/YYYY")
                                novas_mortes = st.number_input("Quantidade de Mortes", min_value=1, max_value=max(1, limite_mortes), value=int(registro["mortes"]), step=1)
                                nova_causa = st.text_input("Causa da Mortalidade", value=registro["causa_mortalidade"] or "")
                                novo_responsavel = st.text_input("Responsável", value=registro["responsavel"] or "")
                                novas_observacoes = st.text_area("Observações", value=registro["observacoes"] or "")
                                salvar_edicao = st.form_submit_button("Salvar Alterações", type="primary", width="stretch")
                            if salvar_edicao:
                                try:
                                    with engine.connect() as conn:
                                        with conn.begin():
                                            conn.execute(text("""
                                                UPDATE pinteiro_registros_mortalidade
                                                SET data = :data, mortes = :mortes,
                                                    causa_mortalidade = :causa, responsavel = :responsavel,
                                                    observacoes = :observacoes
                                                WHERE id = :id AND username = :username
                                            """), {"data": nova_data, "mortes": int(novas_mortes), "causa": nova_causa.strip() or None, "responsavel": novo_responsavel.strip() or None, "observacoes": novas_observacoes.strip() or None, "id": int(registro_id), "username": usuario})
                                    registrar_log("UPDATE", "pinteiro_registros_mortalidade", int(registro_id), "Editou um registro de mortalidade.")
                                    st.success("Registro de mortalidade atualizado com sucesso.")
                                except Exception as erro:
                                    if "unique" in str(erro).lower():
                                        st.warning("Já existe um registro de mortalidade para este lote nessa data.")
                                    else:
                                        st.error(f"Erro ao atualizar registro de mortalidade: {erro}")
                        with aba_excluir:
                            with st.form(f"pinteiro_excluir_mortalidade_{registro_id}"):
                                confirmar_exclusao = st.checkbox("Confirmo a exclusão deste registro de mortalidade")
                                excluir_mortalidade = st.form_submit_button("Excluir Registro", type="primary", width="stretch")
                            if excluir_mortalidade:
                                if not confirmar_exclusao:
                                    st.error("Marque a confirmação antes de excluir o registro.")
                                else:
                                    try:
                                        with engine.connect() as conn:
                                            with conn.begin():
                                                conn.execute(text("DELETE FROM pinteiro_registros_mortalidade WHERE id = :id AND username = :username"), {"id": int(registro_id), "username": usuario})
                                        registrar_log("DELETE", "pinteiro_registros_mortalidade", int(registro_id), "Excluiu um registro de mortalidade.")
                                        st.success("Registro de mortalidade excluído com sucesso.")
                                    except Exception as erro:
                                        st.error(f"Erro ao excluir registro de mortalidade: {erro}")

    with abas[3]:
        lotes = enriquecer_lotes(carregar_lotes())
        if lotes.empty:
            st.info("Cadastre um lote antes de registrar vacinações.")
        else:
            opcoes_lotes = {int(linha.id): linha.nome for linha in lotes.itertuples()}
            with st.form("pinteiro_form_vacina", clear_on_submit=True):
                lote_id = st.selectbox("Lote", options=list(opcoes_lotes), format_func=lambda valor: opcoes_lotes[valor])
                coluna_1, coluna_2 = st.columns(2)
                with coluna_1:
                    vacina = st.text_input("Vacina")
                    data_prevista = st.date_input("Data prevista", value=hoje, format="DD/MM/YYYY")
                    dose = st.number_input("Quantidade ou dose", min_value=0.0, step=0.1, format="%.3f")
                with coluna_2:
                    lote_vacina = st.text_input("Lote da vacina")
                    responsavel = st.text_input("Responsável")
                    observacoes = st.text_area("Observações")
                salvar_vacina = st.form_submit_button("Agendar Vacina", type="primary", width="stretch")

            if salvar_vacina:
                if not vacina.strip():
                    st.error("Informe o nome da vacina.")
                else:
                    chave = "pinteiro_agendar_vacina"
                    payload = (usuario, lote_id, vacina.strip(), data_prevista)
                    if not acao_repetida(chave, payload):
                        try:
                            with engine.connect() as conn:
                                with conn.begin():
                                    vacina_id = conn.execute(text("""
                                        INSERT INTO pinteiro_vacinacoes (
                                            username, lote_id, vacina, data_prevista, dose,
                                            lote_vacina, responsavel, observacoes
                                        ) VALUES (
                                            :username, :lote_id, :vacina, :data_prevista, :dose,
                                            :lote_vacina, :responsavel, :observacoes
                                        ) RETURNING id
                                    """), {
                                        "username": usuario, "lote_id": int(lote_id), "vacina": vacina.strip(),
                                        "data_prevista": data_prevista, "dose": float(dose) or None,
                                        "lote_vacina": lote_vacina.strip() or None,
                                        "responsavel": responsavel.strip() or None,
                                        "observacoes": observacoes.strip() or None,
                                    }).scalar_one()
                            registrar_log("INSERT", "pinteiro_vacinacoes", vacina_id, f"Agendou a vacina {vacina.strip()} para o lote {opcoes_lotes[lote_id]}.")
                            st.success("Vacina agendada com sucesso.")
                        except Exception as erro:
                            liberar_acao(chave)
                            st.error(f"Erro ao agendar vacina: {erro}")

        vacinas = carregar_vacinas()
        if vacinas.empty:
            st.info("Nenhuma vacina cadastrada.")
        else:
            vacinas["status_exibicao"] = vacinas.apply(
                lambda linha: status_exibicao_vacina(linha["status"], linha["data_prevista"], hoje), axis=1
            )
            atrasadas = vacinas[vacinas["status_exibicao"] == "atrasada"]
            if not atrasadas.empty:
                st.warning(f"Há {len(atrasadas)} vacina(s) atrasada(s).")
            proximas = vacinas[(vacinas["status_exibicao"] == "prevista") & (pd.to_datetime(vacinas["data_prevista"]).dt.date <= hoje + timedelta(days=7))]
            if not proximas.empty:
                st.info(f"Há {len(proximas)} vacina(s) prevista(s) para os próximos 7 dias.")

            exibicao = vacinas[["id", "lote", "vacina", "data_prevista", "data_aplicacao", "dose", "status_exibicao", "responsavel"]].rename(columns={
                "id": "ID", "lote": "Lote", "vacina": "Vacina", "data_prevista": "Prevista",
                "data_aplicacao": "Aplicação", "dose": "Dose", "status_exibicao": "Status",
                "responsavel": "Responsável",
            })
            exibicao["Status"] = exibicao["Status"].map(rotulo_status_vacina)
            st.dataframe(
                exibicao,
                width="stretch",
                hide_index=True,
                height=min(420, 74 + len(exibicao) * 35),
                column_config={
                    "Prevista": st.column_config.DateColumn(
                        "Prevista", format="DD/MM/YYYY"
                    ),
                    "Aplicação": st.column_config.DateColumn(
                        "Aplicação", format="DD/MM/YYYY"
                    ),
                },
            )

            pendentes = vacinas[vacinas["status"].isin(["prevista", "atrasada"])].copy()
            if not pendentes.empty:
                opcoes_vacinas = {int(linha.id): f"{linha.lote} - {linha.vacina} ({pd.to_datetime(linha.data_prevista).strftime('%d/%m/%Y')})" for linha in pendentes.itertuples()}
                with st.form("pinteiro_form_atualizar_vacina", clear_on_submit=True):
                    vacina_id = st.selectbox("Vacina para atualizar", options=list(opcoes_vacinas), format_func=lambda valor: opcoes_vacinas[valor])
                    data_aplicacao = st.date_input("Data da aplicação", value=hoje, max_value=hoje, format="DD/MM/YYYY")
                    coluna_aplicar, coluna_cancelar = st.columns(2)
                    with coluna_aplicar:
                        aplicar = st.form_submit_button("Marcar como Aplicada", type="primary", width="stretch")
                    with coluna_cancelar:
                        cancelar = st.form_submit_button("Cancelar Vacina", width="stretch")

                if aplicar or cancelar:
                    novo_status = "aplicada" if aplicar else "cancelada"
                    try:
                        with engine.connect() as conn:
                            with conn.begin():
                                conn.execute(text("""
                                    UPDATE pinteiro_vacinacoes
                                    SET status = :status,
                                        data_aplicacao = CASE WHEN :status = 'aplicada' THEN :data_aplicacao ELSE data_aplicacao END
                                    WHERE id = :id AND username = :username
                                """), {"status": novo_status, "data_aplicacao": data_aplicacao, "id": int(vacina_id), "username": usuario})
                        registrar_log("UPDATE", "pinteiro_vacinacoes", int(vacina_id), f"Atualizou vacina: {novo_status}.")
                        st.success("Status da vacina atualizado.")
                    except Exception as erro:
                        st.error(f"Erro ao atualizar vacina: {erro}")

    with abas[4]:
        st.markdown("#### Destino Previsto: Galpão 4")
        disponivel = destino_disponivel()
        if disponivel:
            st.success("Galpão 4 está marcado como disponível para receber lotes do Pinteiro.")
        else:
            st.warning("Galpão 4 ainda não está disponível. A transferência definitiva permanece bloqueada.")

        with st.expander("Configurar Disponibilidade do Galpão 4", expanded=False):
            with st.form("pinteiro_form_destino"):
                ativo = st.checkbox("Galpão 4 está pronto para receber aves", value=disponivel)
                salvar_destino = st.form_submit_button("Salvar Disponibilidade", width="stretch")
            if salvar_destino:
                try:
                    with engine.connect() as conn:
                        with conn.begin():
                            conn.execute(text("""
                                INSERT INTO pinteiro_destinos (username, galpao, ativo)
                                VALUES (:username, :galpao, :ativo)
                                ON CONFLICT (username, galpao) DO UPDATE
                                SET ativo = EXCLUDED.ativo, atualizado_em = CURRENT_TIMESTAMP
                            """), {"username": usuario, "galpao": DESTINO_PADRAO, "ativo": ativo})
                    registrar_log("UPDATE", "pinteiro_destinos", detalhes=f"Disponibilidade do {DESTINO_PADRAO}: {'ativa' if ativo else 'em construção'}.")
                    st.success("Disponibilidade atualizada.")
                except Exception as erro:
                    st.error(f"Erro ao configurar destino: {erro}")

        lotes = enriquecer_lotes(carregar_lotes())
        transferiveis = lotes[lotes["status"].isin(STATUS_ATIVOS)].copy() if not lotes.empty else lotes
        if transferiveis.empty:
            st.info("Não há lotes ativos ou prontos para transferência.")
        else:
            opcoes_lotes = {
                int(linha.id): (
                    f"{linha.nome} - {int(linha.aves_vivas)} aves vivas - "
                    f"{rotulo_status_lote(linha.status)}"
                )
                for linha in transferiveis.itertuples()
            }
            with st.form("pinteiro_form_pronto_transferencia", clear_on_submit=True):
                lote_pronto_id = st.selectbox("Lote", options=list(opcoes_lotes), format_func=lambda valor: opcoes_lotes[valor], key="pinteiro_lote_pronto")
                marcar_pronto = st.form_submit_button("Marcar como Pronto para Transferência", width="stretch")
            if marcar_pronto:
                try:
                    with engine.connect() as conn:
                        with conn.begin():
                            conn.execute(text("""
                                UPDATE pinteiro_lotes
                                SET status = 'pronto_transferencia'
                                WHERE id = :id AND username = :username AND status = 'ativo'
                            """), {"id": int(lote_pronto_id), "username": usuario})
                    registrar_log("UPDATE", "pinteiro_lotes", int(lote_pronto_id), "Lote marcado como pronto para transferência.")
                    st.success("Lote marcado como pronto para transferência.")
                except Exception as erro:
                    st.error(f"Erro ao atualizar lote: {erro}")

            prontos = transferiveis[transferiveis["status"] == "pronto_transferencia"].copy()
            if prontos.empty:
                st.info("Marque um lote como pronto antes de transferi-lo.")
            else:
                opcoes_prontos = {int(linha.id): f"{linha.nome} - {int(linha.aves_vivas)} aves vivas" for linha in prontos.itertuples()}
                with st.form("pinteiro_form_transferir", clear_on_submit=True):
                    lote_id = st.selectbox("Lote pronto", options=list(opcoes_prontos), format_func=lambda valor: opcoes_prontos[valor])
                    lote = prontos[prontos["id"] == lote_id].iloc[0]
                    data_transferencia = st.date_input("Data da transferência", value=hoje, max_value=hoje, format="DD/MM/YYYY")
                    st.number_input("Quantidade a transferir", min_value=int(lote["aves_vivas"]), max_value=int(lote["aves_vivas"]), value=int(lote["aves_vivas"]), disabled=True)
                    responsavel = st.text_input("Responsável pela transferência")
                    observacoes = st.text_area("Observações da transferência")
                    confirmar = st.checkbox("Confirmo a transferência integral deste lote para o Galpão 4")
                    transferir = st.form_submit_button("Confirmar Transferência", type="primary", width="stretch", disabled=not disponivel)

                if transferir:
                    if not confirmar:
                        st.error("Marque a confirmação antes de transferir o lote.")
                    else:
                        chave = "pinteiro_transferir_lote"
                        payload = (usuario, lote_id, data_transferencia, int(lote["aves_vivas"]))
                        if not acao_repetida(chave, payload):
                            try:
                                with engine.connect() as conn:
                                    with conn.begin():
                                        lote_atual = conn.execute(text("""
                                            SELECT quantidade_inicial, quantidade_transferida, status
                                            FROM pinteiro_lotes
                                            WHERE id = :id AND username = :username
                                            FOR UPDATE
                                        """), {"id": int(lote_id), "username": usuario}).mappings().one_or_none()
                                        destino_ativo = conn.execute(text("""
                                            SELECT ativo FROM pinteiro_destinos
                                            WHERE username = :username AND galpao = :galpao
                                            FOR UPDATE
                                        """), {"username": usuario, "galpao": DESTINO_PADRAO}).scalar()
                                        transferencia_existente = conn.execute(text("""
                                            SELECT id FROM pinteiro_transferencias WHERE lote_id = :lote_id
                                        """), {"lote_id": int(lote_id)}).scalar()
                                        mortes = conn.execute(text("""
                                            SELECT COALESCE(SUM(mortes), 0)
                                            FROM pinteiro_registros_mortalidade
                                            WHERE username = :username AND lote_id = :lote_id
                                        """), {"username": usuario, "lote_id": int(lote_id)}).scalar()

                                        if not lote_atual or lote_atual["status"] != "pronto_transferencia":
                                            raise ValueError("O lote não está pronto para transferência.")
                                        if not destino_ativo:
                                            raise ValueError("O Galpão 4 não está disponível para transferência.")
                                        if transferencia_existente:
                                            raise ValueError("Este lote já foi transferido.")
                                        quantidade = calcular_aves_vivas(
                                            lote_atual["quantidade_inicial"], mortes, lote_atual["quantidade_transferida"]
                                        )
                                        if quantidade <= 0:
                                            raise ValueError("O lote não possui aves vivas para transferir.")

                                        movimento_adulto = conn.execute(text("""
                                            SELECT id, quantidade_total
                                            FROM aves
                                            WHERE username = :username
                                                AND galpao = :galpao
                                                AND data_registro = :data
                                            ORDER BY id LIMIT 1 FOR UPDATE
                                        """), {"username": usuario, "galpao": DESTINO_PADRAO, "data": data_transferencia}).mappings().one_or_none()
                                        if movimento_adulto:
                                            conn.execute(text("""
                                                UPDATE aves SET quantidade_total = :quantidade
                                                WHERE id = :id AND username = :username
                                            """), {"quantidade": int(movimento_adulto["quantidade_total"]) + quantidade, "id": movimento_adulto["id"], "username": usuario})
                                        else:
                                            conn.execute(text("""
                                                INSERT INTO aves (username, galpao, quantidade_total, data_registro)
                                                VALUES (:username, :galpao, :quantidade, :data)
                                            """), {"username": usuario, "galpao": DESTINO_PADRAO, "quantidade": quantidade, "data": data_transferencia})

                                        conn.execute(text("""
                                            INSERT INTO pinteiro_transferencias (
                                                username, lote_id, data, quantidade, destino, responsavel, observacoes
                                            ) VALUES (
                                                :username, :lote_id, :data, :quantidade, :destino, :responsavel, :observacoes
                                            )
                                        """), {
                                            "username": usuario, "lote_id": int(lote_id), "data": data_transferencia,
                                            "quantidade": quantidade, "destino": DESTINO_PADRAO,
                                            "responsavel": responsavel.strip() or None,
                                            "observacoes": observacoes.strip() or None,
                                        })
                                        conn.execute(text("""
                                            UPDATE pinteiro_lotes
                                            SET status = 'transferido', quantidade_transferida = :quantidade,
                                                data_transferencia = :data
                                            WHERE id = :id AND username = :username
                                        """), {"quantidade": quantidade, "data": data_transferencia, "id": int(lote_id), "username": usuario})
                                registrar_log("UPDATE", "pinteiro_lotes", int(lote_id), f"Transferiu {quantidade} aves do Pinteiro para o {DESTINO_PADRAO}.")
                                st.success(f"Transferência concluída: {quantidade} aves registradas no {DESTINO_PADRAO}.")
                            except Exception as erro:
                                liberar_acao(chave)
                                st.error(f"Transferência não concluída: {erro}")

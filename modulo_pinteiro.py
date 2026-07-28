from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text


DESTINO_PADRAO = "Galpão 4"
STATUS_ATIVOS = ("ativo", "pronto_transferencia")


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
                COALESCE(SUM(r.mortes), 0) AS mortes_acumuladas
            FROM pinteiro_lotes l
            LEFT JOIN pinteiro_registros_diarios r ON r.lote_id = l.id
                AND r.username = l.username
            WHERE l.username = :username
            GROUP BY l.id
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

    def carregar_registros():
        return pd.read_sql(text("""
            SELECT r.*, l.nome AS lote
            FROM pinteiro_registros_diarios r
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

    st.markdown("### Pinteiro")
    st.caption(
        "Controle isolado de pintos. Os dados desta area nao entram nos indicadores "
        "dos Galpoes 2 e 3."
    )

    abas = st.tabs([
        "Dashboard",
        "Lotes",
        "Controle diario",
        "Vacinacao",
        "Transferencia",
    ])

    with abas[0]:
        lotes = enriquecer_lotes(carregar_lotes())
        registros = carregar_registros()
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
                    "Periodo inicial",
                    value=data_minima,
                    min_value=data_minima,
                    max_value=hoje,
                    format="DD/MM/YYYY",
                    key="pinteiro_dashboard_inicio",
                )
            with col_fim:
                data_fim = st.date_input(
                    "Periodo final",
                    value=hoje,
                    min_value=data_minima,
                    max_value=hoje,
                    format="DD/MM/YYYY",
                    key="pinteiro_dashboard_fim",
                )

            if data_inicio > data_fim:
                st.error("A data inicial nao pode ser posterior a data final.")
            else:
                if lote_selecionado:
                    lotes = lotes[lotes["id"] == lote_selecionado].copy()
                    registros = registros[registros["lote_id"] == lote_selecionado].copy()
                    vacinas = vacinas[vacinas["lote_id"] == lote_selecionado].copy()

                if not registros.empty:
                    registros["data"] = pd.to_datetime(registros["data"])
                    registros_periodo = registros[
                        (registros["data"].dt.date >= data_inicio)
                        & (registros["data"].dt.date <= data_fim)
                    ].copy()
                else:
                    registros_periodo = registros

                vacinas["status_exibicao"] = vacinas.apply(
                    lambda linha: status_exibicao_vacina(
                        linha["status"], linha["data_prevista"], hoje
                    ),
                    axis=1,
                ) if not vacinas.empty else pd.Series(dtype="object")

                mortes_no_dia = 0
                if not registros.empty:
                    mortes_no_dia = int(registros.loc[
                        registros["data"].dt.date == data_fim, "mortes"
                    ].sum())
                quantidade_inicial = int(lotes["quantidade_inicial"].sum())
                aves_vivas = int(lotes["aves_vivas"].sum())
                mortes_acumuladas = int(lotes["mortes_acumuladas"].sum())
                consumo_periodo = float(registros_periodo["racao_consumida"].sum()) if not registros_periodo.empty else 0
                consumo_acumulado = float(registros["racao_consumida"].sum()) if not registros.empty else 0
                percentual_mortalidade = (mortes_acumuladas / quantidade_inicial * 100) if quantidade_inicial else 0
                consumo_por_ave = consumo_periodo / aves_vivas if aves_vivas else 0

                metricas_linha_1 = st.columns(5)
                metricas_linha_1[0].metric("Quantidade inicial", _formatar_inteiro(quantidade_inicial))
                metricas_linha_1[1].metric("Aves vivas", _formatar_inteiro(aves_vivas))
                metricas_linha_1[2].metric("Mortalidade no dia", _formatar_inteiro(mortes_no_dia))
                metricas_linha_1[3].metric("Mortalidade acumulada", _formatar_inteiro(mortes_acumuladas))
                metricas_linha_1[4].metric("Mortalidade", f"{percentual_mortalidade:.2f}%")

                metricas_linha_2 = st.columns(4)
                metricas_linha_2[0].metric("Racao no periodo", f"{_formatar_kg(consumo_periodo)} kg")
                metricas_linha_2[1].metric("Racao acumulada", f"{_formatar_kg(consumo_acumulado)} kg")
                metricas_linha_2[2].metric("Media por ave viva", f"{_formatar_kg(consumo_por_ave)} kg")
                idade_media = int(lotes["idade_dias"].mean()) if not lotes.empty else 0
                metricas_linha_2[3].metric("Idade atual", f"{idade_media} dias")
                previstas = int((vacinas["status_exibicao"] == "prevista").sum()) if not vacinas.empty else 0
                atrasadas = int((vacinas["status_exibicao"] == "atrasada").sum()) if not vacinas.empty else 0
                aplicadas = int((vacinas["status_exibicao"] == "aplicada").sum()) if not vacinas.empty else 0
                metricas_vacinas = st.columns(3)
                metricas_vacinas[0].metric("Vacinas pendentes", previstas)
                metricas_vacinas[1].metric("Vacinas aplicadas", aplicadas)
                metricas_vacinas[2].metric("Vacinas atrasadas", atrasadas)

                previsoes = lotes["data_prevista_transferencia"].dropna()
                if not previsoes.empty:
                    st.caption(
                        "Previsao de transferencia mais proxima: "
                        f"{pd.to_datetime(previsoes.min()).strftime('%d/%m/%Y')} para {DESTINO_PADRAO}."
                    )

                if registros_periodo.empty:
                    st.info("Nao ha registros diarios no periodo selecionado.")
                else:
                    diario = registros_periodo.groupby("data", as_index=False).agg(
                        racao_consumida=("racao_consumida", "sum"),
                        mortes=("mortes", "sum"),
                    ).sort_values("data")
                    diario["racao_acumulada"] = diario["racao_consumida"].cumsum()
                    diario["mortes_acumuladas"] = diario["mortes"].cumsum()
                    diario["aves_vivas_periodo"] = aves_vivas + diario["mortes"].sum() - diario["mortes_acumuladas"]
                    diario["racao_por_ave"] = diario.apply(
                        lambda linha: linha["racao_consumida"] / linha["aves_vivas_periodo"]
                        if linha["aves_vivas_periodo"] else 0,
                        axis=1,
                    )

                    grafico_coluna_1, grafico_coluna_2 = st.columns(2)
                    with grafico_coluna_1:
                        fig = px.bar(diario, x="data", y="racao_consumida", title="Consumo diario de racao")
                        st.plotly_chart(fig, width="stretch", key="pinteiro_grafico_consumo_diario")
                        fig = px.line(diario, x="data", y="mortes", markers=True, title="Mortalidade diaria")
                        st.plotly_chart(fig, width="stretch", key="pinteiro_grafico_mortes_diarias")
                        fig = px.line(diario, x="data", y="aves_vivas_periodo", markers=True, title="Evolucao de aves vivas")
                        st.plotly_chart(fig, width="stretch", key="pinteiro_grafico_aves_vivas")
                    with grafico_coluna_2:
                        fig = px.line(diario, x="data", y="racao_acumulada", markers=True, title="Consumo acumulado de racao")
                        st.plotly_chart(fig, width="stretch", key="pinteiro_grafico_consumo_acumulado")
                        fig = px.line(diario, x="data", y="mortes_acumuladas", markers=True, title="Mortalidade acumulada")
                        st.plotly_chart(fig, width="stretch", key="pinteiro_grafico_mortes_acumuladas")
                        fig = px.line(diario, x="data", y="racao_por_ave", markers=True, title="Consumo medio por ave")
                        st.plotly_chart(fig, width="stretch", key="pinteiro_grafico_consumo_por_ave")

                if not vacinas.empty:
                    vacinas_grafico = vacinas.copy()
                    vacinas_grafico["data"] = pd.to_datetime(vacinas_grafico["data_aplicacao"].fillna(vacinas_grafico["data_prevista"]))
                    fig_vacinas = px.scatter(
                        vacinas_grafico,
                        x="data",
                        y="lote",
                        color="status_exibicao",
                        hover_data=["vacina", "dose", "responsavel"],
                        title="Linha do tempo de vacinacao",
                    )
                    st.plotly_chart(fig_vacinas, width="stretch", key="pinteiro_grafico_vacinas")

    with abas[1]:
        st.markdown("#### Cadastrar lote")
        with st.form("pinteiro_form_lote", clear_on_submit=True):
            coluna_1, coluna_2 = st.columns(2)
            with coluna_1:
                nome = st.text_input("Identificacao do lote")
                data_chegada = st.date_input(
                    "Data de chegada", value=hoje, max_value=hoje, format="DD/MM/YYYY"
                )
                quantidade_inicial = st.number_input("Quantidade inicial de pintos", min_value=1, step=1)
                fornecedor = st.text_input("Fornecedor ou origem")
            with coluna_2:
                linhagem = st.text_input("Linhagem")
                data_prevista = st.date_input(
                    "Data prevista de transferencia",
                    value=hoje + timedelta(days=120),
                    min_value=data_chegada,
                    format="DD/MM/YYYY",
                )
                st.text_input("Destino previsto", value=DESTINO_PADRAO, disabled=True)
                observacoes = st.text_area("Observacoes")
            salvar_lote = st.form_submit_button("Salvar lote", type="primary", width="stretch")

        if salvar_lote:
            nome = nome.strip()
            if not nome:
                st.error("Informe a identificacao do lote.")
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
                            st.error("Ja existe um lote com essa identificacao.")
                        else:
                            st.error(f"Erro ao cadastrar lote: {erro}")

        lotes = enriquecer_lotes(carregar_lotes())
        st.divider()
        st.markdown("#### Lotes cadastrados")
        if lotes.empty:
            st.info("Nenhum lote cadastrado.")
        else:
            exibicao = lotes[[
                "nome", "data_chegada", "idade_dias", "quantidade_inicial", "mortes_acumuladas",
                "aves_vivas", "status", "data_prevista_transferencia", "destino_previsto",
            ]].rename(columns={
                "nome": "Lote", "data_chegada": "Chegada", "idade_dias": "Idade (dias)",
                "quantidade_inicial": "Inicial", "mortes_acumuladas": "Mortes",
                "aves_vivas": "Aves vivas", "status": "Status",
                "data_prevista_transferencia": "Previsao", "destino_previsto": "Destino",
            })
            st.dataframe(
                exibicao,
                width="stretch",
                hide_index=True,
                height=min(420, 74 + len(exibicao) * 35),
                column_config={
                    "Chegada": st.column_config.DateColumn(
                        "Chegada", format="DD/MM/YYYY"
                    ),
                    "Previsao": st.column_config.DateColumn(
                        "Previsao", format="DD/MM/YYYY"
                    ),
                },
            )

            lotes_encerraveis = lotes[lotes["status"].isin(STATUS_ATIVOS)]
            if not lotes_encerraveis.empty:
                opcoes_encerramento = {
                    int(linha.id): linha.nome for linha in lotes_encerraveis.itertuples()
                }
                with st.expander("Encerrar lote", expanded=False):
                    with st.form("pinteiro_form_encerrar_lote", clear_on_submit=True):
                        lote_encerrar_id = st.selectbox(
                            "Lote para encerrar",
                            options=list(opcoes_encerramento),
                            format_func=lambda valor: opcoes_encerramento[valor],
                        )
                        confirmar_encerramento = st.checkbox("Confirmo o encerramento deste lote")
                        encerrar_lote = st.form_submit_button("Encerrar lote", width="stretch")
                    if encerrar_lote:
                        if not confirmar_encerramento:
                            st.error("Marque a confirmacao antes de encerrar o lote.")
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
        if lotes_ativos.empty:
            st.info("Cadastre um lote ativo antes de lancar o controle diario.")
        else:
            opcoes_lotes = {int(linha.id): f"{linha.nome} - {int(linha.aves_vivas)} aves vivas" for linha in lotes_ativos.itertuples()}
            with st.form("pinteiro_form_registro_diario", clear_on_submit=True):
                lote_id = st.selectbox("Lote", options=list(opcoes_lotes), format_func=lambda valor: opcoes_lotes[valor])
                coluna_1, coluna_2 = st.columns(2)
                with coluna_1:
                    data_registro = st.date_input("Data", value=hoje, max_value=hoje, format="DD/MM/YYYY")
                    racao_consumida = st.number_input("Racao consumida (kg)", min_value=0.0, step=0.1, format="%.3f")
                    entrada_racao = st.number_input("Entrada de racao (kg)", min_value=0.0, step=0.1, format="%.3f")
                with coluna_2:
                    mortes = st.number_input("Mortes no dia", min_value=0, step=1)
                    causa = st.text_input("Causa da mortalidade (opcional)")
                    responsavel = st.text_input("Responsavel pelo registro")
                observacoes = st.text_area("Observacoes")
                salvar_registro = st.form_submit_button("Salvar registro diario", type="primary", width="stretch")

            if salvar_registro:
                lote = lotes_ativos[lotes_ativos["id"] == lote_id].iloc[0]
                if mortes > int(lote["aves_vivas"]):
                    st.error("A quantidade de mortes nao pode ser maior que as aves vivas do lote.")
                else:
                    chave = "pinteiro_salvar_registro"
                    payload = (usuario, lote_id, data_registro, float(racao_consumida), int(mortes))
                    if not acao_repetida(chave, payload):
                        try:
                            with engine.connect() as conn:
                                with conn.begin():
                                    conn.execute(text("""
                                        INSERT INTO pinteiro_registros_diarios (
                                            username, lote_id, data, racao_consumida, entrada_racao,
                                            mortes, causa_mortalidade, observacoes, responsavel
                                        ) VALUES (
                                            :username, :lote_id, :data, :racao_consumida, :entrada_racao,
                                            :mortes, :causa, :observacoes, :responsavel
                                        )
                                    """), {
                                        "username": usuario, "lote_id": int(lote_id), "data": data_registro,
                                        "racao_consumida": float(racao_consumida), "entrada_racao": float(entrada_racao),
                                        "mortes": int(mortes), "causa": causa.strip() or None,
                                        "observacoes": observacoes.strip() or None,
                                        "responsavel": responsavel.strip() or None,
                                    })
                            registrar_log("INSERT", "pinteiro_registros_diarios", detalhes=f"Lancou controle diario do lote {lote.nome} em {data_registro.strftime('%d/%m/%Y')}.")
                            st.success("Registro diario salvo com sucesso.")
                        except Exception as erro:
                            liberar_acao(chave)
                            if "unique" in str(erro).lower():
                                st.warning("Ja existe um registro diario para este lote nesta data. Edite o registro existente antes de continuar.")
                            else:
                                st.error(f"Erro ao salvar registro diario: {erro}")

        registros = carregar_registros()
        st.divider()
        st.markdown("#### Historico diario")
        if registros.empty:
            st.info("Nenhum registro diario cadastrado.")
        else:
            registros = registros.sort_values(["lote", "data", "id"]).copy()
            saldo_diario = registros["entrada_racao"] - registros["racao_consumida"]
            registros["estoque_racao_lote"] = saldo_diario.groupby(registros["lote"]).cumsum()
            exibicao = registros[["data", "lote", "racao_consumida", "entrada_racao", "estoque_racao_lote", "mortes", "responsavel"]].rename(columns={
                "data": "Data", "lote": "Lote", "racao_consumida": "Consumida (kg)",
                "entrada_racao": "Entrada (kg)", "estoque_racao_lote": "Saldo de racao (kg)",
                "mortes": "Mortes", "responsavel": "Responsavel",
            })
            st.dataframe(
                exibicao,
                width="stretch",
                hide_index=True,
                height=min(420, 74 + len(exibicao) * 35),
                column_config={
                    "Data": st.column_config.DateColumn(
                        "Data", format="DD/MM/YYYY"
                    ),
                },
            )

    with abas[3]:
        lotes = enriquecer_lotes(carregar_lotes())
        if lotes.empty:
            st.info("Cadastre um lote antes de registrar vacinacoes.")
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
                    responsavel = st.text_input("Responsavel")
                    observacoes = st.text_area("Observacoes")
                salvar_vacina = st.form_submit_button("Agendar vacina", type="primary", width="stretch")

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
                st.warning(f"Ha {len(atrasadas)} vacina(s) atrasada(s).")
            proximas = vacinas[(vacinas["status_exibicao"] == "prevista") & (pd.to_datetime(vacinas["data_prevista"]).dt.date <= hoje + timedelta(days=7))]
            if not proximas.empty:
                st.info(f"Ha {len(proximas)} vacina(s) prevista(s) para os proximos 7 dias.")

            exibicao = vacinas[["id", "lote", "vacina", "data_prevista", "data_aplicacao", "dose", "status_exibicao", "responsavel"]].rename(columns={
                "id": "ID", "lote": "Lote", "vacina": "Vacina", "data_prevista": "Prevista",
                "data_aplicacao": "Aplicacao", "dose": "Dose", "status_exibicao": "Status",
                "responsavel": "Responsavel",
            })
            st.dataframe(
                exibicao,
                width="stretch",
                hide_index=True,
                height=min(420, 74 + len(exibicao) * 35),
                column_config={
                    "Prevista": st.column_config.DateColumn(
                        "Prevista", format="DD/MM/YYYY"
                    ),
                    "Aplicacao": st.column_config.DateColumn(
                        "Aplicacao", format="DD/MM/YYYY"
                    ),
                },
            )

            pendentes = vacinas[vacinas["status"].isin(["prevista", "atrasada"])].copy()
            if not pendentes.empty:
                opcoes_vacinas = {int(linha.id): f"{linha.lote} - {linha.vacina} ({pd.to_datetime(linha.data_prevista).strftime('%d/%m/%Y')})" for linha in pendentes.itertuples()}
                with st.form("pinteiro_form_atualizar_vacina", clear_on_submit=True):
                    vacina_id = st.selectbox("Vacina para atualizar", options=list(opcoes_vacinas), format_func=lambda valor: opcoes_vacinas[valor])
                    data_aplicacao = st.date_input("Data da aplicacao", value=hoje, max_value=hoje, format="DD/MM/YYYY")
                    coluna_aplicar, coluna_cancelar = st.columns(2)
                    with coluna_aplicar:
                        aplicar = st.form_submit_button("Marcar como aplicada", type="primary", width="stretch")
                    with coluna_cancelar:
                        cancelar = st.form_submit_button("Cancelar vacina", width="stretch")

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
        st.markdown("#### Destino previsto: Galpao 4")
        disponivel = destino_disponivel()
        if disponivel:
            st.success("Galpao 4 esta marcado como disponivel para receber lotes do Pinteiro.")
        else:
            st.warning("Galpao 4 ainda nao esta disponivel. A transferencia definitiva permanece bloqueada.")

        with st.expander("Configurar disponibilidade do Galpao 4", expanded=False):
            with st.form("pinteiro_form_destino"):
                ativo = st.checkbox("Galpao 4 esta pronto para receber aves", value=disponivel)
                salvar_destino = st.form_submit_button("Salvar disponibilidade", width="stretch")
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
                    registrar_log("UPDATE", "pinteiro_destinos", detalhes=f"Disponibilidade do {DESTINO_PADRAO}: {'ativa' if ativo else 'em construcao'}.")
                    st.success("Disponibilidade atualizada.")
                except Exception as erro:
                    st.error(f"Erro ao configurar destino: {erro}")

        lotes = enriquecer_lotes(carregar_lotes())
        transferiveis = lotes[lotes["status"].isin(STATUS_ATIVOS)].copy() if not lotes.empty else lotes
        if transferiveis.empty:
            st.info("Nao ha lotes ativos ou prontos para transferencia.")
        else:
            opcoes_lotes = {int(linha.id): f"{linha.nome} - {int(linha.aves_vivas)} aves vivas - {linha.status}" for linha in transferiveis.itertuples()}
            with st.form("pinteiro_form_pronto_transferencia", clear_on_submit=True):
                lote_pronto_id = st.selectbox("Lote", options=list(opcoes_lotes), format_func=lambda valor: opcoes_lotes[valor], key="pinteiro_lote_pronto")
                marcar_pronto = st.form_submit_button("Marcar como pronto para transferencia", width="stretch")
            if marcar_pronto:
                try:
                    with engine.connect() as conn:
                        with conn.begin():
                            conn.execute(text("""
                                UPDATE pinteiro_lotes
                                SET status = 'pronto_transferencia'
                                WHERE id = :id AND username = :username AND status = 'ativo'
                            """), {"id": int(lote_pronto_id), "username": usuario})
                    registrar_log("UPDATE", "pinteiro_lotes", int(lote_pronto_id), "Lote marcado como pronto para transferencia.")
                    st.success("Lote marcado como pronto para transferencia.")
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
                    data_transferencia = st.date_input("Data da transferencia", value=hoje, max_value=hoje, format="DD/MM/YYYY")
                    st.number_input("Quantidade a transferir", min_value=int(lote["aves_vivas"]), max_value=int(lote["aves_vivas"]), value=int(lote["aves_vivas"]), disabled=True)
                    responsavel = st.text_input("Responsavel pela transferencia")
                    observacoes = st.text_area("Observacoes da transferencia")
                    confirmar = st.checkbox("Confirmo a transferencia integral deste lote para o Galpao 4")
                    transferir = st.form_submit_button("Confirmar transferencia", type="primary", width="stretch", disabled=not disponivel)

                if transferir:
                    if not confirmar:
                        st.error("Marque a confirmacao antes de transferir o lote.")
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
                                            FROM pinteiro_registros_diarios
                                            WHERE username = :username AND lote_id = :lote_id
                                        """), {"username": usuario, "lote_id": int(lote_id)}).scalar()

                                        if not lote_atual or lote_atual["status"] != "pronto_transferencia":
                                            raise ValueError("O lote nao esta pronto para transferencia.")
                                        if not destino_ativo:
                                            raise ValueError("O Galpao 4 nao esta disponivel para transferencia.")
                                        if transferencia_existente:
                                            raise ValueError("Este lote ja foi transferido.")
                                        quantidade = calcular_aves_vivas(
                                            lote_atual["quantidade_inicial"], mortes, lote_atual["quantidade_transferida"]
                                        )
                                        if quantidade <= 0:
                                            raise ValueError("O lote nao possui aves vivas para transferir.")

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
                                st.success(f"Transferencia concluida: {quantidade} aves registradas no {DESTINO_PADRAO}.")
                            except Exception as erro:
                                liberar_acao(chave)
                                st.error(f"Transferencia nao concluida: {erro}")

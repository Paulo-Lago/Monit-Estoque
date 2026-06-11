import base64
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from sqlalchemy import text


def render_modulo_producao(
    engine,
    base_dir,
    tipos_ovo,
    galpoes,
    cores,
    registrar_log,
    acao_repetida,
    liberar_acao,
):
    BASE_DIR = base_dir
    TIPOS_OVO = tipos_ovo
    GALPOES = galpoes
    CORES = cores

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
                    registrar_log(
                        "INSERT", "producao",
                        detalhes=(
                            f"Registrou {qtd_val} ovos ({tipo_ovo}, {cor}) "
                            f"no {galpao} em {data_reg.strftime('%d/%m/%Y')}"
                        )
                    )
                    st.balloons()
                    st.success(
                        f"✅ {qtd_val} ovos ({tipo_ovo}, {cor}) do {galpao} registrados com sucesso!")
                except Exception as e:
                    liberar_acao(chave_acao)
                    st.error(f"Erro ao salvar colheita: {e}")
            else:
                st.error("Quantidade deve ser maior que zero.")

        st.divider()
        st.markdown("### 🥚 Registro Geral de Ovos por Galpão")
        st.caption("Informe o total geral coletado em cada galpão na data selecionada.")

        with st.form("form_ovos_geral_galpao", clear_on_submit=True):
            data_ovos_geral = st.date_input(
                "📅 Data do registro",
                value=datetime.now().date(),
                format="DD/MM/YYYY",
                key="data_ovos_geral"
            )
            colunas_galpoes = st.columns(len(GALPOES))
            quantidades_gerais = {}
            for indice, nome_galpao in enumerate(GALPOES):
                with colunas_galpoes[indice]:
                    quantidades_gerais[nome_galpao] = st.number_input(
                        f"🥚 Total no {nome_galpao}",
                        min_value=0,
                        step=1,
                        value=0,
                        format="%d",
                        key=f"ovos_geral_qtd_{indice}"
                    )

            salvar_ovos_geral = st.form_submit_button(
                "✅ Salvar Totais por Galpão",
                type="primary",
                use_container_width=True
            )

        if salvar_ovos_geral:
            if not any(quantidade > 0 for quantidade in quantidades_gerais.values()):
                st.error("Informe uma quantidade maior que zero em pelo menos um galpão.")
            else:
                chave_acao = "salvar_ovos_geral_galpao"
                payload_acao = (
                    st.session_state.username,
                    data_ovos_geral,
                    tuple(quantidades_gerais.items())
                )
                if not acao_repetida(chave_acao, payload_acao):
                    try:
                        with engine.connect() as conn:
                            with conn.begin():
                                for nome_galpao, quantidade in quantidades_gerais.items():
                                    conn.execute(text("""
                                        INSERT INTO ovos_geral_galpao
                                            (username, data, galpao, quantidade)
                                        VALUES (:username, :data, :galpao, :quantidade)
                                        ON CONFLICT (username, data, galpao)
                                        DO UPDATE SET
                                            quantidade = EXCLUDED.quantidade,
                                            data_registro = CURRENT_TIMESTAMP
                                    """), {
                                        "username": st.session_state.username,
                                        "data": data_ovos_geral,
                                        "galpao": nome_galpao,
                                        "quantidade": int(quantidade)
                                    })
                        registrar_log(
                            "UPDATE",
                            "ovos_geral_galpao",
                            detalhes=f"Totais gerais por galpão em {data_ovos_geral.strftime('%d/%m/%Y')}: {quantidades_gerais}"
                        )
                        st.success("✅ Totais gerais por galpão salvos com sucesso!")
                    except Exception as e:
                        liberar_acao(chave_acao)
                        st.error(f"Erro ao salvar os totais por galpão: {e}")

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

                df_ovos_geral = pd.read_sql(text("""
                    SELECT data, galpao, quantidade
                    FROM ovos_geral_galpao
                    WHERE username = :username
                    ORDER BY data DESC, galpao
                """), engine, params={"username": st.session_state.username})

                if df_producao.empty and df_ovos_geral.empty:
                    st.info("📭 Nenhum registro de produção encontrado.")
                else:
                    df_producao['data'] = pd.to_datetime(
                        df_producao['data'])
                    df_ovos_geral['data'] = pd.to_datetime(
                        df_ovos_geral['data'])

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
                    df_ovos_geral_filtrado = df_ovos_geral[
                        (df_ovos_geral['data'].dt.date >= data_inicio) &
                        (df_ovos_geral['data'].dt.date <= data_fim)
                    ].copy()

                    titulo_periodo = f"Período: {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}"
                    st.markdown(f"**{titulo_periodo}**")
                    st.divider()

                    if df_filtrado.empty and df_ovos_geral_filtrado.empty:
                        st.warning(
                            "Nenhum registro encontrado para o período selecionado.")
                    else:
                        sub_tabs = st.tabs(
                            ["📋 Detalhes por Galpão e Tipo", "📦 Caixas de Ovos"])

                        with sub_tabs[0]:
                            st.markdown(
                                "#### 📋 Detalhes por Galpão e Tipo")

                            st.markdown("##### 🥚 Resumo Geral Informado por Galpão")
                            if df_ovos_geral_filtrado.empty:
                                st.info("Nenhum total geral por galpão informado neste período.")
                            else:
                                resumo_geral = df_ovos_geral_filtrado.groupby(
                                    'galpao', as_index=False)['quantidade'].sum()
                                total_geral_periodo = int(resumo_geral['quantidade'].sum())
                                colunas_resumo = st.columns(len(GALPOES) + 1)
                                for indice, nome_galpao in enumerate(GALPOES):
                                    total_galpao_geral = resumo_geral.loc[
                                        resumo_geral['galpao'] == nome_galpao,
                                        'quantidade'
                                    ].sum()
                                    with colunas_resumo[indice]:
                                        st.metric(nome_galpao, f"{int(total_galpao_geral):,} ovos")
                                with colunas_resumo[-1]:
                                    st.metric("Total Geral", f"{total_geral_periodo:,} ovos")

                                detalhes_gerais = df_ovos_geral_filtrado.copy()
                                detalhes_gerais['data'] = detalhes_gerais['data'].dt.strftime('%d/%m/%Y')
                                st.dataframe(
                                    detalhes_gerais.rename(columns={
                                        'data': 'Data',
                                        'galpao': 'Galpão',
                                        'quantidade': 'Total Geral de Ovos'
                                    }),
                                    use_container_width=True,
                                    hide_index=True
                                )

                            st.divider()
                            st.markdown("##### Produção Classificada por Tipo e Cor")
                            if df_filtrado.empty:
                                st.info("Nenhuma produção classificada por tipo e cor neste período.")
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
                                registrar_log(
                                    "UPDATE", "producao", selected_id,
                                    detalhes=(
                                        f"Atualizou colheita para {novo_val} ovos "
                                        f"({novo_tipo}, {nova_cor}) no {novo_galpao} "
                                        f"em {nova_data.strftime('%d/%m/%Y')}"
                                    )
                                )
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
                                "Excluir agora", type="primary", disabled=selected_id_excluir is None)

                            if excluir_colheita and selected_id_excluir is not None:
                                if not confirmar:
                                    st.error("Marque a confirmação antes de excluir.")
                                else:
                                    try:
                                        with engine.connect() as conn:
                                            conn.execute(
                                                text("DELETE FROM producao WHERE id = :id AND username = :username"),
                                                {"id": selected_id_excluir, "username": st.session_state.username}
                                            )
                                            conn.commit()
                                        registrar_log(
                                            "DELETE", "producao", selected_id_excluir,
                                            f"Excluiu colheita de {registro_excluir['quantidade']} ovos"
                                        )
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
                        registrar_log(
                            "INSERT", "aves",
                            detalhes=(
                                f"Registrou {qtd_aves} aves no {galpao_aves} "
                                f"em {data_aves.strftime('%d/%m/%Y')}"
                            )
                        )
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
                    registrar_log(
                        "INSERT", "aves_mortas",
                        detalhes=(
                            f"Registrou {qtd_morta} aves mortas no {galpao_morta} "
                            f"em {data_morta.strftime('%d/%m/%Y')}"
                        )
                    )
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
                                    registrar_log(
                                        "UPDATE", "aves", selected_id,
                                        detalhes=(
                                            f"Atualizou registro para {nova_qtd} aves no {novo_galpao} "
                                            f"em {nova_data.strftime('%d/%m/%Y')}"
                                        )
                                    )
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
                                    "Sim, excluir permanentemente", type="primary", disabled=selected_id_excluir is None)

                                if excluir_ave and selected_id_excluir is not None:
                                    if not confirmar_ave:
                                        st.error("Marque a confirmação antes de excluir.")
                                    else:
                                        try:
                                            with engine.connect() as conn:
                                                conn.execute(text("""
                                                    DELETE FROM aves
                                                    WHERE id = :id AND username = :username
                                                """), {"id": selected_id_excluir, "username": st.session_state.username})
                                                conn.commit()
                                            registrar_log(
                                                "DELETE", "aves", selected_id_excluir,
                                                f"Excluiu registro de aves: {opcoes[selected_id_excluir]}"
                                            )
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
                                "Excluir agora", type="primary", disabled=selected_id_morta is None)

                            if excluir_ave_morta and selected_id_morta is not None:
                                if not confirmar_morta:
                                    st.error("Marque a confirmação antes de excluir.")
                                else:
                                    try:
                                        quantidade_morta_excluida = df_mortas[
                                            df_mortas['id'] == selected_id_morta
                                        ].iloc[0]['Quantidade']
                                        with engine.connect() as conn:
                                            conn.execute(text("""
                                                DELETE FROM aves_mortas
                                                WHERE id = :id AND username = :username
                                            """), {"id": selected_id_morta, "username": st.session_state.username})
                                            conn.commit()
                                        registrar_log(
                                            "DELETE", "aves_mortas", selected_id_morta,
                                            f"Excluiu registro de morte de {quantidade_morta_excluida} aves"
                                        )
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

            df_aves_registradas = pd.read_sql(text("""
                SELECT data_registro AS data, quantidade_total AS quantidade, galpao
                FROM aves
                WHERE username = :username
                ORDER BY data_registro
            """), engine, params={"username": st.session_state.username})

            if not df_producao.empty:
                df_producao['data'] = pd.to_datetime(df_producao['data'])
            if not df_quebrados.empty:
                df_quebrados['data'] = pd.to_datetime(df_quebrados['data'])
            if not df_mortas.empty:
                df_mortas['data'] = pd.to_datetime(df_mortas['data'])
            if not df_aves_registradas.empty:
                df_aves_registradas['data'] = pd.to_datetime(
                    df_aves_registradas['data'])

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

                        st.markdown("#### Total Diário e Percentual de Postura por Galpão")
                        st.caption(
                            "O percentual considera uma capacidade de 1 ovo por ave viva ao dia.")

                        for galpao in GALPOES:
                            df_total_galpao = df_filtrado[
                                df_filtrado['galpao'] == galpao
                            ].groupby('data', as_index=False)['quantidade'].sum()

                            if df_total_galpao.empty:
                                st.info(
                                    f"Nenhum registro de produção para {galpao} no período selecionado.")
                                continue

                            registros_galpao = df_aves_registradas[
                                df_aves_registradas['galpao'] == galpao
                            ] if not df_aves_registradas.empty else df_aves_registradas
                            mortes_galpao = df_mortas[
                                df_mortas['galpao'] == galpao
                            ] if not df_mortas.empty else df_mortas

                            aves_vivas_por_dia = []
                            percentuais_postura = []
                            for _, registro_dia in df_total_galpao.iterrows():
                                data_producao = registro_dia['data']
                                total_registradas = registros_galpao.loc[
                                    registros_galpao['data'] <= data_producao,
                                    'quantidade'
                                ].sum() if not registros_galpao.empty else 0
                                total_mortes = mortes_galpao.loc[
                                    mortes_galpao['data'] <= data_producao,
                                    'quantidade'
                                ].sum() if not mortes_galpao.empty else 0
                                aves_vivas = max(
                                    0, int(total_registradas) - int(total_mortes))
                                percentual = (
                                    float(registro_dia['quantidade']) / aves_vivas * 100
                                    if aves_vivas > 0 else None
                                )
                                aves_vivas_por_dia.append(aves_vivas)
                                percentuais_postura.append(percentual)

                            df_total_galpao['aves_vivas'] = aves_vivas_por_dia
                            df_total_galpao['percentual_postura'] = percentuais_postura

                            fig_desempenho = make_subplots(
                                specs=[[{"secondary_y": True}]])
                            fig_desempenho.add_trace(
                                go.Bar(
                                    x=df_total_galpao['data'],
                                    y=df_total_galpao['quantidade'],
                                    name='Total de ovos',
                                    marker_color='#2F80ED',
                                    text=df_total_galpao['quantidade'].astype(int),
                                    textposition='auto',
                                    customdata=df_total_galpao[['aves_vivas']],
                                    hovertemplate=(
                                        '<b>%{x|%d/%m/%Y}</b><br>'
                                        'Total de ovos: %{y:,.0f}<br>'
                                        'Aves vivas: %{customdata[0]:,.0f}'
                                        '<extra></extra>'
                                    ),
                                ),
                                secondary_y=False,
                            )
                            fig_desempenho.add_trace(
                                go.Scatter(
                                    x=df_total_galpao['data'],
                                    y=df_total_galpao['percentual_postura'],
                                    name='Percentual de postura',
                                    mode='lines+markers+text',
                                    line=dict(color='#E05A33', width=3),
                                    marker=dict(size=8),
                                    text=[
                                        f'{valor:.1f}%' if pd.notna(valor) else 'Sem aves'
                                        for valor in df_total_galpao['percentual_postura']
                                    ],
                                    textposition='top center',
                                    hovertemplate=(
                                        '<b>%{x|%d/%m/%Y}</b><br>'
                                        'Postura: %{y:.1f}%'
                                        '<extra></extra>'
                                    ),
                                ),
                                secondary_y=True,
                            )
                            fig_desempenho.update_layout(
                                title=f'Total de Ovos e Percentual de Postura - {galpao}',
                                plot_bgcolor='#ffffff',
                                paper_bgcolor='#ffffff',
                                font=dict(color='#000000', size=12),
                                legend=dict(
                                    orientation='h',
                                    yanchor='bottom',
                                    y=1.02,
                                    xanchor='left',
                                    x=0,
                                ),
                                hovermode='x unified',
                                margin=dict(t=90),
                            )
                            fig_desempenho.update_xaxes(
                                title_text='Data', tickformat='%d/%m', color='#000000')
                            fig_desempenho.update_yaxes(
                                title_text='Total de ovos',
                                rangemode='tozero',
                                color='#2F80ED',
                                secondary_y=False,
                            )
                            fig_desempenho.update_yaxes(
                                title_text='Percentual de postura',
                                ticksuffix='%',
                                rangemode='tozero',
                                color='#E05A33',
                                secondary_y=True,
                            )
                            st.plotly_chart(
                                fig_desempenho, use_container_width=True)
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
                        registrar_log(
                            "INSERT", "ovos_quebrados",
                            detalhes=(
                                f"Registrou {qtd_quebrados} ovos quebrados no {galpao_quebrados} "
                                f"em {data_quebrados.strftime('%d/%m/%Y')}"
                            )
                        )
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
                                registrar_log(
                                    "UPDATE", "usuarios",
                                    detalhes="Alterou a senha da conta"
                                )
                                st.success("✅ Senha alterada com sucesso!")
                            else:
                                st.error("Senha atual incorreta.")
                    except Exception as e:
                        st.error(f"Erro ao alterar senha: {e}")

# ============================================================

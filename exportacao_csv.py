import inspect
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st


def _csv_compativel_excel(dados):
    tabela = dados.copy()
    for coluna in tabela.columns:
        serie = tabela[coluna]
        if pd.api.types.is_datetime64_any_dtype(serie):
            tabela[coluna] = serie.dt.strftime('%d/%m/%Y')
        elif serie.map(lambda valor: isinstance(valor, (date, datetime))).any():
            tabela[coluna] = serie.map(
                lambda valor: valor.strftime('%d/%m/%Y')
                if isinstance(valor, (date, datetime)) else valor
            )
    return tabela.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')


def instalar_exportacao_csv_excel():
    """Acrescenta um download CSV compatível com Excel a cada tabela do app."""
    if getattr(st, '_monit_exportacao_csv_instalada', False):
        return

    dataframe_original = st.dataframe
    contador_exportacoes = 0

    def dataframe_com_exportacao(dados, *args, **kwargs):
        nonlocal contador_exportacoes
        resultado = dataframe_original(dados, *args, **kwargs)
        if isinstance(dados, pd.DataFrame):
            contador_exportacoes += 1
            chamada = inspect.currentframe().f_back
            chamada_pai = chamada.f_back
            arquivo_origem = Path(chamada.f_code.co_filename).stem
            identificador = (
                f'{arquivo_origem}_{chamada.f_lineno}_'
                f'{chamada_pai.f_lineno if chamada_pai else 0}_'
                f'{contador_exportacoes}'
            )
            st.download_button(
                'Baixar CSV para Excel',
                data=_csv_compativel_excel(dados),
                file_name=f'{identificador}.csv',
                mime='text/csv;charset=utf-8',
                key=f'csv_excel_{identificador}',
            )
        return resultado

    st.dataframe = dataframe_com_exportacao
    st._monit_exportacao_csv_instalada = True

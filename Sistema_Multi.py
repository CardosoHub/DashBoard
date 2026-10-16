import streamlit as st
import pandas as pd
import plotly.express as px
import os

# EXIBIR SITE : py -m streamlit run codigo.py

st.write("# Cadastro Mensal Multi")

NOME_ARQUIVO = "dadosmulti.csv"

# Ordem padrão para os meses no eixo X
ORDEM_MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

# 1. Função para carregar os dados
def carregar_dados():
    if os.path.exists(NOME_ARQUIVO):
        try:
            return pd.read_csv(NOME_ARQUIVO)
        except Exception:
            return pd.DataFrame(columns=["Ano", "Mês", "Consultor", "Percentual"])
    else:
        return pd.DataFrame(columns=["Ano", "Mês", "Consultor", "Percentual"])

# 2. Inicializa a sessão
if "dados" not in st.session_state:
    st.session_state.dados = carregar_dados()

# --- FORMULÁRIO DE CADASTRO ---
st.sidebar.write("### Novo Cadastro")

Ano = st.sidebar.number_input("Digite o ano", min_value=2000, max_value=2100, step=1, value=2026)
Mes = st.sidebar.selectbox("Selecione o mês", ORDEM_MESES)
Consultor = st.sidebar.selectbox("Selecione o consultor", ["Loja", "Angela", "Camila", "Juliana"])
Percentual = st.sidebar.number_input("Digite o percentual", min_value=0.0, max_value=400.0, value=0.0, step=0.01, format="%.2f")

botao_cadastra = st.sidebar.button("Cadastrar Multi")

# Ação do Botão: Salvar registro no CSV
if botao_cadastra:
    novo_registro = pd.DataFrame({
        "Ano": [int(Ano)],
        "Mês": [Mes],
        "Consultor": [Consultor],
        "Percentual": [float(Percentual)]
    })
    
    st.session_state.dados = pd.concat([st.session_state.dados, novo_registro], ignore_index=True)
    st.session_state.dados.to_csv(NOME_ARQUIVO, index=False)
    st.success("Cadastro realizado com sucesso!")
    st.rerun()

# --- DASHBOARD & TABELA ---
st.write("---")
st.write("### Dashboard Geral")

if not st.session_state.dados.empty:
    df_temp = st.session_state.dados.copy()
    
    # Tratamento dos tipos de dados
    df_temp["Ano"] = pd.to_numeric(df_temp["Ano"], errors="coerce").fillna(0).astype(int)
    df_temp["Percentual"] = pd.to_numeric(df_temp["Percentual"], errors="coerce").fillna(0)

    # =========================================================================
    # RANKING VISUAL: MEDALHAS DE OURO, PRATA E BRONZE
    # =========================================================================
    st.write("---")
    st.write("### 🏆 Ranking de Consultores")
    st.caption("O ranking considera a média do percentual de cada consultor no período selecionado. A Loja não participa da classificação.")

    col_rank_ano, col_rank_mes = st.columns(2)
    with col_rank_ano:
        anos_ranking = sorted(df_temp["Ano"].dropna().unique().tolist(), reverse=True)
        ano_ranking = st.selectbox("Ano do ranking", anos_ranking, key="ano_ranking")
    with col_rank_mes:
        meses_do_ano = [m for m in ORDEM_MESES if m in df_temp.loc[df_temp["Ano"] == ano_ranking, "Mês"].astype(str).str.strip().unique()]
        mes_ranking = st.selectbox("Mês do ranking", meses_do_ano or ORDEM_MESES, key="mes_ranking")

    df_ranking = df_temp[
        (df_temp["Ano"] == int(ano_ranking))
        & (df_temp["Mês"].astype(str).str.strip() == mes_ranking)
        & (df_temp["Consultor"].astype(str).str.strip().str.casefold() != "loja")
    ].copy()

    if not df_ranking.empty:
        ranking = (
            df_ranking.groupby("Consultor", as_index=False)["Percentual"]
            .mean()
            .sort_values("Percentual", ascending=False)
            .reset_index(drop=True)
        )
        ranking["Posição"] = ranking.index + 1
        medalhas = {1: ("🥇", "Ouro"), 2: ("🥈", "Prata"), 3: ("🥉", "Bronze")}
        # Coloque as fotos reais em fotos/Angela.jpg, fotos/Camila.jpg e fotos/Juliana.jpg.
        # Enquanto a foto não existir, é exibido um avatar com o nome do consultor.
        fotos_consultores = {
            "Angela": "fotos/Angela.jpg",
            "Camila": "fotos/Camila.jpg",
            "Juliana": "fotos/Juliana.jpg",
        }

        primeiros = ranking.head(3)
        colunas_ranking = st.columns(len(primeiros))
        for coluna, (_, consultor) in zip(colunas_ranking, primeiros.iterrows()):
            posicao = int(consultor["Posição"])
            medalha, nome_medalha = medalhas[posicao]
            nome = str(consultor["Consultor"])
            caminho_foto = fotos_consultores.get(nome)
            with coluna:
                st.markdown(f"### {medalha} {nome_medalha} lugar")
                if caminho_foto and os.path.exists(caminho_foto):
                    st.image(caminho_foto, width=150)
                else:
                    nome_avatar = nome.replace(" ", "+")
                    st.image(
                        f"https://ui-avatars.com/api/?name={nome_avatar}&size=256&background=E8EDF3&color=243447&bold=true",
                        width=150,
                    )
                st.markdown(f"**{nome}**")
                st.metric("Percentual alcançado", f"{float(consultor['Percentual']):.2f}%")
                st.caption(f"Posição no ranking: {posicao}º")
    else:
        st.info(f"Não há dados de consultores para {mes_ranking} de {ano_ranking}.")


    # =========================================================================
    # ACOMPANHAMENTO EXCLUSIVO DA LOJA
    # =========================================================================
    st.write("---")
    st.write("## 🏬 Acompanhamento da Loja")
    st.caption("Cadastre o percentual da Loja no formulário lateral e acompanhe o resultado por mês e por ano.")

    df_loja_acomp = df_temp[
        df_temp["Consultor"].astype(str).str.strip().str.casefold() == "loja"
    ].copy()
    df_loja_acomp["Mês"] = df_loja_acomp["Mês"].astype(str).str.strip()

    if not df_loja_acomp.empty:
        anos_loja = sorted(df_loja_acomp["Ano"].dropna().unique().tolist(), reverse=True)
        ano_loja = st.selectbox("Ano para acompanhar a Loja", anos_loja, key="ano_acomp_loja")
        df_loja_ano = df_loja_acomp[df_loja_acomp["Ano"] == int(ano_loja)].copy()
        meses_loja = [m for m in ORDEM_MESES if m in df_loja_ano["Mês"].unique()]

        if meses_loja:
            mes_loja = st.selectbox("Mês para acompanhar a Loja", meses_loja, key="mes_acomp_loja")
            df_loja_mes = df_loja_ano[df_loja_ano["Mês"] == mes_loja]
            percentual_mes_loja = float(df_loja_mes["Percentual"].mean())
            media_ano_loja = float(df_loja_ano["Percentual"].mean())
            variacao = percentual_mes_loja - media_ano_loja

            if percentual_mes_loja < 70:
                status_loja = "🔴 Abaixo de 70%"
            elif percentual_mes_loja < 100:
                status_loja = "🟡 Entre 70% e 99,99%"
            else:
                status_loja = "🟢 Meta atingida (100% ou mais)"

            col_loja_1, col_loja_2, col_loja_3 = st.columns(3)
            col_loja_1.metric(f"Loja — {mes_loja}/{ano_loja}", f"{percentual_mes_loja:.2f}%", delta=f"{variacao:+.2f} p.p. vs. média anual")
            col_loja_2.metric(f"Média anual — {ano_loja}", f"{media_ano_loja:.2f}%")
            col_loja_3.metric("Status do período", status_loja)

            # Consolida possíveis cadastros duplicados em uma média por mês.
            evolucao_loja = (
                df_loja_ano.groupby("Mês", as_index=False)["Percentual"]
                .mean()
            )
            evolucao_loja["Mês"] = pd.Categorical(
                evolucao_loja["Mês"], categories=ORDEM_MESES, ordered=True
            )
            evolucao_loja = evolucao_loja.sort_values("Mês")
            evolucao_loja["Status"] = evolucao_loja["Percentual"].apply(
                lambda valor: "Abaixo de 70%" if valor < 70
                else ("70% a 99,99%" if valor < 100 else "100% ou mais")
            )

            grafico_loja = px.bar(
                evolucao_loja,
                x="Mês",
                y="Percentual",
                color="Status",
                text=evolucao_loja["Percentual"].map(lambda valor: f"{valor:.2f}%"),
                category_orders={"Mês": ORDEM_MESES},
                color_discrete_map={
                    "Abaixo de 70%": "red",
                    "70% a 99,99%": "yellow",
                    "100% ou mais": "green",
                },
                labels={"Mês": "Mês", "Percentual": "Percentual alcançado (%)", "Status": "Resultado"},
                title=f"Evolução mensal do percentual da Loja — {ano_loja}",
            )
            grafico_loja.update_traces(textposition="outside")
            grafico_loja.update_layout(yaxis_title="Percentual (%)", xaxis_title="Mês")
            st.plotly_chart(grafico_loja, use_container_width=True)
        else:
            st.info(f"Não há percentuais cadastrados para a Loja em {ano_loja}.")
    else:
        st.info("Ainda não há percentuais cadastrados para a Loja. Use o formulário lateral, selecione 'Loja' e informe o percentual atingido.")

    # 1. Cards Média Anual - EXCLUSIVO LOJA
    st.write("#### Média Anual (Loja)")
    
    df_loja = df_temp[df_temp["Consultor"] == "Loja"]

    if not df_loja.empty:
        media_anual_loja = (
            df_loja.groupby("Ano")["Percentual"]
            .mean()
            .reset_index()
            .sort_values("Ano")
        )

        cols = st.columns(len(media_anual_loja))
        for i, row in enumerate(media_anual_loja.itertuples()):
            cols[i].metric(label=f"Ano {row.Ano}", value=f"{row.Percentual:.2f}%")
    else:
        st.info("Nenhum cadastro encontrado para a Loja.")

    st.write("---")

    # 2. Tabela de Dados Cadastrados
    st.write("### Dados Cadastrados")
    st.info("💡 Selecione a linha na caixa à esquerda e pressione **Delete** no teclado para apagar.")

    dados_editados = st.data_editor(
        st.session_state.dados,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_tabela"
    )

    if not dados_editados.equals(st.session_state.dados):
        st.session_state.dados = dados_editados
        st.session_state.dados.to_csv(NOME_ARQUIVO, index=False)
        st.success("Linha excluída com sucesso!")
        st.rerun()

    st.write("---")

    # =========================================================================
    # GRÁFICO 1: EVOLUÇÃO MENSAL POR CONSULTOR (COM REGRA DE CORES)
    # =========================================================================
    st.write("### 1. Evolução Mensal por Consultor")

    col_filtro1, col_filtro2 = st.columns(2)

    with col_filtro1:
        lista_consultores = ["Todos"] + sorted(df_temp["Consultor"].unique().tolist())
        consultor_selecionado = st.selectbox("Selecione o Consultor:", lista_consultores, key="filtro_consultor_g1")

    with col_filtro2:
        lista_anos = ["Todos"] + sorted(df_temp["Ano"].unique().tolist())
        ano_selecionado = st.selectbox("Selecione o Ano:", lista_anos, key="filtro_ano_g1")

    df_filtrado = df_temp.copy()

    if consultor_selecionado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Consultor"] == consultor_selecionado]

    if ano_selecionado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Consultor"] == int(ano_selecionado)] if "Ano" in df_filtrado and False else df_filtrado[df_filtrado["Ano"] == int(ano_selecionado)]

    if not df_filtrado.empty:
        st.write(f"#### Média Anual - Consultor: **{consultor_selecionado}** | Ano: **{ano_selecionado}**")
        
        media_consultor_por_ano = (
            df_filtrado.groupby("Ano")["Percentual"]
            .mean()
            .reset_index()
            .sort_values("Ano")
        )

        cols_consultor = st.columns(len(media_consultor_por_ano) + 1)
        media_geral_filtrada = df_filtrado["Percentual"].mean()
        cols_consultor[0].metric(label="Média do Filtro", value=f"{media_geral_filtrada:.2f}%")

        for i, row in enumerate(media_consultor_por_ano.itertuples()):
            cols_consultor[i + 1].metric(label=f"Média Ano {row.Ano}", value=f"{row.Percentual:.2f}%")

        # 1. Aplicação da regra das cores por percentual
        def definir_cor(valor):
            if valor < 70:
                return "Abaixo de 70%"
            elif 70 <= valor <= 99:
                return "70% a 99%"
            else:
                return "100% ou mais"

        df_filtrado["Status"] = df_filtrado["Percentual"].apply(definir_cor)

        # Garante a ordem correta dos meses no eixo X
        df_filtrado["Mês"] = pd.Categorical(df_filtrado["Mês"], categories=ORDEM_MESES, ordered=True)
        df_filtrado = df_filtrado.sort_values("Mês")

        # 2. Gráfico 1 com regra de cores + barras lado a lado por consultor
        Grafico_Mensal = px.bar(
            df_filtrado,
            x="Mês",
            y="Percentual",
            color="Status",
            barmode="group",  # Mantém as barras lado a lado
            text="Consultor",  # Exibe o nome do consultor no topo das barras
            hover_data=["Consultor", "Ano", "Percentual"],
            color_discrete_map={
                "Abaixo de 70%": "red",
                "70% a 99%": "yellow",
                "100% ou mais": "green"
            },
            labels={'Mês': 'Mês', 'Percentual': 'Percentual (%)', 'Status': 'Atingimento'},
            title=f"Evolução Mensal - Consultor: {consultor_selecionado} | Ano: {ano_selecionado}"
        )
        
        Grafico_Mensal.update_traces(textposition="outside")

        st.plotly_chart(Grafico_Mensal, use_container_width=True)
    else:
        st.info("Nenhum dado encontrado para os filtros selecionados no Gráfico 1.")

    # =========================================================================
    # GRÁFICO 2: SEGUNDO GRÁFICO COMPARATIVO DIRETO DE CONSULTORES POR ANO E MÊS
    # =========================================================================
    st.write("### 2. Comparativo de Consultores por Período (Ano e Mês)")

    col_g2_1, col_g2_2 = st.columns(2)

    with col_g2_1:
        anos_disponiveis_g2 = sorted(df_temp["Ano"].unique().tolist())
        ano_g2 = st.selectbox("Selecione o Ano para Comparar:", anos_disponiveis_g2, key="ano_g2")

    with col_g2_2:
        df_ano_g2 = df_temp[df_temp["Ano"] == ano_g2]
        meses_disponiveis_g2 = [m for m in ORDEM_MESES if m in df_ano_g2["Mês"].unique()]
        opcao_meses_g2 = meses_disponiveis_g2 if meses_disponiveis_g2 else ORDEM_MESES
        mes_g2 = st.selectbox("Selecione o Mês para Comparar:", opcao_meses_g2, key="mes_g2")

    # Filtra exclusivamente para o Mês e Ano escolhidos
    df_comparativo_g2 = df_temp[(df_temp["Ano"] == ano_g2) & (df_temp["Mês"] == mes_g2)].copy()

    if not df_comparativo_g2.empty:
        # Função para determinar a cor por status no gráfico 2
        def definir_cor(valor):
            if valor < 70:
                return "Abaixo de 70%"
            elif 70 <= valor <= 99:
                return "70% a 99%"
            else:
                return "100% ou mais"

        df_comparativo_g2["Status"] = df_comparativo_g2["Percentual"].apply(definir_cor)
        df_comparativo_g2 = df_comparativo_g2.sort_values("Consultor")

        # GRÁFICO 2: Compara diretamente os consultores no mês e ano selecionados
        Grafico_Comparativo_Direto = px.bar(
            df_comparativo_g2,
            x="Consultor",
            y="Percentual",
            color="Status",
            text_auto=".2f",
            color_discrete_map={
                "Abaixo de 70%": "red",
                "70% a 99%": "yellow",
                "100% ou mais": "green"
            },
            labels={'Consultor': 'Consultor', 'Percentual': 'Percentual (%)', 'Status': 'Atingimento'},
            title=f"Atingimento dos Consultores em {mes_g2} / {ano_g2}"
        )
        Grafico_Comparativo_Direto.update_traces(textposition="outside")

        st.plotly_chart(Grafico_Comparativo_Direto, use_container_width=True)
    else:
        st.info(f"Nenhum dado cadastrado para {mes_g2} de {ano_g2}.")

else:
    st.warning("Nenhum dado cadastrado ainda.")

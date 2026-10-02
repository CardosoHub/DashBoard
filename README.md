# 📊 Cadastro Mensal Multi - Dashboard Streamlit

Este é um sistema interativo desenvolvido com **Streamlit**, **Pandas** e **Plotly** para acompanhamento, cadastro e análise de metas e percentuais de atingimento mensal por consultor.

---

## 🚀 Funcionalidades

- **📝 Cadastro Interativo**:
  - Formulário para inserção de ano, mês, consultor e percentual.
  - Salvamento automático e persistência de dados em arquivo `.csv` 

- **📊 Dashboard Geral & Métricas**:
  - Card exclusivo com a **Média Anual do cadastro da Loja**.
  - Tabela dinâmica (`st.data_editor`) para visualização e exclusão simples de registros diretamente na interface.

- **📈 Análise Visual (Gráficos Plotly)**:
  - **1. Evolução Mensal por Consultor**:
    - Agrupamento das barras lado a lado (`barmode="group"`).
    - Identificação visual por cores conforme o status de atingimento:
      - 🔴 **Abaixo de 70%** (Vermelho)
      - 🟡 **70% a 99%** (Amarelo)
      - 🟢 **100% ou mais** (Verde)
    - Filtros por Consultor e Ano.
  - **2. Comparativo por Período**:
    - Comparação direta do desempenho de todos os consultores em um **Ano** e **Mês** selecionados.

---

## 🛠️ Tecnologias Utilizadas

- **[Python](https://www.python.org/)** (v3.9+)
- **[Streamlit](https://streamlit.io/)** — Interface web interativa
- **[Pandas](https://pandas.pydata.org/)** — Manipulação e análise de dados
- **[Plotly Express](https://plotly.com/python/plotly-express/)** — Visualização de gráficos interativos

---

## 📂 Estrutura do Projeto

import os
import sqlite3
import hashlib
import hmac
import secrets
from contextlib import contextmanager
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Multi Analytics | Performance",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = os.environ.get("MULTI_ANALYTICS_DB", "multi_analytics.db")
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
MES_NUMERO = {mes: indice for indice, mes in enumerate(MESES, start=1)}
FAIXAS = ["Abaixo de 70%", "70% a 99,99%", "100% ou mais"]
CORES_FAIXAS = {
    "Abaixo de 70%": "#F87171",
    "70% a 99,99%": "#FBBF24",
    "100% ou mais": "#34D399",
}
CORES_CONSULTORES = ["#60A5FA", "#A78BFA", "#2DD4BF", "#FB7185", "#FBBF24", "#38BDF8"]




@contextmanager
def conectar_banco():
    conexao = sqlite3.connect(DB_PATH, timeout=30)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    try:
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def inicializar_banco():
    with conectar_banco() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS consultants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL COLLATE NOCASE,
                photo TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name),
                UNIQUE(user_id, id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                consultant_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                month TEXT NOT NULL,
                percentage REAL NOT NULL CHECK(percentage >= 0 AND percentage <= 400),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id, consultant_id)
                    REFERENCES consultants(user_id, id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_results_user_period
                ON results(user_id, year, month);
            CREATE INDEX IF NOT EXISTS idx_results_user_consultant
                ON results(user_id, consultant_id);
        """)


def criar_hash_senha(senha, salt=None):
    salt = salt or secrets.token_hex(16)
    derivada = hashlib.pbkdf2_hmac(
        "sha256", senha.encode("utf-8"), bytes.fromhex(salt), 310_000
    ).hex()
    return salt + "$" + derivada


def verificar_senha(senha, hash_salvo):
    try:
        salt, esperado = hash_salvo.split("$", 1)
        calculado = criar_hash_senha(senha, salt).split("$", 1)[1]
        return hmac.compare_digest(calculado, esperado)
    except (ValueError, TypeError):
        return False


def criar_usuario(email, senha):
    email = email.strip().lower()
    if not email or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return False, "Informe um e-mail válido."
    if len(senha) < 10:
        return False, "A senha deve ter pelo menos 10 caracteres."
    try:
        with conectar_banco() as con:
            cursor = con.execute(
                "INSERT INTO users(email, password_hash) VALUES (?, ?)",
                (email, criar_hash_senha(senha)),
            )
            user_id = cursor.lastrowid
            for nome in ("Loja", "Angela", "Camila", "Juliana"):
                con.execute(
                    "INSERT INTO consultants(user_id, name) VALUES (?, ?)",
                    (user_id, nome),
                )
        return True, "Conta criada com sucesso."
    except sqlite3.IntegrityError:
        return False, "Já existe uma conta com esse e-mail."


def autenticar_usuario(email, senha):
    with conectar_banco() as con:
        usuario = con.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ? COLLATE NOCASE",
            (email.strip().lower(),),
        ).fetchone()
    if usuario and verificar_senha(senha, usuario["password_hash"]):
        return {"id": int(usuario["id"]), "email": usuario["email"]}
    return None


def listar_consultores(user_id):
    with conectar_banco() as con:
        linhas = con.execute(
            "SELECT id, name, photo FROM consultants WHERE user_id = ? ORDER BY name",
            (int(user_id),),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def adicionar_consultor(user_id, nome, foto=None):
    nome = nome.strip()
    if not nome:
        return False, "Informe o nome do consultor."
    try:
        with conectar_banco() as con:
            con.execute(
                "INSERT INTO consultants(user_id, name, photo) VALUES (?, ?, ?)",
                (int(user_id), nome, foto),
            )
        return True, "Consultor " + nome + " cadastrado."
    except sqlite3.IntegrityError:
        return False, "Já existe um consultor com esse nome na sua conta."


def excluir_consultor(user_id, consultant_id):
    with conectar_banco() as con:
        cursor = con.execute(
            "DELETE FROM consultants WHERE id = ? AND user_id = ?",
            (int(consultant_id), int(user_id)),
        )
        return cursor.rowcount == 1


def salvar_resultado(user_id, consultant_id, ano, mes, percentual):
    with conectar_banco() as con:
        con.execute(
            """INSERT INTO results(user_id, consultant_id, year, month, percentage)
               SELECT ?, id, ?, ?, ? FROM consultants
               WHERE id = ? AND user_id = ?""",
            (int(user_id), int(ano), mes, float(percentual), int(consultant_id), int(user_id)),
        )
        if con.execute("SELECT changes()").fetchone()[0] != 1:
            raise PermissionError("Consultor não pertence à conta autenticada.")


def carregar_dados(user_id):
    with conectar_banco() as con:
        linhas = con.execute(
            """SELECT r.id, r.user_id, r.consultant_id, r.year AS Ano,
                      r.month AS 'Mês', c.name AS Consultor,
                      r.percentage AS Percentual
               FROM results r
               INNER JOIN consultants c
                 ON c.id = r.consultant_id AND c.user_id = r.user_id
               WHERE r.user_id = ?
               ORDER BY r.year, r.month, c.name""",
            (int(user_id),),
        ).fetchall()
    return pd.DataFrame([dict(linha) for linha in linhas], columns=[
        "id", "user_id", "consultant_id", "Ano", "Mês", "Consultor", "Percentual"
    ])


def atualizar_resultado(user_id, resultado_id, consultant_id, ano, mes, percentual):
    with conectar_banco() as con:
        cursor = con.execute(
            """UPDATE results
               SET consultant_id = ?, year = ?, month = ?, percentage = ?
               WHERE id = ? AND user_id = ?
                 AND EXISTS (
                     SELECT 1 FROM consultants c
                     WHERE c.id = ? AND c.user_id = ?
                 )""",
            (int(consultant_id), int(ano), mes, float(percentual),
             int(resultado_id), int(user_id), int(consultant_id), int(user_id)),
        )
        return cursor.rowcount == 1


def excluir_resultado(user_id, resultado_id):
    with conectar_banco() as con:
        cursor = con.execute(
            "DELETE FROM results WHERE id = ? AND user_id = ?",
            (int(resultado_id), int(user_id)),
        )
        return cursor.rowcount == 1


def faixa_performance(valor):
    if pd.isna(valor):
        return "Abaixo de 70%"
    if valor < 70:
        return "Abaixo de 70%"
    if valor < 100:
        return "70% a 99,99%"
    return "100% ou mais"


def preparar_dados(dados):
    dados = dados.copy()
    if dados.empty:
        return pd.DataFrame(columns=["id", "user_id", "consultant_id", "Ano", "Mês", "Consultor", "Percentual", "MêsNum", "Data", "Faixa"])
    dados["Ano"] = pd.to_numeric(dados["Ano"], errors="coerce")
    dados["Percentual"] = pd.to_numeric(dados["Percentual"], errors="coerce")
    dados["Mês"] = dados["Mês"].astype(str).str.strip()
    dados["Consultor"] = dados["Consultor"].astype(str).str.strip()
    dados = dados.dropna(subset=["Ano", "Percentual"])
    dados = dados[dados["Mês"].isin(MESES) & dados["Consultor"].ne("")]
    dados["Ano"] = dados["Ano"].astype(int)
    dados["MêsNum"] = dados["Mês"].map(MES_NUMERO)
    dados["Data"] = pd.to_datetime(
        {"year": dados["Ano"], "month": dados["MêsNum"], "day": 1},
        errors="coerce",
    )
    dados["Faixa"] = dados["Percentual"].apply(faixa_performance)
    return dados.sort_values(["Ano", "MêsNum", "Consultor"]).reset_index(drop=True)


def aplicar_estilo(fig, altura=390):
    fig.update_layout(
        template="plotly_dark",
        height=altura,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", color="#E5E7EB", size=12),
        title=dict(font=dict(size=17, color="#F8FAFC"), x=0.02, xanchor="left"),
        margin=dict(l=18, r=18, t=68, b=25),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#111827", bordercolor="#475569", font_size=12, font_family="Inter, Segoe UI, sans-serif"),
        xaxis=dict(showgrid=False, zeroline=False, automargin=True),
        yaxis=dict(gridcolor="rgba(148,163,184,0.16)", zeroline=False, automargin=True),
        transition=dict(duration=350, easing="cubic-in-out"),
    )
    return fig


PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": True,
    "responsive": True,
    "toImageButtonOptions": {"format": "png", "filename": "multi_analytics", "scale": 2},
    "modeBarButtonsToAdd": ["drawline", "eraseshape"],
}


def mostrar_grafico(fig, chave, descricao=None):
    if descricao:
        st.caption(descricao)
    fig = aplicar_estilo(fig)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=f"grafico_{chave}")

    # A imagem/PDF só é preparada quando solicitada, evitando lentidão em cada atualização.
    assinatura = hashlib.sha256(fig.to_json().encode("utf-8")).hexdigest()[:12]
    col_png, col_pdf, _ = st.columns([1, 1, 5])
    with col_png:
        if st.button("Preparar PNG", key=f"preparar_png_{chave}"):
            try:
                st.session_state[f"export_png_{chave}_{assinatura}"] = fig.to_image(format="png", scale=2)
            except Exception as erro:
                st.error(f"Não foi possível gerar o PNG. Verifique a instalação do Kaleido. Detalhe: {erro}")
        png = st.session_state.get(f"export_png_{chave}_{assinatura}")
        if png:
            st.download_button(
                "Baixar PNG", data=png, file_name=f"{chave}.png", mime="image/png",
                key=f"baixar_png_{chave}_{assinatura}",
            )
    with col_pdf:
        if st.button("Preparar PDF", key=f"preparar_pdf_{chave}"):
            try:
                st.session_state[f"export_pdf_{chave}_{assinatura}"] = fig.to_image(format="pdf", scale=2)
            except Exception as erro:
                st.error(f"Não foi possível gerar o PDF. Verifique a instalação do Kaleido. Detalhe: {erro}")
        pdf = st.session_state.get(f"export_pdf_{chave}_{assinatura}")
        if pdf:
            st.download_button(
                "Baixar PDF", data=pdf, file_name=f"{chave}.pdf", mime="application/pdf",
                key=f"baixar_pdf_{chave}_{assinatura}",
            )


def sem_dados(mensagem="Não há dados para os filtros selecionados."):
    st.info(mensagem)


# Aparência premium e responsiva.
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: Inter, 'Segoe UI', sans-serif; }
    .stApp { background: radial-gradient(ellipse at top left, rgba(37,99,235,.12), transparent 38%), #080D18; }
    [data-testid="stHeader"] { background: rgba(8,13,24,.88); }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #111827 0%, #0B1220 100%); border-right: 1px solid rgba(148,163,184,.15); }
    [data-testid="stMetric"] { background: linear-gradient(145deg, rgba(30,41,59,.82), rgba(15,23,42,.86)); padding: 17px 18px; border: 1px solid rgba(148,163,184,.17); border-radius: 16px; box-shadow: 0 12px 30px rgba(0,0,0,.13); transition: transform .2s ease, border-color .2s ease; }
    [data-testid="stMetric"]:hover { transform: translateY(-2px); border-color: rgba(96,165,250,.55); }
    [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 18px; }
    h1 { letter-spacing: -1.4px; font-weight: 800 !important; }
    h2, h3 { letter-spacing: -.45px; }
    div[data-testid="stPlotlyChart"] { border: 1px solid rgba(148,163,184,.12); border-radius: 16px; padding: 5px; background: rgba(15,23,42,.36); }
    .hero { padding: 26px 28px; border-radius: 22px; background: linear-gradient(120deg, rgba(30,64,175,.35), rgba(15,23,42,.92) 60%, rgba(13,148,136,.16)); border: 1px solid rgba(96,165,250,.22); margin-bottom: 18px; }
    .hero-kicker { color: #93C5FD; text-transform: uppercase; letter-spacing: 2px; font-size: 11px; font-weight: 800; }
    .hero-subtitle { color: #CBD5E1; font-size: 14px; margin-top: 6px; }
    div.stButton > button, div.stDownloadButton > button { border-radius: 10px; border: 1px solid rgba(148,163,184,.24); transition: all .18s ease; }
    div.stButton > button:hover, div.stDownloadButton > button:hover { border-color: #60A5FA; color: #BFDBFE; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Inicializa o banco local permanente antes de aceitar logins.
inicializar_banco()

if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = None

if not st.session_state.usuario_autenticado:
    st.markdown(
        """
        <div class="hero">
          <div class="hero-kicker">Multi Analytics · Acesso seguro</div>
          <h1 style="margin:7px 0 0 0;">Seu espaço de performance</h1>
          <div class="hero-subtitle">Entre na sua conta ou crie um acesso para manter seus dados privados.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col_login, col_registro = st.columns(2, gap="large")
    with col_login:
        st.subheader("Entrar")
        with st.form("form_login"):
            email_login = st.text_input("E-mail", key="email_login")
            senha_login = st.text_input("Senha", type="password", key="senha_login")
            enviar_login = st.form_submit_button("Entrar na minha conta", use_container_width=True)
        if enviar_login:
            usuario = autenticar_usuario(email_login, senha_login)
            if usuario:
                st.session_state.usuario_autenticado = usuario
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")
    with col_registro:
        st.subheader("Criar conta")
        st.caption("Cada conta tem seus próprios consultores e resultados.")
        with st.form("form_registro"):
            email_novo = st.text_input("Seu e-mail", key="email_novo")
            senha_nova = st.text_input("Crie uma senha (mínimo 10 caracteres)", type="password", key="senha_nova")
            senha_confirmacao = st.text_input("Confirme a senha", type="password", key="senha_confirmacao")
            enviar_registro = st.form_submit_button("Criar conta", use_container_width=True)
        if enviar_registro:
            if senha_nova != senha_confirmacao:
                st.error("As senhas não coincidem.")
            else:
                ok, mensagem = criar_usuario(email_novo, senha_nova)
                if ok:
                    usuario = autenticar_usuario(email_novo, senha_nova)
                    st.session_state.usuario_autenticado = usuario
                    st.success(mensagem)
                    st.rerun()
                else:
                    st.error(mensagem)
    st.info("Seus dados ficam em um banco separado logicamente por identificador de usuário. Não compartilhe sua senha.")
    st.stop()

USUARIO_ID = int(st.session_state.usuario_autenticado["id"])
USUARIO_EMAIL = st.session_state.usuario_autenticado["email"]

st.markdown(
    """
    <div class="hero">
      <div class="hero-kicker">Multi Analytics · Business Intelligence</div>
      <h1 style="margin:7px 0 0 0;">Painel de Performance</h1>
      <div class="hero-subtitle">Indicadores, tendências e comparações da equipe em uma visão executiva.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.session_state.dados = carregar_dados(USUARIO_ID)
consultores_usuario = listar_consultores(USUARIO_ID)

st.sidebar.markdown(f"## 👤 {USUARIO_EMAIL}")
if st.sidebar.button("Sair da conta", use_container_width=True):
    st.session_state.usuario_autenticado = None
    for chave in list(st.session_state.keys()):
        if chave not in {"usuario_autenticado"}:
            del st.session_state[chave]
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("## ✚ Novo lançamento")
if not consultores_usuario:
    st.sidebar.warning("Cadastre um consultor antes de lançar resultados.")
else:
    with st.sidebar.form("form_cadastro", clear_on_submit=True):
        ano_atual = date.today().year
        ano_cadastro = st.number_input("Ano", min_value=2000, max_value=2100, value=max(2026, ano_atual), step=1)
        mes_cadastro = st.selectbox("Mês", MESES, index=date.today().month - 1)
        consultor_por_nome = {c["name"]: c["id"] for c in consultores_usuario}
        nome_consultor_cadastro = st.selectbox("Consultor", list(consultor_por_nome.keys()))
        percentual_cadastro = st.number_input("Percentual alcançado (%)", min_value=0.0, max_value=400.0, value=0.0, step=0.01, format="%.2f")
        salvar_cadastro = st.form_submit_button("Salvar resultado", use_container_width=True)

    if salvar_cadastro:
        salvar_resultado(
            USUARIO_ID, consultor_por_nome[nome_consultor_cadastro],
            int(ano_cadastro), mes_cadastro, float(percentual_cadastro),
        )
        st.sidebar.success("Resultado salvo na sua conta.")
        st.rerun()

with st.sidebar.expander("👥 Gerenciar meus consultores"):
    with st.form("form_novo_consultor", clear_on_submit=True):
        novo_nome_consultor = st.text_input("Nome do novo consultor")
        adicionar_consultor_btn = st.form_submit_button("Adicionar consultor", use_container_width=True)
    if adicionar_consultor_btn:
        ok, mensagem = adicionar_consultor(USUARIO_ID, novo_nome_consultor)
        (st.success if ok else st.error)(mensagem)
        if ok:
            st.rerun()

    consultores_atualizados = listar_consultores(USUARIO_ID)
    if consultores_atualizados:
        mapa_consultores = {f'{c["name"]} (ID {c["id"]})': c["id"] for c in consultores_atualizados}
        consultor_para_excluir = st.selectbox("Remover consultor", list(mapa_consultores), key="consultor_para_excluir")
        st.caption("A remoção do consultor também apaga os lançamentos vinculados a ele.")
        if st.button("Excluir consultor selecionado", key="excluir_consultor_btn", use_container_width=True):
            if excluir_consultor(USUARIO_ID, mapa_consultores[consultor_para_excluir]):
                st.success("Consultor e seus lançamentos foram removidos da sua conta.")
                st.rerun()

df = preparar_dados(st.session_state.dados)

st.sidebar.markdown("---")
st.sidebar.markdown("## 🎛️ Filtros globais")
if df.empty:
    st.sidebar.info("Cadastre ou importe dados para habilitar os filtros.")
    anos_opcoes = ["Todos"]
    meses_opcoes = ["Todos"] + MESES
    consultores_opcoes = ["Todos"]
    min_data = pd.Timestamp(date.today().year, 1, 1)
    max_data = min_data
else:
    anos_opcoes = ["Todos"] + sorted(df["Ano"].unique().tolist(), reverse=True)
    meses_opcoes = ["Todos"] + [m for m in MESES if m in df["Mês"].unique()]
    consultores_opcoes = ["Todos"] + sorted(df["Consultor"].unique().tolist())
    min_data = df["Data"].min()
    max_data = df["Data"].max()

filtro_ano = st.sidebar.selectbox("Ano", anos_opcoes, key="global_ano")
filtro_mes = st.sidebar.selectbox("Mês", meses_opcoes, key="global_mes")
filtro_consultor = st.sidebar.selectbox("Consultor", consultores_opcoes, key="global_consultor")
filtro_faixa = st.sidebar.selectbox("Faixa de performance", ["Todas"] + FAIXAS, key="global_faixa")
filtro_status = st.sidebar.selectbox("Status do consultor", ["Todos"] + FAIXAS, key="global_status")
usar_periodo = st.sidebar.checkbox("Ativar período personalizado", value=False, key="usar_periodo")
if usar_periodo:
    periodo = st.sidebar.date_input(
        "De / até",
        value=(min_data.date(), max_data.date()),
        min_value=min_data.date(),
        max_value=max_data.date(),
        key="global_periodo",
    )
else:
    periodo = None

# Filtros globais aplicados a todos os gráficos.
df_base = df.copy()
if not df_base.empty:
    if filtro_ano != "Todos":
        df_base = df_base[df_base["Ano"] == int(filtro_ano)]
    if filtro_mes != "Todos":
        df_base = df_base[df_base["Mês"] == filtro_mes]
    if filtro_consultor != "Todos":
        df_base = df_base[df_base["Consultor"] == filtro_consultor]
    if periodo and len(periodo) == 2:
        inicio = pd.Timestamp(periodo[0]).to_period("M").to_timestamp()
        fim = pd.Timestamp(periodo[1]).to_period("M").to_timestamp()
        df_base = df_base[(df_base["Data"] >= inicio) & (df_base["Data"] <= fim)]

# Status é calculado por média do consultor no período filtrado antes da faixa por registro.
if not df_base.empty:
    medias_status = df_base[df_base["Consultor"].str.casefold() != "loja"].groupby("Consultor")["Percentual"].mean()
    status_consultores = {nome: faixa_performance(valor) for nome, valor in medias_status.items()}
    if filtro_status != "Todos":
        consultores_status_validos = [nome for nome, status in status_consultores.items() if status == filtro_status]
        df_base = df_base[df_base["Consultor"].isin(consultores_status_validos)]
    if filtro_faixa != "Todas":
        df_base = df_base[df_base["Faixa"] == filtro_faixa]

df_graf = df_base.copy()
df_consultores = df_graf[df_graf["Consultor"].str.casefold() != "loja"].copy() if not df_graf.empty else df_graf.copy()
df_loja = df_graf[df_graf["Consultor"].str.casefold() == "loja"].copy() if not df_graf.empty else df_graf.copy()

# Indicadores principais do recorte atual.
st.markdown("### Visão executiva")
if df_graf.empty:
    sem_dados("Nenhum registro corresponde aos filtros globais. Ajuste os filtros ou cadastre novos resultados.")
else:
    media_geral = df_graf["Percentual"].mean()
    total_consultores = df_consultores["Consultor"].nunique()
    atingiram_meta = int((df_consultores.groupby("Consultor")["Percentual"].mean() >= 100).sum()) if not df_consultores.empty else 0
    melhor_consultor = df_consultores.groupby("Consultor")["Percentual"].mean().idxmax() if not df_consultores.empty else "—"
    melhor_media = df_consultores.groupby("Consultor")["Percentual"].mean().max() if not df_consultores.empty else None
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Média do recorte", f"{media_geral:.2f}%")
    k2.metric("Consultores ativos", f"{total_consultores}")
    k3.metric("Consultores com meta", f"{atingiram_meta}/{total_consultores}")
    k4.metric("Destaque do período", melhor_consultor, f"{melhor_media:.2f}%" if melhor_media is not None else None)

st.caption("Todos os gráficos respeitam os filtros globais. Passe o mouse para ver detalhes; use a barra do gráfico para zoom, seleção e PNG. Os botões abaixo de cada gráfico preparam arquivos PNG e PDF para baixar.")
st.markdown("---")

# 1. Evolução Mensal por Consultor
st.markdown("## 1. Evolução Mensal por Consultor")
if not df_consultores.empty:
    d = df_consultores.groupby(["Ano", "Mês", "MêsNum", "Consultor"], as_index=False)["Percentual"].mean()
    d["Período"] = d["Mês"] + " " + d["Ano"].astype(str)
    d = d.sort_values(["Ano", "MêsNum"])
    fig = px.line(d, x="Período", y="Percentual", color="Consultor", markers=True, custom_data=["Ano", "Mês"], color_discrete_sequence=CORES_CONSULTORES, title="Evolução mensal por consultor", labels={"Percentual": "Atingimento (%)", "Período": "Período"})
    fig.update_traces(hovertemplate="<b>%{fullData.name}</b><br>%{customdata[1]} / %{customdata[0]}<br>Resultado: %{y:.2f}%<extra></extra>", line=dict(width=3))
    fig.update_xaxes(tickangle=-25)
    mostrar_grafico(fig, "01_evolucao_mensal")
else:
    sem_dados("Não há dados de consultores (excluindo Loja) para esse recorte.")

st.markdown("---")
# 2. Comparação entre Consultores
st.markdown("## 2. Comparação entre Consultores")
if not df_consultores.empty:
    d = df_consultores.groupby("Consultor", as_index=False)["Percentual"].mean().sort_values("Percentual", ascending=True)
    fig = px.bar(d, x="Percentual", y="Consultor", orientation="h", color="Percentual", color_continuous_scale=["#F87171", "#FBBF24", "#34D399"], text=d["Percentual"].map(lambda x: f"{x:.2f}%"), title="Média de performance por consultor", labels={"Percentual": "Média (%)"})
    fig.update_traces(textposition="outside", hovertemplate="<b>%{y}</b><br>Média: %{x:.2f}%<extra></extra>")
    mostrar_grafico(fig, "02_comparacao_consultores")
else:
    sem_dados()

st.markdown("---")
# 3. Ranking Geral
st.markdown("## 3. Ranking Geral")
if not df_consultores.empty:
    d = df_consultores.groupby("Consultor", as_index=False)["Percentual"].mean().sort_values("Percentual", ascending=False).reset_index(drop=True)
    d["Posição"] = d.index + 1
    d["Rótulo"] = d["Posição"].map(lambda p: "🥇" if p == 1 else ("🥈" if p == 2 else ("🥉" if p == 3 else f"{p}º")))
    fig = px.bar(d.sort_values("Percentual"), x="Percentual", y="Consultor", orientation="h", color="Percentual", color_continuous_scale=["#F87171", "#FBBF24", "#34D399"], text=d.sort_values("Percentual")["Rótulo"], custom_data=["Posição"], title="Classificação geral por média no período", labels={"Percentual": "Média (%)"})
    fig.update_traces(textposition="outside", hovertemplate="Posição %{customdata[0]}<br><b>%{y}</b><br>Média: %{x:.2f}%<extra></extra>")
    mostrar_grafico(fig, "03_ranking_geral")
else:
    sem_dados()

st.markdown("---")
# 4. Evolução Anual
st.markdown("## 4. Evolução Anual")
if not df_consultores.empty:
    d = df_consultores.groupby(["Ano", "Consultor"], as_index=False)["Percentual"].mean()
    fig = px.line(d, x="Ano", y="Percentual", color="Consultor", markers=True, color_discrete_sequence=CORES_CONSULTORES, title="Média anual por consultor", labels={"Ano": "Ano", "Percentual": "Média anual (%)"})
    fig.update_traces(line=dict(width=3), hovertemplate="<b>%{fullData.name}</b><br>Ano: %{x}<br>Média: %{y:.2f}%<extra></extra>")
    mostrar_grafico(fig, "04_evolucao_anual")
else:
    sem_dados()

st.markdown("---")
# 5. Média da Equipe por Ano
st.markdown("## 5. Média da Equipe por Ano")
if not df_consultores.empty:
    d = df_consultores.groupby("Ano", as_index=False)["Percentual"].mean()
    fig = px.area(d, x="Ano", y="Percentual", markers=True, title="Média da equipe por ano", labels={"Ano": "Ano", "Percentual": "Média da equipe (%)"})
    fig.update_traces(line=dict(color="#60A5FA", width=3), fillcolor="rgba(96,165,250,0.20)", hovertemplate="Ano: %{x}<br>Média da equipe: %{y:.2f}%<extra></extra>")
    fig.add_hline(y=100, line_dash="dash", line_color="#34D399", annotation_text="Meta 100%", annotation_position="top left")
    mostrar_grafico(fig, "05_media_equipe_ano")
else:
    sem_dados()

st.markdown("---")
# 6. Distribuição de Performance por Faixa de Cor
st.markdown("## 6. Distribuição de Performance por Faixa de Cor")
if not df_consultores.empty:
    d = df_consultores.groupby("Faixa", as_index=False).size().rename(columns={"size": "Registros"})
    d["Faixa"] = pd.Categorical(d["Faixa"], categories=FAIXAS, ordered=True)
    d = d.sort_values("Faixa")
    fig = px.pie(d, names="Faixa", values="Registros", hole=0.62, color="Faixa", color_discrete_map=CORES_FAIXAS, title="Distribuição dos registros por faixa")
    fig.update_traces(textinfo="percent+label", hovertemplate="%{label}<br>Registros: %{value}<br>Participação: %{percent}<extra></extra>")
    mostrar_grafico(fig, "06_distribuicao_faixas")
else:
    sem_dados()

st.markdown("---")
# 7. Heatmap de Performance Mensal
st.markdown("## 7. Heatmap de Performance Mensal")
if not df_consultores.empty:
    d = df_consultores.groupby(["Consultor", "Ano", "Mês", "MêsNum"], as_index=False)["Percentual"].mean()
    d["Linha"] = d["Consultor"] + " · " + d["Ano"].astype(str)
    matriz = d.pivot_table(index="Linha", columns="Mês", values="Percentual", aggfunc="mean", observed=False)
    matriz = matriz.reindex(columns=[m for m in MESES if m in matriz.columns])
    if not matriz.empty:
        fig = go.Figure(data=go.Heatmap(
            z=matriz.values, x=matriz.columns.tolist(), y=matriz.index.tolist(),
            colorscale=[[0, "#F87171"], [0.45, "#FBBF24"], [1, "#34D399"]],
            colorbar=dict(title="Atingimento (%)"),
            hovertemplate="Consultor/Ano: %{y}<br>Mês: %{x}<br>Performance: %{z:.2f}%<extra></extra>",
            zmin=0, zmax=max(100, float(matriz.max().max())),
        ))
        fig.update_layout(title="Mapa de calor mensal por consultor e ano", xaxis_title="Mês", yaxis_title="Consultor · Ano")
        mostrar_grafico(fig, "07_heatmap_mensal", "Cores mais quentes indicam resultados menores; verde indica performance mais alta.")
    else:
        sem_dados()
else:
    sem_dados()

st.markdown("---")
# 8. Radar de Comparação de Consultores
st.markdown("## 8. Radar de Comparação de Consultores")
if not df_consultores.empty:
    d = df_consultores.groupby(["Consultor", "Mês", "MêsNum"], as_index=False)["Percentual"].mean()
    fig = go.Figure()
    for nome in sorted(d["Consultor"].unique()):
        serie = d[d["Consultor"] == nome].set_index("Mês").reindex(MESES)
        valores = serie["Percentual"].tolist()
        categorias = MESES
        valores_radar = [None if pd.isna(v) else float(v) for v in valores]
        if any(v is not None for v in valores_radar):
            fig.add_trace(go.Scatterpolar(
                r=valores_radar + [valores_radar[0]],
                theta=categorias + [categorias[0]],
                name=nome, mode="lines+markers", connectgaps=False,
                line=dict(width=2.5),
                hovertemplate="<b>%{fullData.name}</b><br>%{theta}: %{r:.2f}%<extra></extra>",
            ))
    fig.update_layout(title="Perfil mensal comparativo", polar=dict(
        bgcolor="rgba(0,0,0,0)",
        radialaxis=dict(visible=True, gridcolor="rgba(148,163,184,.22)", ticksuffix="%"),
        angularaxis=dict(gridcolor="rgba(148,163,184,.18)"),
    ))
    mostrar_grafico(fig, "08_radar_consultores", "O radar usa a média de cada consultor por mês dentro do período filtrado.")
else:
    sem_dados()

st.markdown("---")
# 9. Tendência de Crescimento
st.markdown("## 9. Tendência de Crescimento")
if not df_consultores.empty:
    d = df_consultores.groupby(["Data", "Ano", "Mês", "MêsNum"], as_index=False)["Percentual"].mean().sort_values("Data")
    d["Período"] = d["Mês"] + " " + d["Ano"].astype(str)
    fig = px.line(d, x="Período", y="Percentual", markers=True, title="Tendência da média da equipe", labels={"Período": "Período", "Percentual": "Média (%)"})
    fig.update_traces(line=dict(color="#2DD4BF", width=3), hovertemplate="%{x}<br>Média: %{y:.2f}%<extra></extra>")
    if len(d) >= 2:
        x_num = list(range(len(d)))
        coef = pd.Series(d["Percentual"].values).reset_index(drop=True)
        tendencia = pd.Series(x_num).map(lambda x: float(coef.mean()) if len(coef) < 2 else float(__import__("numpy").polyfit(x_num, coef.values, 1)[0] * x + __import__("numpy").polyfit(x_num, coef.values, 1)[1]))
        fig.add_trace(go.Scatter(x=d["Período"], y=tendencia, mode="lines", name="Linha de tendência", line=dict(color="#FBBF24", width=2, dash="dash"), hovertemplate="Tendência: %{y:.2f}%<extra></extra>"))
    fig.update_xaxes(tickangle=-25)
    mostrar_grafico(fig, "09_tendencia_crescimento")
else:
    sem_dados()

# Acompanhamento da Loja separado da classificação de consultores.
st.markdown("---")
st.markdown("## 🏬 Acompanhamento da Loja")
if not df_loja.empty:
    loja_mes = df_loja.groupby(["Ano", "Mês", "MêsNum"], as_index=False)["Percentual"].mean().sort_values(["Ano", "MêsNum"])
    media_loja = df_loja["Percentual"].mean()
    status_loja = faixa_performance(media_loja)
    l1, l2, l3 = st.columns(3)
    l1.metric("Média da Loja", f"{media_loja:.2f}%")
    l2.metric("Faixa atual", status_loja)
    l3.metric("Registros", f"{len(df_loja)}")
    loja_mes["Status"] = loja_mes["Percentual"].apply(faixa_performance)
    fig = px.bar(loja_mes, x="Mês", y="Percentual", color="Status", facet_col="Ano", category_orders={"Mês": MESES, "Status": FAIXAS}, color_discrete_map=CORES_FAIXAS, title="Acompanhamento mensal da Loja", labels={"Percentual": "Atingimento (%)"})
    fig.update_traces(hovertemplate="%{x}<br>Resultado: %{y:.2f}%<extra></extra>")
    mostrar_grafico(fig, "10_acompanhamento_loja")
else:
    sem_dados("Ainda não há registros da Loja no recorte selecionado. Use o formulário lateral e selecione 'Loja'.")

# Tabela de dados e edição.
st.markdown("---")
with st.expander("🗂️ Consultar, editar e excluir meus lançamentos", expanded=False):
    st.caption("Esta tabela mostra somente os seus registros. Toda alteração é validada pelo identificador da conta autenticada.")
    if not st.session_state.dados.empty:
        st.dataframe(
            st.session_state.dados[["id", "Ano", "Mês", "Consultor", "Percentual"]],
            use_container_width=True,
            hide_index=True,
        )
        registros = st.session_state.dados.to_dict("records")
        rotulos = {
            f'#{int(r["id"])} · {r["Consultor"]} · {r["Mês"]}/{int(r["Ano"])} · {float(r["Percentual"]):.2f}%': r
            for r in registros
        }
        registro_escolhido_label = st.selectbox(
            "Selecione um dos seus lançamentos", list(rotulos.keys()), key="registro_para_editar"
        )
        registro_escolhido = rotulos[registro_escolhido_label]
        mapa_consultores_edicao = {c["name"]: c["id"] for c in listar_consultores(USUARIO_ID)}
        nomes_edicao = list(mapa_consultores_edicao)
        nome_atual = str(registro_escolhido["Consultor"])
        indice_consultor = nomes_edicao.index(nome_atual) if nome_atual in nomes_edicao else 0
        with st.form("form_editar_resultado"):
            c1, c2 = st.columns(2)
            with c1:
                edit_ano = st.number_input(
                    "Ano do lançamento", min_value=2000, max_value=2100,
                    value=int(registro_escolhido["Ano"]), step=1
                )
                edit_mes = st.selectbox(
                    "Mês do lançamento", MESES,
                    index=MESES.index(str(registro_escolhido["Mês"]))
                )
            with c2:
                edit_consultor_nome = st.selectbox(
                    "Consultor do lançamento", nomes_edicao, index=indice_consultor
                )
                edit_percentual = st.number_input(
                    "Percentual (%)", min_value=0.0, max_value=400.0,
                    value=float(registro_escolhido["Percentual"]), step=0.01, format="%.2f"
                )
            salvar_edicao = st.form_submit_button("Salvar alterações")
        if salvar_edicao:
            ok = atualizar_resultado(
                USUARIO_ID, int(registro_escolhido["id"]),
                mapa_consultores_edicao[edit_consultor_nome],
                int(edit_ano), edit_mes, float(edit_percentual),
            )
            if ok:
                st.success("Lançamento atualizado.")
                st.rerun()
            else:
                st.error("Não foi possível atualizar esse lançamento.")
        st.warning("Excluir é permanente e afeta somente o lançamento selecionado.")
        confirmar_exclusao = st.checkbox("Confirmo que desejo excluir este lançamento", key="confirmar_exclusao_lancamento")
        if st.button("Excluir lançamento selecionado", key="excluir_lancamento_btn", disabled=not confirmar_exclusao):
            if excluir_resultado(USUARIO_ID, int(registro_escolhido["id"])):
                st.success("Lançamento excluído da sua conta.")
                st.rerun()
            else:
                st.error("Não foi possível excluir esse lançamento.")
    else:
        sem_dados("Você ainda não possui lançamentos. Use o formulário lateral para cadastrar o primeiro resultado.")

st.markdown("---")
st.caption("Multi Analytics · Os resultados são calculados a partir dos registros cadastrados. Exporte os gráficos em PNG ou PDF pelos controles de cada visualização.")

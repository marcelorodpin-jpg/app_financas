import hashlib
import hmac
import html
import os
import re
import secrets
from datetime import date, datetime
from pathlib import Path

import firebase_admin
import streamlit as st
from firebase_admin import credentials, firestore
from google.api_core.exceptions import AlreadyExists, GoogleAPICallError
from streamlit.errors import StreamlitSecretNotFoundError


APP_TITLE = "Gestão Financeira"
DEFAULT_CREDENTIALS_FILE = "app-financas-c2243-firebase-adminsdk-fbsvc-f5cc8404d9.json"
PASSWORD_ITERATIONS = 310_000
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,40}$")


@st.cache_resource
def get_firestore_client():
    try:
        firebase_secrets = st.secrets.get("firebase")
    except StreamlitSecretNotFoundError:
        firebase_secrets = None
    if firebase_secrets:
        firebase_credential = credentials.Certificate(dict(firebase_secrets))
    else:
        credentials_path = Path(
            os.environ.get("FIREBASE_CREDENTIALS", DEFAULT_CREDENTIALS_FILE)
        )
        if not credentials_path.is_file():
            raise FileNotFoundError(
                f"Credenciais Firebase não encontradas em st.secrets[firebase] "
                f"ou no arquivo: {credentials_path}"
            )
        firebase_credential = credentials.Certificate(str(credentials_path))

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(firebase_credential)
    return firestore.client()


def normalized_username(username: str) -> str:
    return username.strip().casefold()


def user_document_id(username: str) -> str:
    return hashlib.sha256(normalized_username(username).encode("utf-8")).hexdigest()


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )


def register_user(db, username: str, password: str) -> tuple[bool, str]:
    clean_username = username.strip()
    if not USERNAME_PATTERN.fullmatch(clean_username):
        return False, "Use um usuário de 3 a 40 caracteres: letras, números, ponto, _ ou -."
    if len(password) < 10:
        return False, "A senha deve ter pelo menos 10 caracteres."

    salt = secrets.token_bytes(16)
    user_ref = db.collection("usuarios").document(user_document_id(clean_username))
    try:
        user_ref.create(
            {
                "username": normalized_username(clean_username),
                "password_salt": salt.hex(),
                "password_hash": hash_password(password, salt).hex(),
                "password_iterations": PASSWORD_ITERATIONS,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )
    except AlreadyExists:
        return False, "Esse usuário já está cadastrado."
    return True, "Cadastro realizado. Agora você já pode entrar."


def authenticate_user(db, username: str, password: str) -> bool:
    user_ref = db.collection("usuarios").document(user_document_id(username))
    user_snapshot = user_ref.get()
    if not user_snapshot.exists:
        return False

    user = user_snapshot.to_dict()
    try:
        salt = bytes.fromhex(user["password_salt"])
        expected_hash = bytes.fromhex(user["password_hash"])
        iterations = int(user["password_iterations"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("O cadastro deste usuário está inválido no Firestore.") from exc

    actual_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(actual_hash, expected_hash)


def format_currency(amount: float) -> str:
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def load_transactions(db, owner_id: str) -> list[dict]:
    snapshots = db.collection("transacoes").where("owner_id", "==", owner_id).stream()
    transactions = []
    for snapshot in snapshots:
        transaction = snapshot.to_dict()
        transaction["id"] = snapshot.id
        transaction["date"] = transaction["date"].date()
        transactions.append(transaction)
    return sorted(transactions, key=lambda item: (item["date"], item["id"]), reverse=True)


def save_transaction(
    db,
    owner_id: str,
    transaction_type: str,
    description: str,
    category: str,
    amount: float,
    transaction_date: date,
    transaction_id: str | None = None,
) -> None:
    data = {
        "owner_id": owner_id,
        "type": transaction_type,
        "description": description.strip(),
        "category": category.strip(),
        "amount": round(amount, 2),
        "date": datetime.combine(transaction_date, datetime.min.time()),
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    if transaction_id:
        db.collection("transacoes").document(transaction_id).update(data)
    else:
        data["created_at"] = firestore.SERVER_TIMESTAMP
        db.collection("transacoes").add(data)


def render_authentication(db) -> None:
    st.title(APP_TITLE)
    st.caption("Entre ou crie uma conta para gerenciar suas receitas e despesas.")
    login_tab, register_tab = st.tabs(["Entrar", "Criar conta"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Usuário", key="login_username")
            password = st.text_input("Senha", type="password", key="login_password")
            submitted = st.form_submit_button("Entrar", type="primary")
        if submitted:
            if authenticate_user(db, username, password):
                st.session_state["user_id"] = user_document_id(username)
                st.session_state["username"] = normalized_username(username)
                st.rerun()
            st.error("Usuário ou senha inválidos.")

    with register_tab:
        with st.form("register_form"):
            username = st.text_input("Usuário", key="register_username")
            password = st.text_input("Senha", type="password", key="register_password")
            password_confirmation = st.text_input(
                "Confirme a senha", type="password", key="register_password_confirmation"
            )
            submitted = st.form_submit_button("Cadastrar", type="primary")
        if submitted:
            if password != password_confirmation:
                st.error("As senhas não conferem.")
            else:
                created, message = register_user(db, username, password)
                (st.success if created else st.error)(message)


def render_mobile_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stMainBlockContainer"] {
            max-width: 600px;
            padding-bottom: 6rem;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.5rem;
            margin: 0.5rem 0 1.5rem;
        }
        .summary-card {
            min-width: 0;
            padding: 0.8rem 0.65rem;
            border: 1px solid rgba(128, 128, 128, 0.22);
            border-radius: 0.9rem;
            background: var(--secondary-background-color);
        }
        .summary-label {
            display: block;
            margin-bottom: 0.35rem;
            color: var(--text-color);
            font-size: 0.78rem;
            opacity: 0.75;
        }
        .summary-value {
            display: block;
            overflow-wrap: anywhere;
            color: var(--text-color);
            font-size: clamp(0.8rem, 3.5vw, 1.08rem);
            font-weight: 700;
        }
        .transaction-card {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.8rem;
            margin: 0.6rem 0;
            padding: 0.9rem 1rem;
            border: 1px solid rgba(128, 128, 128, 0.22);
            border-radius: 0.9rem;
            background: var(--secondary-background-color);
        }
        .transaction-description {
            overflow-wrap: anywhere;
            font-weight: 650;
        }
        .transaction-detail {
            margin-top: 0.25rem;
            color: var(--text-color);
            font-size: 0.8rem;
            opacity: 0.72;
        }
        .transaction-amount {
            flex-shrink: 0;
            font-weight: 700;
            text-align: right;
        }
        .transaction-income { color: #138a50; }
        .transaction-expense { color: #d64b4b; }
        div.st-key-add_transaction_button {
            position: fixed;
            z-index: 1000;
            bottom: calc(1rem + env(safe-area-inset-bottom));
            left: 50%;
            width: 3.75rem;
            transform: translateX(-50%);
        }
        div.st-key-add_transaction_button button {
            width: 3.75rem;
            height: 3.75rem;
            min-height: 3.75rem;
            padding: 0;
            border-radius: 50%;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.24);
            font-size: 2rem;
            line-height: 1;
        }
        @media (max-width: 420px) {
            [data-testid="stMainBlockContainer"] {
                padding-left: 1rem;
                padding-right: 1rem;
            }
            .summary-grid { gap: 0.35rem; }
            .summary-card { padding: 0.7rem 0.45rem; }
            .summary-label { font-size: 0.72rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_transaction_list(transactions: list[dict]) -> None:
    if not transactions:
        st.info("Nenhuma movimentação cadastrada. Toque no + para adicionar a primeira.")
        return

    for item in transactions:
        is_income = item["type"] == "Receita"
        amount_class = "transaction-income" if is_income else "transaction-expense"
        sign = "+" if is_income else "−"
        description = html.escape(item["description"])
        category = html.escape(item["category"])
        transaction_type = html.escape(item["type"])
        st.markdown(
            f"""
            <div class="transaction-card">
                <div>
                    <div class="transaction-description">{description}</div>
                    <div class="transaction-detail">
                        {transaction_type} · {category} · {item["date"].strftime("%d/%m/%Y")}
                    </div>
                </div>
                <div class="transaction-amount {amount_class}">
                    {sign} {format_currency(item["amount"])}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_transaction_actions(db, owner_id: str, transactions: list[dict]) -> None:
    if not transactions:
        return

    transaction_ids = [item["id"] for item in transactions]
    transaction_by_id = {item["id"]: item for item in transactions}
    with st.expander("Editar ou excluir movimentações"):
        selected_id = st.selectbox(
            "Selecione uma movimentação",
            transaction_ids,
            format_func=lambda transaction_id: (
                f"{transaction_by_id[transaction_id]['date'].strftime('%d/%m/%Y')} · "
                f"{transaction_by_id[transaction_id]['type']} · "
                f"{transaction_by_id[transaction_id]['description']} · "
                f"{format_currency(transaction_by_id[transaction_id]['amount'])}"
            ),
            key="manage_transaction_selection",
        )
        selected = transaction_by_id[selected_id]
        with st.form("edit_transaction_form"):
            transaction_type = st.selectbox(
                "Tipo",
                ["Despesa", "Receita"],
                index=["Despesa", "Receita"].index(selected["type"]),
                key="edit_type",
            )
            description = st.text_input(
                "Descrição", value=selected["description"], key="edit_description"
            )
            category = st.text_input(
                "Categoria", value=selected["category"], key="edit_category"
            )
            amount = st.number_input(
                "Valor (R$)",
                min_value=0.01,
                value=float(selected["amount"]),
                step=0.01,
                format="%.2f",
                key="edit_amount",
            )
            transaction_date = st.date_input(
                "Data", value=selected["date"], format="DD/MM/YYYY", key="edit_date"
            )
            updated = st.form_submit_button("Salvar alterações", type="primary")
        if updated:
            if not description.strip() or not category.strip():
                st.error("Preencha a descrição e a categoria.")
            else:
                save_transaction(
                    db,
                    owner_id,
                    transaction_type,
                    description,
                    category,
                    amount,
                    transaction_date,
                    selected_id,
                )
                st.success("Movimentação atualizada.")
                st.rerun()

        confirm_delete = st.checkbox(
            "Confirmo que desejo excluir esta movimentação.",
            key=f"confirm_delete_{selected_id}",
        )
        if st.button(
            "Excluir movimentação",
            disabled=not confirm_delete,
            key=f"delete_{selected_id}",
        ):
            db.collection("transacoes").document(selected_id).delete()
            st.success("Movimentação excluída.")
            st.rerun()


def render_new_transaction(db, owner_id: str) -> None:
    if st.button("← Voltar para listagem", use_container_width=True):
        st.session_state["screen"] = "list"
        st.rerun()

    st.subheader("Nova movimentação")
    with st.form("create_transaction_form"):
        transaction_type = st.selectbox("Tipo", ["Despesa", "Receita"])
        description = st.text_input("Descrição")
        category = st.text_input("Categoria")
        amount = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
        transaction_date = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        submitted = st.form_submit_button("Salvar movimentação", type="primary")
    if submitted:
        if not description.strip() or not category.strip():
            st.error("Preencha a descrição e a categoria.")
        else:
            save_transaction(
                db,
                owner_id,
                transaction_type,
                description,
                category,
                amount,
                transaction_date,
            )
            st.session_state["screen"] = "list"
            st.rerun()


def render_dashboard(db, owner_id: str, username: str) -> None:
    render_mobile_styles()
    st.title(APP_TITLE)
    header_col, logout_col = st.columns([4, 1])
    header_col.caption(f"Olá, **{username}**")
    if logout_col.button("Sair", use_container_width=True):
        st.session_state.pop("user_id", None)
        st.session_state.pop("username", None)
        st.session_state.pop("screen", None)
        st.rerun()

    transactions = load_transactions(db, owner_id)
    income = sum(item["amount"] for item in transactions if item["type"] == "Receita")
    expenses = sum(item["amount"] for item in transactions if item["type"] == "Despesa")
    st.markdown(
        f"""
        <div class="summary-grid">
            <div class="summary-card">
                <span class="summary-label">Receita</span>
                <span class="summary-value transaction-income">{format_currency(income)}</span>
            </div>
            <div class="summary-card">
                <span class="summary-label">Despesa</span>
                <span class="summary-value transaction-expense">{format_currency(expenses)}</span>
            </div>
            <div class="summary-card">
                <span class="summary-label">Saldo</span>
                <span class="summary-value">{format_currency(income - expenses)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("screen") == "new_transaction":
        render_new_transaction(db, owner_id)
        return

    st.subheader("Movimentações")
    render_transaction_list(transactions)
    render_transaction_actions(db, owner_id, transactions)
    if st.button("+", type="primary", key="add_transaction_button"):
        st.session_state["screen"] = "new_transaction"
        st.rerun()


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="💰", layout="wide")
    try:
        db = get_firestore_client()
    except (FileNotFoundError, ValueError, OSError, GoogleAPICallError) as exc:
        st.error(
            "Não foi possível conectar ao Firebase. Confira o arquivo de credenciais, "
            "a variável FIREBASE_CREDENTIALS e o acesso ao Firestore."
        )
        st.caption(f"Detalhe: {type(exc).__name__}: {exc}")
        st.stop()

    try:
        if "user_id" not in st.session_state:
            render_authentication(db)
        else:
            render_dashboard(
                db, st.session_state["user_id"], st.session_state["username"]
            )
    except GoogleAPICallError as exc:
        st.error("Falha ao acessar o Firestore. Verifique a conexão e as permissões.")
        st.caption(f"Detalhe: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()

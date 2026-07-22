import streamlit as st

from frontend.api_client import (
    APIClientError,
    BACKEND_URL,
    get_health,
)


st.set_page_config(
    page_title="EnterpriseMind AI",
    page_icon="🧠",
    layout="wide",
)


st.title("EnterpriseMind AI")

st.write(
    "Secure organizational knowledge, document search, "
    "grounded AI answers and enterprise analytics."
)

st.divider()

st.subheader("System status")

st.caption(f"Backend address: {BACKEND_URL}")

try:
    health_data = get_health()

    st.success(
        "The EnterpriseMind AI backend is online."
    )

    st.json(health_data)

except APIClientError as exc:
    st.error(str(exc))

    st.info(
        "Start the FastAPI backend and refresh this page."
    )
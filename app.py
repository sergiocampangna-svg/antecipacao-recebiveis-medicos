from __future__ import annotations

from pathlib import Path
import runpy

import streamlit as st


ROOT = Path(__file__).resolve().parent
VERSIONS = {
    "Versão 90 dias fixo": ROOT / "versao-90-dias-fixo" / "app.py",
    "Versão original": ROOT / "versao-original" / "app.py",
}


def main() -> None:
    st.set_page_config(
        page_title="Simulação de Antecipação Médica",
        page_icon="",
        layout="wide",
    )

    with st.sidebar:
        st.markdown("**Versões da aplicação**")
        selected_version = st.radio(
            "Escolha a versão",
            list(VERSIONS.keys()),
            index=0,
            key="selected_app_version",
            label_visibility="collapsed",
        )

    target = VERSIONS[selected_version]
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()

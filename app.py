#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Punto de entrada para Streamlit Community Cloud.

La aplicación real (login con contraseña + predictor completo) vive en
dashboard_ui.py; este archivo existe porque el despliegue usa `app.py`
como main file. Ejecuta el dashboard en el mismo contexto de script.
"""

import runpy
import streamlit as st

# --- ELIMINACIÓN TOTAL DE MARCAS DE STREAMLIT ---
st.markdown("""
    <style>
        /* Ocultar Creator Badge moderno por ID */
        [data-testid="stViewerBadge"] {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
        
        /* Ocultar Creator Badge por comodín de clase */
        div[class*="viewerBadge"], .viewerBadge_container {
            display: none !important;
            visibility: hidden !important;
        }
        
        /* Ocultar barra superior y pie de página */
        footer, [data-testid="stHeader"] {
            display: none !important;
            visibility: hidden !important;
        }
        
        /* Bloquear redirecciones a su dominio */
        a[href^="https://share.streamlit.io"] {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

runpy.run_path("dashboard_ui.py", run_name="__main__")

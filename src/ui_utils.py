import streamlit as st
import requests

LOTTIE_SCANNING_URL = "https://lottie.host/8b51d113-d023-4b95-bd71-8c4391672322/e1bCjB2E6a.json"


def inject_custom_css():
    st.markdown(
        """
        <style>
        h1, h2, h3, p, span {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        .stButton > button {
            border-radius: 8px;
            transition: all 0.2s ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 119, 182, 0.2);
        }

        .stCard {
            border-radius: 0;
            padding: 1rem 0 0.25rem 0;
            border: none;
            border-top: 1px solid rgba(128, 128, 128, 0.18);
            box-shadow: none;
            margin-top: 0.5rem;
        }

        @media (prefers-color-scheme: dark) {
            .stCard {
                box-shadow: none;
                border: none;
                border-top: 1px solid rgba(255, 255, 255, 0.16);
            }
        }

        [data-testid="stChatInput"] {
            border-radius: 12px;
        }

        [data-testid="stSidebarNav"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_lottieurl(url: str):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception:
        return None

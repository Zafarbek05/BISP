import streamlit as st
import src.chat_storage as db

def process_post_login_identity():
    """
    Post-login hook for Zero-Friction Social Login (OIDC).
    Handles JIT Provisioning and Identity Merging.
    """
    if not st.user or not st.user.get("is_logged_in", False):
        return None
    
    user_info = st.user
    email = user_info.get("email")
    name = user_info.get("name")
    social_id = user_info.get("sub")
    picture = user_info.get("picture")
    
    if not email:
        st.error("Google login failed: Email not provided by identity provider.")
        return None

    # Step 2 & 3: JIT Provisioning & Identity Merging
    # upsert_social_user handles searching by email, merging if existing, or creating if new.
    db.upsert_social_user(
        email=email,
        username=name,
        social_id=social_id,
        picture=picture,
        provider='google'
    )
    
    # Get the final user record from the database
    user = db.get_user_by_email(email)
    
    if user:
        # Step 5: Session Management
        st.session_state.authenticated = True
        st.session_state.user_id = user["id"]
        st.session_state.current_user_id = user["id"] # Requirement 5
        st.session_state.username = user["username"]
        st.session_state.role = user["role"]
        st.session_state.picture = user.get("picture")
        st.session_state.provider = user.get("provider")
        st.session_state.rate_limit_timestamps = []
        
        # Clear any existing chat session info to ensure fresh start
        for key in ["session_id", "messages"]:
            if key in st.session_state:
                del st.session_state[key]
        
        return user
    return None

def process_social_login():
    """Legacy wrapper for backward compatibility."""
    return process_post_login_identity()

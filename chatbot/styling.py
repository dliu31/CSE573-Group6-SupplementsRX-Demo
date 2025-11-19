import streamlit as st

CHAT_CSS = """
<style>


.chat-row {
    display: flex;
    margin-bottom: 0.5rem;
    width: 100%;          /* full width row */
    /* remove max-width here, we'll control width on the bubble */
}

.chat-row > div {
    max-width: 60%;          /* bubble can grow to 60% of the row width */
    width: 100%;
}

.chat-row.user {
    justify-content: flex-end;
}

.chat-row.assistant {
    justify-content: flex-start;
}

/* The message bubble */
.chat-bubble {
    width: fit-content; 
    # max-width: 80%;       /* or whatever width you want */
    padding: 0.8rem 1rem;
    border-radius: 1rem;
    line-height: 1.4;
    font-size: 0.95rem;
    overflow-wrap: break-word;
    white-space: normal;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    border: 1px solid rgba(0,0,0,0.08);
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* User bubble (right side) */
.chat-row.user .chat-bubble {

    background: #2b6cb0;
    max-width: 80%;
    color: white;
    margin-left: auto;
    

}

/* Assistant bubble (left side) */
.chat-row.assistant .chat-bubble {
    background: #f1f1f1;
    color: #222;
    max-width: 100%;
    border-bottom-left-radius: 0.3rem;
    border: 1px solid rgba(0,0,0,0.1);
}

/* Small label above each bubble */
.role-label {
    font-size: 0.7rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
    color: #666;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    text-align: left;
}

.chat-row.user .role-label {
    text-align: right;
    color: #4a5568;
}




# .stChatInput {
#         position: fixed;
#         bottom: 1rem; /* Adjust as needed for spacing from the bottom */
#         width: 55%; /* Adjust width as needed */ 
#         z-index: 999; /* Ensure it stays on top of other content */
#     }



/* base styling for consistency */
.stButton > button {
    padding: 0.45rem 1rem !important;
    border-radius: 0.5rem !important;
    border: none !important;
    font-weight: 600 !important;
    color: white !important;
}

/* Column 1 = Accept = green */
div[data-testid="column"]:nth-of-type(1) .stButton > button {
    background-color: #22c55e !important; /* green */
}

/* Column 2 = Reject = red */
div[data-testid="column"]:nth-of-type(2) .stButton > button {
    background-color: #dc2626 !important; /* red */
}





</style>
"""

def inject_css():
    
    st.markdown(CHAT_CSS, unsafe_allow_html=True)


def render_message(role: str, pretty_role: str, content: str):
    """Render one chat bubble row in the correct position."""
    st.markdown(
        f"""
        <div class="chat-row {role}">
            <div>
                <div class="role-label">{pretty_role}</div>
                <div class="chat-bubble">{content}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )







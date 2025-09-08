import streamlit as st
import pandas as pd
from chatbot import get_chatbot_reply

# Set page config with title and icon
st.set_page_config(
    page_title="🏥 Medical Chatbot",
    page_icon="🩺",
    layout="centered",
)

# Custom CSS styling for buttons and chatboxes
st.markdown("""
    <style>
        .stButton>button {
            background-color: #4CAF50;
            color: #FFFACD;  /* Light yellow text */
            font-size: 18px;
            padding: 10px 24px;
            border-radius: 10px;
            border: none;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #45a049;
        }
        .chatbox {
            background-color: #22223b;   /* DARK NAVY BACKGROUND */
            border-radius: 10px;
            padding: 15px;
            margin-top: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.4);
            color: #e9e9e9;
        }
        .user-msg {
            color: #FFD700;  /* Gold Color for user message */
            font-weight: bold;
            margin-bottom: 5px;
        }
        .bot-msg {
            color: #89b4fa;  /* Soft blue text for chatbot */
            padding-left: 10px;
            margin-bottom: 5px;
        }
        .sql-query {
            background-color: #1e1e2f;
            color: #d4d4d4;
            padding: 10px;
            border-radius: 8px;
            font-family: monospace;
            margin-top: 10px;
            white-space: pre-wrap;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🏥 Medical Chatbot")
st.write("Ask me about doctors, hospitals, symptoms, specialties, and availability.")

chat_container = st.container()

with st.form(key='chat_form', clear_on_submit=True):
    user_input = st.text_area("Enter your health concern and hospital:", max_chars=200, height=80)
    submit_button = st.form_submit_button("Get Recommendation")

if submit_button:
    if user_input.strip():
        with st.spinner("🤖 Thinking..."):
            reply = get_chatbot_reply(user_input, filepath="hospital_dataset.csv")

        with chat_container:
            # User Message
            st.markdown(f"""
                <div class='chatbox'>
                    <div class='user-msg'>You:</div>
                    <div>{user_input}</div>
                </div>
            """, unsafe_allow_html=True)

            # Chatbot Reply (Natural language)
            st.markdown(f"""
                <div class='chatbox'>
                    <div class='bot-msg'>Chatbot Response:</div>
                    <div>{reply['result']}</div>
                </div>
            """, unsafe_allow_html=True)

            # SQL Query Display
            st.markdown(f"""
                <div class='chatbox sql-query'>
                <strong>Generated SQL Query:</strong>
                <pre>{reply['sql_query']}</pre>
                </div>
            """, unsafe_allow_html=True)

            # Results Table
            if reply["rows"]:
                df = pd.DataFrame(reply["rows"])
                st.table(df)
            else:
                st.warning("❌ No matching records found.")

            # NLP Suggestions if any
            if reply.get("nlp_suggestion"):
                st.info(f"💡 NLP Suggestion: {reply['nlp_suggestion']}")
    else:
        st.warning("⚠️ Please enter a health-related query to get a recommendation.")

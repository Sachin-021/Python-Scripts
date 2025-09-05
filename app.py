import streamlit as st
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
        }
        .user-msg {
            color: #e9e9e9;  /* Soft light gray text */
            font-weight: bold;
        }
        .bot-msg {
            color: #89b4fa;  /* Soft blue text for chatbot */
            padding-left: 10px;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🏥 Medical Chatbot")
st.write("Ask me about doctors, hospitals, symptoms, specialties, and availability.")

# Container for displaying chat
chat_container = st.container()

with st.form(key='chat_form', clear_on_submit=True):
    user_input = st.text_area("Enter your health concern and hospital:", max_chars=200, height=80)
    submit_button = st.form_submit_button("Get Recommendation")

if submit_button:
    if user_input.strip():
        with st.spinner("🤖 Thinking..."):
            reply = get_chatbot_reply(user_input, filepath="hospital_dataset.csv")
        with chat_container:
            st.markdown(f"<div class='chatbox'><div class='user-msg'>You:</div><div>{user_input}</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='chatbox'><div class='bot-msg'>Chatbot:</div><div>{reply}</div></div>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ Please enter a health-related query to get a recommendation.")

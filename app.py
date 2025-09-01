import streamlit as st
from chatbot import get_chatbot_reply

st.title("🏥 Medical Chatbot")

user_input = st.text_input("Enter your health concern and hospital:")

if st.button("Get Recommendation"):
    if user_input.strip():
        reply = get_chatbot_reply(user_input, filepath="C:\\Users\\Sachi\\Downloads\\database_hosp.csv")
        st.markdown("### Chatbot Reply")
        st.write(reply)
    else:
        st.warning("Please enter a query.")

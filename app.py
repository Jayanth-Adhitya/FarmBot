from flask import Flask, render_template, request, jsonify
from textwrap import dedent
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from pathlib import Path
from datetime import datetime, timedelta
from phi.assistant import Assistant
from phi.llm.groq import Groq
import json
import requests
from phi.utils.log import logger
from tools import PyREPLTool, EmailTool, SchedulerTool
from phi.tools.shell import ShellTools
from apscheduler.schedulers.background import BackgroundScheduler
from phi.tools.duckduckgo import DuckDuckGo
import os 
from PIL import Image
import pytesseract
from groq import Groq as Groqq
from phi.tools.file import FileTools
from BrowserTool import BrowserAgent
import csv
import time
import queue
import av
import shelve
import streamlit as st
from datetime import datetime, timedelta

from streamlit_mic_recorder import mic_recorder

st.set_page_config(page_title="Farmer Assistant", page_icon="🌾", layout="wide")

st.sidebar.image("icon.png", width=300, caption="Farmer Assistant")
# Create the Assistant as in your main code
py_repl = PyREPLTool.PythonRepl()
browser = BrowserAgent()

# Assuming email configuration is loaded as in your original code
def read_email_config(filename: str):
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            return row

def query_browser_agent(query: str) -> str:
    try:
        response = requests.post('http://localhost:8080/query', json={'query': query})
        response.raise_for_status()
        return response.json()['result']
    except requests.RequestException as e:
        return f"Error querying BrowserAgent: {str(e)}"

email_config = read_email_config('tools/email_config.csv')
email_tools = EmailTool.EmailTools(
    receiver_email=email_config["receiver_email"],
    sender_email=email_config["sender_email"],
    sender_name=email_config["sender_name"],
    sender_passkey=email_config["sender_passkey"],
)

async def run_browser_query(query):
    return await browser.run(query)

instructions = ["""
Try to respond in the language the questions is from. But your tool calls and other background things must be in english even for websearch.
You are an Assistant designed to help Indian farmers with various queries they may have. Be polite and explain 
your answers in a way that they can understand, even if they have no educational background. Try to use the same language they use to respond.
You have access to several tools:

2. EmailTools: Use this to send or read emails.
3. ShellTools: Use this to execute commands on a Linux terminal. Be cautious and refuse any potentially dangerous commands.
4. schedulertools: Use this to schedule tasks for later or repeat them.
6. DuckDuckGo: Use this for web searches.

Always Try to use the websearch tool for any query to get an understanding about the question.
Do not use tools unless it is required for the query asked by the user.
NEVER run any potentially dangerous code or commands, and refuse such requests from users.

When scheduling tasks, always include a prompt describing what should be done when the task is executed.
"""]

# Create the Main Assistant
Main_Assistant = Assistant(
    name="Main Assistant",
    llm=Groq(model="llama3-70b-8192"),
    description="You are a helpful assistant designed to help Farmers with their Queries",
    tools=[ ShellTools(), FileTools(), email_tools,DuckDuckGo()],
    show_tool_calls=True,
    markdown=True,
    add_datetime_to_instructions=True,
    limit_tool_access=True,
    instructions=instructions
)

def load_chat_history():
    with shelve.open("chat_history") as db:
        return db.get("messages", [])
    
def extract_text_from_image(image):
    # Use Tesseract to extract text from the image
    extracted_text = pytesseract.image_to_string(image)
    
    # Instructions for the assistant
    instructions = """You have to create a json classifying Name, Address, Aadhar Number based on the input and save it as Profile.json"""
    
    # Initialize the Assistant with Groq model
    ExtractAssistant = Assistant(
        name="Main Assistant",
        llm=Groq(model="llama3-70b-8192"),
        description="You are a classification assistant. You will classify the given input string.",
        tools=[FileTools()],
        show_tool_calls=True,
        markdown=True,
        add_datetime_to_instructions=True,
        limit_tool_access=True,
        instructions=[instructions]
    )

    # Get the Assistant's response
    response = ExtractAssistant.run(extracted_text, stream=False)
    
    return extracted_text, response


# Save chat history to shelve file
def save_chat_history(messages):
    with shelve.open("chat_history") as db:
        db["messages"] = messages

# Audio processing
audio_queue = queue.Queue()

def audio_frames_callback(frame: av.AudioFrame):
    audio_queue.put(frame.to_ndarray().tobytes())

# Placeholder for audio transcription function
groq_client = Groqq()
def transcribe_audio(audio_data):
    filename = "temp_audio.m4a"
    with open(filename, "wb") as f:
        f.write(audio_data)

    with open(filename, "rb") as file:
        transcription = groq_client.audio.transcriptions.create(
            file=(filename, file.read()),
            model="whisper-large-v3",
            response_format="verbose_json",
        )

    os.remove(filename)  # Clean up the temporary file
    return transcription.text

# Main app
def main():
    # Profile button
    if st.button("Profile", key="profile_button"):
        st.session_state.page = "profile"
    
    # Page navigation
    if "page" not in st.session_state:
        st.session_state.page = "main"

    if st.session_state.page == "main":
        main_page()
    elif st.session_state.page == "profile":
        profile_page()

def main_page():
    st.title("FARMER ASSISTANT")

    USER_AVATAR = "👤"
    BOT_AVATAR = "🤖"

    # Initialize or load chat history
    if "messages" not in st.session_state:
        st.session_state.messages = load_chat_history()

    # Sidebar with a button to delete chat history
    with st.sidebar:
        if st.button("Delete Chat History"):
            st.session_state.messages = []
            save_chat_history([])

    # Display chat messages
    for message in st.session_state.messages:
        avatar = USER_AVATAR if message["role"] == "user" else BOT_AVATAR
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    st.write("Click to record your voice:")
    audio = mic_recorder(start_prompt="⏺", stop_prompt="⏹", key='recorder')

    if audio:
        transcript = transcribe_audio(audio['bytes'])
        st.session_state.messages.append({"role": "user", "content": transcript})
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(transcript)
        
        # Process the transcribed text with the Main Assistant
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            message_placeholder = st.empty()
            full_response = Main_Assistant.run(transcript, stream=False)
            message_placeholder.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Text input
    if prompt := st.chat_input("How can I help?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt)

        # Integrate your custom LLAMA assistant processing
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            message_placeholder = st.empty()
            full_response = Main_Assistant.run(prompt, stream=False)
            message_placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Save chat history after each interaction
    save_chat_history(st.session_state.messages)

def profile_page():
    st.title("Image to Text Transcription with Assistant")

    # Upload an image
    uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        # Display the uploaded image
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_column_width=True)

        # Extract and display text from the image
        extracted_text, response = extract_text_from_image(image)
        
        st.subheader("Extracted Text:")
        st.text(extracted_text)

        st.subheader("Assistant's Response:")
        st.write(response)

        # Option to save the extracted data as JSON
        if st.button("Save as Profile.json"):
            profile_data = {
                "extracted_text": extracted_text,
                "assistant_response": response
            }
            with open("Profile.json", "w") as json_file:
                json.dump(profile_data, json_file, indent=4)
            st.success("Profile.json saved successfully!")
            
    if st.button("Go to Main", key="main_button"):
        st.session_state.page = "main"

if __name__ == "__main__":
    main()
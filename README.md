# AI-IVR: AI-Driven Interactive Voice Response System

AI-IVR is an interactive voice response (IVR) system powered by an LLM. It enables real-time conversational interaction with users through voice calls. The system leverages the language model to process text outputs from Assembly AI's STT service to process user speech input, manage dynamic dialogues while retaining conversational memories, and optionally bring human agents into the conversation based on user input.

This project integrates Twilio’s APIs over websockets for call handling and media streaming, along with an OpenAI endpoint to provide a seamless user experience.

## Features

- **Real-time IVR system:** Supports interactive menus and gathers user input via DTMF (Dual-tone multi-frequency) and speech recognition.
- **AI-Powered Conversational Flow:** Integrates AI models for understanding user intent, enabling more natural and flexible conversations.
- **Human-Agent Handover:** Allows the system to loop in a human agent based on user input (e.g., pressing a digit to talk to an agent).
- **Twilio Media Streams:** Utilizes Twilio's media streaming to transmit real-time audio data for bi-directional conversations.
- **Text-to-Speech and Speech-to-Text:** Uses Assembly AI for TTS and transcription of user input.
- **Scalable and Modular Design:** Built with Flask and Python, making it easy to integrate with other services or expand with new features.

### Setup

1. Clone the repository:
   git clone https://github.com/viraj-singh1998/AIIVR.git
   cd AIIVR

2. Install dependencies:
   pip install -r requirements.txt

3. Set up environment variables for Twilio and Assembly AI:
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `ASSEMBLYAI_API_KEY`
   - `OPENAI_API_KEY`

4. Run the Flask application:
   python ivr_caller.py

5. The app will be available on `http://localhost:5000`. You can use ngrok or any similar service to expose your local server to the internet for testing with Twilio.

## Usage

### 1. Starting a Call

You can initiate a call to the IVR system by triggering the `make_call()` function in the code, or by setting up a Twilio webhook endpoint that points to your Flask app.

### 2. Interacting with the IVR Menu

Once the call is connected, the user can interact with the IVR menu by pressing digits on their phone (DTMF input) or by speaking, which will be transcribed by the AI model.

### 3. Human Agent Handover

If the user presses the designated key (e.g., "5"), the system will loop in a human agent to the call, allowing a seamless transition from AI to human support.

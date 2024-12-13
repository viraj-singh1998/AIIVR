from flask import Flask, request, render_template
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import os
import base64
import requests
import time
from dotenv import load_dotenv

from utils import transcribe

load_dotenv()

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

app = Flask(__name__)

SAVE_RECORDING = False

# Endpoint to make an outbound call
@app.route("/", methods=["GET"])
def make_call():
    from_number = '+18564153853'
    to_number = '+918433426632'
    
    # Create the call
    call = client.calls.create(
        to=to_number,
        from_=from_number,
        url="https://d83d-2401-4900-1c61-8ebd-45d4-c6f4-c7e6-e38c.ngrok-free.app/handle_voice"
    )
    return f"Calling {to_number}"

@app.route('/twiml', methods=['POST'])
def return_twiml():
    print("POST TwiML")
    return render_template('streams.xml')

# Endpoint to handle the call
@app.route("/handle_voice", methods=["POST"])
def handle_voice():
    response = VoiceResponse()
    response.say("Call created, recording now.")
    response.record(max_length=10, action="/handle_recording")
    return str(response)

# Handle the recording of the call
@app.route("/handle_recording", methods=["POST"])
def handle_recording():
    time.sleep(5)
    recording_url = request.form['RecordingUrl']
    credentials = f"{account_sid}:{auth_token}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {encoded_credentials}'
    }
    # Download the audio file to your server
    audio_filename = os.path.join("", f"recording_{request.form['CallSid']}.wav")
    print(f"Call recording saved to {recording_url}")
    audio_data = requests.get(recording_url + ".wav", headers=headers, stream=True).content
    if SAVE_RECORDING:
        with open(audio_filename, 'wb') as audio_file:
            audio_file.write(audio_data)
        print(f"Recording saved locally at: {audio_filename}")
    transcribed_turn = transcribe(audio_data)

    return "Recording has been saved!"

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, url_for, redirect, render_template
from flask_sock import Sock
from twilio.twiml.voice_response import VoiceResponse, Connect, Gather
from twilio.rest import Client
import os
import json
import base64
import requests
import time
from dotenv import load_dotenv

from utils import get_ngrok_url_and_port, transcribe_audio_bytes, text_to_mulaw_base64_media

load_dotenv()

# Setting up Twilio client
account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

MAX_DURATION = os.environ['MAX_DURATION']
NGROK_URL, HTTP_SERVER_PORT = get_ngrok_url_and_port()

print(NGROK_URL, HTTP_SERVER_PORT)

app = Flask(__name__)
sockets = Sock(app)

audio_buffer = b''

# Endpoint to make an outbound call
@app.route("/start/<patient_name>", methods=["GET"])
def make_call(patient_name):
    from_number = '+18564153853'
    to_number = 'your-number-here'
    print('making call')
    # Create the call
    call = client.calls.create(
        to=to_number,
        from_=from_number,
        url=f"https://{NGROK_URL}/twiml/{patient_name}"
    )
    return f"Calling {to_number}"

@app.route('/twiml/<patient_name>', methods=['POST'])
def return_twiml(patient_name):
    print("POST TwiML")
    return render_template('bidirectional_connect.xml', ngrok_url=NGROK_URL.replace('https://', ''), patient_name=patient_name)

@sockets.route('/<patient_name>')
def converse(ws, patient_name):
    print(f"Patient name: {patient_name}")
    global audio_buffer
    started = False
    send_response = True
    opening_audio_played = False
    print("Connection accepted")
    count, turn = 0, 0
    while True:
        if started and not opening_audio_played:
            client.calls(callSid).update(
                    twiml=f'<Response><Play digits="1w2w3" /></Response>'
                )
            opening_audio_played = True
            # mulaw_encoded = text_to_mulaw_base64_media(f"Hello! This call is regarding the insurance claim status of {patient_name}. What is the status of the claim? Press 1 to mark the end of your response. Press 9 to end the call.")
            mulaw_encoded = text_to_mulaw_base64_media(f"Yo yo yo, what's up {patient_name}?! Press 1 to mark the end of your response. Press 9 to end the call.")
            ws.send(json.dumps({
                'event': 'media',
                'streamSid': streamSid,
                'media': {
                    'payload': mulaw_encoded
                    }
                })
            )
            ws.send(json.dumps({
                'event': 'mark', 
                'streamSid': streamSid, 
                'mark': {
                    'name': 'mark message'
                    }
                })
            )
        message = ws.receive()
        if message is None:
            print("No message received...")
            continue
        data = json.loads(message)

        if data['event'] == "connected":
            print("Connected Message received", message)
        elif data['event'] == "start":
            print("Start Message received", message)
            streamSid = data['start']['streamSid']
            callSid = data['start']['callSid']
            started = True
        elif data['event'] == "mark":
            print("Mark Message received", message)
        elif data['event'] == "media":
            # Decode and store the audio payload (base64 encoded)
            audio_payload = base64.b64decode(data['media']['payload'])  # audio_payload: bytes
            audio_buffer += audio_payload  # Store audio in the buffer
            # print(f"Buffered {len(audio_payload)} bytes of audio data")
        elif data.get('event') == 'dtmf':
            digit = data['dtmf']['digit']
            print(f"DTMF digit received: {digit}")
            if digit == "1":
                # Process the audio buffer for transcription
                transcription = transcribe_audio_bytes(audio_buffer)
                print(f"Transcription: {transcription}")
                
                ## TODO: Call to LLM to handle response from insurance agent
                llm_response = "Okay, any aditional details?"

                # Reset the audio buffer after processing
                audio_buffer = b''
                
                mulaw_encoded = text_to_mulaw_base64_media(llm_response)
                ws.send(json.dumps({
                    'event': 'media',
                    'streamSid': streamSid,
                    'media': {
                        'payload': mulaw_encoded
                        }
                    })
                )
                # One turn (AI + user) is completed
                turn += 1
                ws.send(json.dumps({
                    'event': 'mark', 
                    'streamSid': streamSid, 
                    'mark': {
                        'name': f'ai response turn: {turn}'
                        }
                    })
                )
            elif digit == "9":
                ws.close()
        elif data.get('event') == 'stop':
            print("Stream stopped")
            break
        elif data['event'] == "closed":
            print("Closed Message received", message)
            break
        count += 1

    print("Connection closed. Received a total of {} messages".format(count))
    transcription = transcribe_audio_bytes(audio_buffer)
    print(f"Transcription: {transcription}")

if __name__ == '__main__':
    app.run(debug=True)
    # Open in any browser as:
    # http://127.0.0.1:5000/start/name_of_patient
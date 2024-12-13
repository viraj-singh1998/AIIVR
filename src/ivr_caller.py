from flask import Flask, redirect, url_for, request, jsonify
from flask_sock import Sock
from twilio.twiml.voice_response import VoiceResponse, Dial, Connect
from twilio.rest import Client
import json
import requests
from markupsafe import escape
import os
import numpy as np
import base64
import time
import threading
from dotenv import load_dotenv

from utils import *

load_dotenv()

# Setting up Twilio client
account_sid = os.environ["TWILIO_ACCOUNT_SID_1"]
auth_token = os.environ["TWILIO_AUTH_TOKEN_1"]
client = Client(account_sid, auth_token)

MAX_DURATION = os.environ['MAX_DURATION']
NGROK_URL, HTTP_SERVER_PORT = get_ngrok_url_and_port()
SAMPLE_RATE = 8000
BYTES_PER_SAMPLE = 2 
HTTP_SERVER_PORT = 5000

print(f"NGROK_URL: {NGROK_URL}, HTTP_SERVER_PORT: {HTTP_SERVER_PORT}")

app = Flask(__name__)
sock = Sock(app)
debug = False
turn = 0
processing_lock = threading.Lock()
callSid = None
chat_memory = []
patient_info = {}   # simulation for key-value DB

@app.route('/make_call/<patient_name>', methods=['GET'])
def make_call(patient_name):
    global callSid
    to_number = '+918433426632'
    from_number = '+18564153853'
    call = client.calls.create(
        to=to_number,
        from_=from_number,
        url=f"https://{NGROK_URL}/ivr_handler/{patient_name}"
    )
    return "Call started"

@app.route('/ivr_handler/<patient_name>', methods=['POST'])
def ivr_handler(patient_name):
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{NGROK_URL.replace('https://', '')}/stream/{patient_name}")
    response.append(connect)
    return str(response)

@sock.route('/stream/<patient_name>')
def ivr_incoming_stream(ws, patient_name):
    print(patient_name)
    global callSid
    global turn
    global chat_memory
    total_bytes = SAMPLE_RATE * BYTES_PER_SAMPLE * 3    # 4 seconds duration
    long_audio_buffer, short_audio_buffer = flush_buffers()
    print("Receiving")
    while True:
        message = ws.receive()
        if not message:
            continue
        data = json.loads(message)
        if data['event'] == "connected":
            print("Connected Message received", message)
            print('\n')
        elif data['event'] == "start":
            print("Start Message received", message)
            print('\n')
            streamSid = data['start']['streamSid']
            callSid = data['start']['callSid']
            started = True
        elif data['event'] == "mark":
            print("Mark Message received", message)
        elif data['event'] == "media":
            # Decode and store the audio payload (base64 encoded)
            audio_payload = base64.b64decode(data['media']['payload'])  # audio_payload: bytes
            short_audio_buffer.extend(audio_payload)    # Stores audio of past 3 seconds
            long_audio_buffer += audio_payload  # Store un-trimmed audio (till the variable is explicitly flushed)
            # Detecting silence (might have to run transcription for this)
            audio_np = np.frombuffer(bytes(short_audio_buffer), dtype=np.int16)
            rms = np.sqrt(np.mean(np.square(audio_np)))
            # if len(short_audio_buffer) == total_bytes and rms >= 99:  # Possible alternative?
            if len(long_audio_buffer) >= SAMPLE_RATE * BYTES_PER_SAMPLE * 10 and rms >= 99:
                response_processing_thread = threading.Thread(target=processing_logic, args=(long_audio_buffer, ws, patient_name))
                response_processing_thread.start()
                response_processing_thread.join()
                long_audio_buffer, short_audio_buffer = flush_buffers()                

        elif data.get('event') == 'stop':
            print("Stream stopped")
            break
        elif data['event'] == "closed":
            print("Closed Message received", message)
            break
    
    print("Connection closed.")

def processing_logic(audio_data, ws, patient_name):
    global processing_lock
    global chat_memory
    global turn
    global patient_info
    with processing_lock:
        print('\nReceived response. Transcribing and querying LLM')
        # is_processing.set()
        transcription = transcribe_audio_bytes(audio_data)
        print(f"Transcription for this turn: {transcription}")
        conversation = get_conversation(chat_memory, transcription)
        print(f"Conversation memory: {conversation}")
        try:
            patient_records = patient_info[patient_name]
        except Exception as e:
            print(f"{patient_name}'s information not present in records")
            patient_records = "NA"
        llm_response, prompt = query_llm(conversation=conversation, patient_info=patient_records)
        print(f"LLM response:\n{llm_response}\n")
        chat_memory.append({"ivr": transcription, "llm": llm_response})
        if debug:
            print("\n\n")
            print("*"*20)
            print("\n")
            print(f"Prompt:\n{prompt}")
            print("\n")
            print("*"*20)
            print("\n\n")

        if llm_response['end_call'] == 'true':
            if llm_response['speaking_to'] == "human":
                audio_length_seconds = 4
                send_dialogue(
                    dialogue="Thank you, and good day!", 
                    dialogue_duration=audio_length_seconds,
                    reconnect=False,
                    patient_name=patient_name
                    )
            print('Terminating call')
            ws.close()
            return

        if llm_response['speaking_to'] == "ivr":
            print(f"Sending digit response: {int(llm_response['digit'])}")
            # send_dmtf_response =  redirect(url_for(f'send_dtmf', digit=llm_response['digit']))
            send_digit(digit=llm_response['digit'], patient_name=patient_name)
        elif llm_response['speaking_to'] == "human":
            print(f"Sending dialogue response: {llm_response['dialogue']}")
            # mulaw_encoded, audio_length_seconds = text_to_mulaw_base64_media(llm_response['dialogue'])
            # print(f'audio_length_seconds = {audio_length_seconds}')
            audio_length_seconds = 10
            send_dialogue(
                dialogue=llm_response['dialogue'], 
                dialogue_duration=audio_length_seconds,
                reconnect=True,
                patient_name=patient_name
                )
        else:
            print('invalid LLM output')
            ws.close()

def send_digit(digit, patient_name):

    # Send DTMF tones (digits) and then reconnect to the WebSocket stream
    client.calls(callSid).update(
        twiml=f'''
        <Response>
            <Play digits="{digit}"/>
            <Connect>
                <Stream url="wss://{NGROK_URL.replace('https://', '')}/stream/{patient_name}"/>
            </Connect>
        </Response>
        '''
    )
    print(f"Digit {digit} sent and reconnected to stream.")

def send_dialogue(dialogue, dialogue_duration, reconnect, patient_name):

    # Send DTMF tones (digits) and then reconnect to the WebSocket stream
    if reconnect:
        client.calls(callSid).update(
            twiml=f'''
            <Response>
                <Say voice="alice" language="en-US">{dialogue}</Say>
                <Connect>
                    <Stream url="wss://{NGROK_URL.replace('https://', '')}/stream/{patient_name}"/>
                </Connect>
            </Response>
            '''
        )
    else:
        client.calls(callSid).update(
            twiml=f'''
            <Response>
                <Say voice="alice" language="en-US">{dialogue}</Say>
            </Response>
            '''
        )

    print(f"Dialogue sent and reconnected to stream.")

def load_patient_info():
    global patient_info
    records_dir = '/Users/viraj/Desktop/dev_stuff/ai_phone_operator/resources/records'
    for record_file in os.listdir(records_dir):
        if record_file.endswith("txt"):
            with open(os.path.join(records_dir, record_file), 'r', encoding='ascii', errors='replace') as f:
                patient_info[record_file.split('.')[0]] = f.read()
    print("Patient records loaded")

if __name__ == '__main__':
    load_patient_info()
    app.run(debug=True)

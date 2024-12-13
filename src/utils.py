import requests
import os
import assemblyai
from dotenv import load_dotenv
import wave
import audioop
import io
import json
import flask
import threading
import base64
from pydub import AudioSegment
from gtts import gTTS
import collections
import time
from openai import OpenAI

load_dotenv()

openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

def flush_buffers(total_bytes=48000):
    return b'', collections.deque(maxlen=total_bytes)

def twiml(resp):
    resp = flask.Response(str(resp))
    resp.headers['Content-Type'] = 'text/xml'
    return resp

def get_conversation(chat_memory, transcription):
    conversation = ""
    for turn in chat_memory:
        conversation += f'<start of turn>\nIVR/Human: {turn["ivr"]}\nLLM: {turn["llm"]}\n<end of turn>\n'
    conversation += f'<start of turn>\nIVR/Human: {transcription}\n'
    return conversation

def convert_messages_to_prompt(messages):
    prompt = ""
    for message in messages:
        if message["role"] == "system":
            prompt += f"System: {message['content']}\n"
        elif message["role"] == "user":
            prompt += f"User: {message['content']}\n"
        elif message["role"] == "assistant":
            prompt += f"Assistant: {message['content']}\n"
    return prompt.strip() 


def query_llm(conversation, patient_info):
    messages = messages=[
            {
                'role': 'system',
                'content': '''You are a hospital/medical clinic representative who is purposed with contacting insurance companies to inquire about a patient's claim status on the hospital's behalf. You will be directed to an IVR (Interactive Voice Response) machine and based on the IVR menu provided, you have to provide the appropriate digit response to the IVR machine to get the claim's status. If the IVR options don't provide information about the claim, select the option to be re-directed to a human agent/customer representative. When conversing with the human agent, reply with appropriate, concise and to-the-point dialogue responses. Use the IVR menu or the human's response along with the patient's information and these instructions to achieve the objective, Instructions:\n 1. Our main objective is to get the status of the claim. All responses should be made keeping that in mind.2.\n The status of the claim should be able to be classified as EITHER 'acccepted' OR 'rejected' The words used by the IVR/Human for 'accepted' and 'rejected' may be different. \n3. If the claim's status is not available through the IVR menu, the digit option to contact a human agent should be selected. \n4. After being connected to a human agent, you should START YOUR FIRST DIALOGUE by mentioning the patient's Name and their ID (like, "<Greeting>, I'm calling to inquire about the medical claim status for our patient, <patient Name>, ID: <patient ID>), along with the query. After the first dialogue turn, you need not mention the name and ID unless explicitly asked to. \n5. If the status has been confirmed either as 'accepted' or 'rejected', do not enquire further, signal to end the call. \n\n The output MUST ALWAYS be in the following JSON format: {"speaking_to": <str: "ivr" or "human" depending on whom we are currently replying to>, "digit": <str: ONLY if speaking_to == ivr ELSE ""; should be the appropriate digit response to be sent, should be a string eg. "1" or "2">, "dialogue": <str: ONLY if speaking_to == human ELSE ""; should be the appropriate and concise response to human>, "end_call": <str: "true" if the status has been confirmed as either accepted or rejected, "false" if it hasn't>, "comments": <str: reason behind choosing this digit or dialogue as response>}\n\nThere should be NOTHING ELSE in the output besides the JSON blob i.e. no backticks(`) or other characters.The patient's information:\n''' + f"{patient_info}\n"
            },
            {
                "role": "user",
                "content": "{conversation} \n\nIf we're speaking to the IVR, what should be the digit pressed here?\nIf we're speaking to a human, respond to the human appropriately to arrive at the objective of getting the status of the claim using the information given to you.".format(conversation=conversation)
            }
        ]
    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    text_response = completion.choices[0].message.content.strip()
    try:
        text_response = text_response[text_response.index('{'): text_response.index('}') + 1]
        json_response = json.loads(text_response)
    except Exception as e:
        print(e)
        print(text_response)
    return json_response, convert_messages_to_prompt(messages)


def get_ngrok_url_and_port():
    try:
        # Request the tunnel information from the ngrok API
        response = requests.get('http://localhost:4040/api/tunnels')
        data = response.json()
        
        for tunnel in data["tunnels"]:
            if tunnel["proto"] == "https":
                return tunnel["public_url"].split("//")[1], tunnel["config"]["addr"][-4:]
    except Exception as e:
        print(f"Error fetching ngrok URL: {e}")
        return None


def transcribe_audio_bytes(audio_data: bytes):
    assemblyai.settings.api_key = os.environ['ASSEMBLYAI_API_KEY']
    transcriber = assemblyai.Transcriber()
    file_name = "temp_recording.wav"
    channels = 1
    sample_width = 2
    frame_rate = 8000
    pcm_data = audioop.ulaw2lin(audio_data, sample_width)
    with wave.open(file_name, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(frame_rate)
        # Write the audio buffer to the file
        wf.writeframes(pcm_data)
    # with open("temp_recording.wav", 'xb') as audio_file:
    #     audio_file.write(audio_data)
    # transcript = transcriber.transcribe("https://storage.googleapis.com/aai-web-samples/news.mp4")
    max_retries = 2
    wait_time = 1
    for attempt in range(max_retries):
        try:
            transcript = transcriber.transcribe("temp_recording.wav")
            return transcript.text  # Return the successful transcription
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("Max retries reached. Unable to transcribe.")
                raise
    transcript = transcriber.transcribe("temp_recording.wav")
    return transcript.text


def text_to_mulaw_base64_media(text):

    tts = gTTS(text=text, lang='en', tld='us')
    mp3_filename = "output.mp3"
    tts.save(mp3_filename)

    # Convert MP3 to PCM (WAV)
    try:
        audio_segment = AudioSegment.from_file(mp3_filename, format="mp3")
    except Exception as e:
        print(f"Error converting MP3 to PCM: {e}")
        return None

    audio_length_seconds = len(audio_segment) / 1000.0  # AudioSegment length is in milliseconds

    # Resample to 8000 Hz
    audio_segment = audio_segment.set_frame_rate(8000)
    
    # Export PCM data to a buffer
    pcm_buffer = io.BytesIO()
    audio_segment.export(pcm_buffer, format="wav")
    pcm_buffer.seek(0)  # Reset buffer position
    pcm_data = pcm_buffer.read()

    # Convert PCM to Mu-Law (audio/x-mulaw)
    try:
        mulaw_data = audioop.lin2ulaw(pcm_data, 2)  # 2 is the sample width for 16-bit PCM
    except Exception as e:
        print(f"Error converting PCM to Mu-Law: {e}")
        return None

    # Step 5: Base64 encode the Mu-Law data
    encoded_data = base64.b64encode(mulaw_data).decode('utf-8')

    return encoded_data, audio_length_seconds

    pcm_data = text_to_speech_gtts(text)  # Get PCM audio data
    print(f"PCM data length: {len(pcm_data)} bytes")
    return convert_pcm_to_mulaw_and_encode(pcm_data)
    
    # ----------------------------------------------------------------------
    # return convert_pcm_to_mulaw_and_encode(text_to_speech_gtts(text))

# Function to convert PCM to Mu-Law and then to base64
def convert_pcm_to_mulaw_and_encode(audio_data):
    # Check if the audio_data is in the correct format
    if len(audio_data) == 0:
        print("Audio data is empty!")
        return None

    try:
        # Convert PCM (16-bit) to Mu-Law (8-bit)
        mulaw_data = audioop.lin2ulaw(audio_data, 2)  # 2 is the sample width for 16-bit PCM
        print(f"Mu-Law data length: {len(mulaw_data)} bytes")
        
        # Base64 encode the Mu-Law data
        encoded_data = base64.b64encode(mulaw_data)
        print(f"Encoded data length: {len(encoded_data)} characters")
        return encoded_data.decode('utf-8')  # Return as string for transmission
    except Exception as e:
        print(f"Error during conversion: {e}")
        return None

    # ----------------------------------------------------------------------
    # # Convert PCM (16-bit) to Mu-Law (8-bit)
    # mulaw_data = audioop.lin2ulaw(audio_data, 2)  # 2 is the sample width for 16-bit PCM
    # # Base64 encode the Mu-Law data
    # encoded_data = base64.b64encode(mulaw_data)
    # return encoded_data

def text_to_speech_gtts(text):
    tts = gTTS(text=text, lang='en')
    audio_buffer = io.BytesIO()
    tts.save(audio_buffer)
    audio_buffer.seek(0)

    # Read the raw PCM data from the MP3
    audio_segment = AudioSegment.from_file(audio_buffer, format="mp3")
    pcm_buffer = io.BytesIO()
    audio_segment.export(pcm_buffer, format="wav")
    pcm_buffer.seek(0)

    return pcm_buffer.read()  # Return raw PCM audio data

    # ----------------------------------------------------------------------
    # tts = gTTS(text=text, lang='en')
    # audio_buffer = io.BytesIO()
    # tts.save(audio_buffer)
    # audio_buffer.seek(0)
    # # return audio_buffer.read()  # Return raw PCM audio data
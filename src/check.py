# # # import io
# # # import base64
# # # import audioop
# # # from gtts import gTTS
# # # from pydub import AudioSegment

# # # def text_to_nulaw_base64_media(text):
# # #     # Step 1: Generate TTS audio and save to file
# # #     tts = gTTS(text=text, lang='en')
# # #     mp3_filename = "output.mp3"
# # #     tts.save(mp3_filename)

# # #     # Step 2: Convert MP3 to PCM (WAV)
# # #     try:
# # #         audio_segment = AudioSegment.from_file(mp3_filename, format="mp3")
# # #     except Exception as e:
# # #         print(f"Error converting MP3 to PCM: {e}")
# # #         return None

# # #     # Step 3: Export PCM data to a buffer
# # #     pcm_buffer = io.BytesIO()
# # #     audio_segment.export(pcm_buffer, format="wav")
# # #     pcm_buffer.seek(0)  # Reset buffer position
# # #     pcm_data = pcm_buffer.read()

# # #     # Step 4: Convert PCM to Mu-Law (audio/x-mulaw)
# # #     try:
# # #         mulaw_data = audioop.lin2ulaw(pcm_data, 2)  # 2 is the sample width for 16-bit PCM
# # #     except Exception as e:
# # #         print(f"Error converting PCM to Mu-Law: {e}")
# # #         return None

# # #     # Step 5: Base64 encode the Mu-Law data
# # #     encoded_data = base64.b64encode(mulaw_data).decode('utf-8')

# # #     return encoded_data

# # # # Example usage
# # # text = "Hello, this is a test."
# # # encoded_audio = text_to_nulaw_base64_media(text)
# # # if encoded_audio:
# # #     print(f"Encoded audio data: {encoded_audio[:50]}...")  # Print the first 50 characters
# # # else:
# # #     print("Failed to generate audio.")

# # import requests
# # import os

# # def get_ngrok_url_and_port():
# #     try:
# #         # Request the tunnel information from the ngrok API
# #         response = requests.get('http://localhost:4040/api/tunnels')
# #         data = response.json()
        
# #         for tunnel in data["tunnels"]:
# #             if tunnel["proto"] == "https":
# #                 return tunnel["public_url"].split("//")[1], tunnel["config"]["addr"][-4:]
# #     except Exception as e:
# #         print(f"Error fetching ngrok URL: {e}")
# #         return None
    
# # print(get_ngrok_url_and_port())

# import os
# from openai import OpenAI
# from dotenv import load_dotenv

# load_dotenv()

# openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

# def query_llm(ivr_transcription):

#     completion = openai_client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             # {"role": "system", "content": "You are a hospital/medical clinic representative who is purposed with contacting insurance companies to inquire about the status of the insurance claim and any comments pertaining to the claim's acceptance/rejection. Be concise, and patient and to the point."},
#             {
#                 'role': 'system',
#                 'content': '''You are a hospital/medical clinic representative who is purposed with contacting insurance companies to inquire about the claim statuses. You will be directed to an IVR (Interactive Voice Response) machine and based on the IVR menu provided, you have to provide the appropriate digit response on the basis of the IVR menu and these instructions:\n 1. Our main objective is to get the status of the claim. All responses should be made keeping that in mind.2.\n The status of the claim should be able to be classified as EITHER 'acccepted' OR 'rejected'. \n3. If the claim's status is not available through the IVR menu, the digit option to contact a human agent should be selected.\n\n The output MUST ALWAYS be in the following JSON format: {"digit": <int: appropriate digit response>, "speaking_to": <str: either of 'ivr' or 'human' depending on who is intended be on the other side of the call following our current response>, "comments": <str: reason behind choosing this digit as response>} \n\n
#                 There should be NOTHING ELSE in the output besides the JSON blob i.e. no backticks(`) or other characters.'''
#             },
#             {
#                 "role": "user",
#                 "content": "IVR Menu: {ivr_transcription}\n\n What should be the digit pressed here?".format(ivr_transcription=ivr_transcription)
#             }
#         ]
#     )
#     text_response = completion.choices[0].message.content.strip()
#     try:
#         text_response = text_response[text_response.index('{'): text_response.index('}') + 1]
#     except Exception as e:
#         print(e)
#     return text_response

# # output = query_llm("Hello. Thanks for calling Moore Medical. Press 1 if you wish to submit a claim. Press 2 to inquire about our services. Press 3 for speaking to our customer care. Press 4 to hear the menu again.")
# # print(output, )

import assemblyai
from dotenv import load_dotenv
load_dotenv()
import os
import time

def transcribe_audio_bytes(audio_file):
    assemblyai.settings.api_key = os.environ['ASSEMBLYAI_API_KEY']
    transcriber = assemblyai.Transcriber()
    max_retries = 2
    wait_time = 1
    for attempt in range(max_retries):
        try:
            transcript = transcriber.transcribe(audio_file)
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

text = transcribe_audio_bytes('/Users/viraj/Desktop/dev_stuff/ai_phone_operator/resources/recordings/recording_CA4109411393025461f796bc24f07c4605.wav')
print(text)
from flask import (
    Flask,
    render_template,
    redirect,
    request,
    session,
    url_for,
)
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import os
from dotenv import load_dotenv
from utils import *

load_dotenv()

# Setting up Twilio client
account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

MAX_DURATION = os.environ['MAX_DURATION']
NGROK_URL, HTTP_SERVER_PORT = get_ngrok_url_and_port()
HTTP_SERVER_PORT = 5001
PETER_PHONE = "your-number-here"

print(f"NGROK_URL: {NGROK_URL}, HTTP_SERVER_PORT: {HTTP_SERVER_PORT}")

app = Flask(__name__)

@app.route('/', methods=['POST'])
@app.route('/ivr/welcome', methods=['POST'])
def welcome():
    response = VoiceResponse()
    with response.gather(
        num_digits=1, action=url_for('menu'), method="POST"
    ) as g:
        g.say(message="Thanks for calling the Pawtucket Brewery!" + 
              "Please press 1 for Peter's address." + 
              "Press 2 to directly speak to the fat bastard", 
              loop=3
              )
    return twiml(response)


@app.route('/ivr/menu', methods=['POST'])
def menu():
    print("-"*40)
    print(request)
    print("-"*40)
    selected_option = request.form['Digits']
    option_actions = {'1': _give_address,
                      '2': _add_Peter}

    if option_actions.has_key(selected_option):
        response = VoiceResponse()
        option_actions[selected_option](response)
        return twiml(response)

    return _redirect_welcome()


@app.route('/ivr/call_agent', methods=['POST'])
def _add_Peter():
    selected_option = request.form['Digits']
    # option_actions = {'2': "+19295566487",
    #                   '3': "+17262043675",
    #                   "4": "+16513582243"}

    response = VoiceResponse()
    response.dial(PETER_PHONE)
    return twiml(response)



# private methods

def _give_address(response):
    response.say("31 Spooner Street, Quahog, Rhode Island",
                 voice="Polly.Amy", language="en-GB")

    response.say("By the way, our customer support specialist, Opie, is very angry you're going over his head.")

    response.hangup()
    return response


def _add_Peter(response):
    with response.gather(
        numDigits=1, action=url_for('planets'), method="POST"
    ) as g:
        g.say("",
              voice="Polly.Amy", language="en-GB", loop=3)

    return response


def _redirect_welcome():
    response = VoiceResponse()
    response.say("Returning to the main menu", voice="Polly.Amy", language="en-GB")
    response.redirect(url_for('welcome'))

    return twiml(response)

if __name__ == '__main__':
    app.run(port=5001, debug=True)
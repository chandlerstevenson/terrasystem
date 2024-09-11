#!/usr/bin/env python3.11

from flask import Flask, request, jsonify, abort
from openai import OpenAI
from dotenv import load_dotenv
import os
from flask_cors import CORS, cross_origin  # Import CORS
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import re
from py_smsify import SmsMessage

def utf8_to_gsm7(text: str):
    return SmsMessage(text).encoded_text

# Load environment variables
load_dotenv()
account_sid = 'AC6aeaaea30e46f0ecb32fe657ca79d1d8'
auth_token = '992e476301e544888716a8b67a43bc7f'
openai_api_key = "sk-proj-V12JWzAwBr3KgfeSbyUKT3BlbkFJL3uRvnJmuLshRRk4jnaS"

twilio_client = Client(account_sid, auth_token)
client = OpenAI(api_key=openai_api_key)

CHANDLER_NUMBER = "4047133808"

app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

def query_str(msg: str) -> str:
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a personal gardening tutor..."},
            {"role": "user", "content": msg}
        ]
    )
    return completion.choices[0].message.content

def send_response_str(msg: str) -> str:
    resp = MessagingResponse()
    resp.message(msg)
    return str(resp)

@app.route('/submit', methods=['GET', 'POST', 'OPTIONS'])
@cross_origin()
def submit():
    try:
        content = request.json
        msg = content["query"]
        reply = query_str(msg)

        print(f"Sending message: {reply}")  # Debugging statement
        message = twilio_client.messages.create(
            from_='+18889846584',
            body=reply,
            to=CHANDLER_NUMBER
        )

        print(f"Sent message to {CHANDLER_NUMBER} with id {message.sid}")  # Debugging statement

        response_data = {'reply': reply}

        # Return the JSON response
        return jsonify(response_data)

    except Exception as e:
        print(f"Error: {e}")  # Debugging statement
        abort(500, description="Internal Server Error")

@app.route("/", methods=['GET', 'POST'])
def sms_reply():
    """Respond to incoming calls with a MMS message."""
    print(f"Received text!")  # Debugging statement
    body = request.values.get('Body', None)
    print(f"Body: {body}")  # Debugging statement

    reply = utf8_to_gsm7(query_str(body))

    resp = MessagingResponse()
    resp.message(reply)

    print(f"Sending response: {reply}")  # Debugging statement
    return str(resp)

@app.route('/test', methods=['GET', 'POST', 'OPTIONS'])
def test_route():
    return jsonify({"message": "Test successful"}), 200

if __name__ == '__main__':
    app.run(port=8000, debug=True)

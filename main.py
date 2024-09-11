from flask import Flask, request, jsonify, abort
from typing import *
from dataclasses import dataclass, asdict
from openai import OpenAI
from dotenv import load_dotenv
import os
from flask_cors import CORS, cross_origin
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import re
import time
from py_smsify import SmsMessage
import mysql.connector
from datetime import datetime
import xml.sax.saxutils as saxutils
import requests
from flask import Flask, request, jsonify, abort
from typing import Optional
from dotenv import load_dotenv
import os
from flask_cors import CORS, cross_origin
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import re
from datetime import datetime
import mysql.connector
from openai import OpenAI
import xml.sax.saxutils as saxutils
import requests
from werkzeug.utils import secure_filename

# Load environment variables from .env file
load_dotenv()

# Database connection
def create_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

def create_chat_table(connection):
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(255),
            user_message TEXT,
            assistant_response TEXT,
            user_message_time TIMESTAMP,
            assistant_response_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            location VARCHAR(255)
        )
    """)
    connection.commit()

connection = create_connection()
create_chat_table(connection)

# Insert chat log into the database
def insert_chat_log(connection, user_id, user_message, assistant_response, user_message_time, location=None):
    cursor = connection.cursor()
    query = """
        INSERT INTO chat_logs (user_id, user_message, assistant_response, user_message_time, location) 
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(query, (user_id, user_message, assistant_response, user_message_time, location))
    connection.commit()

# Retrieve chat history for the user
def get_chat_history(connection, user_id, limit=30):
    cursor = connection.cursor()
    query = """
        SELECT user_message, assistant_response, user_message_time, assistant_response_time, location 
        FROM chat_logs 
        WHERE user_id = %s 
        ORDER BY user_message_time DESC 
        LIMIT %s
    """
    cursor.execute(query, (user_id, limit))
    return cursor.fetchall()[::-1]  # Reverse the order to maintain chronological sequence

# Delete chat history for the user
def delete_chat_history(connection, user_id):
    cursor = connection.cursor()
    query = """
        DELETE FROM chat_logs WHERE user_id = %s
    """
    cursor.execute(query, (user_id,))
    connection.commit()

# Flask app setup
def utf8_to_gsm7(text: str):
    return SmsMessage(text).encoded_text

# Twilio configuration
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = Client(account_sid, auth_token)

app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['UPLOAD_FOLDER'] = 'uploads/'  # Folder to save uploaded images

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
ASSISTANT_ID = os.getenv('ASSISTANT_ID')

def sanitize_phone_number(phone_number: str) -> str:
    return re.sub(r'^\+1', '', phone_number)

def sanitize_response_text(text: str) -> str:
    return saxutils.escape(text)

def sanitize_message_content(content: str) -> str:
    # Remove non-printable characters
    content = re.sub(r'[^\x20-\x7E]', '', content)
    # Escape XML entities
    content = saxutils.escape(content)
    return content

def extract_location(message: str) -> Optional[str]:
    # Regex to capture US zip codes (5 digits)
    zip_code_match = re.search(r"\b\d{5}\b", message)
    if zip_code_match:
        return zip_code_match.group(0).strip()
    return None

def convert_zip_to_location(zip_code: str) -> str:
    zip_code_mapping = {
        "00100": "Nairobi, Kenya",
        "80100": "Mombasa, Kenya",
        "40100": "Kisumu, Kenya",
        "20100": "Nakuru, Kenya",
        "30100": "Eldoret, Kenya",
        "01000": "Thika, Kenya",
        "10100": "Nyeri, Kenya",
        "20117": "Naivasha, Kenya",
        "90100": "Machakos, Kenya",
        "50100": "Kakamega, Kenya",
    }
    return zip_code_mapping.get(zip_code, "Unknown Location")

def get_weather_data(location: str) -> dict:
    api_key = os.getenv('WEATHER_API_KEY')
    base_url = os.getenv('WEATHER_API_URL')
    params = {
        'q': location + ',KE',  # Append ,KE to specify Kenya
        'appid': api_key,
        'units': 'metric'
    }
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching weather data: {response.status_code}")
        return {}

def query_str(user_id: str, msg: str, user_message_time: datetime, location=None) -> str:
    if location: 
        city_country = convert_zip_to_location(location)
        # Prepend the location information to the user's message
        weather = get_weather_data(city_country)
        location_info = f"This user lives at location with zipcode {location}. If they ask about weather, their weather is: {weather}. "
        full_message = f"{location_info}\n\n{msg}"
    else:
        full_message = msg

    messages = [{"role": "user", "content": full_message}]

    thread = client.beta.threads.create(messages=messages)
    run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=ASSISTANT_ID)
    
    while run.status != "completed":
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        time.sleep(1)

    message_response = client.beta.threads.messages.list(thread_id=thread.id)
    messages = message_response.data
    latest_message = messages[0]
    
    assistant_response = latest_message.content[0].text.value
    assistant_response_time = datetime.now()

    if location:
        insert_chat_log(connection, user_id, msg, assistant_response, user_message_time, location)
    else:
        last_location = get_last_location(connection, user_id)
        insert_chat_log(connection, user_id, msg, assistant_response, user_message_time, last_location)
    
    return assistant_response

def send_response_str(msg: str) -> str:
    resp = MessagingResponse()
    resp_msg = resp.message(msg)
    return str(resp)

@app.route('/submit', methods=['POST'])
@cross_origin()
def submit():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # Process the file (e.g., send it to a model for analysis)
            # For now, we just acknowledge the file upload
            return jsonify({"message": "File uploaded successfully", "filename": filename}), 200
        
        content = request.form.to_dict()
        msg = content["query"]
        user_id = content.get("user_id", "default_user")
        location = extract_location(msg) or get_last_location(connection, user_id)
        user_message_time = datetime.now()

        # Sanitize the message content
        sanitized_msg = sanitize_message_content(msg)

        # Generate the assistant's response
        reply = query_str(user_id, sanitized_msg, user_message_time, location)

        # Sanitize the reply
        sanitized_reply = sanitize_message_content(reply)

        message = twilio_client.messages.create(
            from_='+3475156422',
            body=sanitized_reply,
            to=sanitize_phone_number(user_id)  # Sanitize the phone number
        )

        print(f"Sent message to {user_id} with id {message.sid}")

        response_data = {'reply': sanitized_reply}

        return jsonify(response_data)

    except Exception as e:
        print(f"Error: {e}")
        abort(500, description="Internal Server Error")

def sanitize(s: str):
    return re.sub(r'[^\w\s\n]', '', s)

@app.route("/", methods=['GET', 'POST'])
def sms_reply():
    body = request.values.get('Body', None)
    user_id = request.values.get('From', 'default_user')
    user_message_time = datetime.now()
    
    if not body:
        return str(send_response_str("Sorry, I didn't receive any message content."))

    if body.strip().upper() == "DELETECHATHISTORY":
        delete_chat_history(connection, user_id)
        return str(send_response_str("Your chat history has been deleted."))

    location = extract_location(body) or get_last_location(connection, user_id)

    sanitized_body = sanitize_message_content(body)

    reply = sanitize_response_text(query_str(user_id, sanitized_body, user_message_time, location))

    resp = MessagingResponse()
    resp.message(reply)

    return str(resp)

@app.route('/chat_history/<user_id>', methods=['GET'])
@cross_origin()
def chat_history(user_id):
    try:
        connection = create_connection()
        chat_logs = get_chat_history(connection, user_id)
        formatted_logs = [{"user_message": log[0], "assistant_response": log[1], "user_message_time": log[2], "assistant_response_time": log[3], "location": log[4]} for log in chat_logs]
        return jsonify(formatted_logs), 200
    except Exception as e:
        print(f"Error: {e}")
        abort(500, description="Internal Server Error")

def get_last_location(connection, user_id):
    cursor = connection.cursor()
    query = """
        SELECT location FROM chat_logs WHERE user_id = %s ORDER BY user_message_time DESC LIMIT 1
    """
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)), debug=True)

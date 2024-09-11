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
import logging

# Load environment variables from .env file
load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.INFO)

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
            assistant_response_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.commit()

connection = create_connection()
create_chat_table(connection)

# Insert chat log into the database
def insert_chat_log(connection, user_id, user_message, assistant_response, user_message_time):
    cursor = connection.cursor()
    query = """
        INSERT INTO chat_logs (user_id, user_message, assistant_response, user_message_time) 
        VALUES (%s, %s, %s, %s)
    """
    cursor.execute(query, (user_id, user_message, assistant_response, user_message_time))
    connection.commit()

# Retrieve chat history for the user
def get_chat_history(connection, user_id):
    cursor = connection.cursor()
    query = "SELECT user_message, assistant_response, user_message_time, assistant_response_time FROM chat_logs WHERE user_id = %s ORDER BY user_message_time"
    cursor.execute(query, (user_id,))
    return cursor.fetchall()

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

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
ASSISTANT_ID = os.getenv('ASSISTANT_ID')

def query_str(user_id: str, msg: str, user_message_time: datetime) -> str:
    """
    Generates string response to string message using assistant and manages user sessions
    """
    chat_history = get_chat_history(connection, user_id)
    messages = [{"role": "user", "content": user_message} for user_message, _, _, _ in chat_history]
    messages.append({"role": "user", "content": msg})

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

    insert_chat_log(connection, user_id, msg, assistant_response, user_message_time)
    
    return assistant_response

def send_response_str(msg: str) -> str:
    resp = MessagingResponse()
    resp_msg = resp.message(msg)
    return str(resp)

@app.route('/create_table', methods=['POST'])
@cross_origin()
def create_table():
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sample (
            id INT AUTO_INCREMENT PRIMARY KEY, 
            name VARCHAR(255), 
            age INT
        )
    """)
    connection.commit()
    cursor.close()
    connection.close()
    return jsonify({"message": "Table created successfully"}), 201

@app.route('/insert_record', methods=['POST'])
@cross_origin()
def insert_record():
    connection = create_connection()
    data = request.json
    name = data['name']
    age = data['age']
    cursor = connection.cursor()
    query = "INSERT INTO sample (name, age) VALUES (%s, %s)"
    cursor.execute(query, (name, age))
    connection.commit()
    cursor.close()
    connection.close()
    return jsonify({"message": "Record inserted successfully"}), 201

@app.route('/select_records', methods=['GET'])
@cross_origin()
def select_records():
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM sample")
    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    return jsonify(rows), 200

@app.route('/update_record', methods=['PUT'])
@cross_origin()
def update_record():
    connection = create_connection()
    data = request.json
    id = data['id']
    name = data['name']
    age = data['age']
    cursor = connection.cursor()
    query = "UPDATE sample SET name = %s, age = %s WHERE id = %s"
    cursor.execute(query, (name, age, id))
    connection.commit()
    cursor.close()
    connection.close()
    return jsonify({"message": "Record updated successfully"}), 200

@app.route('/delete_record', methods=['DELETE'])
@cross_origin()
def delete_record():
    connection = create_connection()
    data = request.json
    id = data['id']
    cursor = connection.cursor()
    query = "DELETE FROM sample WHERE id = %s"
    cursor.execute(query, (id,))
    connection.commit()
    cursor.close()
    connection.close()
    return jsonify({"message": "Record deleted successfully"}), 200

@app.route('/insert_multiple_records', methods=['POST'])
@cross_origin()
def insert_multiple_records():
    connection = create_connection()
    data = request.json
    records = data['records']
    cursor = connection.cursor()
    query = "INSERT INTO sample (name, age) VALUES (%s, %s)"
    cursor.executemany(query, records)
    connection.commit()
    cursor.close()
    connection.close()
    return jsonify({"message": "Multiple records inserted successfully"}), 201

@app.route('/submit', methods=['POST'])
@cross_origin()
def submit():
    try:
        content = request.json
        msg = content["query"]
        user_id = content.get("user_id", "default_user")
        user_message_time = datetime.now()
        reply = query_str(user_id, msg, user_message_time)

        logging.info(f"Sending message to {user_id}")

        message = twilio_client.messages.create(
            from_='+18889846584',
            body=reply,
            to=user_id  # Send the response to the user_id, which is the phone number
        )

        logging.info(f"Sent message to {user_id} with id {message.sid}")

        response_data = {'reply': reply}

        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Error: {e}")
        abort(500, description="Internal Server Error")

def sanitize(s: str):
    return re.sub(r'[^\w\s\n]', '', s)

@app.route("/", methods=['GET', 'POST'])
def sms_reply():
    logging.info("Received text!")
    body = request.values.get('Body', None)
    user_id = request.values.get('From', 'default_user')
    user_message_time = datetime.now()
    logging.info(f"Body: {body}")

    reply = utf8_to_gsm7(query_str(user_id, body, user_message_time))

    resp = MessagingResponse()
    logging.info(f"Sending response: {reply}")
    resp.message(reply)
    logging.info("Sent response")

    return str(resp)

@app.route('/test', methods=['GET', 'POST', 'OPTIONS'])
def test_route():
    return jsonify({"message": "Test successful"}), 200

@app.route('/chat_history/<user_id>', methods=['GET'])
@cross_origin()
def chat_history(user_id):
    try:
        connection = create_connection()
        chat_logs = get_chat_history(connection, user_id)
        formatted_logs = [{"user_message": log[0], "assistant_response": log[1], "user_message_time": log[2], "assistant_response_time": log[3]} for log in chat_logs]
        return jsonify(formatted_logs), 200
    except Exception as e:
        logging.error(f"Error: {e}")
        abort(500, description="Internal Server Error")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8000)), debug=True)

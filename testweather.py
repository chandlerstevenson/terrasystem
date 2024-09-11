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

# Load environment variables from .env file
load_dotenv()

# class ProcessWeatherData(): 
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

location = convert_zip_to_location('00100')


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


import requests

def get_soil_data(lat: float, lon: float) -> dict:
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lon=37&lat=37&property=bdod&property=clay&property=nitrogen&property=phh2o&property=sand&depth=0-5cm&depth=0-30cm&depth=5-15cm&depth=15-30cm&value=mean&value=uncertainty"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching soil data: {response.status_code}")
        return {}



lon = get_weather_data(location).get('coord').get('lon')
lat = get_weather_data(location).get('coord').get('lat') 

soil_data = get_soil_data(lon, lat)

print(soil_data)
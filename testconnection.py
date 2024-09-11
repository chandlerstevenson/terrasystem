import mysql.connector
from mysql.connector import Error

def create_connection():
    try:
        connection = mysql.connector.connect(
            host="terratrendtesting.cpgg8wkeujnk.us-east-2.rds.amazonaws.com",
            user="terratrend",
            password="terratrend24",
            database="terratrendtesting"
        )
        if connection.is_connected():
            print("Connected to MySQL database")
        return connection
    except Error as e:
        print(f"Error: {e}")
        return None

connection = create_connection()
if connection:
    connection.close()

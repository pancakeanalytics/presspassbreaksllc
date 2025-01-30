import streamlit as st
from google.cloud import storage
import psycopg2
import pandas as pd
import random
import string
import os

# Google Cloud SQL Configuration for PostgreSQL
DB_USER = os.getenv('DB_USER', 'pancakes_dev')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'Spiderman1001!')
DB_NAME = os.getenv('DB_NAME', 'presspassbreaks')
DB_HOST = "34.171.57.16"
DB_PORT = 5432  # PostgreSQL default port

# Database Configuration
DB_CONFIG = {
    'dbname': DB_NAME,
    'user': DB_USER,
    'password': DB_PASSWORD,
    'host': DB_HOST,
    'port': DB_PORT
}

# Google Cloud Storage Configuration
BUCKET_NAME = 'ppbdb'

# Function to Get Database Connection with Error Handling
def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        st.error(f"❌ Database connection error: {e}")
        return None

# Helper function to generate a unique certificate number
def generate_unique_cert_number(cursor):
    while True:
        cert_number = ''.join(random.choices(string.digits, k=10))
        cursor.execute("SELECT COUNT(*) FROM cards WHERE certnumber = %s", (cert_number,))
        if cursor.fetchone()[0] == 0:
            return cert_number

# Helper function to upload an image to Google Cloud Storage
def upload_image_to_gcs(image_file, cert_number):
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"cards/{cert_number}.jpg")
        blob.upload_from_file(image_file, content_type='image/jpeg')
        return blob.public_url
    except Exception as e:
        st.error(f"❌ Error uploading image to GCS: {e}")
        return None

# Streamlit App
st.title("Card Inventory Management Tool")
st.subheader("By Pancake Analytics LLC")

# Create only the "Individual Entry" tab
tab = st.tabs(["Individual Entry"])[0]  # ✅ Fixes the syntax error

with tab:
    st.subheader("Add a Single Card")
    client_name = st.text_input("Client Name")
    entrydate = st.date_input("Entry Date")
    sport = st.text_input("Sport")
    sport_grader = st.text_input("Sport Grader")
    grade = st.text_input("Grade")
    player = st.text_input("Player")
    set_year = st.number_input("Set Year", min_value=0, step=1)
    set_name = st.text_input("Set Name")
    parallel = st.text_input("Parallel")
    auto = st.selectbox("Auto", ["Yes", "No"])
    jersey = st.selectbox("Jersey", ["Yes", "No"])
    card_number = st.text_input("Card Number (required)")
    cert_number = st.text_input("CertNumber (leave blank to auto-generate)")
    image_file = st.file_uploader("Upload JPG Image", type=["jpg"])

    if st.button("Submit"):
        if not all([client_name, sport, sport_grader, grade, player, set_year, set_name, parallel, auto, jersey, card_number, image_file]):
            st.error("❌ Please fill in all fields.")
        else:
            conn = get_db_connection()
            if conn is None:
                st.error("❌ Failed to connect to the database.")
                st.stop()

            cursor = conn.cursor()

            try:
                if not cert_number:
                    cert_number = generate_unique_cert_number(cursor)
                else:
                    cursor.execute("SELECT COUNT(*) FROM cards WHERE certnumber = %s", (cert_number,))
                    if cursor.fetchone()[0] > 0:
                        st.error("❌ CertNumber already exists.")
                        st.stop()

                image_url = upload_image_to_gcs(image_file, cert_number)

                insert_query = """
                    INSERT INTO cards (Image, ClientName, EntryDate, Sport, SportGrader, Grade, Player, SetYear, 
                                       SetName, Parallel, CertNumber, CardNumber, Auto, Jersey)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (
                    image_url, client_name, entrydate, sport, sport_grader, grade, player,
                    set_year, set_name, parallel, cert_number, card_number, auto, jersey
                ))
                conn.commit()
                st.success("✅ Card added successfully!")
                st.write(f"CertNumber: {cert_number}")
            except Exception as e:
                st.error(f"❌ Error adding card: {e}")
            finally:
                cursor.close()
                conn.close()

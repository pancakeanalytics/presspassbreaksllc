import streamlit as st
from google.cloud import storage
import psycopg2
import pandas as pd
import plotly.express as px
import random
import string
import os

# Google Cloud SQL Configuration for PostgreSQL
DB_USER = os.getenv('DB_USER', 'pancakes_dev')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'Spiderman1001!')
DB_NAME = os.getenv('DB_NAME', 'pancakes')
DB_CONNECTION_NAME = os.getenv('DB_CONNECTION_NAME', 'pancake-analytics-llc:us-central1:pancakes')

# ✅ Define Cloud SQL Unix Socket Host (NO IP NEEDED)
DB_HOST = f"/cloudsql/{DB_CONNECTION_NAME}"
DB_PORT = 5432  # PostgreSQL default port

# ✅ Corrected Database Configuration
DB_CONFIG = {
    'dbname': DB_NAME,
    'user': DB_USER,
    'password': DB_PASSWORD,
    'host': DB_HOST,
    'port': DB_PORT  # ✅ Port should be an integer, not a string
}

# ✅ Google Cloud Storage Configuration
BUCKET_NAME = 'ppbdb'

# ✅ Function to Get Database Connection
def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)  # ✅ Uses fixed config
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None  # Avoid crashing if connection fails

# Helper function to generate a unique certificate number
def generate_unique_cert_number(cursor):
    while True:
        cert_number = ''.join(random.choices(string.digits, k=10))
        cursor.execute("SELECT COUNT(*) FROM cards WHERE certnumber = %s", (cert_number,))
        if cursor.fetchone()[0] == 0:
            return cert_number

# Helper function to upload an image to Google Cloud Storage
def upload_image_to_gcs(image_file, cert_number):
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"cards/{cert_number}.jpg")
    blob.upload_from_file(image_file, content_type='image/jpeg')
    return blob.public_url

# Helper function to fetch data from the database
def fetch_data(query):
    try:
        conn = get_db_connection()
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"An error occurred while fetching data: {e}")
        return None

# Helper function to process rows for CSV uploads
def process_csv_row(row, cursor):
    cert_number = row.get('CertNumber', '').strip()
    if not cert_number:
        cert_number = generate_unique_cert_number(cursor)
    else:
        cursor.execute("SELECT COUNT(*) FROM cards WHERE certnumber = %s", (cert_number,))
        if cursor.fetchone()[0] > 0:
            raise ValueError(f"CertNumber '{cert_number}' already exists.")
    
    card_number = row.get('Card Number', '').strip()
    if not card_number:
        raise ValueError("Card Number is required.")

    image_url = row.get('Image', 'https://via.placeholder.com/150')
    
    return (
        image_url,
        row['Client Name'],
        row['Entry Date'],
        row['Sport'],
        row['Sport Grader'],
        row['Grade'],
        row['Player'],
        row['Set Year'],
        row['Set Name'],
        row['Parallel'],
        cert_number,
        card_number,
        row['Auto'],
        row['Jersey']
    )

# Streamlit App
st.title("Card Inventory Management Tool")
st.subheader("By Pancake Analytics LLC")

tabs = st.tabs(["Individual Entry", "Bulk CSV Upload", "Reports"])

# Individual Entry Tab
with tabs[0]:
    st.subheader("Add a Single Card")
    client_name = st.text_input("Client Name")
    entry_date = st.date_input("Entry Date")
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
            st.error("Please fill in all fields.")
        else:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                if not cert_number:
                    cert_number = generate_unique_cert_number(cursor)
                else:
                    cursor.execute("SELECT COUNT(*) FROM cards WHERE certnumber = %s", (cert_number,))
                    if cursor.fetchone()[0] > 0:
                        st.error("CertNumber already exists.")
                        st.stop()

                image_url = upload_image_to_gcs(image_file, cert_number)

                insert_query = """
                    INSERT INTO cards (Image, ClientName, EntryDate, Sport, SportGrader, Grade, Player, SetYear, 
                                       SetName, Parallel, CertNumber, CardNumber, Auto, Jersey)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (
                    image_url, client_name, entry_date, sport, sport_grader, grade, player,
                    set_year, set_name, parallel, cert_number, card_number, auto, jersey
                ))
                conn.commit()
                st.success("Card added successfully!")
                st.write(f"CertNumber: {cert_number}")
            except Exception as e:
                st.error(f"An error occurred: {e}")
            finally:
                cursor.close()
                conn.close()

# Reporting Tab
with tabs[2]:
    st.subheader("Reports")
    st.write("View descriptive statistics and trends in your card inventory.")

    query = """
        SELECT CertNumber, CardNumber, EntryDate, Sport, Player, Grade
        FROM cards
    """
    df = fetch_data(query)

    if df is not None and not df.empty:
        # Convert EntryDate to datetime for analysis
        df['EntryDate'] = pd.to_datetime(df['EntryDate'])
        df['Week'] = df['EntryDate'].dt.to_period('W').astype(str)

        # Summary Statistics
        st.write("### Summary Statistics")
        st.write(f"Total Cards in Inventory: {len(df)}")
        st.write(f"Unique Sports: {df['Sport'].nunique()}")
        st.write(f"Unique Players: {df['Player'].nunique()}")

        # 1. Bar Chart: Cards Added by Week
        cards_by_week = df.groupby('Week').size().reset_index(name='Count')
        st.write("### Cards Added by Week")
        fig1 = px.bar(cards_by_week, x='Week', y='Count', title="Cards Added Over Time", labels={'Count': 'Number of Cards'})
        st.plotly_chart(fig1)

        # 2. Bar Chart: Cards Added by Week Grouped by Sport
        cards_by_week_sport = df.groupby(['Week', 'Sport']).size().reset_index(name='Count')
        st.write("### Cards Added by Week Grouped by Sport")
        fig2 = px.bar(cards_by_week_sport, x='Week', y='Count', color='Sport', title="Cards Added by Sport Over Time",
                      labels={'Count': 'Number of Cards'})
        st.plotly_chart(fig2)

        # 3. Table: Top 10 Players by Number of Cards
        top_players = df.groupby('Player').size().reset_index(name='Count').sort_values(by='Count', ascending=False).head(10)
        st.write("### Top 10 Players by Number of Cards")
        st.dataframe(top_players)

        # 4. Bar Chart: Grades Distribution
        grades_distribution = df['Grade'].value_counts().reset_index()
        grades_distribution.columns = ['Grade', 'Count']
        st.write("### Grade Distribution")
        fig3 = px.bar(grades_distribution, x='Grade', y='Count', title="Distribution of Grades", labels={'Count': 'Number of Cards'})
        st.plotly_chart(fig3)
    else:
        st.warning("No data available for reporting.")

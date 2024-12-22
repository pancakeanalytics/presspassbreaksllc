import streamlit as st
from google.cloud import storage
import mysql.connector
import pandas as pd
import plotly.express as px
import random
import string

# Google Cloud SQL Configuration
DB_CONFIG = {
    'user': 'presspassbreaks001',
    'password': 'ABlg0IEstack',
    'host': '35.237.166.69',
    'database': 'PPB_DB',
}

# Google Cloud Storage Configuration
BUCKET_NAME = 'ppbb1'

# Helper function to generate a random certificate number
def generate_unique_cert_number(cursor):
    while True:
        cert_number = ''.join(random.choices(string.digits, k=10))
        cursor.execute("SELECT COUNT(*) FROM cards WHERE CertNumber = %s", (cert_number,))
        if cursor.fetchone()[0] == 0:
            return cert_number

# Helper function to upload image to Google Cloud Storage
def upload_image_to_gcs(image_file, cert_number):
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"cards/{cert_number}.jpg")
    blob.upload_from_file(image_file, content_type='image/jpeg')
    return blob.public_url

# Helper function to fetch data from the database
def fetch_data(query):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"An error occurred while fetching data: {e}")
        return None

# Helper function to process CSV rows
def process_csv_row(row, cursor):
    cert_number = generate_unique_cert_number(cursor)
    image_url = row.get('Image', 'https://via.placeholder.com/150')  # Placeholder image URL if none provided
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
        row['Auto'],
        row['Jersey']
    )

# Streamlit App
st.title("Press Pass Breaks Grading Inventory Tool")
st.subheader("Developed by Pancake Analytics LLC")

# Introduction/Flavor Text
st.markdown("""
Welcome to the **Press Pass Breaks Grading Inventory Tool**, developed by Pancake Analytics LLC. 
This app is your one-stop solution for managing, uploading, and analyzing grading inventory for your trading cards. 

### How to Use This Tool:
1. **Individual Entry**: Use the first tab to add cards one at a time, including uploading images and detailed grading information.
2. **Bulk CSV Upload**: If you have multiple cards to add, upload a CSV file in the second tab. Make sure the file follows the required format.
3. **Reports**: View summary statistics and visualizations of your card inventory in the third tab.

We hope this tool makes managing your card grading inventory seamless and insightful!
""")

# Tabbed interface
tabs = st.tabs(["Individual Entry", "Bulk CSV Upload", "Reports"])

# Individual Entry Tab
with tabs[0]:
    st.subheader("Individual Entry")
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
    image_file = st.file_uploader("Upload JPG Image", type=["jpg"])

    if st.button("Submit Individual Entry"):
        if not all([client_name, sport, sport_grader, grade, player, set_year, set_name, parallel, auto, jersey, image_file]):
            st.error("Please fill in all fields and upload an image.")
        else:
            try:
                conn = mysql.connector.connect(**DB_CONFIG)
                cursor = conn.cursor()

                cert_number = generate_unique_cert_number(cursor)
                image_url = upload_image_to_gcs(image_file, cert_number)

                insert_query = """
                    INSERT INTO cards (Image, ClientName, EntryDate, Sport, SportGrader, Grade, Player, SetYear, SetName, Parallel, CertNumber, Auto, Jersey)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (
                    image_url, client_name, entry_date, sport, sport_grader, grade, player,
                    set_year, set_name, parallel, cert_number, auto, jersey
                ))
                conn.commit()

                st.success("Card entry successfully added!")
                st.write(f"Certificate Number: {cert_number}")
            except Exception as e:
                st.error(f"An error occurred: {e}")
            finally:
                cursor.close()
                conn.close()

# Bulk Upload Tab
with tabs[1]:
    st.subheader("Bulk CSV Upload")
    csv_file = st.file_uploader("Upload CSV File", type=["csv"])

    if csv_file:
        try:
            df = pd.read_csv(csv_file)
            required_columns = [
                "Client Name", "Entry Date", "Sport", "Sport Grader", "Grade",
                "Player", "Set Year", "Set Name", "Parallel", "Auto", "Jersey"
            ]
            if not all(col in df.columns for col in required_columns):
                st.error(f"The CSV file must contain the following columns: {', '.join(required_columns)}")
            else:
                conn = mysql.connector.connect(**DB_CONFIG)
                cursor = conn.cursor()
                
                for _, row in df.iterrows():
                    data = process_csv_row(row, cursor)
                    insert_query = """
                        INSERT INTO cards (Image, ClientName, EntryDate, Sport, SportGrader, Grade, Player, SetYear, SetName, Parallel, CertNumber, Auto, Jersey)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_query, data)
                
                conn.commit()
                st.success("Bulk upload successful!")
        except Exception as e:
            st.error(f"An error occurred while processing the CSV: {e}")
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()

# Reporting Tab
with tabs[2]:
    st.subheader("Reports")
    st.write("View descriptive statistics about the cards data.")

    query = """
        SELECT CertNumber, EntryDate, Sport, Player
        FROM cards
    """
    df = fetch_data(query)

    if df is not None and not df.empty:
        # Convert EntryDate to datetime for analysis
        df['EntryDate'] = pd.to_datetime(df['EntryDate'])
        df['Week'] = df['EntryDate'].dt.to_period('W').astype(str)

        # 1. Bar Graph: Certificate Numbers Added by Week
        certs_by_week = df.groupby('Week').size().reset_index(name='Count')
        st.write("### Certificate Numbers Added by Week")
        fig1 = px.bar(certs_by_week, x='Week', y='Count', title="Cert Numbers by Week")
        st.plotly_chart(fig1)

        # 2. Bar Graph: Certificate Numbers Added by Week Grouped by Sport
        certs_by_week_sport = df.groupby(['Week', 'Sport']).size().reset_index(name='Count')
        st.write("### Certificate Numbers Added by Week Grouped by Sport")
        fig2 = px.bar(certs_by_week_sport, x='Week', y='Count', color='Sport', title="Cert Numbers by Week and Sport")
        st.plotly_chart(fig2)

        # 3. Table: Top 10 Players Graded All-Time by Certificate Number
        top_players = df.groupby('Player').size().reset_index(name='Count').sort_values(by='Count', ascending=False).head(10)
        st.write("### Top 10 Players Graded All-Time by Cert Numbers")
        st.dataframe(top_players)
    else:
        st.warning("No data available for reporting.")

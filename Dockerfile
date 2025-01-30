# Use Python official image
FROM python:3.9

# Set the working directory
WORKDIR /app

# Copy all files to the container
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port Streamlit runs on
EXPOSE 8080

# Run Streamlit
CMD ["streamlit", "run", "grading_card.py", "--server.port=8080", "--server.address=0.0.0.0"]

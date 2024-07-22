from flask import Flask, request, jsonify
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64
import os
import traceback
from google.cloud import storage
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)  # Set up logging

app = Flask(__name__)
CORS(app)  # This will enable CORS for all origins by default

# Set the environment variable for Google Cloud credentials
google_credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
with open("google_credentials.json", "w") as f:
    f.write(google_credentials_json)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_credentials.json"

@app.route('/sendEmail', methods=['POST'])
def send_email():
    try:
        email = request.form.get('email')
        subject = request.form.get('subject')
        body = request.form.get('body')
        file_name = request.form.get('fileName')
        file_content = request.form.get('fileContent')
        hardcoded_recipient = request.form.get('hardcodedRecipient')

        # Decode the base64 file content
        if file_content:
            # Add padding if necessary
            missing_padding = len(file_content) % 4
            if missing_padding:
                file_content += '=' * (4 - missing_padding)
            file_data = base64.b64decode(file_content)
        else:
            raise ValueError("No file content provided")

        # Create the email
        msg = MIMEMultipart()
        msg['From'] = 'ls.paperless@zohomail.com'
        msg['To'] = hardcoded_recipient  # This ensures the email goes to the hardcoded recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        # Attach the file
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(file_data)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={file_name}')

        msg.attach(part)

        # Send the email
        with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
            server.login('ls.paperless@zohomail.com', os.getenv('ZOHO_MAIL_PASSWORD'))
            server.sendmail('ls.paperless@zohomail.com', hardcoded_recipient, msg.as_string())

        logging.info(f'Email sent to {hardcoded_recipient} with subject {subject}')
        return jsonify({'message': 'Email sent successfully!'}), 200

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        logging.error(traceback.format_exc())  # Print the full traceback
        return jsonify({'error': str(e)}), 500

@app.route('/checkFilesAndSendEmails', methods=['GET'])
def check_files_and_send_emails():
    try:
        logging.info("Starting to check files and send emails.")
        
        # Initialize Google Cloud Storage client
        storage_client = storage.Client()
        bucket_name = 'installer-app-8681b.appspot.com'
        bucket = storage_client.bucket(bucket_name)
        
        today_str = datetime.today().strftime('%y-%m-%d')  # Adjusted date format
        logging.info(f"Today's date string: {today_str}")
        
        blobs = bucket.list_blobs()
        
        for blob in blobs:
            logging.info(f"Checking blob: {blob.name}")
            parts = blob.name.split('/')
            logging.info(f"Parts after split: {parts}")

            if len(parts) == 3 and today_str in parts[1]:
                logging.info(f"File found with today's date: {blob.name}")
                email, date_order_part, file_name = parts
                logging.info(f"Parsed email: {email}, date_order_part: {date_order_part}, file_name: {file_name}")
                file_data = blob.download_as_bytes()
                file_content = base64.b64encode(file_data).decode('utf-8')

                # Send email to the hardcoded recipient
                send_email_function(
                     email,  # Hardcoded recipient
                    f"You have work scheduled for today!",
                    f"Order {file_name} contains today's date. ",
                    file_name,
                    file_content,
                    email  # Ensure the email is sent to the hardcoded recipient
                )
            else:
                logging.info(f"No match for today's date: {blob.name}")
        
        logging.info("Finished checking files and sending emails.")
        return jsonify({'message': 'Emails sent successfully!'}), 200
    
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

def send_email_function(email, subject, body, file_name, file_content, hardcoded_recipient):
    try:
        logging.info(f"Preparing to send email to {hardcoded_recipient} with subject {subject} and file {file_name}")
        msg = MIMEMultipart()
        msg['From'] = 'ls.paperless@zohomail.com'
        msg['To'] = email  # Email sent to the hardcoded recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        part = MIMEBase('application', 'octet-stream')
        part.set_payload(base64.b64decode(file_content))
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={file_name}')
        msg.attach(part)

        with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
            logging.info(f"Logging into SMTP server")
            server.login('ls.paperless@zohomail.com', os.getenv('ZOHO_MAIL_PASSWORD'))
            logging.info(f"Sending email to {email}")
            server.sendmail('ls.paperless@zohomail.com', hardcoded_recipient, msg.as_string())
            logging.info(f"Email successfully sent to {hardcoded_recipient}")

    except Exception as e:
        logging.error(f"Error sending email: {str(e)}")
        logging.error(traceback.format_exc())

def scheduled_job():
    logging.info("Scheduled job running.")
    with app.app_context():
        check_files_and_send_emails()

if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    # Schedule job to run daily at a specific hour and minute
    scheduler.add_job(scheduled_job, 'cron', hour=9, minute=0)  # Adjust the hour and minute as needed
    scheduler.start()
    
    logging.info("Scheduler started.")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
#
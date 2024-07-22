from flask import Flask, jsonify
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

app = Flask(__name__)
CORS(app)  # This will enable CORS for all origins by default

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
        msg['To'] = hardcoded_recipient
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
            server.login('ls.paperless@zohomail.com', 'XtY$mHvHXP6')
            server.sendmail('ls.paperless@zohomail.com', hardcoded_recipient, msg.as_string())

        return jsonify({'message': 'Email sent successfully!'}), 200

    except Exception as e:
        # Print the traceback for the exception
        print(f"Error: {str(e)}")
        print(traceback.format_exc())  # Print the full traceback
        return jsonify({'error': str(e)}), 500

@app.route('/checkFilesAndSendEmails', methods=['GET'])
def check_files_and_send_emails():
    try:
        # Initialize Google Cloud Storage client
        storage_client = storage.Client()
        bucket_name = 'installer-app-8681b.appspot.com'
        bucket = storage_client.bucket(bucket_name)
        
        today_str = datetime.today().strftime('%d-%m-%y')
        blobs = bucket.list_blobs()
        
        for blob in blobs:
            if today_str in blob.name:
                email, date_order_part, file_name = blob.name.split('/')
                file_data = blob.download_as_bytes()
                file_content = base64.b64encode(file_data).decode('utf-8')

                # Send email
                send_email_function(
                    'david.hamilton@loudounstairs.com',
                    f"File with today's date found: {file_name}",
                    f"File {file_name} contains today's date.",
                    file_name,
                    file_content,
                    email
                )
        
        return jsonify({'message': 'Emails sent successfully!'}), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

def send_email_function(email, subject, body, file_name, file_content, hardcoded_recipient):
    try:
        msg = MIMEMultipart()
        msg['From'] = 'ls.paperless@zohomail.com'
        msg['To'] = email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        part = MIMEBase('application', 'octet-stream')
        part.set_payload(base64.b64decode(file_content))
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={file_name}')
        msg.attach(part)

        with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
            server.login('ls.paperless@zohomail.com', 'XtY$mHvHXP6')
            server.sendmail('ls.paperless@zohomail.com', hardcoded_recipient, msg.as_string())

        print(f"Email sent to {email} for file: {file_name}")

    except Exception as e:
        print(f"Error sending email: {str(e)}")
        print(traceback.format_exc())

def scheduled_job():
    with app.app_context():
        check_files_and_send_emails()

if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_job, 'cron', hour=9)  # Schedule job to run daily at 8 AM
    scheduler.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

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
        
        emails_sent = []  # List to store emails that were sent

        for blob in blobs:
            logging.info(f"Checking blob: {blob.name}")
            parts = blob.name.split('/')
            logging.info(f"Parts after split: {parts}")

            # Check if the structure starts with '2.0' and has enough parts to parse (like email/folder/file)
            if len(parts) >= 4 and parts[0] == '2.0':  # Ensure the base folder is '2.0'
                email, folder_type, order_number_date = parts[1], parts[2], parts[3]
                
                logging.info(f"Extracted email: {email}, folder_type: {folder_type}, order_number_date: {order_number_date}")
                
                # Check if folder_type matches 'repairs' or 'installinspections'
                if folder_type not in ['repairs', 'installinspections']:
                    logging.info(f"Skipping non-matching folder type: {folder_type}")
                    continue
                
                # Extract the order date part from the filename (assuming format like '24-07-01_order.pdf')
                order_date = order_number_date.split('_')[0]
                logging.info(f"Extracted order date: {order_date}")
                
                # Check if the date in the order matches today's date
                if today_str == order_date:
                    folder_type_upper = folder_type.upper()  # Capitalize the folder type for email
                    
                    # Download the file content and encode it for email
                    file_data = blob.download_as_bytes()
                    file_content = base64.b64encode(file_data).decode('utf-8')

                    # Prepare the email subject and body
                    email_subject = f"You have work scheduled for today! ({folder_type_upper})"
                    email_body = f"Order {order_number_date} from {folder_type_upper} contains today's date: {order_date}."
                    
                    # Send email to the extracted recipient email
                    send_email_function(
                        email,  # Send to the email extracted from the path
                        email_subject,  # Email subject
                        email_body,  # Email body
                        order_number_date,  # File name
                        file_content,
                        email  # To email address
                    )
                    
                    # Add the email to the list of sent emails
                    emails_sent.append(email)
                else:
                    logging.info(f"No match for today's date: {order_date} != {today_str}")
            else:
                logging.info(f"Skipping blob due to invalid path structure or missing '2.0' directory: {blob.name}")
        
        logging.info("Finished checking files and sending emails.")
        
        # Return the list of emails sent in the response
        return jsonify({'message': 'Emails sent successfully!', 'emails_sent': emails_sent}), 200
    
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


# TEST EMAILS IN CONSOLE
# def send_email_function(email, subject, body, file_name, file_content, hardcoded_recipient):
#     try:
#         logging.info(f"Preparing to send email to {hardcoded_recipient} with subject {subject} and file {file_name}")
        
#         # Instead of sending the email, print the details for now
#         print(f"Would send email to: {email}")
#         print(f"Subject: {subject}")
#         print(f"Body: {body}")
#         print(f"File: {file_name}")

#     except Exception as e:
#         logging.error(f"Error sending email: {str(e)}")
#         logging.error(traceback.format_exc())


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



@app.route('/sendWelcomeEmail', methods=['POST'])
def send_welcome_email():
    try:
        email = request.json.get('email')
        temporary_password = request.json.get('temporary_password')
        company_name = request.json.get("companyName")
        subject = "Welcome to Our Service"
        body = f"Dear user,\n\nWelcome to our service! Your temporary password is: {temporary_password}\n\nPlease change your password after logging in.\n\nBest regards,\n{company_name}"

        # Create the email
        msg = MIMEMultipart()
        msg['From'] = 'ls.paperless@zohomail.com'
        msg['To'] = email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        # Send the email
        with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
            server.login('ls.paperless@zohomail.com', os.getenv('ZOHO_MAIL_PASSWORD'))
            server.sendmail('ls.paperless@zohomail.com', email, msg.as_string())

        logging.info(f'Welcome email sent to {email}')
        return jsonify({'message': 'Welcome email sent successfully!'}), 200

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        logging.error(traceback.format_exc())  # Print the full traceback
        return jsonify({'error': str(e)}), 500

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
# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from email.mime.base import MIMEBase
# from email import encoders
# import base64
# import os
# import traceback
# from google.cloud import storage
# from datetime import datetime
# from apscheduler.schedulers.background import BackgroundScheduler
# import logging
# from dotenv import load_dotenv

# load_dotenv()

# logging.basicConfig(level=logging.INFO)  # Set up logging

# app = Flask(__name__)
# CORS(app)  # This will enable CORS for all origins by default

# # Set the environment variable for Google Cloud credentials
# google_credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
# with open("google_credentials.json", "w") as f:
#     f.write(google_credentials_json)
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_credentials.json"

# @app.route('/sendEmail', methods=['POST'])
# def send_email():
#     try:
#         email = request.form.get('email')
#         subject = request.form.get('subject')
#         body = request.form.get('body')
#         file_name = request.form.get('fileName')
#         file_content = request.form.get('fileContent')
#         hardcoded_recipient = request.form.get('hardcodedRecipient')

#         # Decode the base64 file content
#         if file_content:
#             # Add padding if necessary
#             missing_padding = len(file_content) % 4
#             if missing_padding:
#                 file_content += '=' * (4 - missing_padding)
#             file_data = base64.b64decode(file_content)
#         else:
#             raise ValueError("No file content provided")

#         # Create the email
#         msg = MIMEMultipart()
#         msg['From'] = 'ls.paperless@zohomail.com'
#         msg['To'] = hardcoded_recipient  # This ensures the email goes to the hardcoded recipient
#         msg['Subject'] = subject

#         msg.attach(MIMEText(body, 'plain'))

#         # Attach the file
#         part = MIMEBase('application', 'octet-stream')
#         part.set_payload(file_data)
#         encoders.encode_base64(part)
#         part.add_header('Content-Disposition', f'attachment; filename={file_name}')

#         msg.attach(part)

#         # Send the email
#         with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
#             server.login('ls.paperless@zohomail.com', os.getenv('ZOHO_MAIL_PASSWORD'))
#             server.sendmail('ls.paperless@zohomail.com', hardcoded_recipient, msg.as_string())

#         logging.info(f'Email sent to {hardcoded_recipient} with subject {subject}')
#         return jsonify({'message': 'Email sent successfully!'}), 200

#     except Exception as e:
#         logging.error(f"Error: {str(e)}")
#         logging.error(traceback.format_exc())  # Print the full traceback
#         return jsonify({'error': str(e)}), 500

# @app.route('/checkFilesAndSendEmails', methods=['GET'])
# def check_files_and_send_emails():
#     try:
#         logging.info("Starting to check files and send emails.")
        
#         # Initialize Google Cloud Storage client
#         storage_client = storage.Client()
#         bucket_name = 'installer-app-8681b.appspot.com'
#         bucket = storage_client.bucket(bucket_name)
        
#         today_str = datetime.today().strftime('%y-%m-%d')  # Adjusted date format
#         logging.info(f"Today's date string: {today_str}")
        
#         blobs = bucket.list_blobs()
        
#         for blob in blobs:
#             logging.info(f"Checking blob: {blob.name}")
#             parts = blob.name.split('/')
#             logging.info(f"Parts after split: {parts}")

#             # Expecting a structure like: '2.0/{email}/{folder_type}/{date_order}/{file}'
#             if len(parts) == 5 and parts[0] == '2.0' and today_str in parts[3]:
#                 email, folder_type, date_order_part, file_name = parts[1], parts[2], parts[3], parts[4]
                
#                 # Determine if it's a repair or install inspection and adjust the subject accordingly
#                 if folder_type == 'repairs':
#                     folder_type_upper = 'REPAIR'
#                 elif folder_type == 'installinspections':
#                     folder_type_upper = 'INSTALL'
#                 else:
#                     folder_type_upper = 'OTHER'

#                 # Download the file and prepare for email
#                 file_data = blob.download_as_bytes()
#                 file_content = base64.b64encode(file_data).decode('utf-8')

#                 # Prepare the email subject with the folder type
#                 email_subject = f"You have work scheduled for today! ({folder_type_upper})"
#                 email_body = f"Order {file_name} from {folder_type} contains today's date."
                
#                 # Send email to the hardcoded recipient
#                 send_email_function(
#                     email,  # Hardcoded recipient
#                     email_subject,  # Updated subject
#                     email_body,  # Updated body with folder type
#                     file_name,
#                     file_content,
#                     email  # Ensure the email is sent to the hardcoded recipient
#                 )
#             else:
#                 logging.info(f"No match for today's date or invalid path: {blob.name}")
        
#         logging.info("Finished checking files and sending emails.")
#         return jsonify({'message': 'Emails sent successfully!'}), 200
    
#     except Exception as e:
#         logging.error(f"Error: {str(e)}")
#         logging.error(traceback.format_exc())
#         return jsonify({'error': str(e)}), 500


# def send_email_function(email, subject, body, file_name, file_content, hardcoded_recipient):
#     try:
#         logging.info(f"Preparing to send email to {hardcoded_recipient} with subject {subject} and file {file_name}")
#         msg = MIMEMultipart()
#         msg['From'] = 'ls.paperless@zohomail.com'
#         msg['To'] = email  # Email sent to the hardcoded recipient
#         msg['Subject'] = subject

#         msg.attach(MIMEText(body, 'plain'))

#         part = MIMEBase('application', 'octet-stream')
#         part.set_payload(base64.b64decode(file_content))
#         encoders.encode_base64(part)
#         part.add_header('Content-Disposition', f'attachment; filename={file_name}')
#         msg.attach(part)

#         with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
#             logging.info(f"Logging into SMTP server")
#             server.login('ls.paperless@zohomail.com', os.getenv('ZOHO_MAIL_PASSWORD'))
#             logging.info(f"Sending email to {email}")
#             server.sendmail('ls.paperless@zohomail.com', hardcoded_recipient, msg.as_string())
#             logging.info(f"Email successfully sent to {hardcoded_recipient}")

#     except Exception as e:
#         logging.error(f"Error sending email: {str(e)}")
#         logging.error(traceback.format_exc())


# @app.route('/sendWelcomeEmail', methods=['POST'])
# def send_welcome_email():
#     try:
#         email = request.json.get('email')
#         temporary_password = request.json.get('temporary_password')
#         company_name = request.json.get("companyName")
#         subject = "Welcome to Our Service"
#         body = f"Dear user,\n\nWelcome to our service! Your temporary password is: {temporary_password}\n\nPlease change your password after logging in.\n\nBest regards,\n{company_name}"

#         # Create the email
#         msg = MIMEMultipart()
#         msg['From'] = 'ls.paperless@zohomail.com'
#         msg['To'] = email
#         msg['Subject'] = subject

#         msg.attach(MIMEText(body, 'plain'))

#         # Send the email
#         with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
#             server.login('ls.paperless@zohomail.com', os.getenv('ZOHO_MAIL_PASSWORD'))
#             server.sendmail('ls.paperless@zohomail.com', email, msg.as_string())

#         logging.info(f'Welcome email sent to {email}')
#         return jsonify({'message': 'Welcome email sent successfully!'}), 200

#     except Exception as e:
#         logging.error(f"Error: {str(e)}")
#         logging.error(traceback.format_exc())  # Print the full traceback
#         return jsonify({'error': str(e)}), 500

# def scheduled_job():
#     logging.info("Scheduled job running.")
#     with app.app_context():
#         check_files_and_send_emails()

# if __name__ == '__main__':
#     scheduler = BackgroundScheduler()
#     # Schedule job to run daily at a specific hour and minute
#     scheduler.add_job(scheduled_job, 'cron', hour=9, minute=0)  # Adjust the hour and minute as needed
#     scheduler.start()
    
#     logging.info("Scheduler started.")
#     port = int(os.environ.get('PORT', 5000))
#     app.run(host='0.0.0.0', port=port)
# #

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

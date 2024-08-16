import logging
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz  # For timezone management

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emails.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.ethereal.email'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'cole31@ethereal.email'
app.config['MAIL_PASSWORD'] = '6ZEDGksPtWVqK9w7Yf'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

# Timezone configuration
app.config['TIMEZONE'] = 'Asia/Singapore'  # Default timezone

db = SQLAlchemy(app)
mail = Mail(app)

# Initialize the scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, nullable=False)
    recipients = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    schedule_time = db.Column(db.String(20), nullable=False)  # Store as string in desired format
    sent_at = db.Column(db.String(20))  # Store as string in desired format

def get_timezone():
    """Retrieve timezone from configuration."""
    return pytz.timezone(app.config.get('TIMEZONE', 'UTC'))

@app.route('/save_emails', methods=['POST'])
def save_emails():
    logger.info("Received POST request on /save_emails")
    
    data = request.get_json()
    logger.debug(f"Request JSON data: {data}")

    event_id = data.get('event_id')
    recipients = data.get('recipients')
    email_subject = data.get('email_subject')
    email_content = data.get('email_content')
    send_immediately = data.get('send_immediately', False)

    timezone = get_timezone()
    
    if send_immediately:
        schedule_time = datetime.now(timezone).strftime('%d %b %Y %H.%M')
        logger.info("Send immediately selected; using current timestamp")
    else:
        timestamp = data.get('timestamp')
        logger.debug(f"Timestamp received: {timestamp}")
        if not timestamp:
            logger.error("Timestamp is missing when 'Send Immediately' is not checked")
            return jsonify({'error': 'Timestamp is required if not sending immediately.'}), 400

        try:
            schedule_time_dt = datetime.strptime(timestamp, '%d %b %Y %H.%M')
            schedule_time_dt = timezone.localize(schedule_time_dt)  # Localize datetime
            schedule_time = schedule_time_dt.strftime('%d %b %Y %H.%M')
            logger.info(f"Parsed schedule time: {schedule_time}")
        except ValueError:
            logger.error(timestamp)
            logger.error("Failed to parse the timestamp; format should be 'dd MMM yyyy HH.mm'")
            return jsonify({'error': 'Invalid timestamp format. Please use "dd MMM yyyy HH.mm".'}), 400

    email = Email(event_id=event_id, recipients=recipients, subject=email_subject, content=email_content, schedule_time=schedule_time)
    db.session.add(email)
    db.session.commit()
    logger.info(f"Email saved to database with ID: {email.id}")

    schedule_time_dt = datetime.strptime(schedule_time, '%d %b %Y %H.%M')
    schedule_time_dt = timezone.localize(schedule_time_dt)  # Ensure datetime is timezone-aware

    if schedule_time_dt < datetime.now(timezone):
        send_email(email.id)
    else:
        scheduler.add_job(send_email, 'date', run_date=schedule_time_dt, args=[email.id])
        logger.info(f"Email scheduled for {schedule_time_dt}")

    return jsonify({'message': 'Email saved and scheduled successfully.'}), 201

def send_email(email_id):
    with app.app_context():  # Ensure Flask app context is available
        email = Email.query.get(email_id)
        if email and not email.sent_at:
            msg = Message(email.subject,
                          sender=app.config['MAIL_USERNAME'],
                          recipients=email.recipients.split(','))
            msg.body = email.content
            try:
                mail.send(msg)
                email.sent_at = datetime.now(get_timezone()).strftime('%d %b %Y %H.%M')
                db.session.commit()
                logger.info(f'Email sent to {email.recipients}: {email.subject}')
            except Exception as e:
                logger.error(f'Failed to send email: {e}')

def check_scheduled_emails():
    """Check for scheduled emails that need to be sent when the server starts."""
    timezone = get_timezone()
    now = datetime.now(timezone)
    emails_to_send = Email.query.filter(Email.sent_at.is_(None), Email.schedule_time < now.strftime('%d %b %Y %H.%M')).all()
    
    for email in emails_to_send:
        send_email(email.id)

@app.route('/')
def index():
    emails = Email.query.all()
    return render_template('index.html', emails=emails)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables if they don't exist
        check_scheduled_emails()  # Check for any missed emails upon startup
    app.run(debug=True)
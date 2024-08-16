from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

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

db = SQLAlchemy(app)
mail = Mail(app)

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, nullable=False)
    recipients = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    schedule_time = db.Column(db.String(20), nullable=False)  # Store as string in desired format
    sent_at = db.Column(db.String(20))  # Store as string in desired format

scheduler = BackgroundScheduler()
scheduler.start()

@app.route('/save_emails', methods=['POST'])
def save_emails():
    data = request.get_json()
    event_id = data.get('event_id')
    recipients = data.get('recipients')
    email_subject = data.get('email_subject')
    email_content = data.get('email_content')
    send_immediately = data.get('send_immediately', False)

    if send_immediately:
        schedule_time = datetime.now().strftime('%d %b %Y %H.%M')
    else:
        schedule_time = datetime.strptime(data.get('timestamp'), '%d %b %Y %H.%M').strftime('%d %b %Y %H.%M')

    email = Email(event_id=event_id, recipients=recipients, subject=email_subject, content=email_content, schedule_time=schedule_time)
    db.session.add(email)
    db.session.commit()

    if send_immediately:
        send_email(email.id)
    else:
        # Convert schedule_time back to datetime for the scheduler
        schedule_time_dt = datetime.strptime(schedule_time, '%d %b %Y %H.%M')
        scheduler.add_job(send_email, 'date', run_date=schedule_time_dt, args=[email.id])

    return jsonify({'message': 'Email saved and scheduled successfully.'}), 201

def send_email(email_id):
    email = Email.query.get(email_id)
    if email and not email.sent_at:
        msg = Message(email.subject,
                      sender=app.config['MAIL_USERNAME'],
                      recipients=email.recipients.split(','))  # Send to multiple recipients
        msg.body = email.content
        try:
            mail.send(msg)
            email.sent_at = datetime.now().strftime('%d %b %Y %H.%M')  # Record the sent time in desired format
            db.session.commit()
            print(f'Email sent to {email.recipients}: {email.subject}')
        except Exception as e:
            print(f'Failed to send email: {e}')

@app.route('/')
def index():
    emails = Email.query.all()
    return render_template('index.html', emails=emails)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables if they don't exist
    app.run(debug=True)
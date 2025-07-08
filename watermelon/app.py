from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import requests
import base64
import urllib.parse
import json
from datetime import datetime, timedelta, timezone
import random
import uuid
from PIL import Image
import pytesseract
import io

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///login_users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "your-secret-key-change-this-in-production"

# Spotify API Configuration
# Set DEMO_MODE to True to test without real Spotify credentials
DEMO_MODE = True  # Set to False when you have real Spotify credentials

SPOTIFY_CLIENT_ID = "your_spotify_client_id_here"  # Replace with your actual Client ID
SPOTIFY_CLIENT_SECRET = "your_spotify_client_secret_here"  # Replace with your actual Client Secret
SPOTIFY_REDIRECT_URI = "http://localhost:5000/spotify/callback"
SPOTIFY_SCOPE = "user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private playlist-read-collaborative streaming user-read-email user-read-private"

# File upload configuration
UPLOAD_FOLDER = 'uploads'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    streak_count = db.Column(db.Integer, default=0)
    last_activity = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    total_study_time = db.Column(db.Integer, default=0)  # in minutes
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    notes = db.relationship('Note', backref='user', lazy=True)
    quiz_attempts = db.relationship('QuizAttempt', backref='user', lazy=True)
    study_sessions = db.relationship('StudySession', backref='user', lazy=True)

    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def update_streak(self):
        today = datetime.now(timezone.utc).date()
        last_activity_date = self.last_activity.date() if self.last_activity else None
        
        if last_activity_date:
            if last_activity_date == today:
                # Already active today, no change
                return
            elif last_activity_date == today - timedelta(days=1):
                # Consecutive day, increase streak
                self.streak_count += 1
            else:
                # Broke streak, reset to 1
                self.streak_count = 1
        else:
            # First activity
            self.streak_count = 1
        
        self.last_activity = datetime.now(timezone.utc)
        db.session.commit()

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    tags = db.Column(db.String(500))  # comma-separated tags
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    file_path = db.Column(db.String(500))  # for scanned images
    is_scanned = db.Column(db.Boolean, default=False)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    topics = db.relationship('Topic', backref='subject', lazy=True)
    questions = db.relationship('Question', backref='subject', lazy=True)

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    questions = db.relationship('Question', backref='topic', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500), nullable=False)
    option_b = db.Column(db.String(500), nullable=False)
    option_c = db.Column(db.String(500), nullable=False)
    option_d = db.Column(db.String(500), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)  # A, B, C, or D
    explanation = db.Column(db.Text)
    difficulty = db.Column(db.String(20), default='medium')  # easy, medium, hard
    question_type = db.Column(db.String(20), default='mains')  # mains, prelims
    year = db.Column(db.Integer)  # for previous year questions
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    attempts = db.relationship('QuizAttempt', backref='question', lazy=True)

class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    selected_answer = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    time_taken = db.Column(db.Integer)  # in seconds
    attempted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    quiz_session_id = db.Column(db.String(100))  # to group quiz attempts

class StudySession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    topic = db.Column(db.String(100))
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # in minutes
    activity_type = db.Column(db.String(50), nullable=False)  # study, quiz, notes
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class TimeSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text)
    is_completed = db.Column(db.Boolean, default=False)
    reminder_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    is_completed = db.Column(db.Boolean, default=False)
    due_date = db.Column(db.DateTime)
    category = db.Column(db.String(100), default='general')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    reminder_time = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    reminder_type = db.Column(db.String(50), default='general')  # study, break, task, custom
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class FocusSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_type = db.Column(db.String(50), nullable=False)  # focus, study, break
    duration = db.Column(db.Integer, nullable=False)  # in seconds
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    subject = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class DiaryEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(20), default='neutral')  # happy, sad, excited, calm, etc.
    date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_image(image_path):
    try:
        import pytesseract
        from PIL import Image
        import PyPDF2
        import io
        import os
        
        file_extension = os.path.splitext(image_path)[1].lower()
        
        # Handle PDF files
        if file_extension == '.pdf':
            try:
                with open(image_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ''
                    for page_num in range(len(pdf_reader.pages)):
                        page = pdf_reader.pages[page_num]
                        text += page.extract_text() + '\n'
                    
                    if text.strip():
                        return f"Extracted from PDF:\n\n{text.strip()}"
                    else:
                        return "No text found in PDF. The PDF might contain scanned images. Try converting pages to images first."
            except Exception as pdf_error:
                return f"PDF Error: {str(pdf_error)}\n\nDemo PDF content: This PDF contains important study material with detailed explanations of key concepts, historical facts, and current affairs relevant for competitive examinations."
        
        # Handle image files
        elif file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
            try:
                # Configure tesseract path for Windows (adjust if needed)
                # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                
                # Open and preprocess the image
                img = Image.open(image_path)
                
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Try different OCR configurations
                configs = [
                    r'--oem 3 --psm 6 -l eng',  # Default
                    r'--oem 3 --psm 4 -l eng',  # Single column text
                    r'--oem 3 --psm 3 -l eng',  # Fully automatic page segmentation
                    r'--oem 3 --psm 1 -l eng'   # Automatic page segmentation with OSD
                ]
                
                best_text = ""
                for config in configs:
                    try:
                        text = pytesseract.image_to_string(img, config=config)
                        if len(text.strip()) > len(best_text.strip()):
                            best_text = text
                    except:
                        continue
                
                if best_text.strip():
                    return f"Extracted from image:\n\n{best_text.strip()}"
                else:
                    return "No text found in the image. Please ensure the image contains clear, readable text with good contrast."
                    
            except ImportError:
                return "OCR functionality requires pytesseract. Install with:\npip install pytesseract\n\nAlso install Tesseract-OCR from: https://github.com/UB-Mannheim/tesseract/wiki\n\nDemo image text: This image contains important study notes with key points about the subject matter, including definitions, examples, and examination tips."
            except Exception as img_error:
                return f"Image OCR Error: {str(img_error)}\n\nDemo image content: This scanned image contains valuable study material with comprehensive notes on the topic, including important facts, figures, and conceptual explanations suitable for competitive exam preparation."
        
        else:
            return f"Unsupported file format: {file_extension}. Supported formats: PDF, JPG, JPEG, PNG, BMP, TIFF"
            
    except Exception as e:
        return f"General OCR Error: {str(e)}\n\nDemo content: This document contains comprehensive study material covering important topics with detailed explanations, key points, and relevant examples for examination preparation."

def init_db():
    """Initialize the database with sample data"""
    with app.app_context():
        db.create_all()
        
        # Check if users already exist
        if User.query.count() == 0:
            # Create sample users with hashed passwords
            users = [
                {'username': 'admin', 'password': 'admin123'},
                {'username': 'user1', 'password': 'password1'},
                {'username': 'testuser', 'password': 'test123'},
                {'username': 'john_doe', 'password': 'john123'}
            ]
            
            for user_data in users:
                user = User(username=user_data['username'])
                user.set_password(user_data['password'])
                db.session.add(user)
            
            db.session.commit()
            
            # Initialize sample subjects and topics
            if Subject.query.count() == 0:
                subjects_data = [
                    {'name': 'General Studies', 'description': 'General Studies for UPSC'},
                    {'name': 'History', 'description': 'Indian and World History'},
                    {'name': 'Geography', 'description': 'Physical and Human Geography'},
                    {'name': 'Polity', 'description': 'Indian Constitution and Governance'},
                    {'name': 'Economics', 'description': 'Indian Economy and Development'},
                    {'name': 'Science & Technology', 'description': 'Current Developments'},
                    {'name': 'Environment', 'description': 'Environment and Ecology'}
                ]
                
                for subject_data in subjects_data:
                    subject = Subject(**subject_data)
                    db.session.add(subject)
                
                db.session.commit()
                
                # Add sample topics
                topics_data = [
                    {'subject_id': 1, 'name': 'Current Affairs', 'description': 'Latest developments'},
                    {'subject_id': 2, 'name': 'Ancient India', 'description': 'Indus Valley to Mauryas'},
                    {'subject_id': 2, 'name': 'Medieval India', 'description': 'Delhi Sultanate to Mughals'},
                    {'subject_id': 2, 'name': 'Modern India', 'description': 'British Rule to Independence'},
                    {'subject_id': 3, 'name': 'Physical Geography', 'description': 'Landforms and Climate'},
                    {'subject_id': 3, 'name': 'Human Geography', 'description': 'Population and Settlement'},
                    {'subject_id': 4, 'name': 'Fundamental Rights', 'description': 'Constitutional Rights'},
                    {'subject_id': 4, 'name': 'Directive Principles', 'description': 'DPSP'},
                    {'subject_id': 5, 'name': 'Economic Development', 'description': 'Growth and Development'},
                    {'subject_id': 5, 'name': 'Public Finance', 'description': 'Budget and Taxation'}
                ]
                
                for topic_data in topics_data:
                    topic = Topic(**topic_data)
                    db.session.add(topic)
                
                db.session.commit()
                
                # Add sample questions
                questions_data = [
                    # History Questions
{
                        'subject_id': 2, 'topic_id': 2,
                        'question_text': 'Which of the following was the capital of the Mauryan Empire?',
                        'option_a': 'Taxila', 'option_b': 'Pataliputra', 'option_c': 'Ujjain', 'option_d': 'Kausambi',
                        'correct_answer': 'B', 'explanation': 'Pataliputra (modern-day Patna) was the capital of the Mauryan Empire.',
                        'difficulty': 'easy', 'question_type': 'prelims', 'year': 2020
                    },
                    # Additional Questions
                    {
                        'subject_id': 2, 'topic_id': 2,
                        'question_text': 'Who was the first emperor of the Mauryan Empire?',
                        'option_a': 'Ashoka', 'option_b': 'Chandragupta Maurya', 'option_c': 'Bindusara', 'option_d': 'Bimbisara',
                        'correct_answer': 'B', 'explanation': 'Chandragupta Maurya was the founder and first emperor of the Mauryan Empire.',
                        'difficulty': 'easy', 'question_type': 'prelims', 'year': 2021
                    },
                    {
                        'subject_id': 2, 'topic_id': 3,
                        'question_text': 'The Mughals ruled India in which of the following centuries?',
                        'option_a': '15th and 16th', 'option_b': '16th and 17th', 'option_c': '17th and 18th', 'option_d': '18th and 19th',
                        'correct_answer': 'B', 'explanation': 'The Mughal Empire predominantly ruled during the 16th and 17th centuries.',
                        'difficulty': 'medium', 'question_type': 'mains', 'year': 2019
                    },
                    # More dummy questions can be added here following the same pattern.
                    {
                        'subject_id': 2, 'topic_id': 3,
                        'question_text': 'The Delhi Sultanate was established in which year?',
                        'option_a': '1206 AD', 'option_b': '1192 AD', 'option_c': '1210 AD', 'option_d': '1220 AD',
                        'correct_answer': 'A', 'explanation': 'The Delhi Sultanate was established in 1206 AD by Qutb-ud-din Aibak.',
                        'difficulty': 'medium', 'question_type': 'prelims', 'year': 2019
                    },
                    {
                        'subject_id': 2, 'topic_id': 4,
                        'question_text': 'The Indian National Congress was founded in which year?',
                        'option_a': '1885', 'option_b': '1875', 'option_c': '1895', 'option_d': '1905',
                        'correct_answer': 'A', 'explanation': 'The Indian National Congress was founded in 1885 by A.O. Hume.',
                        'difficulty': 'easy', 'question_type': 'prelims', 'year': 2021
                    },
                    
                    # Polity Questions
                    {
                        'subject_id': 4, 'topic_id': 7,
                        'question_text': 'Which Article of the Constitution deals with Right to Equality?',
                        'option_a': 'Article 14', 'option_b': 'Article 15', 'option_c': 'Article 16', 'option_d': 'All of the above',
                        'correct_answer': 'D', 'explanation': 'Articles 14-18 deal with Right to Equality under the Constitution.',
                        'difficulty': 'medium', 'question_type': 'mains', 'year': 2021
                    },
                    {
                        'subject_id': 4, 'topic_id': 8,
                        'question_text': 'Which Article contains the Directive Principles of State Policy?',
                        'option_a': 'Article 36-51', 'option_b': 'Article 14-32', 'option_c': 'Article 52-78', 'option_d': 'Article 79-123',
                        'correct_answer': 'A', 'explanation': 'Articles 36-51 contain the Directive Principles of State Policy.',
                        'difficulty': 'medium', 'question_type': 'prelims', 'year': 2020
                    },
                    
                    # Geography Questions
                    {
                        'subject_id': 3, 'topic_id': 5,
                        'question_text': 'Which mountain range separates Asia from Europe?',
                        'option_a': 'Himalayas', 'option_b': 'Ural Mountains', 'option_c': 'Alps', 'option_d': 'Rockies',
                        'correct_answer': 'B', 'explanation': 'The Ural Mountains act as a natural boundary between Asia and Europe.',
                        'difficulty': 'easy', 'question_type': 'prelims', 'year': 2019
                    },
                    {
                        'subject_id': 3, 'topic_id': 6,
                        'question_text': 'The largest producer of coal in India is:',
                        'option_a': 'Jharkhand', 'option_b': 'Chhattisgarh', 'option_c': 'Odisha', 'option_d': 'West Bengal',
                        'correct_answer': 'B', 'explanation': 'Chhattisgarh is the largest coal-producing state in India.',
                        'difficulty': 'medium', 'question_type': 'prelims', 'year': 2022
                    },
                    
                    # Economics Questions
                    {
                        'subject_id': 5, 'topic_id': 9,
                        'question_text': 'What does GDP stand for?',
                        'option_a': 'Gross Domestic Product', 'option_b': 'General Development Program', 'option_c': 'Global Development Project', 'option_d': 'Gross Development Plan',
                        'correct_answer': 'A', 'explanation': 'GDP stands for Gross Domestic Product, which measures the total economic output of a country.',
                        'difficulty': 'easy', 'question_type': 'prelims', 'year': 2018
                    },
                    {
                        'subject_id': 5, 'topic_id': 10,
                        'question_text': 'The Finance Commission is constituted every how many years?',
                        'option_a': '3 years', 'option_b': '4 years', 'option_c': '5 years', 'option_d': '6 years',
                        'correct_answer': 'C', 'explanation': 'The Finance Commission is constituted every 5 years under Article 280 of the Constitution.',
                        'difficulty': 'medium', 'question_type': 'mains', 'year': 2023
                    },
                    
                    # Current Affairs
                    {
                        'subject_id': 1, 'topic_id': 1,
                        'question_text': 'The G20 Summit 2023 was held in which country?',
                        'option_a': 'Indonesia', 'option_b': 'India', 'option_c': 'Italy', 'option_d': 'Saudi Arabia',
                        'correct_answer': 'B', 'explanation': 'The G20 Summit 2023 was held in New Delhi, India under India\'s presidency.',
                        'difficulty': 'easy', 'question_type': 'prelims', 'year': 2023
                    }
                ]
                
                for question_data in questions_data:
                    question = Question(**question_data)
                    db.session.add(question)
                
                db.session.commit()
            
            print("Database initialized with sample data")

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    
    if not username or not password:
        flash("Please enter both username and password")
        return redirect(url_for('home'))
    
    user = User.query.filter_by(username=username).first()
    
    if user and user.check_password(password):
        session['user_id'] = user.id
        session['username'] = user.username
        return redirect(url_for('dashboard'))
    else:
        flash("Invalid credentials. Please try again.")
        return redirect(url_for('home'))

@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        flash("Please login to access the dashboard")
        return redirect(url_for('home'))
    
    username = session.get('username')
    user = db.session.get(User, session['user_id'])
    user.update_streak()  # Update user streak
    
    # Get statistics
    total_notes = Note.query.filter_by(user_id=user.id).count()
    total_quiz_attempts = QuizAttempt.query.filter_by(user_id=user.id).count()
    correct_answers = QuizAttempt.query.filter_by(user_id=user.id, is_correct=True).count()
    accuracy = (correct_answers / total_quiz_attempts * 100) if total_quiz_attempts > 0 else 0
    
    # Recent study sessions
    recent_sessions = StudySession.query.filter_by(user_id=user.id).order_by(StudySession.created_at.desc()).limit(5).all()
    
    # Upcoming time slots
    upcoming_slots = TimeSlot.query.filter(
        TimeSlot.user_id == user.id,
        TimeSlot.start_time > datetime.now(timezone.utc),
        TimeSlot.is_completed == False
    ).order_by(TimeSlot.start_time).limit(3).all()
    
    dashboard_data = {
        'total_users': User.query.count(),
        'user_id': user.id,
        'member_since': user.created_at.strftime('%B %Y'),
        'streak_count': user.streak_count,
        'total_study_time': user.total_study_time,
        'total_notes': total_notes,
        'total_quiz_attempts': total_quiz_attempts,
        'accuracy': round(accuracy, 1),
        'recent_sessions': recent_sessions,
        'upcoming_slots': upcoming_slots
    }
    
    return render_template("dashboard.html", username=username, data=dashboard_data)

@app.route("/profile")
def profile():
    if 'user_id' not in session:
        flash("Please login to access your profile")
        return redirect(url_for('home'))
    
    user = db.session.get(User, session['user_id'])
    return render_template("profile.html", user=user)

@app.route("/notes/add", methods=["GET", "POST"])
def add_note():
    if 'user_id' not in session:
        flash("Please login to add notes")
        return redirect(url_for('home'))
    
    user_id = session['user_id']
    subjects = Subject.query.all()
    
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        subject_name = request.form.get("subject")
        topic_name = request.form.get("topic")
        tags = request.form.get("tags")
        file = request.files.get("file")
        
        # Handle file upload and OCR
        file_path = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to filename to avoid conflicts
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Extract text from image or PDF
            if file_path.lower().endswith(('png', 'jpg', 'jpeg', 'bmp', 'tiff', 'pdf')):
                extracted_text = extract_text_from_image(file_path)
                if extracted_text and "Error" not in extracted_text:
                    content += "\n\n" + extracted_text
                else:
                    # Add a note about the uploaded file if OCR fails
                    content += f"\n\n[File uploaded: {file.filename}]\n{extracted_text}"
        
        # Find subject and topic
        subject = Subject.query.filter_by(name=subject_name).first()
        topic = None
        if subject:
            topic = Topic.query.filter_by(subject_id=subject.id, name=topic_name).first()
        
        # Create note
        new_note = Note(
            user_id=user_id,
            title=title,
            content=content,
            subject=subject_name,
            topic=topic_name,
            tags=tags,
            file_path=file_path,
            is_scanned=bool(file_path)
        )
        db.session.add(new_note)
        db.session.commit()
        flash("Note added successfully")
        return redirect(url_for('dashboard'))
    
    return render_template("add_note.html", subjects=subjects)

@app.route("/notes/view")
def view_notes():
    if 'user_id' not in session:
        flash("Please login to view notes")
        return redirect(url_for('home'))
    
    user_id = session['user_id']
    
    # Get filter parameters
    subject_filter = request.args.get('subject', '')
    topic_filter = request.args.get('topic', '')
    search_query = request.args.get('search', '')
    
    # Build query
    query = Note.query.filter_by(user_id=user_id)
    
    if subject_filter:
        query = query.filter_by(subject=subject_filter)
    if topic_filter:
        query = query.filter_by(topic=topic_filter)
    if search_query:
        query = query.filter(
            (Note.title.contains(search_query)) |
            (Note.content.contains(search_query)) |
            (Note.tags.contains(search_query))
        )
    
    notes = query.order_by(Note.updated_at.desc()).all()
    subjects = Subject.query.all()
    
    # Convert notes to JSON-serializable format
    notes_json = []
    for note in notes:
        notes_json.append({
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'subject': note.subject,
            'topic': note.topic,
            'tags': note.tags or '',
            'created_at': note.created_at.isoformat(),
            'updated_at': note.updated_at.isoformat(),
            'is_scanned': note.is_scanned
        })
    
    return render_template("view_notes.html", notes=notes, notes_json=notes_json, subjects=subjects, 
                         subject_filter=subject_filter, topic_filter=topic_filter, 
                         search_query=search_query)

@app.route("/notes/edit/<int:note_id>", methods=["GET", "POST"])
def edit_note(note_id):
    if 'user_id' not in session:
        flash("Please login to edit notes")
        return redirect(url_for('home'))
    
    note = Note.query.filter_by(id=note_id, user_id=session['user_id']).first()
    if not note:
        flash("Note not found")
        return redirect(url_for('view_notes'))
    
    subjects = Subject.query.all()
    
    if request.method == "POST":
        note.title = request.form.get("title")
        note.content = request.form.get("content")
        note.subject = request.form.get("subject")
        note.topic = request.form.get("topic")
        note.tags = request.form.get("tags")
        note.updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        flash("Note updated successfully")
        return redirect(url_for('view_notes'))
    
    return render_template("edit_note.html", note=note, subjects=subjects)

@app.route("/notes/delete/<int:note_id>", methods=["POST"])
def delete_note(note_id):
    if 'user_id' not in session:
        flash("Please login to delete notes")
        return redirect(url_for('home'))
    
    note = Note.query.filter_by(id=note_id, user_id=session['user_id']).first()
    if note:
        db.session.delete(note)
        db.session.commit()
        flash("Note deleted successfully")
    else:
        flash("Note not found")
    
    return redirect(url_for('view_notes'))

@app.route("/notes/add-samples")
def add_sample_notes():
    if 'user_id' not in session:
        flash("Please login to add sample notes")
        return redirect(url_for('home'))
    
    user_id = session['user_id']
    
    # Check if user already has notes
    existing_notes = Note.query.filter_by(user_id=user_id).count()
    if existing_notes > 5:
        flash("You already have notes. Sample notes not added.")
        return redirect(url_for('view_notes'))
    
    # Sample notes data
    sample_notes = [
        {
            'title': 'Indian Constitution - Key Features',
            'subject': 'Polity',
            'topic': 'Fundamental Rights',
            'content': '''Key Features of Indian Constitution:

1. Written Constitution: The Indian Constitution is the longest written constitution in the world.

2. Federal Structure: India follows a federal system with a strong center.

3. Parliamentary Government: India has adopted the Westminster model of parliamentary government.

4. Fundamental Rights: Articles 14-32 guarantee fundamental rights to citizens.

5. Directive Principles: Articles 36-51 provide guidelines for governance.

6. Independent Judiciary: The Constitution provides for an independent judiciary.

7. Secular State: India is declared as a secular state.

Important Articles:
- Article 14: Right to Equality
- Article 19: Right to Freedom
- Article 21: Right to Life and Personal Liberty
- Article 32: Right to Constitutional Remedies''',
            'tags': 'constitution, fundamental rights, polity, upsc'
        },
        {
            'title': 'Ancient India - Mauryan Empire',
            'subject': 'History',
            'topic': 'Ancient India',
            'content': '''Mauryan Empire (322-185 BCE):

Founder: Chandragupta Maurya (322 BCE)
Capital: Pataliputra (modern Patna)

Important Rulers:
1. Chandragupta Maurya (322-297 BCE)
   - Founded the empire
   - Defeated Seleucus Nicator
   - Mentioned in Arthashastra by Kautilya

2. Bindusara (297-273 BCE)
   - Known as Amitraghata (slayer of enemies)
   - Extended empire to Deccan

3. Ashoka the Great (273-232 BCE)
   - Greatest Mauryan ruler
   - Embraced Buddhism after Kalinga War
   - Rock Edicts and Pillar Edicts
   - Promoted Dhamma

Administration:
- Highly centralized
- Divided into provinces
- Efficient espionage system
- Well-organized army

Economic Features:
- Agriculture was the backbone
- Trade and commerce flourished
- State control over mines and forests''',
            'tags': 'mauryan empire, chandragupta, ashoka, ancient india'
        },
        {
            'title': 'Indian Economy - GDP and Growth',
            'subject': 'Economics',
            'topic': 'Economic Development',
            'content': '''Indian Economy - GDP and Growth:

Gross Domestic Product (GDP):
- GDP is the total monetary value of all goods and services produced within a country
- India is the 5th largest economy by nominal GDP
- 3rd largest by Purchasing Power Parity (PPP)

Economic Growth:
- India's average GDP growth: 6-7% annually
- Target growth rate: 8-9% for developed nation status
- Growth drivers: Services, Manufacturing, Agriculture

Sectors of Indian Economy:
1. Primary Sector (Agriculture): ~16% of GDP
2. Secondary Sector (Industry): ~30% of GDP
3. Tertiary Sector (Services): ~54% of GDP

Challenges:
- Income inequality
- Unemployment
- Infrastructure deficit
- Rural-urban divide

Government Initiatives:
- Make in India
- Digital India
- Atmanirbhar Bharat
- PLI Schemes

Key Economic Indicators:
- Per capita income: ~$2,500
- Inflation rate: 4-6%
- Fiscal deficit: ~6% of GDP''',
            'tags': 'gdp, economic growth, indian economy, upsc'
        },
        {
            'title': 'Geography - Climate of India',
            'subject': 'Geography',
            'topic': 'Physical Geography',
            'content': '''Climate of India:

Type: Tropical Monsoon Climate
ISO Classification: Köppen Climate Classification

Factors Affecting Climate:
1. Latitude: 8°4' to 37°6' North
2. Altitude: Sea level to 8,848m (K2)
3. Distance from sea
4. Relief features

Seasons in India:
1. Winter (December-February)
   - Northeast monsoon
   - Clear skies
   - Temperature: 10-15°C

2. Summer (March-May)
   - High temperature
   - Loo winds in North India
   - Temperature: 35-45°C

3. Monsoon (June-September)
   - Southwest monsoon
   - 75% of annual rainfall
   - Vital for agriculture

4. Post-Monsoon (October-November)
   - Retreating monsoon
   - Cyclones in eastern coast

Monsoon System:
- Southwest Monsoon: June-September
- Northeast Monsoon: October-December
- Arabian Sea Branch and Bay of Bengal Branch

Rainfall Distribution:
- Highest: Mawsynram, Meghalaya (11,871 mm)
- Lowest: Jaisalmer, Rajasthan (164 mm)
- National Average: 1,170 mm''',
            'tags': 'climate, monsoon, geography, physical geography'
        },
        {
            'title': 'Current Affairs - G20 Summit 2023',
            'subject': 'General Studies',
            'topic': 'Current Affairs',
            'content': '''G20 Summit 2023 - New Delhi:

Date: September 9-10, 2023
Venue: Bharat Mandapam, New Delhi
Theme: "Vasudhaiva Kutumbakam" (One Earth, One Family, One Future)

Key Outcomes:
1. New Delhi Leaders' Declaration
2. African Union became permanent member
3. India-Middle East-Europe Economic Corridor
4. Digital transformation initiatives

India's G20 Presidency Priorities:
1. Green Development
2. LiFE (Lifestyle for Environment)
3. Women-led Development
4. Digital Transformation
5. Health and Well-being

Major Agreements:
- Sustainable Development Goals
- Climate action commitments
- Food and fertilizer security
- Cryptocurrency regulation framework

India's Achievements:
- Successfully hosted 200+ meetings
- Consensus on complex global issues
- Enhanced India's global leadership
- Promoted multilateralism

Significance for India:
- Enhanced diplomatic standing
- Economic partnerships
- Technology cooperation
- Cultural soft power projection

Next G20 Presidency: Brazil (2024)''',
            'tags': 'g20, current affairs, diplomacy, international relations'
        }
    ]
    
    # Add sample notes
    added_count = 0
    for note_data in sample_notes:
        # Check if note with same title already exists for this user
        existing = Note.query.filter_by(user_id=user_id, title=note_data['title']).first()
        if not existing:
            note = Note(
                user_id=user_id,
                title=note_data['title'],
                subject=note_data['subject'],
                topic=note_data['topic'],
                content=note_data['content'],
                tags=note_data['tags'],
                is_scanned=False
            )
            db.session.add(note)
            added_count += 1
    
    db.session.commit()
    flash(f"Added {added_count} sample notes successfully!")
    return redirect(url_for('view_notes'))

@app.route("/quizzes/attempt", methods=["GET", "POST"])
def attempt_quiz():
    if 'user_id' not in session:
        flash("Please login to attempt quizzes")
        return redirect(url_for('home'))
    
    user = db.session.get(User, session['user_id'])
    subjects = Subject.query.all()
    selected_subject = None
    selected_topic = None
    questions = []
    user_answers = {}
    
    if request.method == "POST":
        selected_subject = request.form.get("subject")
        selected_topic = request.form.get("topic")
        quiz_type = request.form.get("quiz_type", "all")
        difficulty = request.form.get("difficulty", "all")
        year_filter = request.form.get("year_filter", "")
        
        # Check if this is a quiz submission (has answers) or quiz setup
        is_submission = any(key.startswith('answer_') for key in request.form.keys())
        
        if is_submission:
            # Process quiz submission
            quiz_session_id = str(uuid.uuid4())
            correct_count = 0
            total_questions = 0
            
            for key, value in request.form.items():
                if key.startswith('answer_') and value:
                    question_id = int(key.replace('answer_', ''))
                    question = Question.query.get(question_id)
                    if question:
                        total_questions += 1
                        is_correct = (value == question.correct_answer)
                        if is_correct:
                            correct_count += 1
                        
                        attempt = QuizAttempt(
                            user_id=user.id,
                            question_id=question_id,
                            selected_answer=value,
                            is_correct=is_correct,
                            time_taken=random.randint(30, 120),
                            quiz_session_id=quiz_session_id
                        )
                        db.session.add(attempt)
            
            db.session.commit()
            
            # Calculate score and show result
            score_percentage = (correct_count / total_questions * 100) if total_questions > 0 else 0
            flash(f"Quiz completed! Score: {correct_count}/{total_questions} ({score_percentage:.1f}%)")
            return redirect(url_for('dashboard'))
            
        else:
            # Setup quiz with filters
            if selected_subject and selected_topic:
                subject = Subject.query.filter_by(name=selected_subject).first()
                if subject:
                    topic = Topic.query.filter_by(subject_id=subject.id, name=selected_topic).first()
                    if topic:
                        # Build query with filters
                        query = Question.query.filter_by(topic_id=topic.id)
                        
                        if quiz_type != "all":
                            query = query.filter_by(question_type=quiz_type)
                        if difficulty != "all":
                            query = query.filter_by(difficulty=difficulty)
                        if year_filter:
                            query = query.filter_by(year=int(year_filter))
                        
                        questions = query.all()
                        
                        if not questions:
                            flash("No questions found for the selected criteria. Try different filters.")
    
    return render_template("attempt_quiz.html", 
                         subjects=subjects, 
                         selected_subject=selected_subject, 
                         selected_topic=selected_topic, 
                         questions=questions, 
                         user_answers=user_answers)

@app.route("/study-sessions/log", methods=["GET", "POST"])
def log_study_session():
    if 'user_id' not in session:
        flash("Please login to log study sessions")
        return redirect(url_for('home'))
    
    user = db.session.get(User, session['user_id'])
    subjects = Subject.query.all()
    
    if request.method == "POST":
        subject_name = request.form.get("subject")
        topic_name = request.form.get("topic")
        start_time_str = request.form.get("start_time")
        end_time_str = request.form.get("end_time")
        activity_type = request.form.get("activity_type")
        
        # Parse times
        start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
        end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M")
        duration = (end_time - start_time).total_seconds() / 60  # duration in minutes
        
        # Create study session
        session = StudySession(
            user_id=user.id,
            subject=subject_name,
            topic=topic_name,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            activity_type=activity_type
        )
        db.session.add(session)
        db.session.commit()
        
        # Update total study time
        user.total_study_time += duration
        db.session.commit()
        
        flash("Study session logged successfully")
        return redirect(url_for('dashboard'))
    
    return render_template("log_study.html", subjects=subjects)

@app.route("/settings")
def settings():
    if 'user_id' not in session:
        flash("Please login to access settings")
        return redirect(url_for('home'))
    
    username = session.get('username')
    return render_template("settings.html", username=username)

@app.route("/time-slots", methods=["GET", "POST"])
def time_slots():
    if 'user_id' not in session:
        flash("Please login to manage time slots")
        return redirect(url_for('home'))
    
    user = db.session.get(User, session['user_id'])
    subjects = Subject.query.all()
    
    if request.method == "POST":
        title = request.form.get("title")
        subject_name = request.form.get("subject")
        start_time_str = request.form.get("start_time")
        end_time_str = request.form.get("end_time")
        description = request.form.get("description")
        
        # Parse times
        start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
        end_time = datetime.strptime(end_time_str, "%Y-%m-%dT%H:%M")
        
        # Create time slot
        slot = TimeSlot(
            user_id=user.id,
            title=title,
            subject=subject_name,
            start_time=start_time,
            end_time=end_time,
            description=description
        )
        db.session.add(slot)
        db.session.commit()
        
        flash("Time slot scheduled successfully")
        return redirect(url_for('time_slots'))
    
    # Get user's time slots
    slots = TimeSlot.query.filter_by(user_id=user.id).order_by(TimeSlot.start_time).all()
    
    return render_template("time_slots.html", subjects=subjects, slots=slots)

@app.route("/statistics")
def statistics():
    if 'user_id' not in session:
        flash("Please login to view statistics")
        return redirect(url_for('home'))
    
    user = db.session.get(User, session['user_id'])
    
    # Quiz statistics
    total_attempts = QuizAttempt.query.filter_by(user_id=user.id).count()
    correct_attempts = QuizAttempt.query.filter_by(user_id=user.id, is_correct=True).count()
    accuracy = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0
    
    # Subject-wise performance
    subject_stats = db.session.query(
        Question.subject_id,
        Subject.name,
        db.func.count(QuizAttempt.id).label('total'),
        db.func.sum(db.case((QuizAttempt.is_correct == True, 1), else_=0)).label('correct')
    ).join(
        Question, QuizAttempt.question_id == Question.id
    ).join(
        Subject, Question.subject_id == Subject.id
    ).filter(
        QuizAttempt.user_id == user.id
    ).group_by(Question.subject_id, Subject.name).all()
    
    # Study time by subject
    study_stats = db.session.query(
        StudySession.subject,
        db.func.sum(StudySession.duration).label('total_time')
    ).filter(
        StudySession.user_id == user.id
    ).group_by(StudySession.subject).all()
    
    # Recent activity (last 7 days)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_activity = StudySession.query.filter(
        StudySession.user_id == user.id,
        StudySession.created_at >= week_ago
    ).order_by(StudySession.created_at.desc()).all()
    
    stats_data = {
        'total_attempts': total_attempts,
        'correct_attempts': correct_attempts,
        'accuracy': round(accuracy, 1),
        'streak_count': user.streak_count,
        'total_study_time': user.total_study_time,
        'subject_stats': subject_stats,
        'study_stats': study_stats,
        'recent_activity': recent_activity
    }
    
    return render_template("statistics.html", stats=stats_data)

@app.route("/api/subjects")
def api_subjects():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    subjects = Subject.query.all()
    return jsonify([{'id': s.id, 'name': s.name, 'description': s.description} for s in subjects])

@app.route("/api/topics/<int:subject_id>")
def api_topics(subject_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    topics = Topic.query.filter_by(subject_id=subject_id).all()
    return jsonify([{'id': t.id, 'name': t.name, 'description': t.description} for t in topics])

@app.route("/previous-year-questions", methods=["GET", "POST"])
def previous_year_questions():
    if 'user_id' not in session:
        flash("Please login to view previous year questions")
        return redirect(url_for('home'))
    
    subjects = Subject.query.all()
    
    # Get filter parameters
    selected_subject = request.args.get('subject') or request.form.get('subject')
    selected_topic = request.args.get('topic') or request.form.get('topic')
    selected_year = request.args.get('year') or request.form.get('year')
    question_type = request.args.get('type') or request.form.get('type', 'all')
    
    # Get available years for dropdown
    available_years = db.session.query(Question.year).filter(Question.year.isnot(None)).distinct().order_by(Question.year.desc()).all()
    available_years = [year[0] for year in available_years if year[0]]
    
    questions = []
    topics = []
    
    if selected_subject:
        subject = Subject.query.filter_by(name=selected_subject).first()
        if subject:
            topics = Topic.query.filter_by(subject_id=subject.id).all()
            
            # Build query for previous year questions
            query = Question.query.filter(
                Question.subject_id == subject.id,
                Question.year.isnot(None)  # Only questions with year data
            )
            
            if selected_topic:
                topic = Topic.query.filter_by(subject_id=subject.id, name=selected_topic).first()
                if topic:
                    query = query.filter_by(topic_id=topic.id)
            
            if selected_year:
                query = query.filter_by(year=int(selected_year))
            
            if question_type != 'all':
                query = query.filter_by(question_type=question_type)
            
            questions = query.order_by(Question.year.desc(), Question.id).all()
    
    # Group questions by year and topic for better organization
    grouped_questions = {}
    for question in questions:
        year_key = question.year or 'Unknown'
        topic_key = question.topic.name if question.topic else 'Unknown Topic'
        
        if year_key not in grouped_questions:
            grouped_questions[year_key] = {}
        if topic_key not in grouped_questions[year_key]:
            grouped_questions[year_key][topic_key] = []
        
        grouped_questions[year_key][topic_key].append(question)
    
    return render_template("previous_year_questions.html", 
                         subjects=subjects,
                         topics=topics,
                         selected_subject=selected_subject,
                         selected_topic=selected_topic,
                         selected_year=selected_year,
                         question_type=question_type,
                         available_years=available_years,
                         questions=questions,
                         grouped_questions=grouped_questions)

@app.route("/api/questions")
def api_questions():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    subject_id = request.args.get('subject_id')
    topic_id = request.args.get('topic_id')
    question_type = request.args.get('type', 'all')  # mains, prelims, or all
    difficulty = request.args.get('difficulty', 'all')  # easy, medium, hard, or all
    year = request.args.get('year')
    
    query = Question.query
    
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if topic_id:
        query = query.filter_by(topic_id=topic_id)
    if question_type != 'all':
        query = query.filter_by(question_type=question_type)
    if difficulty != 'all':
        query = query.filter_by(difficulty=difficulty)
    if year:
        query = query.filter_by(year=year)
    
    questions = query.all()
    
    return jsonify([{
        'id': q.id,
        'question_text': q.question_text,
        'option_a': q.option_a,
        'option_b': q.option_b,
        'option_c': q.option_c,
        'option_d': q.option_d,
        'correct_answer': q.correct_answer,
        'explanation': q.explanation,
        'difficulty': q.difficulty,
        'question_type': q.question_type,
        'year': q.year
    } for q in questions])

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully")
    return redirect(url_for('home'))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if not username or not password:
            flash("Please enter both username and password")
            return render_template("register.html")
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash("Username already exists. Please choose a different one.")
            return render_template("register.html")
        
        # Create new user
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash("Registration successful! Please login.")
        return redirect(url_for('home'))
    
    return render_template("register.html")

# Spotify Authentication Routes
@app.route("/spotify/login")
def spotify_login():
    if 'user_id' not in session:
        flash("Please login first")
        return redirect(url_for('home'))
    
    if DEMO_MODE:
        # Demo mode - simulate successful connection
        session['spotify_access_token'] = 'demo_token'
        session['spotify_demo_mode'] = True
        flash("Demo mode: Simulated Spotify connection successful!")
        return redirect(url_for('dashboard'))
    
    # Real Spotify integration
    if SPOTIFY_CLIENT_ID == "your_spotify_client_id_here":
        flash("Please set up your Spotify API credentials first. Check SPOTIFY_SETUP.md")
        return redirect(url_for('dashboard'))
    
    # Generate Spotify authorization URL
    params = {
        'client_id': SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'scope': SPOTIFY_SCOPE,
        'show_dialog': 'true'
    }
    
    auth_url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)

@app.route("/spotify/callback")
def spotify_callback():
    if 'user_id' not in session:
        flash("Please login first")
        return redirect(url_for('home'))
    
    code = request.args.get('code')
    
    if code:
        # Exchange code for access token
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': SPOTIFY_REDIRECT_URI,
        }
        
        # Encode client credentials
        client_creds = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
        client_creds_b64 = base64.b64encode(client_creds.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {client_creds_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post('https://accounts.spotify.com/api/token', data=token_data, headers=headers)
        
        if response.status_code == 200:
            token_info = response.json()
            session['spotify_access_token'] = token_info['access_token']
            session['spotify_refresh_token'] = token_info.get('refresh_token')
            flash("Successfully connected to Spotify!")
            return redirect(url_for('dashboard'))
        else:
            flash("Failed to connect to Spotify")
            return redirect(url_for('dashboard'))
    else:
        flash("Spotify authentication failed")
        return redirect(url_for('dashboard'))

# Spotify API Routes
@app.route("/api/spotify/playlists")
def get_spotify_playlists():
    if 'spotify_access_token' not in session:
        return jsonify({'error': 'Not authenticated with Spotify'}), 401
    
    if session.get('spotify_demo_mode'):
        # Return demo playlists
        demo_playlists = {
            "items": [
                {
                    "name": "My Chill Vibes",
                    "uri": "spotify:playlist:demo1",
                    "tracks": {"total": 25}
                },
                {
                    "name": "Workout Hits",
                    "uri": "spotify:playlist:demo2",
                    "tracks": {"total": 40}
                },
                {
                    "name": "Focus Music",
                    "uri": "spotify:playlist:demo3",
                    "tracks": {"total": 30}
                },
                {
                    "name": "Party Mix",
                    "uri": "spotify:playlist:demo4",
                    "tracks": {"total": 50}
                },
                {
                    "name": "Throwback Classics",
                    "uri": "spotify:playlist:demo5",
                    "tracks": {"total": 35}
                }
            ]
        }
        return jsonify(demo_playlists)
    
    headers = {'Authorization': f'Bearer {session["spotify_access_token"]}'}
    response = requests.get('https://api.spotify.com/v1/me/playlists', headers=headers)
    
    if response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify({'error': 'Failed to fetch playlists'}), 500

@app.route("/api/spotify/play", methods=['POST'])
def spotify_play():
    if 'spotify_access_token' not in session:
        return jsonify({'error': 'Not authenticated with Spotify'}), 401
    
    if session.get('spotify_demo_mode'):
        # Demo mode - simulate successful play
        return jsonify({'success': True, 'demo': True})
    
    data = request.json
    headers = {'Authorization': f'Bearer {session["spotify_access_token"]}', 'Content-Type': 'application/json'}
    
    play_data = {}
    if 'playlist_uri' in data:
        play_data['context_uri'] = data['playlist_uri']
    elif 'track_uri' in data:
        play_data['uris'] = [data['track_uri']]
    
    response = requests.put('https://api.spotify.com/v1/me/player/play', json=play_data, headers=headers)
    
    if response.status_code in [200, 204]:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to play music', 'details': response.text}), 500

@app.route("/api/spotify/pause", methods=['POST'])
def spotify_pause():
    if 'spotify_access_token' not in session:
        return jsonify({'error': 'Not authenticated with Spotify'}), 401
    
    if session.get('spotify_demo_mode'):
        return jsonify({'success': True, 'demo': True})
    
    headers = {'Authorization': f'Bearer {session["spotify_access_token"]}'}
    response = requests.put('https://api.spotify.com/v1/me/player/pause', headers=headers)
    
    if response.status_code in [200, 204]:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to pause music'}), 500

@app.route("/api/spotify/next", methods=['POST'])
def spotify_next():
    if 'spotify_access_token' not in session:
        return jsonify({'error': 'Not authenticated with Spotify'}), 401
    
    if session.get('spotify_demo_mode'):
        return jsonify({'success': True, 'demo': True})
    
    headers = {'Authorization': f'Bearer {session["spotify_access_token"]}'}
    response = requests.post('https://api.spotify.com/v1/me/player/next', headers=headers)
    
    if response.status_code in [200, 204]:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to skip to next track'}), 500

@app.route("/api/spotify/previous", methods=['POST'])
def spotify_previous():
    if 'spotify_access_token' not in session:
        return jsonify({'error': 'Not authenticated with Spotify'}), 401
    
    if session.get('spotify_demo_mode'):
        return jsonify({'success': True, 'demo': True})
    
    headers = {'Authorization': f'Bearer {session["spotify_access_token"]}'}
    response = requests.post('https://api.spotify.com/v1/me/player/previous', headers=headers)
    
    if response.status_code in [200, 204]:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to skip to previous track'}), 500

@app.route("/api/spotify/current")
def spotify_current():
    if 'spotify_access_token' not in session:
        return jsonify({'error': 'Not authenticated with Spotify'}), 401
    
    if session.get('spotify_demo_mode'):
        # Return demo current track
        demo_tracks = [
            {'name': 'Watermelon Sugar', 'artists': [{'name': 'Harry Styles'}], 'is_playing': True},
            {'name': 'Blinding Lights', 'artists': [{'name': 'The Weeknd'}], 'is_playing': True},
            {'name': 'Levitating', 'artists': [{'name': 'Dua Lipa'}], 'is_playing': True},
            {'name': 'Good 4 U', 'artists': [{'name': 'Olivia Rodrigo'}], 'is_playing': True}
        ]
        import random
        demo_track = random.choice(demo_tracks)
        return jsonify({'item': demo_track, 'is_playing': demo_track['is_playing']})
    
    headers = {'Authorization': f'Bearer {session["spotify_access_token"]}'}
    response = requests.get('https://api.spotify.com/v1/me/player/currently-playing', headers=headers)
    
    if response.status_code == 200:
        return jsonify(response.json())
    elif response.status_code == 204:
        return jsonify({'is_playing': False})
    else:
        return jsonify({'error': 'Failed to get current track'}), 500

@app.route("/api/spotify/devices")
def spotify_devices():
    if 'spotify_access_token' not in session:
        return jsonify({'error': 'Not authenticated with Spotify'}), 401
    
    headers = {'Authorization': f'Bearer {session["spotify_access_token"]}'}
    response = requests.get('https://api.spotify.com/v1/me/player/devices', headers=headers)
    
    if response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify({'error': 'Failed to get devices'}), 500

# Task Management Routes
@app.route("/api/tasks", methods=["GET", "POST"])
def api_tasks():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    
    if request.method == "POST":
        data = request.json
        task = Task(
            user_id=user_id,
            title=data.get('title'),
            description=data.get('description', ''),
            priority=data.get('priority', 'medium'),
            category=data.get('category', 'general'),
            due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') and data.get('due_date').strip() else None
        )
        db.session.add(task)
        db.session.commit()
        
        return jsonify({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'priority': task.priority,
            'category': task.category,
            'is_completed': task.is_completed,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'created_at': task.created_at.isoformat()
        })
    
    # GET request
    tasks = Task.query.filter_by(user_id=user_id).order_by(Task.created_at.desc()).all()
    return jsonify([{
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'priority': task.priority,
        'category': task.category,
        'is_completed': task.is_completed,
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'created_at': task.created_at.isoformat()
    } for task in tasks])

@app.route("/api/tasks/<int:task_id>", methods=["PUT", "DELETE"])
def api_task_detail(task_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    task = Task.query.filter_by(id=task_id, user_id=session['user_id']).first()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    if request.method == "PUT":
        data = request.json
        task.title = data.get('title', task.title)
        task.description = data.get('description', task.description)
        task.priority = data.get('priority', task.priority)
        task.category = data.get('category', task.category)
        task.is_completed = data.get('is_completed', task.is_completed)
        
        if data.get('due_date') and data.get('due_date').strip():
            task.due_date = datetime.fromisoformat(data['due_date'])
        elif data.get('due_date') == '':
            task.due_date = None
        
        if task.is_completed and not task.completed_at:
            task.completed_at = datetime.now(timezone.utc)
        elif not task.is_completed:
            task.completed_at = None
        
        db.session.commit()
        
        return jsonify({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'priority': task.priority,
            'category': task.category,
            'is_completed': task.is_completed,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'created_at': task.created_at.isoformat()
        })
    
    # DELETE request
    db.session.delete(task)
    db.session.commit()
    return jsonify({'message': 'Task deleted successfully'})

# Reminder Routes
@app.route("/api/reminders", methods=["GET", "POST"])
def api_reminders():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    
    if request.method == "POST":
        data = request.json
        reminder = Reminder(
            user_id=user_id,
            title=data.get('title'),
            message=data.get('message', ''),
            reminder_time=datetime.fromisoformat(data['reminder_time']),
            reminder_type=data.get('reminder_type', 'general')
        )
        db.session.add(reminder)
        db.session.commit()
        
        return jsonify({
            'id': reminder.id,
            'title': reminder.title,
            'message': reminder.message,
            'reminder_time': reminder.reminder_time.isoformat(),
            'reminder_type': reminder.reminder_type,
            'is_active': reminder.is_active,
            'created_at': reminder.created_at.isoformat()
        })
    
    # GET request - only active reminders
    reminders = Reminder.query.filter_by(user_id=user_id, is_active=True).order_by(Reminder.reminder_time).all()
    return jsonify([{
        'id': reminder.id,
        'title': reminder.title,
        'message': reminder.message,
        'reminder_time': reminder.reminder_time.isoformat(),
        'reminder_type': reminder.reminder_type,
        'is_active': reminder.is_active,
        'created_at': reminder.created_at.isoformat()
    } for reminder in reminders])

@app.route("/api/reminders/<int:reminder_id>", methods=["DELETE"])
def api_reminder_delete(reminder_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    reminder = Reminder.query.filter_by(id=reminder_id, user_id=session['user_id']).first()
    if not reminder:
        return jsonify({'error': 'Reminder not found'}), 404
    
    reminder.is_active = False
    db.session.commit()
    return jsonify({'message': 'Reminder disabled successfully'})

# Focus Session Routes
@app.route("/api/focus-session", methods=["POST"])
def api_focus_session():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    focus_session = FocusSession(
        user_id=session['user_id'],
        session_type=data.get('session_type', 'focus'),
        duration=data.get('duration'),
        start_time=datetime.fromisoformat(data['start_time']),
        end_time=datetime.fromisoformat(data['end_time']) if data.get('end_time') else None,
        subject=data.get('subject', ''),
        notes=data.get('notes', '')
    )
    db.session.add(focus_session)
    db.session.commit()
    
    # Update user's total study time
    user = db.session.get(User, session['user_id'])
    user.total_study_time += (focus_session.duration // 60)  # Convert to minutes
    db.session.commit()
    
    return jsonify({'message': 'Focus session saved successfully', 'id': focus_session.id})

@app.route("/api/focus-sessions")
def api_focus_sessions():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    sessions = FocusSession.query.filter_by(user_id=session['user_id']).order_by(FocusSession.created_at.desc()).limit(10).all()
    return jsonify([{
        'id': session.id,
        'session_type': session.session_type,
        'duration': session.duration,
        'start_time': session.start_time.isoformat(),
        'end_time': session.end_time.isoformat() if session.end_time else None,
        'subject': session.subject,
        'notes': session.notes,
        'created_at': session.created_at.isoformat()
    } for session in sessions])

# Diary Routes
@app.route("/diary", methods=["GET"])
def diary():
    if 'user_id' not in session:
        flash("Please login to access your diary")
        return redirect(url_for('home'))
    
    entries = DiaryEntry.query.filter_by(user_id=session['user_id']).order_by(DiaryEntry.date.desc()).all()
    return render_template("diary.html", entries=entries)

@app.route("/diary/add", methods=["POST"])
def add_diary_entry():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    entry = DiaryEntry(
        user_id=session['user_id'],
        title=data.get('title'),
        content=data.get('content'),
        mood=data.get('mood', 'neutral')
    )
    db.session.add(entry)
    db.session.commit()
    
    return jsonify({
        'id': entry.id,
        'title': entry.title,
        'content': entry.content,
        'mood': entry.mood,
        'date': entry.date.isoformat(),
        'created_at': entry.created_at.isoformat()
    })

@app.route("/diary/edit/<int:entry_id>", methods=["PUT"])
def edit_diary_entry(entry_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    entry = DiaryEntry.query.filter_by(id=entry_id, user_id=session['user_id']).first()
    if not entry:
        return jsonify({'error': 'Diary entry not found'}), 404
    
    data = request.json
    entry.title = data.get('title', entry.title)
    entry.content = data.get('content', entry.content)
    entry.mood = data.get('mood', entry.mood)
    db.session.commit()
    
    return jsonify({
        'id': entry.id,
        'title': entry.title,
        'content': entry.content,
        'mood': entry.mood,
        'date': entry.date.isoformat(),
        'created_at': entry.created_at.isoformat()
    })

@app.route("/diary/delete/<int:entry_id>", methods=["DELETE"])
def delete_diary_entry(entry_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    entry = DiaryEntry.query.filter_by(id=entry_id, user_id=session['user_id']).first()
    if not entry:
        return jsonify({'error': 'Diary entry not found'}), 404
    
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'message': 'Diary entry deleted successfully'})

# Study Dashboard Route
@app.route("/study-dashboard")
def study_dashboard():
    if 'user_id' not in session:
        flash("Please login to access the study dashboard")
        return redirect(url_for('home'))
    
    username = session.get('username')
    user = db.session.get(User, session['user_id'])
    user.update_streak()  # Update user streak
    
    # Get statistics
    total_notes = Note.query.filter_by(user_id=user.id).count()
    total_quiz_attempts = QuizAttempt.query.filter_by(user_id=user.id).count()
    correct_answers = QuizAttempt.query.filter_by(user_id=user.id, is_correct=True).count()
    accuracy = (correct_answers / total_quiz_attempts * 100) if total_quiz_attempts > 0 else 0
    
    # Recent study sessions
    recent_sessions = StudySession.query.filter_by(user_id=user.id).order_by(StudySession.created_at.desc()).limit(5).all()
    
    # Upcoming time slots
    upcoming_slots = TimeSlot.query.filter(
        TimeSlot.user_id == user.id,
        TimeSlot.start_time > datetime.now(timezone.utc),
        TimeSlot.is_completed == False
    ).order_by(TimeSlot.start_time).limit(3).all()
    
    dashboard_data = {
        'total_users': User.query.count(),
        'user_id': user.id,
        'member_since': user.created_at.strftime('%B %Y'),
        'streak_count': user.streak_count,
        'total_study_time': user.total_study_time,
        'total_notes': total_notes,
        'total_quiz_attempts': total_quiz_attempts,
        'accuracy': round(accuracy, 1),
        'recent_sessions': recent_sessions,
        'upcoming_slots': upcoming_slots
    }
    
    return render_template("study_dashboard.html", username=username, data=dashboard_data)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)

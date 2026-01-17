import sys
import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from StudentDoubtResolving import EducationalAssistant

app = Flask(__name__, template_folder='templates')
CORS(app)

# Configuration
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_questions')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Video URLs
PHYSICS_VIDEO_URL = "https://s3-content-videos.s3.ap-southeast-2.amazonaws.com/physics_topic1.mp4"
AVATAR_VIDEO_URL = "https://s3-content-videos.s3.ap-southeast-2.amazonaws.com/avatar_video.mp4"

# Initialize assistant
assistant = EducationalAssistant(
    transcript_path=os.path.join(os.path.dirname(__file__), 'transcript.json'),
    api_key='AIzaSyCLpxYEdklCsjjrMa8RQaQDZcBNs3gQUio'
)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/interface')
def interface():
    return render_template('interface.html')

@app.route('/get_videos', methods=['GET'])
def get_videos():
    return jsonify({
        'physics_video': PHYSICS_VIDEO_URL,
        'avatar_video': AVATAR_VIDEO_URL
    })

@app.route('/save_question', methods=['POST'])
def handle_question():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'status': 'error', 'message': 'Empty question received'}), 400

        # Save question
        question_path = os.path.join(OUTPUT_DIR, 'user_question.txt')
        with open(question_path, 'w', encoding='utf-8') as f:
            f.write(question)

        # Generate audio response
        audio_path = os.path.join(OUTPUT_DIR, 'ai_response.wav')
        assistant.answer_to_audio(question_path, audio_path)
        
        # Get text response
        with open(question_path, 'r', encoding='utf-8') as f:
            question_text = f.read()
        response_text = assistant._handle_question(question_text) if assistant._is_question(question_text) else assistant._handle_statement(question_text)
        
        return jsonify({
            'status': 'success',
            'audio_url': f'/audio/{os.path.basename(audio_path)}',
            'response_text': response_text,
            'avatar_video': AVATAR_VIDEO_URL
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(OUTPUT_DIR, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
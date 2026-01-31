"""Pumpkin Chat - Flask API Backend"""

import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from services.reducto_service import parse_pdf
from services.openai_service import chat, analyze_document, PUMPKIN_SYSTEM_PROMPT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')
CORS(app)

# In-memory conversation storage (per session)
conversations = {}


@app.route('/')
def index():
    """Serve the chat interface."""
    return send_from_directory('static', 'index.html')


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Handle chat messages."""
    try:
        data = request.json
        message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get or create conversation history
        if session_id not in conversations:
            conversations[session_id] = []
        
        history = conversations[session_id]
        
        # Add user message to history
        history.append({"role": "user", "content": message})
        
        # Get response from OpenAI
        response = chat(history, system_prompt=PUMPKIN_SYSTEM_PROMPT)
        
        # Add assistant response to history
        history.append({"role": "assistant", "content": response})
        
        # Keep only last 20 messages to avoid token limits
        if len(history) > 20:
            conversations[session_id] = history[-20:]
        
        return jsonify({'response': response})
        
    except Exception as e:
        logger.error("Chat error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def api_upload():
    """Handle PDF uploads."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        session_id = request.form.get('session_id', 'default')
        
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are supported'}), 400
        
        # Read file bytes
        file_bytes = file.read()
        filename = file.filename
        
        logger.info("Processing upload: %s (%d bytes)", filename, len(file_bytes))
        
        # Parse with Reducto
        parsed_text = parse_pdf(file_bytes, filename)
        
        # Get or create conversation history
        if session_id not in conversations:
            conversations[session_id] = []
        
        history = conversations[session_id]
        
        # Add document context and get analysis
        response = analyze_document(parsed_text, history.copy())
        
        # Add to history
        history.append({"role": "user", "content": f"[Uploaded document: {filename}]"})
        history.append({"role": "assistant", "content": response})
        
        return jsonify({
            'response': response,
            'filename': filename,
            'parsed_length': len(parsed_text)
        })
        
    except Exception as e:
        logger.error("Upload error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear', methods=['POST'])
def api_clear():
    """Clear conversation history."""
    data = request.json or {}
    session_id = data.get('session_id', 'default')
    
    if session_id in conversations:
        del conversations[session_id]
    
    return jsonify({'status': 'cleared'})


if __name__ == '__main__':
    logger.info("🎃 Starting Pumpkin Chat...")
    print("🎃 Pumpkin Chat running at http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)

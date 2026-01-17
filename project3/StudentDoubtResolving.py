import json
import google.generativeai as genai
import re
import pyttsx3
import os

COMMON_WORDS = {
    "what", "is", "are", "the", "a", "an", "of", "to", "for", "in", "on", "and", "or", "by", "with",
    "about", "from", "at", "as", "do", "does", "did", "how", "why", "when", "where", "who", "which",
    "can", "could", "would", "should", "it", "that", "this", "these", "those"
}

class EducationalAssistant:
    def __init__(self, transcript_path, api_key):
        """Initializes assistant with full question handling capabilities"""
        with open(transcript_path, encoding="utf-8") as f:
            self.transcript = json.load(f)
        self.full_transcript_text = ' '.join(seg['text'] for seg in self.transcript).lower()
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.current_time = 0
        self.offensive_keywords = [
            "porn", "adult", "drugs", "violence", "kill", "hate", "terror", "suicide", "murder", "abuse"
        ]
        self.derivation_keywords = {'derive', 'derivation', 'formula', 'equation', 'proof', 'calculation', 'explain step by step'}
        self.terminating_keywords = ["exit", "replay", "resume", "stop"]
        self.conversation_history = []
        self.transcript_segments = [
            {"section": "Introduction", "start": 0.0, "end": 48.0},
            {"section": "Force and its Types", "start": 48.0, "end": 120.0},
            {"section": "Newton's First Law", "start": 120.0, "end": 218.0},
            {"section": "Newton's Second Law", "start": 218.0, "end": 332.0},
            {"section": "Momentum", "start": 332.0, "end": 454.0},
            {"section": "Newton's Third Law", "start": 454.0, "end": 544.0},
            {"section": "Conservation of Momentum", "start": 544.0, "end": 693.0}
        ]

    # [Keep all your existing helper methods unchanged]
    # (_get_context, _is_offensive, _is_derivation, etc.)
    def _get_context(self):
        """Gets transcript segments within ±40s of current time"""
        return [
            seg for seg in self.transcript
            if float(seg['start']) >= self.current_time - 40
            and float(seg['end']) <= self.current_time + 40
        ]

    def _is_offensive(self, text):
        """Checks for offensive content using regex pattern"""
        pattern = re.compile(r'\b(' + '|'.join(self.offensive_keywords) + r')\b', re.IGNORECASE)
        return bool(pattern.search(text))

    def _is_derivation(self, text):
        """Identifies derivation requests using keyword matching"""
        return any(kw in text.lower() for kw in self.derivation_keywords)

    def _is_question(self, text):
        """Detects question patterns using regex"""
        question_pattern = r'(what|why|how|when|where|who|which|do|does|did|is|are|can|could|would|should|define|explain)\b|[?]'
        return re.search(question_pattern, text.strip().lower()) is not None

    def _is_terminating(self, text):
        """Checks for session termination commands"""
        return any(kw in text.lower() for kw in self.terminating_keywords)

    def _is_stem_question(self, text):
        """Classifies questions using Gemini API"""
        prompt = (
            "Classify this question's subject (answer ONLY one word):\n"
            "1. physics\n2. math\n3. science\n4. other\n\n"
            f"Question: {text}"
        )
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip().lower() in ['physics', 'math', 'science']
        except Exception:
            return False

    def _is_incomplete(self, text):
        """Detects incomplete questions using multiple patterns"""
        incomplete_patterns = [
            r'\bof\s*$', r'\babout\s*$', r'\bon\s*$', r'\bin\s*$', r'\bfor\s*$', r'\bto\s*$'
        ]
        if len(text.strip().split()) < 3:
            return True
        for pat in incomplete_patterns:
            if re.search(pat, text.strip().lower()):
                return True
        words = text.strip().lower().split()
        if len(words) >= 2 and words.count(words[0]) > 1:
            return True
        unclear_patterns = [
            r'its units\??$', r'which units\??$', r'what about\??$', r'what is this\??$', r'what is that\??$'
        ]
        for pat in unclear_patterns:
            if re.search(pat, text.strip().lower()):
                return True
        return False

    def _extract_subject_words(self, text):
        """Extracts non-common words for context matching"""
        words = set(re.findall(r'\b\w+\b', text.lower()))
        return words - COMMON_WORDS

    def _context_has_subject_word(self, subject_words, context_text):
        """Checks keyword presence in context"""
        context_words = set(re.findall(r'\b\w+\b', context_text.lower()))
        return bool(subject_words & context_words)

    def _find_relevant_segment(self, subject_words):
        """Finds relevant video segment using extracted keywords"""
        for seg in self.transcript_segments:
            seg_text = ' '.join(
                s['text'] for s in self.transcript 
                if float(s['start']) >= seg['start'] 
                and float(s['end']) <= seg['end']
            ).lower()
            if self._context_has_subject_word(subject_words, seg_text):
                return seg
        return None

    def _format_response(self, text):
        """Formats responses to 3-line maximum"""
        cleaned = text.replace("", "").replace("*", "").strip()
        sentences = re.split(r'(?<=[.!?]) +', cleaned)
        return "\n".join(sentences[:3])

    def _handle_statement(self, text):
        """Handles non-question user inputs"""
        if re.search(r'\b(understand|got it|clear)\b', text):
            return "Great! Let's continue."
        elif re.search(r'\b(th?anks|thank you)\b', text):
            return "You're welcome! Let's keep going."
        else:
            return "Got your message. Ready when you are!"

    
    def _handle_question(self, text):
        """Main question processing with context-based answers"""
        if self._is_offensive(text):
            return "I'm sorry, that question is inappropriate for our educational session."
        if not self._is_stem_question(text):
            return "That question seems to be outside our focus. Let's stick to STEM topics!"
        if self._is_incomplete(text):
            return "I didn't understand your question. Could you please rephrase or clarify?"
        subject_words = self._extract_subject_words(text)
        if not subject_words:
            return "Please ask a question related to the lesson topic."

        # Check if any subject word exists in full transcript
        if not self._context_has_subject_word(subject_words, self.full_transcript_text):
            return "That question seems to be outside the current lesson scope."

        # Try to answer using full transcript context
        try:
            prompt = f"""Context: {self.full_transcript_text}
    Question: {text}
    Answer concisely (2-3 lines):"""
            response = self.model.generate_content(prompt)
            answer = self._format_response(response.text)
            if answer.strip():
                return answer
        except:
            pass

        # Fallback to general knowledge if context exists but answer failed
        try:
            prompt = f"""Answer this physics question concisely (2-3 lines):
    {text}"""
            response = self.model.generate_content(prompt)
            return self._format_response(response.text)
        except:
            return "Let me think that through..."

    
    def answer_to_audio(self, input_path, output_path):
        """Process question and generate audio response"""
        with open(input_path, 'r', encoding='utf-8') as f:
            question = f.read().strip()
        
        if self._is_question(question):
            response_text = self._handle_question(question)
        else:
            response_text = self._handle_statement(question)

        # Generate audio from response
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 0.9)
            engine.save_to_file(response_text, output_path)
            engine.runAndWait()
            return True
        except Exception as e:
            print(f"Error generating audio: {e}")
            return False
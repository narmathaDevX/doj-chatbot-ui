import requests
import json
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "phi3"

# =====================================================
# LOAD KNOWLEDGE (SECTION GROUPED)
# =====================================================

def load_knowledge():
    knowledge = {}
    current_section = None

    try:
        with open("legal_knowledge.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
    except:
        return {}

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if line.startswith("==="):
            current_section = line.replace("=", "").strip().lower()
            knowledge[current_section] = []
            continue

        if current_section:
            knowledge[current_section].append(line)

    return knowledge


knowledge_by_category = load_knowledge()

# =====================================================
# STOPWORDS
# =====================================================

STOPWORDS = {
    "what", "when", "where", "which", "their", "there",
    "about", "would", "could", "should", "after",
    "before", "under", "between", "into", "from",
    "this", "that", "have", "been", "with", "someone",
    "does", "your"
}

# =====================================================
# SYNONYM MAP (LIGHTWEIGHT SEMANTIC BOOST)
# =====================================================

SYNONYMS = {
    "woman": "women",
    "women": "woman",
    "night": "sunset",
    "arrested": "arrest",
    "arrest": "arrested",
    "fraud": "online",
    "cheque": "cheque",
    "bounce": "dishonour",
}

def normalize(word):
    if word.endswith("ed"):
        word = word[:-2]
    if word.endswith("s"):
        word = word[:-1]
    return word

def apply_synonym(word):
    return SYNONYMS.get(word, word)

def tokenize(text):
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    cleaned = []

    for w in words:
        if w not in STOPWORDS and len(w) > 3:
            w = normalize(w)
            w = apply_synonym(w)
            cleaned.append(w)

    return cleaned

# =====================================================
# FUZZY CATEGORY DETECTION
# =====================================================

def detect_category(message):
    msg = message.lower()

    if any(w in msg for w in ["arrest", "custody", "detention", "magistrate"]):
        return "arrest"
    elif any(w in msg for w in ["fir", "complaint", "theft"]):
        return "fir"
    elif "bail" in msg:
        return "bail"
    elif any(w in msg for w in ["divorce", "maintenance", "custody"]):
        return "divorce"
    elif any(w in msg for w in ["domestic", "dowry", "498a"]):
        return "domestic"
    elif any(w in msg for w in ["consumer", "refund"]):
        return "consumer"
    elif any(w in msg for w in ["cyber", "fraud", "online"]):
        return "cyber"
    elif any(w in msg for w in ["cheque", "dishonour"]):
        return "cheque"
    else:
        return None

# =====================================================
# FUZZY SECTION MATCHING
# =====================================================

def find_relevant_sections(category_keyword):
    if not category_keyword:
        return list(knowledge_by_category.values())

    matched_sections = []

    for section_name, section_content in knowledge_by_category.items():
        if category_keyword in section_name:
            matched_sections.append(section_content)

    if matched_sections:
        return matched_sections

    # fallback to full search
    return list(knowledge_by_category.values())

# =====================================================
# RETRIEVAL
# =====================================================

def retrieve_relevant_chunks(query, category=None, top_k=6):

    query_tokens = tokenize(query)
    scores = []

    sections = find_relevant_sections(category)

    search_space = []
    for section in sections:
        search_space.extend(section)

    for chunk in search_space:
        chunk_tokens = tokenize(chunk)
        score = 0

        for token in query_tokens:
            if token in chunk_tokens:
                score += 3

        if query.lower() in chunk.lower():
            score += 5

        if score > 0:
            scores.append((score, chunk))

    scores.sort(reverse=True, key=lambda x: x[0])

    return [item[1] for item in scores[:top_k]]

# =====================================================
# ANALYTICS
# =====================================================

def update_analytics(category):
    try:
        with open("analytics.json", "r") as f:
            stats = json.load(f)
    except:
        stats = {}

    key = category if category else "general"
    stats[key] = stats.get(key, 0) + 1

    with open("analytics.json", "w") as f:
        json.dump(stats, f, indent=4)

@app.route("/analytics", methods=["GET"])
def analytics():
    try:
        with open("analytics.json", "r") as f:
            stats = json.load(f)
    except:
        stats = {}
    return jsonify(stats)

# =====================================================
# CHAT ROUTE
# =====================================================

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()
    message = data.get("message", "").strip()
    mode = data.get("mode", "strict")

    if not message:
        return jsonify({"response": "Please enter a valid legal question."})

    if message.lower() in ["hi", "hello", "hey"]:
        return jsonify({
            "response": "Welcome to the Department of Justice AI Legal Assistant. Please enter your legal query."
        })

    with open("logs.txt", "a") as log:
        log.write(f"{datetime.now()} - {message}\n")

    category_keyword = detect_category(message)

    relevant_chunks = retrieve_relevant_chunks(message, category_keyword)

    if not relevant_chunks:
        return jsonify({
            "response": "This information is not available in the current legal database.\n\n"
                        "Note: This chatbot provides general legal information and does not constitute legal advice."
        })

    update_analytics(category_keyword)

    # STRICT MODE
    if mode == "strict":
        bullets = "\n".join([f"- {chunk}" for chunk in relevant_chunks])
        final = (
            f"Category: {category_keyword if category_keyword else 'general'}\n\n"
            f"{bullets}\n\n"
            "Confidence Level: High\n\n"
            "Note: This chatbot provides general legal information and does not constitute legal advice."
        )
        return jsonify({"response": final})

    # EXTENDED MODE
    prompt = (
        "You are a legal assistant specializing in Indian law.\n"
        "Use ONLY the provided context.\n"
        "Do not introduce unrelated laws.\n\n"
        "Context:\n" + "\n".join(relevant_chunks)
    )

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload)
    result = response.json()

    ai_text = result.get("response", "AI service error.").strip()

    final = (
        f"Category: {category_keyword if category_keyword else 'general'}\n\n"
        f"{ai_text}\n\n"
        "Confidence Level: AI-Generated\n\n"
        "Note: This chatbot provides general legal information and does not constitute legal advice."
    )

    return jsonify({"response": final})


if __name__ == "__main__":
    app.run(debug=True)
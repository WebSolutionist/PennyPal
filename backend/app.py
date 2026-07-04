import os
import json
import requests
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables relative to the script location
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

app = Flask(__name__)
CORS(app)

# Configuration
PORT = int(os.getenv("PORT", 5000))
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_API_URL = os.getenv("QWEN_API_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-max")
QWEN_BACKGROUND_MODEL = "qwen-plus"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

LOCAL_MEMORIES_FILE = "local_memories.json"

# Initialize Supabase Client
supabase_client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client initialized successfully.")
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
else:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not set. Running with local JSON database.")

# Helper to manage local memories (fallback)
def load_local_memories():
    if not os.path.exists(LOCAL_MEMORIES_FILE):
        return []
    try:
        with open(LOCAL_MEMORIES_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_local_memories(memories):
    try:
        with open(LOCAL_MEMORIES_FILE, 'w') as f:
            json.dump(memories, f, indent=4)
    except Exception as e:
        print(f"Error saving local memories: {e}")

# Database abstraction layer (Memories are global across sessions for the user)
def get_memories(session_id=None, include_inactive=False):
    """Retrieve memories. If include_inactive is True, returns archived history too."""
    if supabase_client:
        try:
            query = supabase_client.table("memories").select("*")
            if not include_inactive:
                query = query.eq("is_active", True)
            response = query.execute()
            return response.data
        except Exception as e:
            print(f"Supabase fetch error: {e}. Falling back to local storage.")
    
    # Fallback
    local_mems = load_local_memories()
    if not include_inactive:
        local_mems = [m for m in local_mems if m.get("is_active", True)]
    return local_mems

def save_memory_direct(memory_data):
    """Insert or update a memory directly."""
    import datetime
    now_str = datetime.datetime.utcnow().isoformat()
    
    if supabase_client:
        try:
            if "id" in memory_data:
                memory_data["updated_at"] = "now()"
                supabase_client.table("memories").update(memory_data).eq("id", memory_data["id"]).execute()
            else:
                supabase_client.table("memories").insert(memory_data).execute()
            return
        except Exception as e:
            print(f"Supabase save error: {e}. Falling back to local storage.")

    # Fallback
    local_mems = load_local_memories()
    memory_data["updated_at"] = now_str
    if "id" in memory_data:
        for idx, m in enumerate(local_mems):
            if m.get("id") == memory_data["id"]:
                local_mems[idx].update(memory_data)
                break
    else:
        import uuid
        memory_data["id"] = str(uuid.uuid4())
        memory_data["created_at"] = now_str
        local_mems.append(memory_data)
    save_local_memories(local_mems)

def get_clean_keywords(text):
    text = text.lower()
    # Remove common filler words
    filler_words = {"wants", "to", "save", "for", "a", "an", "the", "buying", "buy", "saving", "project", "successfully", "bought"}
    words = re.findall(r'\b\w+\b', text)
    keywords = [w for w in words if w not in filler_words and len(w) > 2]
    return keywords

def archive_all_related_memories(session_id, keyword_text):
    """
    Find and archive (is_active = False) all active memories 
    containing any core keywords from the completed goal or action.
    """
    active_mems = get_memories(session_id, include_inactive=False)
    keywords = get_clean_keywords(keyword_text)
    
    if not keywords:
        return
        
    for m in active_mems:
        m_content_lower = m["content"].lower()
        # Check if any clean keyword exists in the memory content
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', m_content_lower):
                m["is_active"] = False
                save_memory_direct(m)
                break

def apply_decay(session_id, current_active_session):
    """
    Apply decay to memories when transitioning sessions.
    Feelings & Attitudes and Habits & Behaviors lose 1 importance if not seen in the current active session.
    """
    memories = get_memories(session_id, include_inactive=False)
    for m in memories:
        if m["category"] in ["Feelings & Attitudes", "Habits & Behaviors"]:
            if m.get("last_session_seen") != current_active_session:
                new_importance = max(1, m["importance"] - 1)
                m["importance"] = new_importance
                save_memory_direct(m)

def process_memory_updates(session_id, extractions):
    """Process extracted memory actions: new, update, contradict, delete, achieve."""
    existing_memories = get_memories(session_id, include_inactive=True)

    for ext in extractions:
        action = ext.get("action", "new")
        category = ext.get("category")
        content = ext.get("content")
        importance = ext.get("importance", 3)
        emotional_tone = ext.get("emotional_tone", "neutral")
        target_memory_content = ext.get("target_memory_content")

        matched_mem = None
        if target_memory_content:
            for m in existing_memories:
                if m["content"].lower() == target_memory_content.lower() and m["category"] == category:
                    matched_mem = m
                    break

        if action == "new":
            duplicate = None
            for m in existing_memories:
                if m["content"].lower() == content.lower() and m["category"] == category and m["is_active"]:
                    duplicate = m
                    break
            
            if duplicate:
                duplicate["mention_count"] = duplicate.get("mention_count", 1) + 1
                duplicate["importance"] = min(5, duplicate["importance"] + 1)
                duplicate["emotional_tone"] = emotional_tone
                duplicate["last_session_seen"] = session_id
                save_memory_direct(duplicate)
            else:
                save_memory_direct({
                    "session_id": session_id,
                    "category": category,
                    "content": content,
                    "importance": importance,
                    "emotional_tone": emotional_tone,
                    "mention_count": 1,
                    "is_active": True,
                    "last_session_seen": session_id
                })

        elif action == "update" and matched_mem:
            matched_mem["mention_count"] = matched_mem.get("mention_count", 1) + 1
            matched_mem["importance"] = min(5, matched_mem["importance"] + 1)
            matched_mem["emotional_tone"] = emotional_tone
            matched_mem["last_session_seen"] = session_id
            save_memory_direct(matched_mem)

        elif action == "contradict" and matched_mem:
            matched_mem["is_active"] = False
            save_memory_direct(matched_mem)

            new_mem = {
                "session_id": session_id,
                "category": category,
                "content": content,
                "importance": importance,
                "emotional_tone": emotional_tone,
                "mention_count": 1,
                "is_active": True,
                "parent_memory_id": matched_mem.get("id"),
                "last_session_seen": session_id
            }
            save_memory_direct(new_mem)

        elif action == "achieve" and matched_mem:
            # 1. Archive the target goal memory directly to guarantee it is disabled
            matched_mem["is_active"] = False
            save_memory_direct(matched_mem)
            
            # 2. Archive all other related memories using keywords from the goal or new content
            combined_text = f"{matched_mem['content']} {content}"
            archive_all_related_memories(session_id, combined_text)
            
            # 3. Add the milestone achievement as a permanent fact (marked is_active: True so it shows on the sidebar)
            new_mem = {
                "session_id": session_id,
                "category": "Constraints & Facts",
                "content": f"Successfully bought the {content} (Goal Achieved)",
                "importance": 5, # Highest importance milestone
                "emotional_tone": "excited",
                "mention_count": 1,
                "is_active": True,
                "parent_memory_id": matched_mem.get("id"),
                "last_session_seen": session_id
            }
            save_memory_direct(new_mem)

        elif action == "delete" and matched_mem:
            matched_mem["is_active"] = False
            save_memory_direct(matched_mem)

def extract_memories_from_message(message, existing_memories):
    """Use Qwen (background) to analyze the user message and extract memory operations."""
    if not QWEN_API_KEY:
        return []

    existing_context = ""
    if existing_memories:
        existing_context = "Existing active memories:\n" + "\n".join([
            f"- [{m['category']}] \"{m['content']}\" (Importance: {m['importance']})" for m in existing_memories
        ])

    prompt = f"""
You are the memory extraction module for PennyPal, an AI financial coach.
Analyze the following user message and determine if the user is introducing new information, reinforcing existing information, contradicting/changing a previous memory, completing a goal, or asking to forget something.

Categories available:
1. "Goals": Specific financial targets. Base importance: 4.
2. "Habits & Behaviors": Repeated spending/saving patterns. Base importance: 3.
3. "Feelings & Attitudes": Emotional states about money. Base importance: 2.
4. "Constraints & Facts": Hard financial facts (rent, salary dates, achievements). Base importance: 3.
5. "Action Plan Commitments": Specific promises the user makes to themselves. Base importance: 4.

Scoring Rules:
- Assign a base importance score according to the category.
- BUMP the score higher (+1 or +2, up to max 5) if the user expresses high urgency, stress, strong emotion, or if they are repeating something they've said before.

{existing_context}

User Message: "{message}"

Determine which action is happening:
- "new": The user shares something not in the existing memories.
- "update": The user reinforces or repeats an existing memory.
- "contradict": The user changes a previous active memory (e.g., changing a goal amount, changing rent cost, changing a habit), OR expresses an emotional state/feeling that directly contradicts a previously stored active feeling (e.g. saying they are feeling excited/confident/calm contradicts a stored memory of feeling stressed/anxious/uneasy about saving). When contradict is triggered, "target_memory_content" MUST match the exact text of the conflicting memory to override it (e.g. target "Feels uneasy and stressed about saving because they have never saved before" to replace it with a new content like "Feels excited and confident about savings").
- "achieve": The user states they have successfully completed or bought a previously tracked goal (e.g. "I bought the laptop"). Clean up the content to just represent the item name (e.g., "laptop" or "phone and headset").
- "delete": The user explicitly asks to forget something, cancel a goal, drop a priority, or states a previous goal is no longer true (e.g., "forget the phone goal", "the phone is no longer a priority", "I don't want to save for a phone anymore", "cancel my saving plans for the phone"). When delete is triggered, "target_memory_content" MUST match the exact text of the existing memory to delete (e.g. "Wants to save $300 for a phone").

Respond ONLY with a valid JSON array of objects. Do not include markdown formatting other than the JSON itself. If nothing is worth remembering or changing, return an empty array [].
Each object must have:
- "action": ("new", "update", "contradict", "achieve", or "delete")
- "category": (one of the 5 categories above)
- "content": (a concise, clear summary of the fact/goal/habit in third person, e.g. "Wants to save $800 for a laptop". Required for "new", "contradict", and "achieve")
- "target_memory_content": (the EXACT content string of the existing memory being updated/contradicted/deleted/achieved. Required if action is "update", "contradict", "achieve", or "delete")
- "importance": (integer 1-5, based on the scoring rules)
- "emotional_tone": (string describing the tone, e.g., "stressed", "excited", "determined", "neutral")
"""

    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": QWEN_BACKGROUND_MODEL,
        "messages": [
            {"role": "system", "content": "You are a precise JSON extractor. Output only JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1
    }

    try:
        response = requests.post(QWEN_API_URL, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content.strip())
    except Exception as e:
        print(f"Memory extraction failed: {e}")
        return []

def get_self_reflection(message, active_memories, newly_extracted, archived_history):
    """
    Perform a hidden 'Self-Reflection' step to analyze constraints, contradictions,
    and consecutive spending patterns before generating the main reply.
    """
    if not QWEN_API_KEY:
        return ""

    history_str = "\n".join([f"- [{m['category']}] \"{m['content']}\" (Importance: {m['importance']})" for m in active_memories])
    new_str = "\n".join([f"- [{n['category']}] \"{n['content']}\"" for n in newly_extracted])
    archive_str = "\n".join([f"- [{a['category']}] \"{a['content']}\"" for a in archived_history])

    prompt = f"""
You are the self-reflection reasoning engine for PennyPal, a Wise Financial Mentor.
Before formulating a response, analyze the user's input against their memory history (both active and archived) to catch logical contradictions, budget risks, or patterns of impulsive spending.

User Input: "{message}"

Active Memory History:
{history_str}

Archived History (Past behaviors, old worries, completed projects):
{archive_str}

Newly Shared Information:
{new_str}

Analyze for:
1. CONTRADICTIONS: Did the user say something that directly contradicts a stored fact or active milestone? (e.g., they express fear about buying a laptop, but memory shows they already bought the laptop).
2. CONSECUTIVE/IMPULSIVE PURCHASES: Did the user just achieve a goal (e.g. buying a laptop) and immediately pivot to another large expense (like a $1000 phone)? Compare it to past patterns.
3. BEHAVIOR COMPARISONS: Can you compare this new plan with their past behavior? (For example: if they want to allocate 70% of their salary for a phone, and the archive shows they previously allocated 50% for a laptop).

Write a short internal reflection note (max 3 sentences) specifying how PennyPal should address this.
"""

    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": QWEN_BACKGROUND_MODEL,
        "messages": [
            {"role": "system", "content": "You are a logical financial critic. Write a brief reflection note."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    try:
        response = requests.post(QWEN_API_URL, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Self-reflection failed: {e}")
        return ""

@app.route("/api/health", methods=["GET"])
def health_check():
    status = {
        "status": "online",
        "qwen_configured": bool(QWEN_API_KEY),
        "supabase_configured": bool(supabase_client)
    }
    return jsonify(status), 200

@app.route("/api/memories", methods=["GET"])
def get_memories_endpoint():
    session_id = request.args.get("session_id", "default-session")
    mems = get_memories(session_id, include_inactive=False)
    return jsonify(mems), 200

@app.route("/api/decay", methods=["POST"])
def trigger_decay():
    data = request.json or {}
    session_id = data.get("session_id")
    last_active_session = data.get("last_active_session")
    if not session_id or not last_active_session:
        return jsonify({"error": "session_id and last_active_session are required"}), 400
        
    apply_decay(session_id, last_active_session)
    return jsonify({"status": "success"}), 200

@app.route("/api/welcome", methods=["POST"])
def welcome_message():
    """
    Generate a personalized welcome message for a session using global active memories.
    Prioritizes active Goals first, then Importance, then Recency (updated_at).
    If the highest priority memory is an ACHIEVED goal, congratulates the user and asks what's next.
    """
    data = request.json or {}
    session_id = data.get("session_id")
    memory_enabled = data.get("memory_enabled", True)
    
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    memories = get_memories(session_id, include_inactive=False) if memory_enabled else []
    
    if not memories or not QWEN_API_KEY:
        return jsonify({
            "reply": "Hello! I'm **PennyPal**, your personal AI financial coach. Let's talk about your money goals, budgets, or any financial questions you have today!"
        }), 200

    # Sort memories:
    # 1. Prioritize category == "Goals" (True is sorted before False when reverse=True)
    # 2. Sort by importance descending
    # 3. Sort by updated_at descending
    memories.sort(key=lambda x: (x.get("category") == "Goals", x.get("importance", 1), x.get("updated_at", "")), reverse=True)
    highest_item = memories[0]

    prompt = f"""
You are PennyPal, a financial coaching chat agent (Wise Financial Mentor).
The user is starting a new session. 
Generate a brief, natural welcome message. Acknowledge returning to the conversation, and check in on this specific item:
- Category: {highest_item['category']}
- Detail: "{highest_item['content']}"

CRITICAL WELCOME INSTRUCTIONS:
1. If the item represents an ACHIEVED goal (e.g. contains "Goal Achieved" or "Successfully bought"), DO NOT ask them how the savings are going. Instead, congratulate them on their achievement, ask how they are enjoying their purchase, and invite them to share what their next financial milestone is.
2. If the item is an active goal (e.g., "save $500 for a laptop"), check in on their progress in a warm, encouraging manner.
3. Keep the welcome message very short and light (1-2 sentences max). Do not recap. Make it sound like a thoughtful friend.
"""

    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": QWEN_MODEL,
        "messages": [
            {
                "role": "system", 
                "content": "You are PennyPal, a Wise Financial Mentor. Keep welcomes extremely short, warm, and natural."
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(QWEN_API_URL, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        reply = response.json()["choices"][0]["message"]["content"]
        return jsonify({"reply": reply}), 200
    except Exception as e:
        return jsonify({
            "reply": "Welcome back! Let's continue working on your financial plans."
        }), 200

@app.route("/api/rename-session", methods=["POST"])
def rename_session():
    """Generate a short 2-3 word topic name for a session based on the chat history."""
    data = request.json or {}
    messages = data.get("messages", [])
    
    if not messages or not QWEN_API_KEY:
        return jsonify({"suggested_name": None}), 200

    history = ""
    for msg in messages[-4:]:
        history += f"{msg['sender']}: {msg['text']}\n"

    prompt = f"""
Analyze the following short conversation snippet and suggest a concise 2 to 3 word title summarizing the main topic (e.g., "Laptop Savings", "Debt Strategy", "Budget Check-in").
Do not include punctuation or quotes.

Snippet:
{history}
"""

    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": QWEN_BACKGROUND_MODEL,
        "messages": [
            {"role": "system", "content": "You are a concise naming assistant. Output only a 2-3 word title."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    try:
        response = requests.post(QWEN_API_URL, headers=headers, json=data, timeout=8)
        response.raise_for_status()
        suggested_name = response.json()["choices"][0]["message"]["content"].strip()
        suggested_name = suggested_name.replace('"', '').replace("'", "")
        return jsonify({"suggested_name": suggested_name}), 200
    except Exception as e:
        return jsonify({"suggested_name": None}), 200

@app.route("/api/chat", methods=["POST"])
def chat():
    user_data = request.json or {}
    message = user_data.get("message")
    session_id = user_data.get("session_id", "default-session")
    memory_enabled_raw = user_data.get("memory_enabled", True)
    
    # Strictly parse boolean values from strings
    memory_enabled = False
    if memory_enabled_raw is True or str(memory_enabled_raw).lower() == 'true':
        memory_enabled = True
    
    if not message:
        return jsonify({"error": "Message is required"}), 400

    # 1. Fetch active memories PRIOR to current message (Hallucination fix)
    prior_active_memories = get_memories(session_id, include_inactive=False) if memory_enabled else []
    
    # 2. Fetch archived (inactive) history (To pass only to Qwen, NOT to the sidebar)
    all_memories = get_memories(session_id, include_inactive=True) if memory_enabled else []
    archived_history = [m for m in all_memories if not m["is_active"]] if memory_enabled else []

    # 3. Extract and save memory operations
    extracted_ops = []
    if memory_enabled and QWEN_API_KEY:
        extracted_ops = extract_memories_from_message(message, prior_active_memories)
        process_memory_updates(session_id, extracted_ops)

    # 4. Perform background Self-Reflection step using both active and archived history
    reflection_note = ""
    if memory_enabled and QWEN_API_KEY:
        reflection_note = get_self_reflection(message, prior_active_memories, extracted_ops, archived_history)
        print(f"Self-Reflection Note: {reflection_note}")

    if not QWEN_API_KEY:
        return jsonify({
            "reply": f"[Demo Mode] You said: '{message}'."
        }), 200

    # 5. Formulate system prompt with split memory labeling
    system_prompt = (
        "You are PennyPal, a financial coaching chat agent. "
        "Your personality is that of a Wise Financial Mentor: calm, educational, and reflective. "
        "Explain the 'why' behind financial concepts. Guide the user to make mindful choices "
        "through thoughtful questioning. Avoid judgmental language, and encourage financial "
        "awareness and long-term planning.\n\n"
    )

    if memory_enabled and prior_active_memories:
        system_prompt += "Here are the user's current ACTIVE GOALS & FACTS (These show in their sidebar):\n"
        for m in prior_active_memories:
            system_prompt += f"- [{m['category']}] \"{m['content']}\" (Importance: {m['importance']}/5)\n"
            
    if memory_enabled and archived_history:
        system_prompt += "\nHere is the user's HISTORICAL ARCHIVE of past completed projects, behaviors, and archived worries (These are HIDDEN from their sidebar, but you can reference them to compare patterns):\n"
        for a in archived_history:
            system_prompt += f"- [{a['category']}] \"{a['content']}\"\n"
            
    if memory_enabled and extracted_ops:
        system_prompt += "\nHere is NEW INFORMATION the user just shared in their current message:\n"
        for n in extracted_ops:
            system_prompt += f"- [{n['category']}] \"{n['content']}\" (Action: {n['action']})\n"

    # Add the reflection note to guide the response
    if reflection_note:
        system_prompt += f"\nINTERNAL REFLECTION (Follow this guidance to form your response):\n{reflection_note}\n"

    system_prompt += (
        "\nCHAT RULES (Always maintain your calm, Wise Financial Mentor tone):\n"
        "1. MENTOR CHALLENGE: If the user recently bought something (represented in their history) and is immediately trying to make another large purchase (like a $1000 phone), act as a gatekeeper of their budget. Gently challenge them: ask if this is a genuine need, if they are spending out of post-purchase excitement, and if it's the right time to commit to another big expense.\n"
        "2. BEHAVIOR COMPARISONS: Proactively draw comparisons between their current plans and their archived past achievements (e.g. 'I remember when you saved for your laptop, you allocated 50% of your salary. Trying to allocate 70% for this phone might be a bit tight...'). Explain the 'why' behind your guidance.\n"
        "3. CONTRADICTION RULE: If the user says something that contradicts a stored memory, you MUST call it out gently: 'I remember you telling me that you had already bought the laptop... did something change?'\n"
        "4. RELEVANCE RULE: Do not force historical memories into the chat unless they are directly relevant to what the user just said or relate to a pattern you are pointing out.\n"
        "5. Speak naturally. Never mention a database, JSON, or state that you are recalling a file."
    )

    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
    }

    try:
        response = requests.post(QWEN_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        reply = result["choices"][0]["message"]["content"]
        return jsonify({
            "reply": reply,
            "memories_processed": extracted_ops
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to get response from Qwen: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

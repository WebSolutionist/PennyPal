# PennyPal — Architecture & Features

This document provides the architecture diagram and the feature descriptions for the Global AI Hackathon Series submission.

## 1. System Architecture

Below is the flow of communication between the user's browser, the Flask backend, the Qwen Cloud LLM, and the Supabase database.

```mermaid
graph TD
    %% Define Nodes
    User[👤 User Browser / UI]
    Backend[🐍 Flask Backend Server]
    Qwen[🧠 Qwen Cloud API]
    Supabase[(🗄️ Supabase Database)]

    %% Define Flows
    User -->|1. Chat Message / Toggle State| Backend
    Backend -->|2. Query Active Memories| Supabase
    Backend -->|3. Message + Active Memories| Qwen
    Qwen -->|4. Generate Natural Response| Backend
    Backend -->|5. Extract Memory Updates (New/Contradict/Delete)| Qwen
    Backend -->|6. Save / Archive / Decay Memories| Supabase
    Backend -->|7. Display Response & Updated Memories| User
```

---

## 2. Key Features

### 🧠 1. Multi-Category Memory Engine
PennyPal extracts and categorizes memories from conversation in real-time into five distinct categories:
- **Goals** (e.g., saving for a laptop or trip)
- **Habits & Behaviors** (e.g., buying coffee daily, eating takeout)
- **Feelings & Attitudes** (e.g., anxiety about credit card debt, excitement about a raise)
- **Constraints & Facts** (e.g., monthly rent amount, salary payment dates)
- **Action Plan Commitments** (e.g., bringing lunch to work on Tuesdays and Thursdays)

### 📈 2. Dynamic Importance Scoring
Memories are not treated equally. PennyPal automatically assigns importance based on category, but dynamically adjusts the score based on the user's tone. If a goal or feeling is mentioned with urgency, stress, or repeated multiple times, the importance score increases.

### 🔄 3. Contradiction Linking & Evolution
If a user changes their mind (e.g., changing a saving goal from $500 to $800), PennyPal doesn't just overwrite it. It archives the old memory and links it to the new one. This allows the AI to reference their journey (e.g., *"I see you've scaled up your goal from $500 to $800—you're thinking bigger now!"*).

### ⏳ 4. Time-Based Memory Decay
To keep the memory pool fresh and relevant, temporary feelings and habits slowly decay in importance (-1 per session) if they are not mentioned or reinforced in subsequent sessions. Hard constraints and long-term goals never decay.

### 🎭 5. Wise Financial Mentor Personality
PennyPal adopts a calm, educational, and reflective tone. It avoids judging the user's spending, explains the "why" behind financial concepts, and guides them to make mindful choices through thoughtful questioning.

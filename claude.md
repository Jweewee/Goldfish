# Goldfish - Rosebud-Style Journaling Assistant

## Project Overview

**Goldfish** is a rosebud-style journaling chatbot application that provides gentle, guided self-reflection through conversational AI. The app focuses on injecting subtle positivity, balancing freeform writing with structured guidance, and helping users break down complex emotions and experiences into manageable elements.

## Core Design Principles

1. **Inject Subtle Positivity/Hope** - Always look for something to affirm, gently reframe, or offer encouragement
2. **Freeform + Structured Balance** - Allow open-ended writing while providing helpful prompts and guidance
3. **Break Things Down** - Help users decompose complex feelings, experiences, or problems into smaller elements
4. **Multi-Dimensional Exploration** - Ask about thoughts, emotions, body sensations, values, intentions, obstacles, and context
5. **Guided Journal Templates** - Structure sessions with themed modules (gratitude, growth, coping, etc.)

## Technical Architecture

### Framework & Dependencies
- **Backend**: Python with OpenAI ChatKit integration (https://openai.github.io/chatkit-python/)
- **AI Model**: OpenAI GPT for conversational intelligence
- **Data Storage**: Local/cloud storage for journal entries and user context
- **Memory System**: Persistent context tracking across sessions

### Core Components

#### 1. Conversation Manager
- Session state management
- Context preservation across conversations
- Memory integration for referencing past entries

#### 2. Positivity Injection Engine
- Sentiment analysis of user input
- Reframing prompts and encouragement insertion
- Micro-affirmation system
- Configurable positivity bias levels

#### 3. Exploration System
- Freeform to guided transition logic
- Progressive questioning algorithms
- Element breakdown mechanisms
- Multi-dimensional inquiry framework

#### 4. Template Engine
- Modular guided journal templates
- Theme-based session structures
- Dynamic prompt generation
- Template weighting and selection

#### 5. Memory & Context System
- Pattern recognition across entries
- Recurring theme tracking
- Personalized prompt generation
- Gentle linking to past reflections

## System Prompt

```
You are "Rosebud-style journaling assistant", a kind, gentle, guiding AI companion whose goal is to help users reflect, grow, and feel seen — not to push them or prescribe solutions.

Your core design principles:
1. Inject subtle positivity / hope — always look for something to affirm, gently reframe, or offer encouragement.
2. Freeform + structured balance — allow open-ended writing, but guide with prompts or branches when helpful.
3. Break things down — when the user gives a long or messy response, you should help them decompose feelings, experiences, or problems into smaller elements.
4. Ask about various elements / dimensions — e.g. thoughts, emotions, body sensations, values, intentions, obstacles, context.
5. Use guided‐journal templates — occasionally structure sessions with themes (gratitude, best possible self, coping, growth) or mini journaling "modules."

How to behave / structure interactions:
• Begin each session with a brief warm opening ("Hello — good to see you again. How are you feeling today?")
• Offer a choice: do you want to free-write, or go through a guided template?
• If user chooses freeform: let them write, then ask follow-ups ("Tell me more about that," "What stood out to you?", "How does that affect you?")
• If guided: present 3–5 scaffolded prompts (e.g. "What's one positive event from today? Why did it matter to you? What could you learn from it?")
• After user writes answers, reflect back (paraphrase, highlight strengths, notice patterns), ask a deeper question or pivot (e.g. "What's another angle?", "What's under the surface?")
• Cap off with a small "closing reflection" — e.g. "One small insight you got from this," or "A small intention for tomorrow."
• Maintain a gentle, compassionate tone. Avoid catastrophizing, judgment, or prescriptive "you must do X" commands.
• If user seems stuck / blank: offer gentle scaffolding ("Here are a few prompts you might consider… do you want any of those?")
• Occasionally (but not too often) interject micro-affirmations or acknowledge effort ("I appreciate your vulnerability in sharing that," "That was brave to reflect on.")
• The assistant should not pretend to be a therapist or substitute for mental health care; if distress is evident, it should gently disclaim and encourage seeking professional help.
• Over time, the assistant can reference past entries (if the app stores them) to notice patterns, ask connections, or revisit themes, but always in a gentle way ("I remember you wrote about X a few days back — would you like to revisit that?").
```

## Guided Journal Templates

### Template Categories
1. **Gratitude & Appreciation**
   - Three good things
   - Appreciation practice
   - Silver linings exploration

2. **Future Visioning**
   - Best possible self
   - Goal setting and alignment
   - Intention setting

3. **Challenge & Coping**
   - Problem decomposition
   - Coping strategy identification
   - Resilience building

4. **Emotional Awareness**
   - Emotion check-in
   - Body sensation mapping
   - Trigger identification

5. **Values & Alignment**
   - Core values exploration
   - Action alignment assessment
   - Priority clarification

6. **Growth & Progress**
   - Small wins recognition
   - Learning reflection
   - Progress tracking

## Conversation Flow Architecture

### Session Structure
1. **Opening** - Warm greeting and mode selection
2. **Content Phase** - Freeform writing or guided prompts
3. **Reflection** - Paraphrasing, pattern recognition, deeper questioning
4. **Integration** - Insight synthesis and future intention
5. **Closing** - Gentle wrap-up with key takeaway

### Flow Decision Points
- **Mode Selection**: Freeform vs. Guided
- **Depth Calibration**: Surface vs. Deep exploration
- **Intervention Points**: When to inject positivity or guidance
- **Transition Triggers**: Moving between conversation phases

## Implementation Features

### Core Functionality
- [ ] Session management and state persistence
- [ ] OpenAI ChatKit integration
- [ ] Template system implementation
- [ ] Memory and context tracking
- [ ] Positivity injection algorithms

### Advanced Features
- [ ] Pattern recognition across entries
- [ ] Mood tracking and visualization
- [ ] Export functionality for journal entries
- [ ] Customizable template preferences
- [ ] Progressive disclosure of insights

### Configurable Parameters
- **Positivity Bias Level**: Frequency of encouragement injection
- **Depth of Questioning**: How far to push exploration
- **Guided vs Freeform Ratio**: Session structure preferences
- **Memory Recall Frequency**: Past entry reference frequency
- **Theme Weighting**: Template selection preferences

## Safety & Ethics

### Guardrails
- Clear disclaimer about not being therapy
- Crisis intervention protocols for self-harm indicators
- Gentle redirection from inappropriate topics
- Emphasis on professional help when needed

### Privacy & Data
- Secure storage of journal entries
- User consent for data usage
- Clear data retention policies
- Export/delete functionality

## Development Roadmap

### Phase 1: MVP
- Basic conversation engine
- Simple template system
- OpenAI ChatKit integration
- Local storage implementation

### Phase 2: Enhanced Intelligence
- Memory system implementation
- Pattern recognition features
- Advanced template engine
- Positivity injection refinement

### Phase 3: Advanced Features
- Mood tracking and analytics
- Export functionality
- Mobile app development
- Cloud synchronization

## Getting Started

### Prerequisites
- Python 3.8+
- OpenAI API access
- ChatKit Python SDK

### Installation
```bash
git clone [repository-url]
cd goldfish
pip install -r requirements.txt
```

### Configuration
1. Set up OpenAI API credentials
2. Configure ChatKit integration
3. Initialize local storage
4. Customize system prompt and templates

### Usage
```bash
python main.py
```

## Contributing

- Follow gentle, compassionate tone in all development
- Test thoroughly with diverse emotional scenarios
- Maintain privacy and security standards
- Document all template additions and modifications

---

*Goldfish aims to create a safe, supportive space for self-reflection and growth through gentle AI guidance.*
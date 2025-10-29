# Goldfish - Rosebud-Style Journaling Assistant with Supabase Integration

A gentle, AI-powered journaling companion that provides supportive conversation, guided reflection, and intelligent context retrieval using vector-based RAG (Retrieval-Augmented Generation), NLU (Natural Language Understanding), and GraphRAG with Neo4j.

## 🌟 Features

### Core Features

- 🌸 Gentle, supportive conversation style inspired by Rosebud
- 💾 Persistent journal entries with Supabase database storage
- 🔍 Vector-based RAG for intelligent context retrieval from past entries
- 🧠 NLU (Natural Language Understanding) with entity, emotion, and event extraction
- 🕸️ GraphRAG with Neo4j for relational knowledge graph storage
- 🎯 Intent-based response routing (self-reflection, planning, emotional-release, insight-generation)
- 📱 Beautiful, responsive web interface with gradient design
- 💬 Real-time chat with typing indicators
- 🔐 User authentication and secure data isolation
- 📝 Automatic conversation summarization
- 🎯 Multiple pages: Login, Home Dashboard, Entries, New Entry

### Technical Features

- **Supabase Integration**: Authentication, database, and vector storage
- **OpenAI Integration**: GPT-3.5-turbo for conversations and text-embedding-3-small for embeddings
- **Vector RAG**: Semantic search through past journal entries
- **NLU Pipeline**: spaCy for entity extraction, LLM for emotion/intent/relationship extraction
- **GraphRAG**: Neo4j knowledge graph for storing relationships between entities, people, places, and events
- **Agent Service**: Intelligent orchestration pipeline (RAG → NLU → GraphRAG → Intent routing → Response)
- **Row Level Security**: User data isolation and security
- **Render Deployment**: Production-ready deployment configuration

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11.9 or higher
- Supabase account
- OpenAI API key

### 2. Supabase Setup

1. **Create a new Supabase project** at [supabase.com](https://supabase.com)

2. **Enable pgvector extension**:

   ```sql
   create extension if not exists vector;
   ```

3. **Create the database tables**:

   ```sql
   -- Journal entries table
   create table journal_entries (
       id uuid primary key default gen_random_uuid(),
       user_id uuid not null references auth.users(id),
       summarized_text text not null,
       journal_interaction text[] not null,
       timestamp timestamptz default now()
   );

   -- Vector embeddings table
   create table journal_entry_vectors (
       id uuid primary key default gen_random_uuid(),
       entry_id uuid not null references journal_entries(id),
       user_id uuid not null,
       chunk_text text not null,
       embedding vector(1536) not null,
       created_at timestamptz default now()
   );

   -- Enable Row Level Security
   alter table journal_entries enable row level security;
   alter table journal_entry_vectors enable row level security;

   -- Create RLS policies
   create policy "Users can view own entries" on journal_entries
       for select using (auth.uid() = user_id);
   create policy "Users can insert own entries" on journal_entries
       for insert with check (auth.uid() = user_id);

   create policy "Users can view own vectors" on journal_entry_vectors
       for select using (auth.uid() = user_id);
   create policy "Users can insert own vectors" on journal_entry_vectors
       for insert with check (auth.uid() = user_id);
   ```

4. **Create vector similarity search function**:
   ```sql
   create or replace function match_documents (
     query_embedding vector(1536),
     match_count int default null,
     filter jsonb default '{}'
   ) returns table (
     id uuid,
     content text,
     similarity float
   )
   language plpgsql
   as $$
   #variable_conflict use_column
   begin
     return query
     select
       journal_entry_vectors.id,
       journal_entry_vectors.chunk_text as content,
       1 - (journal_entry_vectors.embedding <=> query_embedding) as similarity
     from journal_entry_vectors
     where journal_entry_vectors.user_id = (filter->>'user_id')::uuid
     order by journal_entry_vectors.embedding <=> query_embedding
     limit match_count;
   end;
   $$;
   ```

### 3. Environment Setup

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Install spaCy English model**:

   ```bash
   python -m spacy download en_core_web_sm
   ```

   This model is required for entity extraction (PERSON, ORG, GPE, etc.). The model is downloaded separately and not included in the pip requirements.

3. **Create environment file**:

   ```bash
   cp .env.example .env
   ```

4. **Configure environment variables** in `.env`:

   ```env
   # Supabase Configuration
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_KEY=your_supabase_anon_key

   # OpenAI Configuration
   OPENAI_API_KEY=your_openai_api_key

   # Flask Configuration
   FLASK_SECRET_KEY=your_flask_secret_key_here

   # Neo4j Configuration (Optional - app works without it)
   NEO4J_URI=bolt://localhost:7687  # or neo4j+s://xxx.databases.neo4j.io for Aura
   NEO4J_USERNAME=neo4j  # or use NEO4J_USER (both supported)
   NEO4J_PASSWORD=your_password_here
   ```

5. **Get your Supabase credentials**:
   - Go to your Supabase project dashboard
   - Navigate to Settings → API
   - Copy the Project URL and anon/public key

### 4. Set Up Neo4j (Optional but Recommended)

GraphRAG features will gracefully degrade if Neo4j is not configured, but for full functionality:

The application uses **LLM-based entity extraction** for semantic and emotional nuance, prioritizing precision over speed. This approach extracts:

- **People**: Names of people mentioned
- **Organizations**: Companies, institutions, groups
- **Events**: Specific events or activities
- **Topics**: Themes or subjects discussed
- **Emotions**: With valence (positive/negative/neutral) and intensity (1-5 scale)
- **Relationships**: Between entities with relationship types

#### Graph Schema

The Neo4j graph follows this structure:

```
(User:user_id)-[:AUTHORED]->(Entry:entry_id)
(Entry)-[:FEELS]->(Emotion {name, valence, intensity})
(Entry)-[:MENTIONS]->(Person {name})
(Entry)-[:MENTIONS]->(Entity {name})  # for organizations, events, topics
(Person)-[:RELATES_TO {type}]->(Person)
```

**Schema Initialization**: The service automatically initializes schema constraints on startup:

- `User.user_id` - Unique constraint
- `Entry.id` - Unique constraint
- `Emotion.name` - Unique constraint
- `Person.name` - Unique constraint
- `Entity.name` - Unique constraint

These constraints ensure data integrity and improve query performance. Initialization happens automatically when the Neo4j service connects, and errors are gracefully handled if constraints already exist.

#### Option 1: Neo4j Desktop (Recommended for Development)

1. Download Neo4j Desktop from https://neo4j.com/download/
2. Install and launch Neo4j Desktop
3. Create a new database (or use the default)
4. Start the database
5. Note the connection details:
   - **URI**: Usually `bolt://localhost:7687` (local) or `neo4j+s://xxx.databases.neo4j.io` (Aura)
   - **Username**: `neo4j` (default) - can also use `NEO4J_USER` environment variable
   - **Password**: Set during first launch (or reset if needed)

#### Option 2: Neo4j Aura (Cloud - Recommended for Production)

1. Sign up at https://neo4j.com/cloud/aura/
2. Create a free instance
3. Get connection URI, username, and password from the dashboard
4. URI format: `neo4j+s://xxxxx.databases.neo4j.io`

#### Option 3: Docker

```bash
docker run \
    --name neo4j \
    -p7474:7474 -p7687:7687 \
    -e NEO4J_AUTH=neo4j/your-password \
    neo4j:latest
```

Access Neo4j Browser at: http://localhost:7474

#### Schema Initialization

The service automatically initializes schema constraints on startup. You don't need to run these manually, but they're shown here for reference:

```cypher
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE;
CREATE CONSTRAINT entry_id IF NOT EXISTS FOR (e:Entry) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT emotion_name IF NOT EXISTS FOR (em:Emotion) REQUIRE em.name IS UNIQUE;
CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (x:Entity) REQUIRE x.name IS UNIQUE;
```

#### Initialize Neo4j Indexes (Optional - Recommended for Performance)

The service will create indexes automatically, but you can also create them manually for better performance:

1. Open Neo4j Browser (http://localhost:7474)
2. Run these Cypher queries:

```cypher
CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name);
CREATE INDEX place_name IF NOT EXISTS FOR (p:Place) ON (p.name);
CREATE INDEX emotion_type IF NOT EXISTS FOR (e:Emotion) ON (e.type);
CREATE INDEX entry_id IF NOT EXISTS FOR (e:Entry) ON (e.id);
CREATE INDEX entry_user_id IF NOT EXISTS FOR (e:Entry) ON (e.user_id);
```

### 5. Run the Application

**Web Interface (Recommended)**:

```bash
python run_web.py
```

Then open your browser to: http://localhost:3000

**Direct Flask App**:

```bash
python app.py
```

Then open your browser to: http://localhost:8080

## 📱 Application Pages

### `/login` - Authentication

- Clean login/signup interface
- Email and password authentication
- Automatic redirect to dashboard

### `/home` - Dashboard

- Welcome message and user info
- Recent entries preview
- Quick navigation to new entry or all entries
- Logout functionality

### `/entries` - Journal Entries

- List all saved journal entries
- Search and filter functionality
- Expandable conversation details
- Delete entries
- Timestamp and summary display

### `/new-entry` - Journaling Session

- Full chat interface with Goldfish
- Real-time conversation with RAG context
- Save entry functionality
- Session management

## 🔧 API Endpoints

### Authentication

- `POST /api/auth/signup` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/auth/user` - Get current user

### Journal Entries

- `GET /api/entries` - List user's entries
- `GET /api/entries/<id>` - Get specific entry
- `DELETE /api/entries/<id>` - Delete entry

### Chat & Sessions

- `POST /chat` - Send message to Goldfish (with RAG + NLU + GraphRAG)
- `POST /new_session` - Start new conversation
- `POST /save_entry` - Save current conversation (triggers NLU processing and GraphRAG storage)

## 🚀 Render Deployment

### Environment Variables (Render Dashboard)

Add these environment variables in your Render service settings:

- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase anon/public key
- `OPENAI_API_KEY` - Your OpenAI API key
- `FLASK_SECRET_KEY` - A secure random string
- `NEO4J_URI` - Your Neo4j connection URI (optional)
- `NEO4J_USERNAME` or `NEO4J_USER` - Your Neo4j username (optional, both supported)
- `NEO4J_PASSWORD` - Your Neo4j password (optional)

### Deployment Configuration

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python app.py`
- **Python Version**: 3.11.9 (specified in `runtime.txt`)

The application will automatically use the environment variables and connect to Supabase.

## 🧠 How RAG, NLU, and GraphRAG Work

### 1. Entry Storage Pipeline

When you save a journal entry, the conversation is:

- **Summarized** using GPT-3.5-turbo
- **Chunked** into meaningful segments
- **Embedded** using OpenAI's text-embedding-3-small (stored in Supabase pgvector)
- **NLU Processed** to extract:
  - Entities (people, places, organizations) using spaCy
  - Emotions and events using LLM
  - Intent classification (self-reflection, planning, emotional-release, etc.)
  - Relationships between entities
- **GraphRAG Storage** - Entities and relationships stored in Neo4j knowledge graph

### 2. Context Retrieval Pipeline (Per Message)

During new conversations, each message goes through:

1. **RAG Retrieval**: Current message is embedded and semantic search finds relevant past entries
2. **NLU Processing**: Extract entities, emotions, events, and intent from current message
3. **GraphRAG Query**: Retrieve related entities from Neo4j graph based on mentioned entities
4. **Intent Routing**: Route to appropriate workflow (reflective, planning, emotional grounding, insight generation)
5. **Response Generation**: Generate response with all context (RAG + GraphRAG + NLU metadata)

### 3. Graph Schema

**Nodes:**

- `Entry` - Journal entries
- `Person` - People mentioned
- `Place` - Locations mentioned
- `Organization` - Organizations mentioned
- `Emotion` - Emotions expressed
- `Event` - Events/activities

**Relationships:**

- `MENTIONED_IN` - Entity → Entry
- `RELATES_TO` - Entity → Entity
- `EXPERIENCED` - Entry → Emotion
- `OCCURRED_IN` - Entry → Event

### 4. Privacy & Security

- All embeddings and entries are isolated per user using Row Level Security
- Graph nodes include `user_id` for multi-tenant isolation
- NLU processing happens server-side with no data leakage

## 🛠️ Development

### Project Structure

```
Goldfish/
├── app.py                 # Main Flask application
├── main.py               # CLI version (legacy)
├── run_web.py            # Web launcher
├── requirements.txt       # Python dependencies
├── runtime.txt           # Python version for Render
├── Procfile              # Render deployment config
├── .env.example          # Environment template
├── services/             # Service layer
│   ├── supabase_client.py
│   ├── auth_service.py
│   ├── journal_service.py
│   ├── embedding_service.py
│   ├── rag_service.py
│   ├── summary_service.py
│   ├── nlu_service.py      # NLU processing (LLM-based entity extraction with semantic/emotional nuance)
│   ├── neo4j_service.py    # Neo4j GraphRAG operations with schema initialization
│   └── agent_service.py   # Pipeline orchestration
└── templates/            # HTML templates
    ├── login.html
    ├── home.html
    ├── entries.html
    └── new-entry.html
```

### Adding New Features

1. **Services**: Add new service classes in `services/`
2. **Routes**: Add new routes in `app.py`
3. **Templates**: Create new templates in `templates/`
4. **Database**: Update Supabase schema and RLS policies

## 🔒 Security Features

- **Row Level Security**: Users can only access their own data
- **Authentication**: Supabase handles secure user authentication
- **Environment Variables**: Sensitive data stored securely
- **Input Validation**: All user inputs are validated and sanitized

## 🐛 Troubleshooting

### Common Issues

1. **"Assistant not available"**: Check your OpenAI API key
2. **"Authentication failed"**: Verify Supabase URL and key
3. **"Vector search failed"**: Ensure pgvector extension is enabled
4. **"Database connection failed"**: Check Supabase project status
5. **"spaCy model not found"**: Run `python -m spacy download en_core_web_sm`
6. **"Neo4j connection failed"**:
   - Verify Neo4j is running (`curl http://localhost:7474`)
   - Check `NEO4J_URI` format (should start with `bolt://` or `neo4j+s://`)
   - Verify `NEO4J_USERNAME` (or `NEO4J_USER`) and `NEO4J_PASSWORD` in `.env`
   - Note: App will continue with RAG only if Neo4j is unavailable
   - Schema constraints are created automatically on startup; errors may be expected if they already exist

### Graceful Degradation

- **Neo4j unavailable**: App continues with RAG only (no GraphRAG features)
- **LLM extraction unavailable**: Entity extraction falls back to spaCy if available (primary method is LLM-based)
- **OpenAI API issues**: Check API key, rate limits, and account credits

### Debug Mode

Set `FLASK_DEBUG=1` in your environment for detailed error messages.

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For issues and questions:

1. Check the troubleshooting section
2. Review Supabase and OpenAI documentation
3. Open an issue on GitHub

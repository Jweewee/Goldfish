# Goldfish - Rosebud-Style Journaling Assistant with Supabase Integration

A gentle, AI-powered journaling companion that provides supportive conversation, guided reflection, and intelligent context retrieval using vector-based RAG (Retrieval-Augmented Generation).

## 🌟 Features

### Core Features

- 🌸 Gentle, supportive conversation style inspired by Rosebud
- 💾 Persistent journal entries with Supabase database storage
- 🔍 Vector-based RAG for intelligent context retrieval from past entries
- 📱 Beautiful, responsive web interface with gradient design
- 💬 Real-time chat with typing indicators
- 🔐 User authentication and secure data isolation
- 📝 Automatic conversation summarization
- 🎯 Multiple pages: Login, Home Dashboard, Entries, New Entry

### Technical Features

- **Supabase Integration**: Authentication, database, and vector storage
- **OpenAI Integration**: GPT-3.5-turbo for conversations and text-embedding-3-small for embeddings
- **Vector RAG**: Semantic search through past journal entries
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

2. **Create environment file**:

   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables** in `.env`:

   ```env
   # Supabase Configuration
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_KEY=your_supabase_anon_key

   # OpenAI Configuration
   OPENAI_API_KEY=your_openai_api_key

   # Flask Configuration
   FLASK_SECRET_KEY=your_flask_secret_key_here
   ```

4. **Get your Supabase credentials**:
   - Go to your Supabase project dashboard
   - Navigate to Settings → API
   - Copy the Project URL and anon/public key

### 4. Run the Application

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

- `POST /chat` - Send message to Goldfish (with RAG)
- `POST /new_session` - Start new conversation
- `POST /save_entry` - Save current conversation

## 🚀 Render Deployment

### Environment Variables (Render Dashboard)

Add these environment variables in your Render service settings:

- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase anon/public key
- `OPENAI_API_KEY` - Your OpenAI API key
- `FLASK_SECRET_KEY` - A secure random string

### Deployment Configuration

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python app.py`
- **Python Version**: 3.11.9 (specified in `runtime.txt`)

The application will automatically use the environment variables and connect to Supabase.

## 🧠 How RAG Works

1. **Entry Storage**: When you save a journal entry, the conversation is:

   - Summarized using GPT-3.5-turbo
   - Split into meaningful chunks
   - Each chunk is embedded using OpenAI's text-embedding-3-small
   - Stored in the `journal_entry_vectors` table

2. **Context Retrieval**: During new conversations:

   - Your current message is embedded
   - Vector similarity search finds relevant past entries
   - Context is injected into Goldfish's system prompt
   - Responses are more personalized and contextually aware

3. **Privacy**: All embeddings and entries are isolated per user using Row Level Security

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
│   └── summary_service.py
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

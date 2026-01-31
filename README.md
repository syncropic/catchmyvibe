# CatchMyVibe - DJ Enhancement Platform

A comprehensive DJ enhancement system that aggregates music from all sources, provides intelligent analysis, delivers real-time recommendations during live sets, and automates the tedious parts of DJing while amplifying creativity.

## Features

- **Music Aggregation**: Import from Rekordbox, Serato, Spotify, Tidal, and local files
- **Intelligent Analysis**: BPM detection, key detection, energy analysis, and audio embeddings
- **Real-time Recommendations**: Get next-track suggestions based on harmonic compatibility, BPM, and energy flow
- **Cloud-First Storage**: Audio files in the cloud, metadata synced everywhere
- **Multi-Device Access**: Your library travels with you

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- PostgreSQL with pgvector (provided via Docker)

### Development Setup

1. **Clone and install dependencies**:
```bash
cd catchmyvibe
make install
```

2. **Set up environment**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start services**:
```bash
make docker-up  # Start PostgreSQL and Redis
make dev        # Start backend and frontend
```

4. **Access the application**:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs

### Docker Setup (Full Stack)

```bash
docker-compose up -d
```

## Project Structure

```
catchmyvibe/
├── backend/                 # Python FastAPI backend
│   ├── api/                 # REST API endpoints
│   ├── analysis/            # Audio analysis (BPM, key, embeddings)
│   ├── ingest/              # Music import workers
│   ├── models/              # SQLAlchemy database models
│   ├── recommend/           # Recommendation engine
│   └── storage/             # Cloud storage abstraction
├── frontend/                # Next.js web application
│   ├── app/                 # App router pages
│   ├── components/          # React components
│   └── lib/                 # API client and utilities
├── integrations/            # DJ software integrations
│   ├── rekordbox/           # Rekordbox XML parser
│   ├── serato/              # Serato DB reader
│   ├── spotify/             # Spotify API client
│   └── tidal/               # Tidal API client
├── supabase/                # Database migrations
└── docker-compose.yml       # Docker orchestration
```

## Configuration

### Cloud Storage

Configure your cloud storage provider in `.env`:

```env
# Google Drive (recommended)
GOOGLE_DRIVE_CREDENTIALS_FILE=./credentials/google-drive.json
GOOGLE_DRIVE_FOLDER_ID=your-music-folder-id

# Or Backblaze B2
B2_APPLICATION_KEY_ID=your-key-id
B2_APPLICATION_KEY=your-app-key
B2_BUCKET_NAME=your-bucket-name
```

### Streaming Services

For metadata enrichment:

```env
SPOTIFY_CLIENT_ID=your-spotify-client-id
SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
```

## API Endpoints

### Tracks
- `GET /api/tracks` - List tracks with filtering
- `GET /api/tracks/{id}` - Get track details
- `POST /api/tracks` - Create track
- `POST /api/tracks/similar` - Find similar tracks

### Playlists
- `GET /api/playlists` - List playlists
- `GET /api/playlists/{id}` - Get playlist with tracks
- `POST /api/playlists/{id}/tracks/{track_id}` - Add track to playlist

### Import
- `POST /api/import/rekordbox` - Import Rekordbox XML
- `POST /api/import/serato` - Import Serato library
- `POST /api/import/spotify/sync` - Sync Spotify library

### Analysis
- `POST /api/analysis/analyze` - Queue tracks for analysis
- `POST /api/analysis/enrich` - Enrich tracks with API metadata
- `GET /api/analysis/stats` - Get analysis statistics

### Sessions
- `GET /api/sessions` - List DJ sessions
- `POST /api/sessions` - Create session
- `POST /api/sessions/{id}/tracks` - Add track to session

## Importing Your Library

### From Rekordbox

1. Export your Rekordbox library as XML
2. Upload via the web UI or API:
```bash
curl -X POST -F "file=@rekordbox.xml" http://localhost:8000/api/import/rekordbox
```

### From Serato

```bash
curl -X POST http://localhost:8000/api/import/serato
```

### From Local Files

```bash
curl -X POST "http://localhost:8000/api/import/local?directory_path=/path/to/music"
```

## Analysis Pipeline

The ephemeral analysis pipeline:

1. **Download**: Fetch audio from cloud storage
2. **Analyze**: Extract BPM, key, energy, embeddings
3. **Store**: Save results to database
4. **Delete**: Remove temporary audio file

Queue tracks for analysis:
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"track_ids": ["uuid1", "uuid2"]}' \
  http://localhost:8000/api/analysis/analyze
```

## Recommendation Engine

Get next-track recommendations:

```python
from recommend import RecommendationEngine

engine = RecommendationEngine()
recommendations = await engine.get_recommendations(
    session=db_session,
    current_track=playing_track,
    limit=10,
    energy_direction="build"  # or "maintain", "drop"
)
```

The engine considers:
- **BPM compatibility** (including half/double time)
- **Harmonic key matching** (Camelot wheel)
- **Energy flow** based on set direction
- **Audio similarity** via embeddings

## Development

### Running Tests
```bash
make test
```

### Linting
```bash
make lint
```

### Database Migrations
```bash
make migrate
```

## License

MIT License - See LICENSE file for details.

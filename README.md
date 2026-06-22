# DTV-Ad-Monitor

## Real-Time Television Advertisement Monitoring & Verification System

DTV-Ad-Monitor is an enterprise-grade television advertisement monitoring platform designed for broadcasters, regulators, advertising agencies, and media monitoring organizations.

The system captures live television feeds directly from HDMI capture devices, continuously analyzes broadcast content, detects advertisements in real time, verifies scheduled ad playout, generates evidence, and produces operational and compliance reports.

Unlike traditional monitoring systems that rely on RTMP, HLS, or IPTV streams, DTV-Ad-Monitor is built around physical HDMI capture hardware connected to television playout systems and broadcast receivers.

---

# Key Features

## Real-Time Advertisement Detection

* Continuous television monitoring.
* Advertisement fingerprint matching.
* Frame-based and audio-based detection.
* Detection confidence scoring.
* Real-time alert generation.

## HDMI Capture Monitoring

* Physical HDMI capture card integration.
* Automatic capture device discovery.
* Device health monitoring.
* Input probing and validation.
* Live snapshot generation.
* Capture interruption detection.

## Advertisement Verification

* Verify scheduled advertisements against actual broadcasts.
* Detect missed advertisements.
* Detect under-delivery and over-delivery.
* Broadcast reconciliation.

## Evidence Collection

* Screenshot capture.
* Advertisement clip extraction.
* Timestamped proof of transmission.
* Historical evidence retrieval.

## Channel Management

* Configure television channels.
* Assign HDMI capture inputs.
* Monitor channel health.
* Track heartbeat status.
* Capture interruption logging.

## Advertiser Management

* Advertiser profiles.
* Campaign tracking.
* Advertisement library management.
* Analytics and reporting.

## Operations Monitoring

* System health dashboards.
* Worker monitoring.
* Capture device status.
* Detection pipeline visibility.

## Security

* JWT authentication.
* Role-based access control.
* Audit logging.
* Administrative controls.

---

# System Architecture

```text
┌─────────────────────────────┐
│ Television Broadcast Source │
└──────────────┬──────────────┘
               │ HDMI
               ▼
┌─────────────────────────────┐
│ HDMI Capture Card           │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Capture Service             │
│ Frame Extraction            │
│ Audio Extraction            │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Detection Engine            │
│ Fingerprinting              │
│ Classification              │
│ Matching                    │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Detection Database          │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Reports & Analytics         │
└─────────────────────────────┘
```

---

# Technology Stack

## Backend

* Python 3.11+
* FastAPI
* SQLAlchemy
* Alembic
* PostgreSQL
* Kafka
* FFmpeg
* OpenCV

## Frontend

* React
* TypeScript
* Material UI
* Axios

## Infrastructure

* Docker
* Docker Compose
* Nginx

## Media Processing

* FFmpeg
* OpenCV
* Audio Fingerprinting
* Frame Hashing

---

# Prerequisites

Install the following software before running the system.

## Python

```bash
python --version
```

Recommended:

```text
Python 3.11+
```

---

## Node.js

```bash
node --version
npm --version
```

Recommended:

```text
Node.js 20+
```

---

## FFmpeg

Download the FFmpeg Essentials build.

Example installation path:

```text
C:\ffmpeg\ffmpeg-8.1.1-essentials_build
```

Add the following directory to PATH:

```text
C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin
```

Verify installation:

```bash
ffmpeg -version
```

---

## HDMI Capture Hardware

Supported devices include:

* UGREEN HDMI Capture
* Elgato HD60 Series
* AVerMedia Capture Cards
* Magewell Capture Devices
* Blackmagic Capture Devices
* OBS Virtual Camera

The capture card must be visible to the operating system.

---

# Backend Setup

## Create Virtual Environment

Always use a project-local virtual environment.

```bash
cd backend

python -m venv .venv
```

---

## Activate Virtual Environment

### Windows PowerShell

```bash
.venv\Scripts\Activate.ps1
```

### Windows CMD

```bash
.venv\Scripts\activate.bat
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

Additional capture device support:

```bash
pip install pygrabber
```

---

## Configure Environment

Create:

```text
backend/.env
```

Example:

```env
DATABASE_URL=postgresql://postgres:password@localhost/dtv_monitor
SECRET_KEY=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=60

KAFKA_BOOTSTRAP_SERVERS=localhost:9092

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_BUCKET_NAME=
```

---

## Run Database Migrations

```bash
alembic upgrade head
```

---

## Start Backend

```bash
uvicorn app.main:app --reload
```

Backend URL:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

---

# Frontend Setup

Install dependencies:

```bash
cd frontend

npm install
```

Start development server:

```bash
npm start
```

Frontend URL:

```text
http://localhost:3000
```

---

# HDMI Channel Management

The platform manages television inputs through HDMI capture devices.

Each channel contains:

```text
Channel Name
Input Identifier
Capture Device Name
Monitoring Status
Heartbeat Status
Interruption Status
```

Supported API operations:

```text
GET    /api/v1/channels
POST   /api/v1/channels
PATCH  /api/v1/channels/{id}

POST   /api/v1/channels/{id}/probe
POST   /api/v1/channels/{id}/heartbeat

GET    /api/v1/channels/capture-devices
GET    /api/v1/channels/{id}/snapshot
```

---

# Backend Modules

## API Routes

```text
advertisements.py
advertisers.py
auth.py
channels.py
detections.py
reports.py
users.py
```

## Monitoring Services

```text
capture_device_service.py
frame_extractor.py
audio_extractor.py
frame_hashing.py
audio_fingerprint.py
classifier.py
stream_ingestor.py
screenshot_service.py
```

## Workers

```text
ingestion_worker.py
detection_worker.py
detection_consumer.py
reconciliation_worker.py
reporting_worker.py
```

---

# Project Structure

```text
DTV-Ad-monitor
│
├── backend
│   ├── app
│   │   ├── api
│   │   ├── infrastructure
│   │   ├── models
│   │   ├── schemas
│   │   ├── workers
│   │   └── main.py
│   │
│   ├── alembic
│   ├── requirements.txt
│   └── .venv
│
├── frontend
│   ├── src
│   │   ├── api
│   │   ├── pages
│   │   ├── components
│   │   ├── contexts
│   │   └── App.tsx
│
├── docker-compose.yml
└── README.md
```

---

# Running With Docker

Build and start all services:

```bash
docker-compose up --build
```

Run in detached mode:

```bash
docker-compose up -d
```

Stop services:

```bash
docker-compose down
```

---

# Important Notes

* Keep the Python virtual environment inside `backend/.venv`.
* Ensure FFmpeg is installed and accessible from PATH.
* Ensure HDMI capture devices are connected before starting monitoring services.
* Verify capture devices using the Channel Management page before enabling monitoring.
* Physical capture devices are preferred over RTMP, HLS, or software stream sources.
* Snapshot and probe functions are available for troubleshooting capture hardware.

---

# Future Enhancements

* AI-powered advertisement recognition.
* Multi-channel monitoring clusters.
* Automatic ad schedule reconciliation.
* Broadcast compliance reporting.
* Cloud-based monitoring nodes.
* Distributed detection workers.
* Advanced analytics dashboards.
* Real-time notification system.
* Multi-station monitoring support.

---

## License

Internal/Private Project

Copyright © DTV-Ad-Monitor
All Rights Reserved.

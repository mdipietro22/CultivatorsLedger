# Cultivation Telemetry Engine

A local-first cultivation analytics suite built for home growers who want precision data without cloud dependency or subscription fees.

## Overview

This is a **local-first** telemetry engine that runs entirely on your own hardware. No cloud fees. No data sharing. No corporate surveillance. Just you, your plants, and your data.

Key features:

- **Real-time VPD tracking** – Know exactly when your plants are breathing optimally
- **Crop steering analytics** – Track dry-back slopes to dial in irrigation
- **Manual data entry** – Use it as a digital journal, even without sensors
- **Multi-room / multi-zone support** – Monitor different environments separately
- **CSV import** – Bring your existing spreadsheets into the system
- **DIY hardware support** – Connect your own sensors via Home Assistant

## Philosophy

This software follows the **Showroom Model**:

- The core engine is open-source (AGPLv3) and free for personal home growers
- Commercial facilities pay a fair license fee (see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md))
- Your data stays local – optional encrypted cloud backup is user-controlled

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.10+ (for sensor scripts)
- PostgreSQL 15+ (handled by Docker)

### 1. Clone the repository

```bash
git clone https://github.com/mdipietro22/cultivation-telemetry-engine.git
cd cultivation-telemetry-engine

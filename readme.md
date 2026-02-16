# RSS Aggregator (Filtered Cybersecurity Feed)

## Intro

This project is a lightweight RSS aggregation service designed to:

- Pull multiple external RSS feeds
- Apply configurable keyword and/or regex filters
- Aggregate matching entries into a single standardized RSS 2.0 feed
- Serve that feed over HTTP
- Provide a simple internal status page for visibility and diagnostics

It is intended to run inside a Docker container using Docker Compose, with no database required. All configuration is driven by a static `config.json` file mounted into the container.

The service:

- Fetches all configured feeds hourly (from container start)
- Applies inclusive ANY-match filtering
- Deduplicates by article link
- Keeps only the newest N items (default: 15)
- Serves a clean, UTF-8 encoded RSS 2.0 feed
- Logs all activity with timestamps (refresh cycles, fetch results, HTTP hits, etc.)

---

## Configuration

Configuration is handled via a JSON file (default path inside container: `/app/config/config.json`).

You define:

- `master_patterns` — filters applied to all feeds
- `urls` — individual feed definitions with optional per-feed filters

### Filter Types

Each filter rule has either a `keyword` or a `regex` type.

Keyword filter example:

```json
{ "type": "keyword", "keyword": "ZTNA" }

Regex filter example:

```json
{
  "type": "regex",
  "pattern": "regex string", 
  "flags": "i"               
}
```

### Behavior

- Per-feed filters are applied first.
- Master filters are applied second.
- Filters are inclusive ANY-match.
- Matching is done only against:
  - `title`
  - `summary` / `description`
  - `content` (if present)
- Items without:
  - `link`
  - a parsed date (`published_parsed`, `updated_parsed`, etc.)
  
  are dropped as invalid.

### Example `config.json`

```json
{
  "master_patterns": [
    { "type": "keyword", "keyword": "ZTNA" },
    { "type": "regex", "pattern": "\\bCVE-\\d{4}-\\d+\\b", "flags": "i" }
  ],
  "urls": [
    {
      "id": 1,
      "url": "https://isc.sans.edu/rssfeed_full.xml",
      "filters": [
        { "type": "keyword", "keyword": "Cybersecurity" },
        { "type": "regex", "pattern": "\\bnetwork\\s+access\\b", "flags": "i" }
      ]
    },
    {
      "id": 2,
      "url": "https://krebsonsecurity.com/feed/",
      "filters": [
        { "type": "keyword", "keyword": "Vulnerability" }
      ]
    }
  ]
}
```

---

## Deployment

The recommended deployment method is Docker Compose.

The application expects the configuration file to be mounted into the container from the host somewhere. For example, if you create `/data/rss-aggregator/config/config.json` on the host, you can mount that to `/app/config/config.json` in the container.

### Example `docker-compose.yml`

```yaml
services:
  rss-aggregator:
    image: ghcr.io/sphexi/rss-aggregator:main
    container_name: rss-aggregator
    restart: unless-stopped
    ports:
      - "44444:44444"
      - "33333:33333"
    volumes:
      - /path/to/config.json:/app/config:ro
```

### Steps

1. Place your `config.json` inside a local `path/to/` directory.
2. Run:

```bash
docker compose up -d --build
```

3. The container will:
   - Run an initial feed refresh
   - Schedule hourly refreshes
   - Begin serving endpoints

---

## Usage

The application exposes two endpoints on separate ports:

### RSS Feed (Public Safe)

```
http://<host>:44444/rss
```

- Returns a standard RSS 2.0 feed
- UTF-8 encoded
- Max 15 most recent items (default)
- Deduplicated by link
- Suitable for:
  - Feed readers
  - Slack/Discord integrations
  - FreshRSS
  - SIEM ingestion
  - Public consumption

This port may be publicly exposed.

---

### Status Page (Internal Only)

```
http://<host>:33333/status
```

Displays:

- Uptime
- Number of `/rss` hits
- Last refresh result and timestamp
- Configured feeds and filters
- Currently aggregated articles

This endpoint should not be publicly exposed.

Enforce isolation using:

- Firewall rules
- Reverse proxy ACL
- Private network binding
- Cloud security group restrictions

Port-based separation is enforced at the application level, but network-level controls are strongly recommended.

---

## License (MPL 2.0)

This project is intended to be distributed under the Mozilla Public License 2.0 (MPL 2.0).

Key points:

- You may use, modify, and distribute the software.
- If you modify MPL-covered files, you must make those modified files available under MPL 2.0.
- You may combine it with proprietary code.
- The license applies file-by-file, not to the entire larger work.

See: https://www.mozilla.org/en-US/MPL/2.0/

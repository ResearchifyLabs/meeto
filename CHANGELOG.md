# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `ManifestWriter` module for writing meeting participant manifests as JSON
- `SpeakerEventWriter` module for persisting DOM-based speaker events as JSONL
- `ParticipantScraper` for extracting participant metadata from Google Meet DOM
- Unit tests for ManifestWriter, SpeakerEventWriter, and ParticipantScraper

### Changed

- Speaker attribution simplified to pure DOM-based polling — removed audio-level analysis and vote-based stream-name correlation (Google Meet uses ~3 shared audio channels regardless of participant count, making per-stream attribution unreliable)
- All meeting artifacts now output under `{output_dir}/{meeting_id}/` (default `./generated/{meeting_id}/`)
- `JoinConfig.screenshot_dir` default changed from `"./screenshots"` to `None` (auto-computed from output_dir)

### Removed

- `stream_recording_enabled` from `AudioConfig` — per-stream audio recording removed from pipeline
- `stream_id` field from `SpeakerEvent` dataclass
- `update_stream_mapping()` and `stream_to_participant` from manifest output
- Vote-based stream-name correlation logic from `SpeakerTracker` JS

### Fixed

- `CorrelationSpeakerAttribution` now fires `on_speaker_change` callback (was silently ignoring it)

## [0.3.2] - 2026-03-23

### Added

- `make docker-build` and `make docker-test` targets for local Docker-based integration testing

### Changed

- Guest mode uses minimal stealth: `navigator.webdriver` override and `--disable-blink-features=AutomationControlled` only
- Camera permission no longer granted — bot joins without video (microphone-only permission for normal join flow)
- Improved mic/camera toggle selectors with case-insensitive matching and explicit wait

## [0.3.1] - 2026-03-23

### Added

- Xvfb auto-detection: guest mode automatically switches to headed browser when `DISPLAY` env var is set (virtual display), bypassing Google's headless bot detection

### Changed

- Guest mode now uses Chromium (instead of system Chrome) with fake media device streams
- Screenshots are now saved under `{screenshot_dir}/{meeting_id}/` so each meeting has its own folder
- Browser context for guest mode now sets viewport, locale, and microphone/camera permissions
- `Dockerfile.test` installs Chromium instead of Chrome to match library browser choice

### Removed

- Stealth init scripts (navigator.webdriver, plugins, WebGL, userAgentData spoofing) — ineffective against Google's server-side bot detection
- Stealth launch args (`--disable-blink-features=AutomationControlled`, `--no-first-run`, `--no-default-browser-check`)

### Fixed

- Screenshots not uploading when `join_meet` encounters an error — added error screenshot capture and `_flush_pending_uploads` in `finally` block
- Browser/context/playwright resource leak when `join_meet` raises an exception
- `run_meeting_worker` now sets state to `FAILED` if `join_meet` fails (previously stayed stuck on `JOINING`)

## [0.3.0] - 2026-03-23

### Added

- Guest join mode: join meetings without a Google account by setting `bot_name` in `JoinConfig`
- Anti-bot-detection: guest mode uses system Chrome (`channel="chrome"`) with stealth init scripts to bypass Google's automation blocking
- `BOT_NAME` environment variable support in `worker_config_from_env()`

### Changed

- Default `bot_name` is now `"Meeto"` (previously no default; guest mode was opt-in)
- `scripts/example.py` defaults to guest mode (`--storage-state` defaults to `None`, `--bot-name` defaults to `"Meeto"`)

## [0.2.0] - 2026-03-12

### Added

- Correlation-based speaker attribution strategy that maps Deepgram diarization labels to real participant names via Google Meet DOM active-speaker indicator
- `scripts/example.py` CLI entrypoint for running a meeting worker session
- Unit tests for transcript_writer, audio_writer, storage, end_detector, env_config, and deepgram modules
- Logging section in README with configuration examples
- `NullHandler` on root `meeto` logger per Python library best practices

### Changed

- Default diarization strategy from `dom` to `correlation`

### Fixed

- Speaker attribution always showing the same name for all speakers regardless of who was actually talking

## [0.1.0] - 2026-03-10

### Added

- Initial project structure with pluggable STT and storage adapters
- Playwright-based Google Meet joining and audio capture
- Deepgram STT integration
- Speaker attribution via Meet captions
- `meeto-auth` CLI for generating Google login sessions
- In-memory and extensible meeting lifecycle state store

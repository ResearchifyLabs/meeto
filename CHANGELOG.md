# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Screenshots now saved under `screenshots/{meeting_id}/` instead of a shared `screenshots/` directory
- Background screenshot uploads are flushed before process exit so uploads complete even on failure
- Guest mode headless detection: set realistic user-agent, viewport, and extended stealth init script

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

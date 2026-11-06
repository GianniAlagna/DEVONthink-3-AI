# Changelog

All notable changes. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased] — 1.0.0 (not published yet)

First release. Every step was tested on a MacBook Pro 2014 with macOS 11.7 and DEVONthink 3.9.17
(`docs/floor/`).

### Inbox (Block A)
- Smart Rule and menu trigger; background engine with queue, retries and dry-run (test mode) by default.
- Text check and OCR (Apple Vision, de/fr/it/en), document type, date, sender, receiver, subject.
- Standard file names from a template, tags from your vocabulary, filing into allowed groups.
- Review list for every proposal below the confidence threshold; undo for every change.
- Duplicates: replicate, copy or link note — always your choice. Nothing is ever deleted.

### Swiss (Block B)
- Swiss QR-bill decoding with validated IBAN/QR-IBAN and references; UID/MWST numbers.
- Retention classes; stated deadlines become calendar events after your OK; urgent letters flagged.

### Knowledge (Block C)
- Local search index; ask your documents with sources (`x-devonthink-item://` links).
- "Not found" without a model call when nothing matches well enough.
- Summaries and translation de ↔ fr ↔ it ↔ en; related documents; notes about people and companies (opt-in).
- Text that gives orders to an AI is removed before the model sees it; asking can never change your database.

### Schedules and operations (Blocks D, E)
- Nightly run over your scopes; weekly digest; hygiene report; similar-tag proposals; daily feed and mail
  summaries (opt-in).
- Health in the menu bar (AI, index, DT3, queue backlog); power mode (pauses on battery and low memory).
- Optional AI server in your network, with an API key kept in the Keychain.
- Diagnostics export without personal data.

### App
- Menu-bar app with installer, onboarding, settings, review list and ask window in German, French, Italian and
  English; macOS 11 or later, Intel and Apple Silicon.

### Known limits
- Answers of the small default model can be wrong; sources are always shown.
- Both AI servers use about 5 GB of memory; on 8 GB Macs use a LAN AI server.
- Self-signed app (no Apple Developer ID): macOS asks once at first launch.

# DT3 Agent – User guide (English)

DT3 Agent adds an AI to DEVONthink 3 that runs only on your Mac. It names, tags and files documents, reads Swiss
QR-bills, spots deadlines and duplicates, and answers questions about your documents with sources. **It never
deletes anything in DT3**, and every change can be undone.

*DT3 Agent is an independent open-source project and is not affiliated with DEVONtechnologies.*

## 1. Requirements

| | |
|---|---|
| macOS | 11 Big Sur or later; Intel from 2013 (Haswell) or Apple Silicon |
| DEVONthink | 3.9.x (DEVONthink 4 is not supported) |
| Memory | 16 GB recommended; with 8 GB use an AI server in your own network |
| Disk space | about 2.5 GB for the app and AI models |

## 2. Install

1. Open the DMG and drag **DT3 Agent** into **Applications**.
2. First launch: the app is self-signed (no Apple Developer ID).
   - macOS 11–14: right-click the app → **Open** → **Open**.
   - macOS 15 and later: open the app, then **System Settings → Privacy & Security → Open Anyway**.
3. **Quit DT3** (Cmd+Q). The Smart Rule script can only be copied while DT3 is closed.
4. Menu-bar icon → **Installation …**. Tick both AI model boxes (download from huggingface.co, about 1.9 GB,
   checksum verified) → **Install** → wait for `Done.`
5. Open DT3 again. On the first action macOS asks whether "DT3 Agent Engine" may control DEVONthink: **OK**.

## 3. Set up

Menu-bar icon → **Setup …**, then step by step with **Continue**:

1. **System check** – all green? Otherwise **Check again**.
2. **AI** – **Test** → `The AI answers.`
3. **About you** – your name (used as the receiver of letters to you; never proposed as a contact).
4. **Document names** – the name template, with a preview.
5. **Smart Rule in DT3** – in DT3: **Tools → New Smart Rule**, event **On Import**, action
   **Apply Script › External › DT3 Agent Enqueue**. Only groups with such a rule are processed.
6. **Ready** – leave **Keep test mode (recommended)** on.

### Test mode

In test mode (icon: eye) DT3 Agent writes **nothing** to DT3. All proposals go to the **Review Queue**. Once you
trust the proposals: **Settings → General → Test mode** off. Then confident proposals are applied directly;
uncertain ones still go to the Review Queue.

## 4. Everyday use

| What | How |
|---|---|
| New documents | reach the queue through the Smart Rule |
| Single documents | select them in DT3 → menu bar → **Process selected records** |
| Check proposals | menu bar → **Review Queue** → **Accept**, **Edit** or **Reject** |
| Take something back | menu bar → **Undo last batch …** (your own later changes stay) |
| Stop for a while | menu bar → **Pause** |

Each proposal shows **Before**, **Proposal** and the **confidence** in percent. **Show in DT3** opens the document.

### Swiss letters

- **QR-bills**: amount, currency, reference and creditor are read from the QR code and validated.
- **Deadlines**: "payable by …" becomes a proposal for a calendar event with a DT3 reminder – only after your OK.
- **Urgent letters** (debt collection, court, tax office): flagged in the Review Queue, optionally moved to a group.

## 5. Ask and summarise

Menu bar → **Ask …**

- Type a question, press Return. The answer names its **sources**; a click opens the document in DT3.
- If no document matches, DT3 Agent says so instead of guessing.
- **Summarise**: select a document in DT3, pick a language (DE, FR, IT, EN) → **Summarise**.
- Asking can never change anything in DT3. Orders to an AI found inside documents are removed first.

Note: the bundled model is small. Always check important answers in the source.

## 6. Schedule (Settings → Schedule)

| Job | Default | Effect |
|---|---|---|
| **Scopes** | empty | databases and groups the nightly run may read, one per line: `Database \| /Group/` |
| **Nightly run** | on, 02:30 | changed documents in the scopes go to the queue |
| **Weekly digest** | off | Monday 07:30: new documents, open deadlines – as a note proposal |
| **Hygiene report** | off | Sunday 03:30: untagged documents, old items in the inbox group, similar tags |
| **Feeds and mail** | off | daily 06:30: summary of new RSS, web and mail records |
| **Power mode** | on | pauses on battery and when memory is low |

Reports need a **group that already exists in DT3**; DT3 Agent never creates groups. Every report goes to the
Review Queue first; only **Accept** writes it as a note.

Under **Advanced** you can switch on **notes about people and companies**: from two documents of the same company
on, DT3 Agent proposes a note with links.

## 7. Menu-bar icon

| Icon | Meaning | What to do |
|---|---|---|
| ✓ | Ready | – |
| Eye | Test mode | normal; proposals only |
| Pause | Paused | menu → Resume |
| Crossed-out bolt | Waiting: on battery or low memory | connect the charger |
| ⚠︎ red | AI, AI index or DT3 not reachable | open DT3; menu → Installation … → Install |
| Hourglass red | queue stuck for over 2 hours | menu → Settings → General → Export diagnostics …, send to support |
| ⛔ red | engine not running | menu → Installation … → Install |

## 8. Settings at a glance

**General** (test mode, name, export/import, diagnostics) · **AI** (AI server address, optional API key in the
Keychain) · **Names** · **Tags** (your vocabulary) · **Filing** (groups per document type) · **Swiss** (urgent
letters, retention) · **Duplicates & cases** · **Privacy** · **Advanced** (threshold, people and companies) ·
**Schedule** (see 6). **Cmd+S** saves.

## 9. Remove

Menu bar → **Installation …** → **Remove**. Tick the boxes to also delete the AI models or the settings, Review
Queue and logs. Your DT3 databases stay unchanged. Then drag the app from **Applications** to the Trash.

## 10. Privacy and help

- Everything stays on your Mac. Details: [PRIVACY.md](../../PRIVACY.md).
- Report bugs: GitHub issues. Security problems: **Security → Report a vulnerability**.
- Support for businesses: [SUPPORT.md](../../SUPPORT.md).

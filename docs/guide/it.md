# DT3 Agent – Guida (italiano)

DT3 Agent aggiunge a DEVONthink 3 un’IA che funziona solo sul Suo Mac. Assegna nomi, tag e cartelle ai documenti,
legge le QR-fatture svizzere, riconosce scadenze e doppioni e risponde alle domande sui Suoi documenti indicando le
fonti. **Non cancella mai nulla in DT3**, e ogni modifica si può annullare.

*DT3 Agent è un progetto open source indipendente, non collegato a DEVONtechnologies.*

## 1. Requisiti

| | |
|---|---|
| macOS | 11 Big Sur o successivo, Intel o Apple Silicon |
| DEVONthink | 3.9.x (DEVONthink 4 non è supportato) |
| Memoria | 16 GB consigliati; con 8 GB usi un server IA nella propria rete |
| Spazio su disco | circa 2,5 GB per l’app e i modelli IA |

## 2. Installare

1. Apra il DMG e trascini **DT3 Agent** in **Applicazioni**.
2. Primo avvio: l’app è autofirmata (nessun ID sviluppatore Apple).
   - macOS 11–14: clic destro sull’app → **Apri** → **Apri**.
   - macOS 15 e successivi: apra l’app, poi **Impostazioni di Sistema → Privacy e sicurezza → Apri comunque**.
3. **Chiuda DT3** (Cmd+Q). Lo script della regola intelligente si copia solo con DT3 chiuso.
4. Icona nella barra dei menu → **Installazione …**. Spunti entrambi i modelli IA (download da huggingface.co, circa
   1,9 GB, somma di controllo verificata) → **Installa** → attenda «Fatto.»
5. Riapra DT3. Alla prima azione macOS chiede se «DT3 Agent Engine» può controllare DEVONthink: **OK**.

## 3. Configurare

Icona nella barra dei menu → **Configurazione …**, poi passo per passo con **Continua**:

1. **Verifica del sistema** – tutto verde? Altrimenti **Verifica di nuovo**.
2. **IA** – **Prova** → «L’IA risponde.»
3. **Lei** – il Suo nome (usato come destinatario delle lettere a Lei; mai proposto come contatto).
4. **Nomi dei documenti** – il modello del nome, con anteprima.
5. **Regola intelligente in DT3** – in DT3: **Tools → New Smart Rule**, evento **On Import**, azione
   **Apply Script › External › DT3 Agent Enqueue**. Vengono elaborati solo i gruppi con una tale regola.
6. **Pronto** – lasci attiva **Mantieni la modalità test (consigliato)**.

### Modalità test

In modalità test (icona: occhio) DT3 Agent **non scrive nulla** in DT3. Tutte le proposte finiscono nella **lista di
controllo**. Quando le proposte La convincono: **Impostazioni → Generale → Modalità test** disattivata. Le proposte
sicure vengono allora applicate direttamente; quelle incerte restano nella lista di controllo.

## 4. Uso quotidiano

| Cosa | Come |
|---|---|
| Nuovi documenti | entrano in coda tramite la regola intelligente |
| Singoli documenti | li selezioni in DT3 → barra dei menu → **Elabora i documenti selezionati** |
| Controllare le proposte | barra dei menu → **Lista di controllo** → **Accetta**, **Modifica** o **Rifiuta** |
| Tornare indietro | barra dei menu → **Annulla l’ultimo passaggio …** (le Sue modifiche successive restano) |
| Fermarsi un momento | barra dei menu → **Metti in pausa** |

Ogni proposta mostra **Prima**, **Proposta** e la **confidenza** in percento. **Mostra in DT3** apre il documento.

### Lettere svizzere

- **QR-fatture**: importo, valuta, riferimento e creditore vengono letti dal codice QR e verificati.
- **Scadenze**: «pagabile entro …» diventa una proposta di evento di calendario con promemoria DT3 – solo dopo il
  Suo consenso.
- **Lettere urgenti** (esecuzione, tribunale, fisco): segnalate nella lista di controllo, su richiesta spostate in un
  gruppo.

## 5. Chiedere e riassumere

Barra dei menu → **Chiedi …**

- Scriva una domanda e prema Invio. La risposta indica le **fonti**; un clic apre il documento in DT3.
- Se nessun documento corrisponde, DT3 Agent lo dice invece di indovinare.
- **Riassumi**: selezioni un documento in DT3, scelga la lingua (DE, FR, IT, EN) → **Riassumi**.
- Chiedere non può mai modificare nulla in DT3. Gli ordini rivolti a un’IA contenuti nei documenti vengono rimossi prima.

Nota: il modello incluso è piccolo. Verifichi sempre le risposte importanti nella fonte.

## 6. Pianificazione (Impostazioni → Pianificazione)

| Lavoro | Predefinito | Effetto |
|---|---|---|
| **Ambiti** | vuoto | database e gruppi che il lavoro notturno può leggere, uno per riga: `Database \| /Gruppo/` |
| **Lavoro notturno** | attivo, 02:30 | i documenti modificati negli ambiti vanno in coda |
| **Riepilogo settimanale** | disattivato | lunedì 07:30: nuovi documenti, scadenze aperte – come proposta di nota |
| **Rapporto di riordino** | disattivato | domenica 03:30: documenti senza tag, elementi vecchi nel gruppo in entrata, tag simili |
| **Feed e e-mail** | disattivato | ogni giorno 06:30: riassunto dei nuovi elementi RSS, web ed e-mail |
| **Risparmio energetico** | attivo | pausa a batteria e quando la memoria è scarsa |

I rapporti richiedono un **gruppo già esistente in DT3**; DT3 Agent non crea mai gruppi. Ogni rapporto passa prima
dalla lista di controllo; solo **Accetta** lo scrive come nota.

In **Avanzate** può attivare le **note su persone e aziende**: da due documenti della stessa azienda, DT3 Agent
propone una nota con i link.

## 7. Icona nella barra dei menu

| Icona | Significato | Cosa fare |
|---|---|---|
| ✓ | Pronto | – |
| Occhio | Modalità test | normale; solo proposte |
| Pausa | In pausa | menu → Riprendi |
| Fulmine barrato | In attesa: batteria o memoria scarsa | collegare l’alimentatore |
| ⚠︎ rosso | IA, indice IA o DT3 non raggiungibile | aprire DT3; menu → Installazione … → Installa |
| Clessidra rossa | coda bloccata da oltre 2 ore | menu → Impostazioni → Generale → Esporta diagnostica …, inviarla al supporto |
| ⛔ rosso | il motore non è in funzione | menu → Installazione … → Installa |

## 8. Impostazioni in breve

**Generale** (modalità test, nome, esporta/importa, diagnostica) · **IA** (indirizzo del server IA, chiave API
facoltativa nel portachiavi) · **Nomi** · **Tag** (il Suo vocabolario) · **Archiviazione** (gruppi per tipo di
documento) · **Svizzera** (lettere urgenti, conservazione) · **Doppioni e pratiche** · **Privacy** · **Avanzate**
(soglia, persone e aziende) · **Pianificazione** (vedi 6). **Cmd+S** salva.

## 9. Rimuovere

Barra dei menu → **Installazione …** → **Rimuovi**. Spunti le caselle per cancellare anche i modelli IA o
impostazioni, lista di controllo e log. I Suoi database DT3 restano invariati. Poi trascini l’app da
**Applicazioni** nel Cestino.

## 10. Privacy e aiuto

- Tutto resta sul Suo Mac. Dettagli: [PRIVACY.md](../../PRIVACY.md) (in inglese).
- Segnalare errori: issue su GitHub. Problemi di sicurezza: **Security → Report a vulnerability**.
- Supporto per aziende: [SUPPORT.md](../../SUPPORT.md).

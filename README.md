# Paluszki — dokumentacja techniczna

**Aplikacja tłumacząca język migowy na tekst.** Wideokonferencja w przeglądarce, w której
ruch migającego uczestnika jest na żywo zamieniany na napis w języku polskim wyświetlany
pod jego kafelkiem (i u pozostałych rozmówców).

> Status: działające demo end-to-end na CPU. Dataset: ASL Citizen (100 wyselekcjonowanych
> klas konwersacyjnych). LLM lokalnie przez Ollamę (Gemma).

---

## 1. Spis treści

1. [Architektura w skrócie](#2-architektura-w-skrócie)
2. [Technologie](#3-technologie)
3. [Funkcje](#4-funkcje)
4. [Główny przepływ pipeline’u tłumaczenia](#5-główny-przepływ-pipelineu-tłumaczenia)
5. [Komunikacja między komponentami](#6-komunikacja-między-komponentami)
6. [Model klasyfikacji znaków](#7-model-klasyfikacji-znaków)
7. [Kiedy i jak wywoływany jest LLM](#8-kiedy-i-jak-wywoływany-jest-llm)
8. [Parametry (serve.yaml) i ich dobór](#9-parametry-serveyaml-i-ich-dobór)
9. [Wyniki modelu na danych testowych](#10-wyniki-modelu-na-danych-testowych)
10. [Jak uruchomić całość](#11-jak-uruchomić-całość)
11. [Układ repozytorium](#12-układ-repozytorium)
12. [Ograniczenia i kierunki rozwoju](#13-ograniczenia-i-kierunki-rozwoju)

---

## 2. Architektura w skrócie

System składa się z **czterech procesów**, świadomie rozdzielonych, żeby ciężki stack ML
(torch + MediaPipe) był odseparowany od backendu aplikacji:

```
┌─────────────┐   WebSocket (sygnalizacja, chat,    ┌──────────────────┐
│  Frontend   │   klatki video, napisy)             │   Backend API    │
│ Next.js 15  │ ◄─────────────────────────────────► │   FastAPI :8000  │
│   :3000     │   + HTTP /api (auth, meetings)       │  (auth, meetingi,│
└─────────────┘                                      │   WebRTC sygnal.,│
      ▲  ▲                                           │   orkiestracja)  │
      │  │ WebRTC P2P (audio/video                   └────────┬─────────┘
      │  │ między uczestnikami)                               │ HTTP (klatka JPEG,
      │  └───────────────► drugi uczestnik                    │ wynik tłumaczenia)
      │                                                       ▼
      │                                          ┌────────────────────────┐
      │                                          │  Serwis ML  :8001       │
      │                                          │  FastAPI + pipeline     │
      │                                          │  (MediaPipe, klasyfik., │
      │                                          │   segmenter, bufor)     │
      │                                          └───────────┬─────────────┘
      │                                                      │ HTTP (OpenAI-compat
      │                                                      │ /v1/chat/completions)
      │                                                      ▼
      │                                          ┌────────────────────────┐
      └─ (kamera, mikrofon)                      │  Ollama  :11434         │
                                                 │  Gemma (gemma4:e2b)     │
                                                 └────────────────────────┘
```

| Proces | Rola | Domyślny port |
|---|---|---|
| **Frontend** (Next.js) | UI spotkania, przechwytywanie klatek z kamery, render napisów | 3000 |
| **Backend** (FastAPI) | auth/JWT, meetingi, poczekalnia, sygnalizacja WebRTC, chat, **orkiestracja tłumaczenia** | 8000 |
| **Serwis ML** (FastAPI) | trzyma sesje pipeline’u, MediaPipe + klasyfikator + segmenter + bufor + wywołanie LLM | 8001 |
| **Ollama** | lokalny serwer LLM (Gemma) wołany przez serwis ML | 11434 |

Kluczowa decyzja architektoniczna: **backend tylko odpytuje serwis ML po HTTP** — nie importuje
torcha/MediaPipe. Dzięki temu backend jest lekki, szybko startuje, a model można restartować /
przenieść na maszynę z GPU niezależnie. Symetrycznie traktowany jest LLM (też osobny, odpytywany
serwis — Ollama).

---

## 3. Technologie

**Frontend** — TypeScript, Next.js 15 (App Router), React 19, MUI, WebRTC API, Canvas API,
WebSocket. Auth: JWT w localStorage + interceptor axios.

**Backend** — Python 3.12, FastAPI, SQLAlchemy (async) + SQLite (`test.db`), PyJWT, passlib/bcrypt,
httpx (klient serwisu ML). WebSocket przez Starlette.

**Serwis ML** (`ml/`) — Python 3.12, FastAPI + uvicorn, PyTorch 2.10, MediaPipe 0.10.21 (Holistic),
OpenCV, NumPy, httpx (klient LLM). Zarządzanie zależnościami: `uv`.

**LLM** — Ollama, model `gemma4:e2b` (wariant „thinking", patrz §8). Brak kluczy API — wszystko
lokalnie.

---

## 4. Funkcje

- **Konta i logowanie** — rejestracja e-mail/hasło, JWT, (szkielet) Google OAuth.
- **Spotkania** — tworzenie spotkania (host) i dołączanie kodem; kod jest w URL `/meeting/<kod>`.
- **Poczekalnia z akceptacją** — gość dołączający trafia do poczekalni; host widzi panel z ✓/✗
  i zatwierdza/odrzuca. Powiadomienia idą po WebSocket.
- **Wideorozmowa P2P** — WebRTC (audio/wideo) bezpośrednio między uczestnikami, sygnalizacja
  (SDP/ICE) przez backend; STUN Google. Renegocjacja, gdy lokalna kamera pojawi się później.
- **Czat tekstowy** — w trakcie spotkania.
- **Tłumaczenie języka migowego → napisy** — przełącznik „Translate"; klatki lokalnej kamery lecą
  do backendu → serwisu ML, a rozpoznane zdanie wraca jako napis pod kafelkiem (u wszystkich,
  z nadawcą włącznie).
- **Debug overlay** — podgląd strumienia diagnostycznego z serwera (osobny tor WebRTC).

---

## 5. Główny przepływ pipeline’u tłumaczenia

Od ruchu ręki do napisu:

```
kamera (frontend)
  │  co 200 ms (5 fps): rysuje klatkę na <canvas> 480×360,
  │  koduje JPEG (q=0.6) → base64
  ▼
WS: { type: "video_frame", payload: { frameB64, ts } }
  ▼
Backend (ws_repo._handle_video_frame)
  │  - dekoduje base64 → bajty JPEG
  │  - throttle: jeśli poprzednia klatka tej sesji jeszcze się liczy → DROP
  │  - sesja per (meeting_code, user_id)
  ▼
HTTP POST :8001/sessions/{id}/frame   (surowe bajty JPEG, octet-stream)
  ▼
Serwis ML → TranslationSession.push_frame(bgr)
  ├─ 1. EXTRACTOR  — MediaPipe Holistic: klatka → 225-wymiarowy wektor keypointów
  │                  (poza 33×3 + lewa dłoń 21×3 + prawa dłoń 21×3)
  ├─ 2. SEGMENTER  — automat IDLE/SIGNING na podstawie wygładzonej prędkości dłoni;
  │                  zbiera klatki jednego znaku, kończy segment po pauzie
  ├─ 3. KLASYFIKATOR — segment (zmienna długość) → resampling do 32 klatek →
  │                  Transformer encoder → top-5 (gloss, prawdopodobieństwo)
  │                  • jeśli top-1 prob < min_confidence → znak ODRZUCONY
  │                  • wpp. trafia do bufora
  ├─ 4. BUFOR      — kolejka rozpoznanych znaków; „flush" gdy:
  │                  zebrano max_segments  LUB  pauza > flush_pause_ms
  └─ 5. LLM (przy flush) — lista znaków (gloss + top-5) → prompt → Gemma → zdanie PL
  ▼
HTTP 200: { text, gestureLabel, confidence }
  ▼
Backend: jeśli text niepuste →
WS broadcast: { type: "translation_result", payload: { userId, text, gestureLabel, confidence } }
  ▼
Frontend (useTranslationOverlay) → napis pod kafelkiem użytkownika `userId` (TTL ~6 s)
```

**Ticker pauzy.** Klatki przestają napływać, gdy ktoś znieruchomieje. Backend dla każdej sesji
co 0.4 s woła `POST /sessions/{id}/tick`, co pozwala buforowi „flushnąć" zebraną frazę po pauzie
(`flush_pause_ms`) nawet bez nowych klatek. Per sesja działa też lock, który serializuje klatki
względem ticków (sesja jest stanowa, niebezpieczna współbieżnie).

---

## 6. Komunikacja między komponentami

### 6.1 Frontend ↔ Backend

- **HTTP REST pod `/api`** (`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api`):
  `/api/auth/{register,login,current,logout}`, `/api/meetings`, `/api/meetings/{code}`,
  `/api/meetings/{code}/join`, `.../participants/{id}/approve|reject`.
- **WebSocket pod `/ws`** (`NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000/ws`):
  `ws://…/ws/meetings/{code}?token=<JWT>`.

Typy wiadomości WS (`app/schemas/ws.py` ↔ `api/interfaces/chat.ts`):

| Typ | Kierunek | Opis |
|---|---|---|
| `chat_message` | ↔ | czat |
| `sdp_offer` / `sdp_answer` / `ice_candidate` | ↔ | sygnalizacja WebRTC (P2P) |
| `sdp_debug_*` / `ice_debug_candidate` | ↔ | sygnalizacja toru debug |
| `participant_joined` / `participant_left` | ← | obecność (zawiera `status`, np. `waiting`) |
| `participant_approved` / `participant_rejected` | ← | wynik akceptacji w poczekalni |
| `debug_overlay_toggle` | → | włącz/wyłącz overlay debug |
| `video_frame` | → | klatka kamery (base64 JPEG + ts) do tłumaczenia |
| `translation_result` | ← | rozpoznane zdanie + etykieta znaku + confidence |

### 6.2 Backend ↔ Serwis ML (HTTP)

Backend jest klientem httpx (`app/translation_real.py`), serwis ML wystawia
(`ml/src/serve/http_app.py`):

| Endpoint | Opis |
|---|---|
| `POST /sessions` | tworzy `TranslationSession` (ładuje model + MediaPipe), zwraca `session_id` |
| `POST /sessions/{id}/frame` | surowe bajty JPEG → `{ text, gestureLabel, confidence }` |
| `POST /sessions/{id}/tick` | flush po pauzie (bez nowej klatki) |
| `DELETE /sessions/{id}` | zamyka sesję |
| `GET /healthz` | status + liczba aktywnych sesji |

Jedna sesja ML na `(meeting, user)` — bo segmenter i bufor są stanowe per migający.

### 6.3 Serwis ML ↔ Ollama (HTTP)

`OpenAICompatibleClient` (`ml/src/llm/openai_compat_client.py`) woła
`POST http://localhost:11434/v1/chat/completions` (format OpenAI). Bez klucza API.
Provider jest wymienny przez `serve.yaml` (Anthropic / OpenAI / Gemini / Ollama / mock) bez zmian
w kodzie.

### 6.4 Frontend ↔ Frontend (WebRTC)

Audio/wideo płynie **bezpośrednio** P2P między uczestnikami (WebRTC, STUN Google). Backend pełni
tylko rolę sygnalizacji (przekazuje SDP/ICE). Klatki do tłumaczenia idą natomiast osobnym torem
(WS → backend → ML), a nie przez WebRTC.

---

## 7. Model klasyfikacji znaków

**Plik:** `ml/src/models/keypoint_classifier/pipeline.py` (`KeypointClassifierPipeline`).
**Typ zadania:** izolowane rozpoznawanie pojedynczego znaku (isolated sign recognition).

### 7.1 Wejście — keypointy, nie piksele

Model nie patrzy na surowe wideo, tylko na **keypointy z MediaPipe Holistic**: każda klatka to
wektor **225 liczb** = poza `33×3` + lewa dłoń `21×3` + prawa dłoń `21×3` (x, y, z). Segment znaku
jest **resamplowany do 32 klatek** (`data.num_frames`) i opcjonalnie normalizowany
(`normalize_keypoints: true`). Zaleta: lekkość i odporność na tło/oświetlenie; wada: gubi subtelny
handshape i mimikę (stąd RGB-backbone jako kierunek rozwoju).

### 7.2 Architektura

```
keypoints [B, 32, 225]
  → Linear(225 → 256) + LayerNorm          (projekcja)
  → PositionalEncoding (sinusoidalna)
  → TransformerEncoder × 4 warstwy          (d_model=256, nhead=8, ffn=4·256, dropout=0.3)
  → mean-pooling po czasie → [B, 256]
  → głowa: LayerNorm → Dropout → Linear(256→512) → GELU → Dropout → Linear(512→100)
  → logity → softmax → top-5
```

`KeypointEncoder` jest wydzielony jako osobny moduł — celowo, pod przyszły pretraining encodera
na pełnym ASL Citizen (2731 klas) i fine-tuning samej głowy.

### 7.3 Hiperparametry (trening, `configs/asl_citizen100.yaml`)

| Parametr | Wartość |
|---|---|
| `num_frames` | 32 |
| `keypoint_dim` | 225 |
| `d_model` / `nhead` / `num_encoder_layers` | 256 / 8 / 4 |
| `classifier_hidden` / `pooling` | 512 / mean |
| `dropout` / `label_smoothing` | 0.3 / 0.1 |
| `batch_size` / `epochs` | 64 / 80 (early stopping patience 12) |
| `lr` / `weight_decay` | 3e-4 / 0.01 |
| `scheduler` / `warmup_epochs` | cosine / 3 |
| augmentacja | rotacja ±15°, skala 0.85–1.15, translacja, time-warp, frame-drop, szum, landmark-dropout |

Checkpoint: `ml/artifacts/asl_citizen100/best_model.pt` (+ `label_map.json`).

### 7.4 Inferencja (w serwisie)

`ClassifierRunner` (`ml/src/serve/classifier_runner.py`) ładuje checkpoint + label map, resampluje
segment do 32 klatek, normalizuje i woła `model.classify(..., top_k=5)` → zwraca listę
`(gloss, prawdopodobieństwo)` oraz `raw_argmax_conf` (pewność top-1). Urządzenie: `cpu`
(konfigurowalne; runner robi fallback `cuda→cpu`, jeśli brak GPU).

---

## 8. Kiedy i jak wywoływany jest LLM

**LLM NIE jest wołany per klatkę ani per znak.** Jest wołany **raz na frazę**, gdy bufor robi
flush (`ml/src/serve/session.py` → `_flush` → `Postprocessor.translate`).

**Warunek flush** (`ml/src/serve/buffer.py`, `should_flush`):
- w buforze uzbierało się `buffer.max_segments` znaków, **albo**
- minęła pauza dłuższa niż `buffer.flush_pause_ms` od ostatniego znaku
  (to wykrywa ticker backendu wołający `/tick`).

**Co dostaje LLM** (`ml/src/serve/postprocessor.py`):
- *system prompt*: „zamień predykcje glos ASL na płynne zdanie po polsku; dla każdego znaku masz
  top-5 kandydatów z pewnościami; top-1 jest poprawny ~72%, top-5 ~92%, więc prawdziwy znak prawie
  zawsze jest na liście; użyj tylko słów-treści z list kandydatów, wybierz najsensowniejszego
  kontekstowo (niekoniecznie top-1), dołóż minimalne słowa łączące, zachowaj kolejność ASL
  TOPIC-COMMENT, zwróć jedno zdanie".
- *user prompt*: lista `Sign i: gloss1(0.71), gloss2(0.12), …` dla każdego znaku w buforze.

Dzięki podaniu **całego top-5** LLM potrafi „naprawić" błędy top-1 modelu, korzystając z kontekstu
zdania — to kluczowy powód, dla którego niska dokładność top-1 jest znośna.

**Model LLM:** `gemma4:e2b` przez Ollamę. To model „thinking", więc w configu wymuszamy
`extra_body.reasoning_effort: none` — inaczej rozumowanie zjada budżet tokenów i `content` wraca
pusty. Parametry: `max_tokens: 256`, `temperature: 0.0` (deterministycznie).

---

## 9. Parametry (serve.yaml) i ich dobór

Plik `ml/configs/serve.yaml`. Najważniejsze pokrętła:

```yaml
classifier:
  config_path: configs/asl_citizen100.yaml   # config treningowy (architektura + label map)
  checkpoint:  artifacts/asl_citizen100/best_model.pt
  device: cpu                                 # 'cpu' lub 'cuda'
  top_k: 5

llm:
  type: openai_compat                         # anthropic | openai_compat | gemini | mock
  model: gemma4:e2b
  base_url: http://localhost:11434/v1
  max_tokens: 256
  temperature: 0.0
  extra_body:
    reasoning_effort: none                    # wyłącza "myślenie" Gemmy (inaczej pusty content)

pipeline:
  target_lang: pl                             # 'pl' | 'en'
  min_confidence: 0.3                          # odrzuca znak, gdy top-1 prob < próg
  segmenter:
    motion_threshold: 0.02                     # próg ruchu dłoni: IDLE↔SIGNING
    pause_frames: 9                            # ile klatek "ciszy" kończy znak (~0.3 s @30fps)
    min_segment_frames: 8                      # krótsze segmenty są odrzucane (~0.27 s)
    max_segment_frames: 90                     # górny limit długości znaku (~3 s)
    velocity_smoothing: 0.5
  buffer:
    max_segments: 8                            # flush po tylu znakach bez pauzy
    flush_pause_ms: 1500                       # flush po takiej pauzie → wywołanie LLM
  extractor:
    static_image_mode: false                   # true = dokładniej jak w treningu, wolniej
    min_detection_confidence: 0.5
    min_tracking_confidence: 0.5
```

Kalibrację najwygodniej robić na `scripts/test_webcam_pipeline.py` (overlay pokazuje stan
segmentera, bieżącą prędkość vs próg, zawartość bufora i ostatnie zdanie).

**Zmienne środowiskowe:**
- Backend: `PALUSZKI_TRANSLATION_ENABLED=1` (włącza realny pipeline; bez tego stub),
  `PALUSZKI_ML_SERVICE_URL` (domyślnie `http://localhost:8001`).
- Serwis ML: `PALUSZKI_SERVE_CONFIG` (domyślnie `configs/serve.yaml`),
  `PALUSZKI_LOG_LEVEL` (`INFO`; `DEBUG` loguje każdą klatkę).

---

## 10. Wyniki modelu na danych testowych

**Dataset:** ASL Citizen, podzbiór 100 klas konwersacyjnych (`build_asl_citizen_subset.py`).
Podział: **1530 train / 361 val / 1218 test**, ~14–19 próbek na klasę. ASL Citizen to nagrania
o jednolitej jakości (czystsze niż WLASL), z różnymi osobami migającymi w teście (held-out signers).

**Walidacja (zmierzone, MLflow, run `keypoint_classifier_asl_citizen100`, najlepsza epoka z 78):**

| Metryka | Wynik |
|---|---|
| **val top-1 accuracy** | **81.4%** |
| **val top-5 accuracy** | **97.0%** |

**Test (held-out, osoby niewidziane w treningu)** — liczby przyjęte w pipeline (system prompt LLM):

| Metryka | Wynik |
|---|---|
| **test top-1 accuracy** | **~72%** |
| **test top-5 accuracy** | **~92%** |

Spadek val→test wynika z generalizacji na nowe osoby migające (inny styl wykonania znaku) —
typowe dla isolated sign recognition. **Wniosek praktyczny:** top-1 myli się ~co czwarty znak,
ale prawdziwy znak prawie zawsze (≈92%) jest w top-5 — dlatego LLM dostaje pełne top-5 i wybiera
kontekstowo, co podnosi jakość finalnego zdania ponad surowe top-1.

> Ewaluacja: `uv run -m scripts.eval_asl_citizen --config configs/asl_citizen100.yaml
> --checkpoint artifacts/asl_citizen100/best_model.pt` (raportuje top-1/top-5 + accuracy per klasa
> na `test.csv`; wymaga pobranych nagrań w `datasets/ASL_Citizen/`).

---

## 11. Jak uruchomić całość

Wymagane: cztery procesy (lokalnie, CPU). LLM bez kluczy API.

```bash
# 1) Ollama z modelem (zwykle już chodzi jako usługa systemd)
ollama serve            # jeśli nie działa
ollama pull gemma4:e2b

# 2) Serwis ML — URUCHAMIAĆ Z KATALOGU ml/ (żeby ścieżki w serve.yaml się rozwiązały)
cd ml
uv run uvicorn src.serve.http_app:app --port 8001
#   debug klatek:  PALUSZKI_LOG_LEVEL=DEBUG uv run uvicorn src.serve.http_app:app --port 8001

# 3) Backend
cd backend
PALUSZKI_TRANSLATION_ENABLED=1 uv run uvicorn app.main:app --reload --port 8000
#   bez PALUSZKI_TRANSLATION_ENABLED=1 backend startuje na stubie (bez ML)

# 4) Frontend
cd frontend
npm install        # pierwszy raz
npm run dev        # http://localhost:3000
```


Diagnostyka pipeline’u bez frontu (potrzebne nagrania / webcam):
```bash
cd ml
uv run scripts/test_webcam_pipeline.py --mirror --llm-type openai_compat
```

---

## 12. Układ repozytorium

```
paluszki/
├── frontend/                     # Next.js 15
│   └── src/
│       ├── app/(protected)/meeting/[code]/MeetingPage.tsx   # spięcie spotkania
│       ├── components/meeting/   # VideoGrid, MeetingControls, WaitingRoom, ChatPanel
│       ├── hooks/                # useWebRTC, useSignTranslationCapture, useTranslationOverlay, ...
│       └── api/ws/websocketService.ts                        # singleton WS
├── backend/                      # FastAPI :8000
│   └── app/
│       ├── routes/               # auth, meeting (/api), ws (/ws)
│       ├── repos/ws_repo.py      # routing WS + transport klatek + ticker + throttle
│       ├── translation.py        # TranslationService ABC + TranslationManager (per meeting,user)
│       ├── translation_real.py   # klient HTTP do serwisu ML
│       └── schemas/ws.py         # typy i payloady wiadomości WS
└── ml/                           # pipeline + serwis ML :8001
    └── src/
        ├── serve/
        │   ├── http_app.py             # FastAPI serwisu ML (sesje, /frame, /tick)
        │   ├── session.py              # orkiestracja: frame→...→zdanie
        │   ├── live_keypoint_extractor.py  # MediaPipe Holistic
        │   ├── segmenter.py            # automat ruchu IDLE/SIGNING
        │   ├── classifier_runner.py    # adapter modelu + resampling
        │   ├── buffer.py               # bufor top-K + wyzwalacze flush
        │   ├── postprocessor.py        # prompt + wywołanie LLM
        │   └── config.py               # build_session_from_config
        ├── models/keypoint_classifier/pipeline.py   # model (encoder + głowa)
        ├── llm/                        # klienci LLM (anthropic/openai_compat/gemini/mock)
        ├── data/                       # datasety, ekstrakcja/normalizacja keypointów
        └── configs/                    # asl_citizen100.yaml (trening), serve.yaml (inferencja)
```

---

## 13. Ograniczenia i kierunki rozwoju

**Ograniczenia:**
- **Latencja:** 5 fps + MediaPipe + klasyfikator + flush LLM po ~1.5 s pauzy → napis pojawia się
  ~2–4 s po końcu frazy. To nie jest „real-time per znak".
- **CPU:** cały stack (MediaPipe + torch + Gemma) na CPU; OK dla 1–2 osób, przy większej liczbie
  rośnie obciążenie. Każda sesja buduje własny pełny pipeline (osobny load checkpointu + MediaPipe).
- **Słownictwo:** 100 wyselekcjonowanych klas — to demo, nie pełny PJM/ASL.
- **Keypointy gubią detal** (handshape/mimika) — sufit dokładności keypoint-based.
- `process_frame` liczy MediaPipe+klasyfikator na pętli zdarzeń serwisu (wariant demo); pod większym
  obciążeniem do przeniesienia na wątek (`asyncio.to_thread`).

**Kierunki rozwoju** (`ml/NOTES_asl_citizen.md`):
1. **Pretrain encodera** na pełnym ASL Citizen (2731 klas) → fine-tune głowy na 100 klasach
   (oczekiwane ~70–80% val) — `KeypointEncoder` jest już pod to wydzielony.
2. Łączenie wariantów per koncept (więcej danych na klasę).
3. RGB backbone (cnn_transformer / I3D / SlowFast) zamiast keypointów — większy koszt, ale
   łapie detal.
4. Współdzielenie jednego klasyfikatora między sesjami w serwisie ML (oszczędność pamięci/czasu).

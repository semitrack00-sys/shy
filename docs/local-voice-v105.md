# SHY v0.104–v0.105 local microphone path

SHY supports a selected microphone, an input-level meter, and a bounded WAV
transcription request to an optional local whisper.cpp server. Voice, speed, and
volume controls remain in the browser voice panel. The core does not install or
download a model at startup, capture the system microphone, or synthesize audio.

## Set up a local speech server

Use whisper.cpp v1.9.4 at commit
`927cfce34f31707e17f2bff35c349632fb9e2c3a`. Its server accepts WAV files at
`/inference`. Build it using its official Windows instructions and a CMake-capable
C++ toolchain. Keep it separate from the installed SHY checkout. In a development
terminal with Git and CMake available:

```powershell
git clone --branch v1.9.4 --depth 1 https://github.com/ggml-org/whisper.cpp.git C:\SHY-speech\whisper.cpp
if ($LASTEXITCODE -ne 0) { throw 'Speech engine checkout failed' }
Set-Location C:\SHY-speech\whisper.cpp
git rev-parse HEAD
cmake -S . -B build -DGGML_CUDA=OFF
if ($LASTEXITCODE -ne 0) { throw 'Speech engine configuration failed' }
cmake --build build --config Release --target whisper-server
if ($LASTEXITCODE -ne 0) { throw 'Speech engine build failed' }
```

Verify the printed commit against the pinned commit above. Download a multilingual
GGML model using the repository's documented model instructions. An English-only
`.en` model is unsuitable for testing other languages. This is a CPU build; GPU
support requires a compatible compiler/toolchain and separate hardware testing.

Start the executable from its actual build output location. Visual Studio builds
normally place it under `build\bin\Release`; other generators may use `build\bin`:

```powershell
.\build\bin\Release\whisper-server.exe -m .\models\ggml-base.bin --host 127.0.0.1 --port 8178 -nc
```

Use the model path actually downloaded. `-nc` prevents prior audio context carrying
into later requests. Do not enable `--convert`: SHY sends validated PCM WAV, avoiding
ffmpeg conversion and its temporary files. Keep the server on loopback and run
without administrator privileges. Review the engine's own logging and retention.

## Connect SHY

For a native core process, set:

```powershell
$env:SHY_WHISPER_URL = 'http://127.0.0.1:8178'
```

For the isolated Docker candidate, add this argument to its existing `docker run`
command **before** the image name:

```powershell
-e SHY_WHISPER_URL=http://host.docker.internal:8178
```

Docker Desktop must be able to reach that Windows service. If it cannot, use the
native local core or a deliberately isolated speech-service setup; do not expose
the speech server publicly. SHY allows HTTP loopback or `host.docker.internal` with
an explicit port, no credentials/path/query, and no redirects. Callers cannot
supply a destination URL. The route is disabled when configuration is absent or invalid.

`GET /voice/status` reports configuration, not model availability or measured
accuracy. `POST /voice/transcribe` accepts `{ "audio_base64": "...", "language": "auto" }`.
Only complete mono, 16-bit, 16 kHz PCM WAV of at most 30 seconds is accepted.
Body, transcript, response, concurrency, and time are bounded. The SHY core keeps
audio in request memory and does not write it to disk.

## Use the microphone panel

Open **Local speech engine and microphone**. **Choose microphone** requests
permission, refreshes input devices, and immediately releases its temporary stream.
Select the device and language, then press **Record with local engine**. The meter
shows peak input amplitude, not calibrated noise or audio quality. Press
**Transcribe recording**, or wait for the 30-second limit. Review the transcript,
then press Send. Cancel discards the result, stops microphone tracks, and aborts
the client request. A provider already computing may finish; cancellation does
not claim to terminate model inference.

Browser recognition and local recording are mutually exclusive. Remote browser
speech permission does not configure a cloud backend. Automatic language detection
is requested from the local engine when selected; availability and accuracy depend
on the model. Speech never grants approval or executes a computer action.

## Evidence

Tests cover PCM encoding/resampling, selected-device constraints, late microphone
permission, stale transcripts, malformed/truncated WAV, body limits, redirects,
timeouts, concurrency, and disabled setup. The release gate also builds the pinned
CPU engine, downloads a tiny multilingual model, and checks one JFK WAV through
the real adapter. That English smoke case is not a French/Haitian Creole benchmark,
Windows microphone validation, or GPU performance evidence.

Sources: [server documentation](https://github.com/ggml-org/whisper.cpp/blob/v1.9.4/examples/server/README.md)
and [build/model instructions](https://github.com/ggml-org/whisper.cpp/tree/v1.9.4).

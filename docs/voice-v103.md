# SHY v0.101–v0.103 browser voice

The web chat now offers **Speak to SHY**, **Stop voice**, **Read latest reply**, and
optional automatic reading of new replies. This uses the browser's recognition
and speech synthesis APIs; it does not install a speech model in the core.

## Use it on the Windows SHY computer

Update and validate the candidate core using the existing isolated Windows guide.
The current runtime version is 0.103.0. In the matching checkout, run:

```powershell
Set-Location C:\SHY-v100\apps\web
npm ci
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Web build failed' }
$env:SHY_BACKEND_BASE_URL = 'http://127.0.0.1:18000'
npm run start -- --hostname 127.0.0.1 --port 3000
```

That backend URL refers to the isolated candidate from the Windows validation
guide. Use your installed core's actual address only when intentionally testing
the installed runtime. Open `http://localhost:3000` in a supporting browser.
The app's existing Next.js server proxies submitted text to the selected SHY core.

1. Open **Voice settings and privacy** and select a language.
2. Keep browser-service permission off for on-device recognition. If the browser
   lacks local recognition or its language pack, SHY reports the limitation.
3. To use the browser's potentially remote service instead, explicitly enable
   **Allow browser speech services for this session**.
4. Press **Speak to SHY**, allow the microphone, and speak. Press **Finish
   recording** or wait for the browser's speech-end event. Capture is limited to
   30 seconds. No background listening or wake word is enabled.
5. Review and edit the transcript in the composer, then press **Send**. The text
   follows the existing chat and approval path. Speech is never an approval token.
6. Enable **Read new replies aloud**, or use **Read latest reply**. **Stop voice**
   cancels recording and playback; it does not cancel an already submitted server
   request. Starting a recording interrupts playback to avoid self-transcription.

Local speech synthesis uses only voices advertised as local by the browser unless
browser services are explicitly allowed. Language, voice, speed, and volume
controls are session settings. Installed voices and recognition providers determine
actual language support; a Haitian Creole menu option is not a speech-quality claim.
Changing conversations resets session voice settings and cancels queued audio.
Hiding the page or leaving the component cancels recording/playback. Typed chat
remains usable when speech is unavailable or permission is denied.

SHY does not receive or persist raw microphone audio. A browser service may process
audio or text externally when permitted. Transcripts are stored with your chat in
this browser after you send them, using existing history behavior. Local recognition
is conditional on browser support and language packs; offline operation is not
guaranteed. The core's `audio_capture: false` refers to server-side capture, not the
browser microphone. `/health` describes that distinction under
`browser_voice_capabilities`.

## Validation and remaining work

Automated tests cover session consent, final transcripts, late-event cancellation,
silence/deadline handling, denied permission, local voice selection, reply timing,
interruption, and conversation changes. They use browser API fixtures. The release
gate separately validates the packaged core and existing utility endpoints.

Real microphone recognition, installed voices, audio quality, Windows behavior,
and GPU speech performance must be checked on the target computer. Microphone
selection, automatic language detection, wake words, and hands-free mode remain
unimplemented. The full [v0.101–v0.200 roadmap](roadmap-v101-v200.md) records each
feature's actual status.

API references: [SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition)
and [SpeechSynthesis](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis).

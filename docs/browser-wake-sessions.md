# Bounded browser wake sessions — v0.105.7

Open **Voice settings and privacy**, allow a bounded wake session, and press
**Start wake voice session**. Say “Hey SHY” followed by your message. Saying only
“Hey SHY” arms the next utterance. Default mode stops capture and adds the command
to your draft; review it and press Send.

For optional hands-free conversation, separately select **Send wake-recognized
messages automatically for this session**, then give fresh session consent and
start. SHY sends only wake-recognized commands through the existing project chat
path, waits for the reply, reads it with a permitted voice, and then listens again.
Recognition pauses during sending and playback to avoid recognizing SHY's own
reply. No approval token is supplied; tool approvals require the existing text
review flow. Errors, blocked replies and pending approvals end the session.

This uses the existing browser speech API and transcript prefixes, not a custom
acoustic wake model. The browser microphone can process speech throughout an
active session. Compatible recognition and installed voices are required. Local
speech availability depends on browser language packs; remote browser speech
still needs its separate session opt-in. Audio is not saved by SHY. Multilingual
quality and microphone/GPU latency have not been measured on the user's PC.

Limits are three minutes total, twelve capture starts and six automatic messages.
The existing thirty-second per-capture limit remains. Speech errors, including
no-speech, stop the session. It does not listen indefinitely or in the background.
Expiry is checked both by timer and before processing a delayed transcript.

**Stop voice** cancels future recognition, queued rearming and playback, and
invalidates wake consent. It cannot cancel an already submitted backend chat.
Changing conversations, hiding or leaving the page, changing recognition language
or provider, or starting local microphone recording stops wake mode. Consent and
automatic sending are never stored and reset on reload. Switching automatic-send
mode requires fresh consent. Refused or uncertain submissions are never retried.

Tests cover prefix boundaries, accented command preservation, default review,
a separate command utterance, response/playback pausing, late callback rejection,
limits, refused submissions, approval boundaries and page exit. Chromium release
acceptance uses speech fixtures: it verifies UI/request behavior, not acoustic
quality. The core's raw audio, raw image and unrestricted execution invariants
remain disabled.

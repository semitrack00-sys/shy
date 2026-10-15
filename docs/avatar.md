# SHY human avatar (v0.105.26)

The user-selected fictional young adult Black male portrait appears in the header,
welcome screen, assistant replies and voice section. It is a locally served 640-pixel
WebP asset (about 28 KB); no external image or animation service is contacted.

The welcome and voice portraits explicitly say **AI avatar**. The photo is static:
there is no lip synchronization, facial animation or human operator. Existing browser
recognition/playback states drive listening/speaking rings. Pending chat shows thinking;
local recording/transcription reports its own state. A conversation switch stops local
recording and browser playback. The portrait never activates a microphone or speech.

A missing image falls back to an initial. Reduced-motion preferences disable the
activity animation. Existing voice consent, data-sharing and owner-access protections
remain in effect. Checks cover stop/switch transitions, asset failure, real image loading
and phone/desktop layout in the production frontend with fixture services.

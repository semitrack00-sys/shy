# Prepare the v0.106 multilingual speech evaluation

The evaluation runner is implemented as preparation for v0.106. That milestone
is not complete until genuine English, French, and Haitian Creole recordings are
evaluated and the resulting limits are reviewed. No such corpus is bundled.

Put consented mono 16-bit 16 kHz PCM WAV files (at most 30 seconds each) beside a
UTF-8 case manifest. Each reference must be checked against the actual recording,
not copied from the model's output. Use varied speakers, accents, background noise,
and task types relevant to SHY. Dataset representativeness is not automatically
verified by the runner. A minimum case count is a coverage check, not a statistical
guarantee of general accuracy.

The manifest structure is:

```json
{
  "cases": [
    {"id": "en-01", "language": "en", "audio": "en-01.wav", "reference": "Actual words spoken in this recording"},
    {"id": "fr-01", "language": "fr", "audio": "fr-01.wav", "reference": "Les mots réellement prononcés dans cet enregistrement"},
    {"id": "ht-01", "language": "ht", "audio": "ht-01.wav", "reference": "Pawòl moun nan di nan anrejistreman sa a"}
  ]
}
```

This illustrates the schema only; those files and reference recordings do not
exist in the repository. Add at least three distinct recordings per language for
the default coverage gate. Reusing identical audio cannot inflate coverage. The
runner rejects audio paths outside the manifest directory, malformed audio, empty
references, oversized manifests, and duplicate case IDs or audio.

After configuring the local server, run from the matching SHY checkout:

```powershell
$env:SHY_WHISPER_URL = 'http://127.0.0.1:8178'
python scripts/evaluate_speech.py --cases C:\SHY-speech\evaluation\cases.json --max-wer 0.25 --report .validation\speech-evaluation.json
```

`0.25` is an example caller-selected acceptance threshold, not a universal quality
standard. Choose and record the threshold before evaluation. Word error rate counts
substitutions, insertions, and deletions divided by reference words. Case and basic
punctuation are normalized; accents are preserved. A rate can exceed one when
insertions are numerous. The report also records per-case latency and real-time
factor, corpus WER for each language, failed requests, and missing coverage.

Exit status is nonzero if a required language lacks coverage, a request fails, or
a language exceeds the selected threshold. The report contains IDs, checksums,
counts, and metrics, not full transcripts or audio. It does not establish target
Windows microphone performance or GPU usage. Keep the corpus, consent, model
identity, engine commit, hardware details, and report together when reviewing the
results. A single English CI smoke case must not be presented as this evaluation.

# Prepare the v0.106 multilingual speech evaluation

The evaluation runner is implemented as preparation for v0.106. That milestone
is not complete until genuine English, French, and Haitian Creole recordings are
evaluated and the resulting limits are reviewed. No such corpus is bundled.

An offline Common Voice importer is available. Mozilla publishes the
[Haitian test dataset](https://mozilladatacollective.com/datasets/cmu5o29ou00w3mh07e9heh8xv),
but access requires your own account and acceptance of download terms. Use the
official download flow for English, French, and Haitian datasets. The importer
does not sign in, accept terms, fetch data, or re-share recordings. Keep the
original dataset provenance and terms with your local evaluation materials.

After extracting each language directory containing `test.tsv` and `clips/`, and
installing a trusted ffmpeg executable, run:

```powershell
python scripts/import_speech_corpus.py --dataset en=C:\SHY-speech\en --dataset fr=C:\SHY-speech\fr --dataset ht=C:\SHY-speech\ht --output C:\SHY-speech\evaluation --cases-per-language 3
```

Use a new output directory outside the SHY repository. The importer selects the
first requested test-split rows in source order, converts real recordings to the
required PCM format, and writes `cases.json`. It rejects duplicate audio,
traversal, missing coverage, and recordings over 30 seconds. Conversion failures
leave no partial corpus. Conversion tests use synthetic signals solely to check
file handling; they do not establish recognition quality. Check the selected
references and coverage before running the evaluator below.

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

# Criteria comparisons and reasoning checks

v0.105.13 adds numeric comparisons in ordinary chat and `/agent`, using the `option_comparison` request field. The web composer has a **Compare options** form. The stateless `POST /comparisons/evaluate` endpoint exposes the same calculation without history. It does not authenticate supplied scope or retrieve facts. The existing intelligence registry remains 50 handlers.

Supply 1–6 criteria and 2–8 options. Each criterion needs a unique ID, name, unit label, maximize/minimize direction and positive decimal weight at most 100. Each option needs its own unique ID, name and exactly one decimal string per criterion. Values support 12 integer and 8 fractional digits. No scientific notation, unit conversion, inferred values or missing entries. Labels are single-line text and are escaped in Markdown output.

Each column is normalized between its minimum and maximum across the supplied options. Maximizing uses `(value-min)/(max-min)`; minimizing uses `(max-value)/(max-min)`. Equal columns contribute 0.5. Weighted utility is divided by total weight and multiplied by 100. Forty-digit decimal calculation rounds scores to six places, and equal displayed scores share a rank with original input order preserved. Changing the option set or weights can change ranks. Exact supplied values also determine Pareto dominance in the structured result. Dominance requires no worse values on every criterion and strictly better on at least one.

The answer includes every criterion, direction, weight, unit and supplied value. It describes the score as relative to these inputs, with facts explicitly unverified. No model or external tool is invoked. Conversation ownership and project separation use existing chat checks, and the complete answer is saved in history. Comparison cannot be combined with task cancellation, resumption or approval tokens. `/comparisons/evaluate` inherits the 256 KiB streamed JSON body guard.

## Reproducible checks

Run `python scripts/evaluate_reasoning.py --report .validation/reasoning.json`. The 33 fixed reference cases in `docs/examples/reasoning-benchmark.json` cover exact decimal arithmetic, unsafe/undefined arithmetic rejection, numeric ranking and ties, invalid comparison rejection, citation membership, bounded atomic-field disagreement and provider date estimates against a fixed UTC clock. The report includes the fixture SHA-256 and individual results. CI publishes it with release validation.

These synthetic cases measure deterministic behavior only. They do not measure source truth, broad reasoning ability, semantic citation support, live models, representative user questions or performance on the user's hardware. The report deliberately leaves qualification incomplete. Actual PostgreSQL integration separately checks both chat routes, durable answer history, project ownership and no model invocation. Browser acceptance checks the filled form's request and reply persistence using fixtures.

## Remaining milestones through v0.150

The project cannot honestly declare v0.150 complete with the current evidence. Representative consented English, French and Haitian Creole recordings and actual speech evaluation remain missing for v0.106. Wake recognition quality, user microphone reliability and hardware latency are unqualified. General memory and document answer accuracy need representative datasets beyond regression checks. Image question answering, OCR, screenshot analysis, receipt/chart interpretation, multi-image comparison, selected screen capture and multimodal requests remain planned; there is no qualified vision model or user hardware available. Live research quality requires configured provider access and model evaluation; citation membership and provider date checks do not prove claims true. General prose contradiction detection and semantic evidence-gap checks are also incomplete.

The runtime stays v0.105.13 while these sequential qualifications remain unfinished. Later roadmap features implemented early are identified individually rather than relabeling the whole runtime v0.150.

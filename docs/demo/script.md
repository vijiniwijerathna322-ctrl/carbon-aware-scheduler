# Reproducible 60–90 second demo recording script

A [64-second native walkthrough](native-walkthrough.gif) is generated from real API responses by `scripts/record_demo.py`; [responses.json](responses.json) retains the actual outputs. This is a rendered walkthrough, not a browser or Docker screen recording. The following procedure is for the still-pending live capture.

1. Start the credential-free Docker demo using the README commands. Show the image running without an EIA key; keep terminals free of secret environment output.
2. Open `http://localhost:8000/docs` and show health, forecast and schedule endpoints. Explain that timestamps come from a frozen historical snapshot.
3. Call a six-hour carbon forecast. Point out the median, lower/upper values, issue time, data_as_of and artifact version. State that nominal carbon intervals failed held-out coverage validation.
4. Submit the documented two-hour 7 kW job and historical deadline. Show the recommendation and explain the deadline and whole-hour constraints.
5. Open the generated local CISO monitoring HTML report. Show input drift and insufficient post-fit coverage data; do not label absent realized metrics as healthy.
6. Show the coverage and scheduling figures. Explain the mean scenario result and oracle comparison, with a visible note that the target is an average generation proxy rather than marginal avoided emissions.

Native local API responses and Linux Docker smoke checks have been verified.
A [scripted real Chromium/container recording](browser/README.md) is now retained
from the published research image. It is automated, with the historical monitor
report identified separately; an independent human five-minute quickstart trial
remains pending.

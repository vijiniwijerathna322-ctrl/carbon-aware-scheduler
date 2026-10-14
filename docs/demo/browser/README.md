# Scripted real browser/container recording

[research-demo.webm](research-demo.webm) records actual headless Chromium running
against the published v0.2.0 container digest. It is an automated browser session,
not a human screen recording and not the earlier Matplotlib-rendered walkthrough.

Run 38522125741 pulled the verified image, started its credential-free frozen CISO
demo under read-only/non-root restrictions, displayed Swagger, and issued real
browser fetches for health, six-hour forecast and a two-hour 7 kW schedule. JSON
responses are displayed by the recording script and retained in
[responses.json](responses.json). The demo monitoring endpoint correctly returns
404 because the image does not embed a stale report. The video separately shows
the saved October 13 alert HTML and committed coverage/scheduling figures; that
HTML is historical evidence, not a current container monitoring response.

Artifact digest verified before extraction:
`sha256:d722b0eef74da8c3fe0c423d040fbb8df9afff5af18e833779d77cee7e107cc6`.

Reproduce through `.github/workflows/browser-demo.yml` and
`scripts/record_browser_demo.py`. Browser tooling is isolated to the capture job;
production dependencies, model bytes and registry selections remain unchanged.
An independent human quickstart trial is still separate acceptance work.

Verified video duration: 65.04 seconds. Extracted frames were visually inspected for Swagger, forecast, schedule, the saved alert report and result figures. Full response JSON retains forecast rows below the video viewport.

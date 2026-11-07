# Project workflow

Use Superpowers as the execution workflow and one coherent plan/test/review loop. Load Addy Osmani guidance for engineering depth on demand; its documentation-and-adrs skill owns architectural decision records. Use writing-technical-documentation for implementation-grounded explanations. The original skill setup lives outside this deliverable and is not required to run the benchmark.

Inspect source, tests, contracts, and existing ADRs before changing behavior. Keep agent and verifier build contexts separate. Never copy oracle code, private fixtures, provider credentials, host authentication files, or repository access into the agent image. Do not compile Python bytecode inside task directories; it can alter task checksums.

Do not change a task after observing model trials without versioning and explicitly separating results. Preserve all attempts, including infrastructure failures. Difficulty is an empirical result, not a property established by an oracle or a failing no-op. Publish complete contracts, not hidden requirements.

Run meaningful numerical, adversarial, and end-to-end Harbor controls before interpreting model scores. Record consequential decisions under docs/decisions. Do not claim a performance gain without a measurement, or policy-learning improvement from task evaluation alone.

Never commit credentials. Do not commit, push, or deploy without user authorization. The user authorized creation and publication to a private GitHub repository for this project; that does not authorize making it public or unbounded paid model runs.

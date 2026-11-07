# Model replacement audit

The deployment users are new people absent from model training. Reproduce the original comparison, then compare the same two frozen recipes under an evaluation appropriate for deployment. All measurements use the official UCI HAR training partition supplied in `data/dev.npz`. The private official test partition is unavailable. Private-set accuracy is diagnostic only and does not determine your reward.

## Data and recipes

`numpy.load('data/dev.npz', allow_pickle=False)` provides `X` (7352 rows × 561 engineered features), `y` (integer activity labels 1–6), and `subjects` (participant IDs). Row `i` has ID `dev-{i:05d}`. IDs and subjects are metadata, not predictive features. Keep the feature representation fixed. Dataset details and activity mappings are in `data/`.

The `baseline` is StandardScaler followed by LinearSVC(C=0.001, dual=False, max_iter=10000, random_state=17). The `candidate` is ExtraTreesClassifier(n_estimators=64, max_features='sqrt', random_state=17, n_jobs=1). The executable definitions are in `rrbench/experiments.py`. Hyperparameters are frozen. Fit preprocessing using training rows only. Do not tune models, use new data, or submit executable models.

The original protocol is StratifiedKFold(n_splits=3, shuffle=True, random_state=17) over rows. `original_report.json` is its actual output. Reproduce it rather than trusting it.

## Experiments and artifacts

The helper `python -m rrbench.cli --output original.json` reruns the original comparison. For another split: `python -m rrbench.cli --folds folds.json --output corrected.json`. It fits both frozen recipes on the same splits and outputs the evidence object below. The helper is available for convenience; the trusted verifier does not use your modified copy.

`folds.json` is an object mapping **every** development row ID to exactly one integer fold ID, 0, 1, or 2. For each fold, its validation rows are those assigned that ID and its training rows are the full complement. All three validation and training sets must contain every activity class. A corrected split must estimate performance on people absent from each fitted model's training data. Balance the number of validation people across the three folds (maximum difference one). Any partition meeting these conditions is accepted; the oracle's exact partition is not required.

Each evidence object has exactly these keys: `baseline_accuracy`, `candidate_accuracy`, `delta`, `ci95`, and `per_subject`. The last is an object keyed by each participant ID as a string, with `baseline` and `candidate` accuracies. Accuracy per participant is correct windows divided by that participant's windows. Overall accuracy is the unweighted mean over participants, not over windows. Delta is the mean of paired candidate-minus-baseline participant accuracies.

Compute `ci95` by sorting participant IDs numerically; draw 10000 bootstrap samples of participant indices using `numpy.random.default_rng(112).integers(0, n_people, size=(10000, n_people))`; compute the mean paired delta for each sample; then take quantiles [0.025, 0.975] with `method='linear'`. This is descriptive uncertainty conditional on the fitted CV models, not a population-wide guarantee.

`audit.json` has exactly `schema_version` (integer 1), `original` (original evidence object), `corrected` (corrected evidence object), `decision`, and `selected_recipe`. Use the corrected interval and a practical margin of 0.01 (one percentage point):

- Lower bound strictly above 0.01: `promote`, select `candidate`.
- Upper bound strictly below 0.01: `reject`, select `baseline`.
- Otherwise, including equality at either boundary: `inconclusive`, select `baseline`.

Reject means the evidence does not establish the required improvement; it does not assert the candidate is always worse. The threshold is a fixed benchmark policy, not a claim about real deployment economics.

`report.md` must explain the original problem, corrected protocol, numerical finding, decision, and limits in 40–16000 UTF-8 bytes. It is retained for analysis; it is not scored by an LLM. Scores are fractions in [0,1], not percentages. All submitted numbers must be finite. JSON duplicate keys, unknown fields, extra/missing rows, symlinks, and NaN/Infinity are rejected. Maximum artifact sizes are 1 MB for folds and 100 KB for audit. Numerical tolerance is absolute 1e-6.

## Reward and runtime

The primary reward is 1 only if all three artifacts satisfy this contract, corrected folds represent unseen people, independently recomputed evidence agrees, and the decision and selected frozen recipe agree with the policy. Otherwise a validly graded attempt gets 0. Infrastructure failures are recorded separately. The verifier never executes submitted code. Its internal logs and private data are inaccessible during your attempt.

You have 20 minutes on two CPU cores and 4 GB RAM. Package dependencies are installed. No package installation, GPU, network research, or external data is needed. Both recipes use one training thread. Model API access is supplied by the agent harness; it is not a task data source.

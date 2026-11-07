# Smartphone activity classifier replacement audit

## Question and original comparison

The deployment population is people absent from model fitting. The supplied report compares two frozen recipes with stratified three-fold cross-validation over individual windows. Windows from one participant therefore occur in both training and validation, allowing the models to benefit from person-specific patterns. That split does not estimate performance for new people, so its accuracy improvement does not substantiate the deployment claim.

I reproduced the original row-level protocol exactly (StratifiedKFold, three folds, shuffle enabled, seed 17) using the supplied UCI HAR development partition and the frozen recipes. The result matches `original_report.json`: participant-mean baseline accuracy 0.9711488703, candidate accuracy 0.9835005230, and paired mean change +0.0123516527. Its participant-bootstrap 95% interval is [0.0056722202, 0.0200414124]. This describes the leaky row-level comparison, not new-person performance.

## New-person comparison

I assigned all windows for each participant to one validation fold, with seven participants in each of three folds. Each fold's training data is the complement, so none of its validation participants is represented in that fitted model. Every training and validation partition contains all six activities. The features and frozen model recipes were unchanged; preprocessing was fitted on training rows only. The fold manifest is in `folds.json`.

For the corrected protocol, accuracy is calculated per participant and then averaged with equal weight across the 21 participants. The baseline mean is 0.9224774073 and the candidate mean is 0.9166391641. The paired candidate-minus-baseline difference is -0.0058382431 (about -0.58 percentage points); the participant bootstrap 95% interval is [-0.0281064276, 0.0178368525]. The interval is descriptive uncertainty over these participants conditional on the three fitted cross-validation models.

## Decision and deployment recipe

The fixed promotion margin is +0.01. Promotion requires the corrected interval's lower endpoint to be strictly above +0.01; rejection requires its upper endpoint to be strictly below +0.01. This interval spans the margin, so the decision is **inconclusive** and the policy selects the **baseline** recipe for deployment. The original raw accuracy increase is not evidence that the candidate improves performance for people absent from training.

## Limits

This audit uses only the 21 participants in the supplied official training partition. The grouped cross-validation estimates held-out performance within these development participants; it does not establish population-wide performance or guarantee behavior on a private test set or future users. The private official test partition was unavailable and was not used. The bootstrap interval reflects sampling participants from this small evaluation set and is conditional on the fitted CV models. The recipe comparison is limited to the stated frozen models and benchmark's one-percentage-point policy.

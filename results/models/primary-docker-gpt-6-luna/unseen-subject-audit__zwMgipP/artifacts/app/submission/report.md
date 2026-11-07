# Smartphone activity classifier audit

## Audit of the original claim

I reran the supplied three-fold, shuffled, row-stratified protocol with the frozen recipes and reproduced `original_report.json` exactly. It reports baseline accuracy 97.115% and candidate accuracy 98.350%, a paired difference of +1.235 percentage points (95% participant-bootstrap interval +0.567 to +2.004 points). This does not clear the specified +1-point promotion margin: its lower bound is below the margin. More fundamentally, row-wise splitting puts windows from the same participants in both training and validation, so the result does not estimate accuracy on new people. Reporting an unweighted mean over participants does not remove that training overlap.

## Person-held-out comparison

I assigned whole participants to three validation folds, with seven participants in each fold; every fold's training set is the complement. The assignment is a shuffled `StratifiedGroupKFold` partition (seed 17), keeping participants disjoint while spreading the six activity classes across folds. Fold 0 holds out participants 5, 14, 21, 23, 26, 27, 30; fold 1 holds out 6, 8, 11, 15, 16, 19, 22; fold 2 holds out 1, 3, 7, 17, 25, 28, 29. Both frozen models use the supplied features and are fit only on each fold's training rows. The reported accuracies average the 21 participant-level accuracies equally. The paired 95% interval uses the contract's 10,000 participant bootstrap samples and seed 112.

Baseline accuracy was 92.248%; candidate accuracy was 91.664%. Candidate minus baseline was -0.584 percentage points, with a 95% interval from -2.811 to +1.784 points. The corrected interval spans the +1-point practical margin, so the policy result is **inconclusive** and the selected recipe is the **baseline**. The evidence does not establish that the candidate meets the required improvement for new people.

## Recommendation and limits

Deploy the frozen StandardScaler + LinearSVC baseline (C=0.001, `dual=False`, `max_iter=10000`, `random_state=17`) as the current recipe. Do not replace it based on the original report. Reconsider a replacement only after evidence under the stated person-held-out policy clears the one-point margin.

This audit uses only the supplied official training partition and 21 participants. Its bootstrap interval is descriptive uncertainty conditional on these fitted folds; it is not a guarantee for the wider deployment population. The private official test partition was unavailable, and neither result establishes performance for people or settings beyond the supplied data.

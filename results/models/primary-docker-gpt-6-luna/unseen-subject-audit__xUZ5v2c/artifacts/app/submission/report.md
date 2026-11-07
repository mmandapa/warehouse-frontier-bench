# Audit of the activity classifier replacement claim

## Original comparison

The supplied row-wise StratifiedKFold split puts windows from the same participant in both training and validation. This leaks participant-specific information across the split and does not estimate performance for people absent from training. Re-running the frozen recipes reproduces the supplied report: participant-macro accuracy is 0.971149 for the baseline and 0.983501 for the candidate, a paired difference of +0.012352 (1.24 percentage points). The participant bootstrap 95% interval is [0.005672, 0.020041]. Although this looks favorable, it does not support the stated new-person deployment population.

## Corrected comparison

I used three-fold StratifiedGroupKFold (shuffle enabled, random_state 17), assigning each participant wholly to one validation fold. There are seven validation participants per fold; each training set is the complement and includes all activity classes. All windows for a held-out participant are therefore evaluated by models that did not train on that person. The features and both frozen recipes were unchanged, and scaling was fit within each training fold.

The participant-macro accuracy is 0.922477 for the baseline and 0.916639 for the candidate. The paired candidate-minus-baseline difference is -0.005838 (-0.58 percentage points), with a participant bootstrap 95% interval of [-0.028106, 0.017837] ([-2.81, +1.78] percentage points). The interval crosses the fixed +0.01 practical-improvement threshold, so the policy decision is **inconclusive** and selects the **baseline**. The result does not establish that the candidate is generally worse; it fails to establish the required improvement for this deployment population.

## Recommendation and limits

Keep the baseline for deployment decisions pending stronger evidence. The corrected estimate is based on only 21 participants in the official training partition, and its bootstrap interval describes uncertainty conditional on these fitted cross-validation models; it is not a population-wide guarantee. The private official test partition was unavailable and is not used to determine the decision. Any later evaluation should preserve participant separation and recruit or reserve additional people representative of deployment users.

# Smartphone activity classifier replacement audit

## Finding

The reported row-wise comparison gives the candidate an accuracy of 0.983501 versus 0.971149 for the baseline, a gain of 0.012352 (1.235 percentage points). Its participant-level bootstrap 95% interval is [0.005672, 0.020041]. The original run reproduces `original_report.json` exactly. This result does not estimate performance on new people: the shuffled row split puts windows from the same participants in both training and validation, allowing person-specific patterns to be shared across the split.

## Deployment-relevant comparison

I assigned the 21 development participants, in ascending participant ID order and round-robin, to three folds of seven participants each. Each fold validates on all windows from its seven participants, while training on the other 14 participants; no validation participant occurs in that fold's training data. All activity classes are present in every training and validation set. The feature representation and both frozen recipes are unchanged, and all preprocessing is fitted on the training rows for each fold.

Accuracy is computed within each participant, then averaged equally across the 21 participants. Under this protocol, baseline accuracy is 0.922629 and candidate accuracy is 0.922452. The paired mean candidate-minus-baseline difference is -0.000177 (-0.018 percentage points), with a participant bootstrap 95% interval of [-0.018844, 0.020373]. The interval is descriptive uncertainty conditional on these fitted cross-validation models, using 10,000 participant resamples and seed 112.

## Decision and recommendation

The predeclared practical margin is 0.01. The corrected interval's lower bound is not strictly above 0.01, and its upper bound is not strictly below 0.01. The policy therefore classifies the evidence as **inconclusive**. Select the frozen **baseline** for deployment pending stronger evidence; these results do not establish that the candidate is worse.

## Limits

This audit uses only the 21 people in the supplied official training partition. The official test partition was unavailable, and neither its accuracy nor performance on a broader deployment population can be inferred here. Each cross-validation model is trained on 14 people, fewer than a final model could use, and the bootstrap interval reflects only resampling of these 21 participants conditional on the fitted predictions. It is not a population-wide guarantee. The original window-level estimate is not evidence for the intended new-person population.

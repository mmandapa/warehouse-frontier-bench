# Replacement audit

The original row split puts windows from the same people in training and validation. It does not estimate the stated unseen-person deployment target. I used three person-disjoint folds and refit both frozen recipes on each training partition, including training-only scaling.

Original subject-macro accuracies: baseline 0.97114887, candidate 0.98350052. Corrected: baseline 0.90912746, candidate 0.90678586. Paired mean change -0.00234160; descriptive 95% interval [-0.018614847442751124, 0.016480270676641068].

Decision: inconclusive; retain the baseline unless promotion is established. This does not prove that every tree model is worse or that the interval generalizes to a population. The folds share training observations, and the dataset has few people. A larger prospective study is needed before a real deployment decision.

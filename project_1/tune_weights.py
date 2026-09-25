from credibility import score_url, llm_opinion
from evaluate import LABELLED_URLS


# Parameter tuning experiments for Project 1. 
# MAE is used to compare different parameter values.
# The results are used as a guide when selecting the final values. 

# Experiment 1: Preprint penalty 
# Test different penalties for arXiv and bioRxiv. 
# These sources were receiving too much credit from academic
# signals even though preprints may not have completed peer review. 

pre_prints = [ 
    {"name": "arXiv", "score": 0.77, "expected": 0.65},
    {"name": "bioRxiv", "score": 0.72, "expected": 0.50},
]
results = []

# Test penalties from 0.00 to 0.50 in steps of 0.01. 
for penalty in [i / 100 for i in range(51)]:
    errors = [] 

    for source in pre_prints: 
        new_score = source["score"] - penalty 
        error = abs(source["expected"] - new_score)
        errors.append(error)

    # Calculate the average absolute error for this penalty
    mae = sum(errors) / len(errors)
    results.append((penalty, mae))

    print(f"Penalty: {penalty:.2f} | MAE: {mae:.3f}")

# Find the lowest MAE produced during the experiment.
best_mae = min(mae for penalty, mae in results)

# More than one penalty can produce the same lowest MAE,
# so keep all penalties thar produce the best result 
best_penalties = [ 
    penalty
    for penalty, mae in results
    if abs(mae - best_mae) < 1e-9
]

min_penalty = min(best_penalties)
max_penalty = max(best_penalties)


# This midpoint is shown for comparison only.
# The final implementation does not automatically use it. 
midpoint_penalty = (min_penalty + max_penalty) / 2

print()
print(f"Best MAE: {best_mae:.3f}")
print(f"Best penalties: {best_penalties}")
print(f"Optimal range: {min_penalty:.2f} to {max_penalty:.2f}")
print(f"Midpoint of optimal range: {midpoint_penalty:.2f}")

# The lowest MAE occurred for penalties from 0.12 to 0.22.
# The final implementation uses 0.12, the smallest penalty in this range, 
# to avoid applying a stronger penalty when it does not improve the MAE. 


# Experiment 2: Positive URLS path bonus 
# Jama, WHO, and IMF received scores that were too low because the 
# original rules did not capture useful information in their URL paths. 
# Test how much additional weight should be given to positive path terms. 

positive_paths = [
    {"name": "JAMA", "score": 0.52, "expected": 0.93},
    {"name": "WHO", "score": 0.52, "expected": 0.88},
    {"name": "IMF", "score": 0.62, "expected": 0.85},
]

positive_results = []

# Test bonuses from 0.00 to 0.50 in steps of 0.01
for bonus in [i / 100 for i in range(51)]:
    errors = []

    for source in positive_paths:
        new_score = source["score"] + bonus
        error = abs(source["expected"] - new_score)
        errors.append(error)

    # Calculate the average absolute error for this bonus. 
    mae = sum(errors) / len(errors)
    positive_results.append((bonus, mae))

    print(f"Bonus: {bonus:.2f} | MAE: {mae:.3f}")

# Find the lowest MAE produced during the path bonus experiment. 
best_positive_mae = min(
    mae for bonus, mae in positive_results
)

# Keep all bonuses that produced the lowest MAE.
best_bonuses = [
    bonus
    for bonus, mae in positive_results
    if abs(mae - best_positive_mae) < 1e-9
]

min_bonus = min(best_bonuses)
max_bonus = max(best_bonuses)

# Show the best tested value without treating it as the 
# final value automatically used by the credibility scorer. 
best_tested_bonus = (min_bonus + max_bonus) / 2

print()
print(f"Best positive MAE: {best_positive_mae:.3f}")
print(f"Best bonuses: {best_bonuses}")
print(f"Optimal bonus range: {min_bonus:.2f} to {max_bonus:.2f}")
print(f"Best tested bonus: {best_tested_bonus:.2f}")

# A bonus of 0.36 produced the lowest MAE for these three examples. 
# Because the experiment used only three URLs, the final implementation 
# uses a smaller bonus od 0.10 to reduce the risk of overfitting. 
# The 0.10 bonus was then evaluated across all 24 labeled URLs. 


# Experiment 3: Rule-based and Claude weights 
# Collect one rule score and one Claude score for each labeled URL.
# Different combinations are then compared using MAE.

weight_data = []

for url, expected, rationale in LABELLED_URLS:

    #Get the rule-based score without calling Claude.
    rule_result = score_url(url, use_llm=False)
    rule_score = rule_result["score"]

    # Get Claude's credibility judment for the same URL.
    llm_signal = llm_opinion(url)

    # Only yse the eample if Claude returned a valid result.
    if llm_signal is not None:
        llm_score = llm_signal.value
        weight_data.append((expected, rule_score, llm_score))

weight_results = []

# Test rule weights from 0% to 100% in steps of 10%.
# The Claude weight is the remaining percentage. 
for rule_weight in [i / 10 for i in range(11)]:
    llm_weight = 1.0 - rule_weight
    errors = []

    for expected, rule_score, llm_score in weight_data:
        final_score = (
            rule_weight * rule_score
            + llm_weight * llm_score
        )

        error = abs(expected - final_score)
        errors.append(error)

    # Calculate MAE for this rule/Claude combination
    mae = sum(errors) / len(errors)
    weight_results.append((rule_weight, llm_weight, mae))

    print(
        f"Rules: {rule_weight:.1f} | "
        f"Claude: {llm_weight:.1f} | "
        f"MAE: {mae:.3f}"
    )

# Find and display the combination with the lowest MAE. 
best_weight_result = min(
    weight_results, 
    key=lambda result: result[2]
)

best_rule_weight, best_llm_weight, best_weight_mae = (
    best_weight_result
)

print()
print(
    f"Best combination: "
    f"{best_rule_weight:.1f} rules / "
    f"{best_llm_weight:.1f} Claude"
)
print(f"Best weight MAE: {best_weight_mae:.3f}")

# The weight experimet produced the lowest MAE with 
# 20% rules and 80% Claude.
# This combination was selected for the final implementation.
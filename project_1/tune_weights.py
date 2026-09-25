from credibility import score_url, llm_opinion
from evaluate import LABELLED_URLS


# Parameter tuning for Project 1 
# Find weights using evaluation error instead of choosing them manually. 

pre_prints = [ 
    {"name": "arXiv", "score": 0.77, "expected": 0.65},
    {"name": "bioRxiv", "score": 0.72, "expected": 0.50},
]
results = []
for penalty in [i / 100 for i in range(51)]:
    errors = [] 

    for source in pre_prints: 
        new_score = source["score"] - penalty 
        error = abs(source["expected"] - new_score)
        errors.append(error)

    mae = sum(errors) / len(errors)
    results.append((penalty, mae))

    print(f"Penalty: {penalty:.2f} | MAE: {mae:.3f}")

best_mae = min(mae for penalty, mae in results)

best_penalties = [ 
    penalty
    for penalty, mae in results
    if abs(mae - best_mae) < 1e-9
]

min_penalty = min(best_penalties)
max_penalty = max(best_penalties)

chosen_penalty = (min_penalty + max_penalty) / 2

print()
print(f"Best MAE: {best_mae:.3f}")
print(f"Best penalties: {best_penalties}")
print(f"Optimal range: {min_penalty:.2f} to {max_penalty:.2f}")
print(f"Chosen penalty: {chosen_penalty:.2f}")

# The grid search found an optimal penalty range from 0.12 to 0.22.
# A conservative penalty of 0.12 was selected from this optimal range.


# Tune positive path bonus using labeled examples

positive_paths = [
    {"name": "JAMA", "score": 0.52, "expected": 0.93},
    {"name": "WHO", "score": 0.52, "expected": 0.88},
    {"name": "IMF", "score": 0.62, "expected": 0.85},
]

positive_results = []

for bonus in [i / 100 for i in range(51)]:
    errors = []

    for source in positive_paths:
        new_score = source["score"] + bonus
        error = abs(source["expected"] - new_score)
        errors.append(error)

    mae = sum(errors) / len(errors)
    positive_results.append((bonus, mae))

    print(f"Bonus: {bonus:.2f} | MAE: {mae:.3f}")

best_positive_mae = min(mae for bonus, mae in positive_results)

best_bonuses = [
    bonus
    for bonus, mae in positive_results
    if abs(mae - best_positive_mae) < 1e-9
]

min_bonus = min(best_bonuses)
max_bonus = max(best_bonuses)

chosen_bonus = (min_bonus + max_bonus) / 2

print()
print(f"Best positive MAE: {best_positive_mae:.3f}")
print(f"Best bonuses: {best_bonuses}")
print(f"Optimal bonus range: {min_bonus:.2f} to {max_bonus:.2f}")
print(f"Chosen bonus: {chosen_bonus:.2f}")

# The grid search suggested 0.36 using only three examples.
# A conservative bonus of 0.10 was selected to reduce the risk of overfitting
# and was validated using all 24 URLs.


# Tune rule-based and Claude weights using the labeled examples.

weight_data = []

for url, expected, rationale in LABELLED_URLS:
    rule_result = score_url(url, use_llm=False)
    rule_score = rule_result["score"]

    llm_signal = llm_opinion(url)

    if llm_signal is not None:
        llm_score = llm_signal.value
        weight_data.append((expected, rule_score, llm_score))

weight_results = []

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

    mae = sum(errors) / len(errors)
    weight_results.append((rule_weight, llm_weight, mae))

    print(
        f"Rules: {rule_weight:.1f} | "
        f"Claude: {llm_weight:.1f} | "
        f"MAE: {mae:.3f}"
    )
"""
Constants of COVID-19 diasease and wealth distribution
"""

import numpy as np

"""
Probability of each infection serverity by age

Source: Imperial College Covid-19 research team
"""

age_hospitalization_probs = [0.001, 0.003, 0.012, 0.032, 0.049, 0.102, 0.166, 0.243, 0.273]
age_severe_probs = [0.05, 0.05, 0.05, 0.05, 0.063, 0.122, 0.274, 0.432, 0.709]
age_death_probs = [0.00002, 0.00006, 0.0003, 0.0008, 0.0015, 0.006, 0.022, 0.051, 0.093]

## Citar fontes

"""
Wealth distribution - Lorenz Curve

By quintile, source: https://www.worldbank.org/en/topic/poverty/lac-equity-lab1/income-inequality/composition-by-quintile
"""

lorenz_curve = [.04, .08, .13, .2, .55]
share = np.min(lorenz_curve)
basic_income = np.array(lorenz_curve) / share


def get_age_group_index(age):
    """
    Map age to Imperial College Table 6 age group index
    Age groups: 0-9, 10-19, 20-29, 30-39, 40-49, 50-59, 60-69, 70-79, 80+
    """
    if age < 10:
        return 0
    elif age < 20:
        return 1
    elif age < 30:
        return 2
    elif age < 40:
        return 3
    elif age < 50:
        return 4
    elif age < 60:
        return 5
    elif age < 70:
        return 6
    elif age < 80:
        return 7
    else:
        return 8

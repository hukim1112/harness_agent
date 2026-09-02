# Data Integrity and Basic Statistics Report

### `districts.json` Data Integrity and Basic Statistics

- All expected fields are present in every district object.

**Field Details:**
- `district`: Type: `str` (Unique values: 망원동, 삼성역, 성수동, 여의도, 홍대입구)
- `daily_foot_traffic`: Type: `int` (Range: 38000 - 93000)
- `monthly_rent_per_pyeong`: Type: `int` (Range: 150000 - 420000)
- `competitor_cafes`: Type: `int` (Range: 19 - 47)
- `avg_household_income_10k_won`: Type: `int` (Range: 3800 - 7100)
- `public_transit_score`: Type: `int` (Range: 72 - 98)
- `parking`: Type: `str` (Unique values: HIGH, LOW, MEDIUM)
- `target_age_group`: Type: `str` (Unique values: 20-30대, 25-35대, 30-45대)
- `weekend_traffic_boost`: Type: `float` (Range: 0.4 - 1.6)

**Note on requested fields vs. actual fields:**
The prompt requested 'name', 'latitude', 'longitude', 'population', 'competition', 'rent_cost', 'traffic_flow', 'accessibility'.
The `districts.json` file contains 'district' (maps to 'name'), 'daily_foot_traffic' (maps to 'traffic_flow'), 'monthly_rent_per_pyeong' (maps to 'rent_cost'), 'competitor_cafes' (maps to 'competition'), 'public_transit_score' (maps to 'accessibility').
Fields 'latitude', 'longitude', 'population' were not found in the `districts.json` file. Additional fields like 'avg_household_income_10k_won', 'parking', 'target_age_group', 'weekend_traffic_boost' are present.


### `scoring_weights.json` Data Integrity and Weight Analysis

**Weight Details:**
- `foot_traffic`: Weight: `0.3`, Description: `일일 유동인구`
- `rent_efficiency`: Weight: `0.25`, Description: `임대료 대비 유동인구 효율`
- `competition`: Weight: `0.2`, Description: `경쟁 카페 밀집도`
- `income_level`: Weight: `0.15`, Description: `주변 가구 평균 소득`
- `accessibility`: Weight: `0.1`, Description: `대중교통 접근성`

**Total Weight Sum**: `1.00`
- **Verification**: The sum of all weights is `1.0`, which is correct.

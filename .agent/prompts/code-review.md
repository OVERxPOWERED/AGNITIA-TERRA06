# Prompt: code review

Review the diff for subphase <ID> against ROADMAP.md *Done when* and `.agent/rules/`. Check in order:
1. Leakage (any `act_*` or post-issue-time data in features? random splits?)
2. Correctness of units/timezones (UTC inside, MW/MWh)
3. Tests present for the subphase's required checks
4. Config instead of constants; no secrets/data committed
5. API/schema/frontend type consistency
6. Readability and naming per data-contracts.md
Report findings as: severity, file:line, issue, concrete fix. Don't restate code that is fine.

You are an expert debugging assistant. I have a large number of failing tests, and I believe many are failing due to a few root-cause issues. My goal is to identify the most foundational test to fix first.

Based on the following list of failing test names and errors, please analyze the potential dependencies.

Instructions:

Identify the test that is most likely testing a core, low-level function that other features depend on (e.g., a database connection, a core model validation, a utility function).

Suggest the top 1-3 tests I should focus on first.

Provide a brief explanation for your reasoning.

please run poetry run pytest -q  to get a list of failing tests.  Then give me the top 3 tests I should focus on first.

Here is the list of failing tests:

[Paste the summary of your failing tests here]

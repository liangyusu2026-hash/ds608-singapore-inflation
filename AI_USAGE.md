## SU, Liang-Yu

Tool: Claude (Anthropic), used through claude.ai.

What I used it for:
- Proposal: generated a first draft of the group proposal, which the group then rewrote and edited.
- Data collection: helped me find the data.gov.sg and SingStat sources and check the downloaded CPI file (series count, date range, whether it was already linked across base years).
- Data cleaning: drafted src/wrangle.py and tested it on our raw files; typed the CPI weights table (cpi_weights_2024.csv) from Appendix III of the SingStat rebasing paper.
- Git/GitHub: gave step-by-step instructions for setting up the repo, branches and pull requests, which I typed and ran myself.
- Review: helped me review the Stage 2 analysis PR (wrote a check script that reproduced the tables and found the 2019-weight basis issue).
- Final check: compared the repo against the proposal and listed gaps to fix.

What I did myself / how I checked it:
- Ran wrangle.py myself and checked the processed files against the raw data.
- Spot-checked the typed weights against the rebasing paper PDF.
- Made all commits and pull requests, and wrote the README data section.
- All decisions on scope and methods were agreed upon by the group.
----------------------------------------------------------------------------------------------------------------------------------------------------------------------
## Amsyar

Tool: ChatGPT (OpenAI)

What I used it for: 
- Explaining Plotly and Streamlit concepts and tools
- Providing example code for dashboard features such as date-range sliders, category selectors and income-group comparisons.
- Assisting with debugging, code organisation and interface improvements.
- Highlighting important limitations of the processed data such as the expenditure weight change and residual differences that may affect objective interpretation of   visuals

## Jiang Liuru

Tools: Claude (Anthropic), used through claude.ai; GitHub Copilot Chat (agent mode) in VS Code.

What I used them for:
- Claude: explained the group's task split and the project guide, and helped me draft a detailed prompt for my analysis tasks; gave step-by-step Git instructions (pull, branch, stash, push).
- Copilot: implemented the Private Transport change, the surge_vs_cooling() table and the page findings in key_findings(), then ran the pipeline and recomputed the numbers independently. Also added these documentation entries and pushed them.

What I did myself / how I checked it:
- Reviewed the full diff of src/analysis.py before committing.
- Reran wrangle.py and analysis.py myself and checked each page finding against the output tables.
- Checked that the findings use descriptive, not causal, wording.
- Made the commit and pull request myself.

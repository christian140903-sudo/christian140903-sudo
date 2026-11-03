# Christian Bucher

Vienna, Austria

### [Portfolio: what I found, delivered, and where I am credited →](https://github.com/christian140903-sudo/christian140903-sudo/tree/main/portfolio)

First example: **CIRCL** (Computer Incident Response Center Luxembourg) released four commits from me in VulnTrain
3.4.0. They fix train/test leakage and the CVSS 4.0 reading in the dataset behind CIRCL's VLAI severity classifiers;
the release notes say "reported and fixed by Christian Bucher".
[Details →](https://github.com/christian140903-sudo/christian140903-sudo/blob/main/portfolio/01-circl-vulntrain/README.md)

## Contributions

Each entry links to its page in the portfolio, with the public record, the delivered files and verbatim quotes.

- **CIRCL**: train/test leakage and two readings of CVSS 4.0 in the dataset `CIRCL/vulnerability-scores`. Four
  commits accepted into VulnTrain 3.4.0; CIRCL rebuilt the dataset, retrained its RoBERTa classifier and published a
  technical report. A second fix, for the CVSS scores in `CIRCL/Vulnerability-FSTEC`, was merged on 3 November 2026
  ([details of the second fix](https://github.com/christian140903-sudo/christian140903-sudo/blob/main/portfolio/01-circl-vulntrain/README.md#part-2-vulnerability-fstec-november-2026)).
  [Details](https://github.com/christian140903-sudo/christian140903-sudo/blob/main/portfolio/01-circl-vulntrain/README.md)
- **AIT Austrian Institute of Technology**: three commits accepted into `main` of the repository that accompanies the
  CAM-LDS paper: a prompt script that samples the log lines again in every repetition, as Sect. 5.1.2 of the paper
  describes; a script that reproduces the numbers in the README's clarification of the paper's stability results
  (identical prompts in 89 of 198 attack steps); README notes on data set versions and `attack_times.csv`.
  [Details](https://github.com/christian140903-sudo/christian140903-sudo/blob/main/portfolio/02-ait-cam-lds/README.md)
- **Leibniz Institute for Astrophysics Potsdam (AIP)**: swapped site latitude and longitude columns in the APPLAUSE
  plate tables, for two plate archives in DR4 and one in DR3. AIP's errata name me ("User (C. Bucher, Wien) has
  pointed out …"); a correction is announced for a further data release.
  [Details](https://github.com/christian140903-sudo/christian140903-sudo/blob/main/portfolio/03-aip-applause/README.md)
- **OASIS CSAF Technical Committee and BSI**: public review comment on CSAF 2.1. Under the new `initial_release_date`
  rule, a converter would replace that date in 12,765 of 40,882 published CSAF 2.0 documents. Tracked as issue #1724,
  "created on behalf of Christian Bucher"; open.
  [Details](https://github.com/christian140903-sudo/christian140903-sudo/blob/main/portfolio/04-oasis-bsi-csaf/README.md)
- **Space Telescope Science Institute (STScI) / MAST**: correction package for the POSS-I plate dates in the MAST plate
  list of the Digitized Sky Survey; about three quarters of the listed dates are one day early. Reported to the MAST
  helpdesk; adoption not publicly documented.
  [Details](https://github.com/christian140903-sudo/christian140903-sudo/blob/main/portfolio/05-stsci-mast-poss1/README.md)
- **NeurIPS 2026 Predictive AI Evaluation Competition (PAIEC, Stanford AIMS)**: competition entry with code and report,
  including a data-quality audit of the competition data: the public baseline loader sees only 60 of 156 eligible graded
  benchmarks; three patches proposed. No leaderboard result is claimed.
  [Details](https://github.com/christian140903-sudo/christian140903-sudo/blob/main/portfolio/06-paiec-2026/README.md)

## Open-source tools

- [soul-mcp](https://github.com/christian140903-sudo/soul-mcp): memory server for MCP clients; quarantines injected
  instructions, records provenance ([on npm](https://www.npmjs.com/package/soul-mcp)).
- [postcondition-mcp](https://github.com/christian140903-sudo/postcondition-mcp): checks whether the world changed,
  not whether the agent said so ([on npm](https://www.npmjs.com/package/postcondition-mcp)).
- [behaviorlock](https://github.com/christian140903-sudo/behaviorlock): drift gate that compares recorded runs against
  contracts, without an LLM judge. Referenced by MediaPlural/agent-proven (its agent-regression skill points to
  behaviorlock).
- [agent-invariants](https://github.com/christian140903-sudo/agent-invariants): fail-closed checks for conditions that
  must stay true during an agent run. Listed by ContextOS among existing solutions in its landscape review.

Both references are pointers in other projects' documentation, not usage reports
([details](https://github.com/christian140903-sudo/christian140903-sudo/blob/main/portfolio/07-tools-cited-by-others/README.md)).
soul-mcp is on npm (current release 4.0.2); postcondition-mcp, behaviorlock and agent-invariants are small v0.1
releases from July 2026. No external users are documented for any of them yet.

## About

Based in Vienna. I work full-time outside IT, in sales and advisory work, and before that in dispatching; explaining
technical things to non-experts is my day job.

## Contact

If something here is wrong or out of date, please open an issue in this repository.

# Proposed contribution: prompt creation with new log samples per repetition

For [ait-aecid/attack-manifestations-interpretation](https://github.com/ait-aecid/attack-manifestations-interpretation)
(CAM-LDS case study), based on upstream commit `54bd78e` (2026-10-20).
Status: proposed to the maintainer; it is part of the upstream repository only if merged there.

## Background
Sect. 5.1.2 of the paper describes five repetitions per attack step "with new random samples of log lines".
`create_llm_prompt.py` samples the log lines once per scenario variant and step, so repetitions that select the
same variant receive identical prompts (89 of 198 steps). The upstream README explains this in the section
"Clarification regarding the stability results in our paper".

## Contents (three commits)
1. `create_llm_prompt_resample.py`: works like `create_llm_prompt.py` and takes the same parameters, but samples the
   log lines again in every repetition; writes `llm_queries_resampled.json` by default (`--output`).
   `create_llm_prompt.py` and `llm_queries.json` remain unchanged.
2. `count_identical_prompts.py`: counts identical prompts per step and reproduces the numbers of the clarification.
3. README notes on the data set versions and `attack_times.csv`.

## Apply
In a clone of the upstream repository (commit `54bd78e` or later):

```
git am cam-lds-resample.mbox
```

The same commits are in `patches/` as single files. The two scripts are included here only for reading.

## License
GPL-3.0, like the upstream repository (see `LICENSE`). `create_llm_prompt_resample.py` is a modified copy of
`create_llm_prompt.py` by the upstream authors; modifications by Christian Bucher, 2026-10-20.

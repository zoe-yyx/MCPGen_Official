# MCP Workflow Benchmark Release

This repository contains an anonymous release of the MCP workflow benchmark and its evaluation code.

## Contents

- `data/projects/`: public benchmark projects `mcp_project51` to `mcp_project75` only.
- `evaluation/`: the evaluation code used for the reported experiments.

## Data Release Scope

Only 25 projects are included in this public release.

- Public: `mcp_project51` to `mcp_project75`
- Withheld for a later release: the remaining projects not included here

Each released project directory includes a `.env` file with placeholder values only. No real API keys, base URLs, personal names, or email addresses are included in this repository.

## Placeholder Policy

Any secret or private value has been replaced with a neutral placeholder such as:

- `REDACTED_API_KEY`
- `REDACTED_SERVICE_TOKEN`
- `ENDPOINT_PLACEHOLDER
- `EMAIL_PLACEHOLDER`

These placeholders are present only to preserve file structure and reproducibility of the benchmark code.

## Evaluation Code

The `evaluation/` directory contains the streamlined evaluation pipeline for the released benchmark.

## Usage

The repository is intended for offline inspection and evaluation setup. Update the placeholder values in `.env` files only in your local environment before running experiments.


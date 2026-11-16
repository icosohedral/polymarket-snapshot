# Snapshot Refresh Action Setup

This repository includes a scheduled GitHub Actions workflow:
- `.github/workflows/snapshot-refresh.yml`

The workflow now contains all non-sensitive fixed values in the file itself.

## Required GitHub Secrets

Add these in:
- `GitHub repo -> Settings -> Secrets and variables -> Actions -> Secrets`

Required:
- `CLOUDFLARE_API_TOKEN`
- `ETHERSCAN_API_KEY`

## Fixed Values Already Embedded In Workflow

These do not need to be added as GitHub Variables:

- `CLOUDFLARE_ACCOUNT_ID=7e1d81bbd6646256381bd8a30b9532c2`
- `CLOUDFLARE_D1_DATABASE_ID=455f72ab-103e-413d-bff8-30726a46fcf6`
- `POLYMARKET_USER_ADDRESS=0x5838192D931f91D2e56893C634aD8861A49C367C`
- `PUSD_CONTRACT_ADDRESS=0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB`
- `CHAIN_ID=137`
- `SNAPSHOT_RETENTION=100`

## Important Security Note

An older Cloudflare API token existed in git history.
Do not reuse that token.

Create a new Cloudflare API token with the minimum D1 permissions needed by the refresh script,
save it as `CLOUDFLARE_API_TOKEN`, and revoke any previously exposed token.

## Expected Workflow Behavior

The workflow should run:

```bash
python -m pip install --upgrade pip -r scripts/requirements.txt
python scripts/snapshot_refresh.py
```

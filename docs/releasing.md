# Release checklist

The public repository is [vladzima/volna-skillcheck](https://github.com/vladzima/volna-skillcheck). GitHub releases carry the wheel and source archive. PyPI publishing is not configured.

1. Use **volna-skillcheck** as the GitHub repository name, distribution name, and CLI name. Confirm the GitHub owner, visibility, and PyPI ownership before publishing. If any name is unavailable, ask the maintainer; do not choose a replacement name.
2. Review every included file for private material and confirm rights to publish it under MIT. The fixtures must remain synthetic. Inspect `git status --short --untracked-files=all`; reports, credentials, and local runtime files must stay excluded.
3. Run the offline suite on supported Python versions and Linux/macOS in CI. Build a wheel and source distribution, run `twine check`, inspect archive contents, then install the wheel into a fresh environment outside the checkout and run the documented CLI path.
4. Run a live Codex smoke evaluation with at least one nonidentical answer pair and a positive-control case. Require zero adapter errors, both swapped judgments for the nonidentical pair, and populated model/version metadata. Do not require an improvement verdict: ties or insufficient evidence are valid results. Keep the report private. Revalidate isolation on every Codex upgrade; the initial tested CLI version is 0.166.0.
5. Set the release date, update the changelog, and synchronize the version in `pyproject.toml` and `volna_skillcheck.py`. Add verified repository URLs to package metadata after the repository exists.
6. Enable GitHub private vulnerability reporting and require the CI workflow before merging. Protect the release environment and configure PyPI trusted publishing if a package release is wanted. No automatic publishing workflow is included until the destination and ownership are verified.
7. Tag and publish only after reviewing the actual artifacts. Install the published artifact in a clean environment and repeat the CLI smoke test before announcing it.

A successful smoke evaluation verifies integration, not model quality. Publish the limitations alongside any example results.

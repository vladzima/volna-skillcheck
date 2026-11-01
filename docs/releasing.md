# Release checklist

The public repository is [vladzima/volna-skillcheck](https://github.com/vladzima/volna-skillcheck). GitHub releases and [PyPI](https://pypi.org/project/volna-skillcheck/) carry the wheel and source archive. The portable skill lives in `skills/volna-skillcheck/` and is installed from GitHub independently of the CLI.

1. Use **volna-skillcheck** as the GitHub repository name, distribution name, and CLI name. Confirm the GitHub owner, visibility, and PyPI ownership before publishing. If any name is unavailable, ask the maintainer; do not choose a replacement name.
2. Review every included file for private material and confirm rights to publish it under MIT. The fixtures must remain synthetic. Inspect `git status --short --untracked-files=all`; reports, credentials, and local runtime files must stay excluded.
3. Run the offline suite on supported Python versions and Linux/macOS in CI. Build a wheel and source distribution, run `twine check`, inspect archive contents, then install the wheel into a fresh environment outside the checkout and run the documented CLI path.
4. For adapter behavior changes, run a live smoke evaluation where credentials are available, with at least one nonidentical answer pair and a positive-control case. Require zero adapter errors, both swapped judgments for the nonidentical pair, and populated model/version metadata. Do not require an improvement verdict: ties or insufficient evidence are valid results. Keep the report private. Revalidate isolation on runtime upgrades; disclose adapters that remain fixture-tested. For skill changes, validate frontmatter and references, install a standalone copy with the documented installer in a scratch project, and check discovery in an available harness.
5. Set the release date, update the changelog, and synchronize the version in `pyproject.toml` and `volna_skillcheck.py`. Add verified repository URLs to package metadata after the repository exists.
6. Require the CI workflow before merging. The `pypi` GitHub environment allows version tags (`v*`) and the `main` branch for manual dispatch. The publishing identity is the owner/repository/workflow/environment tuple below; only the separate publish job can obtain an OIDC token.
7. Tag and publish only after reviewing the actual artifacts and the exact commit's CI. Publishing a GitHub release triggers `.github/workflows/publish.yml`. It checks tag/version agreement and ancestry on `main`, reruns offline tests, builds/checks/smoke-tests the wheel, and passes artifacts to the isolated publish job. Confirm the workflow succeeds, then install the package from PyPI in a clean environment and repeat the CLI smoke test before announcing it. Verify the public skill installer too.

## Trusted Publishing setup

The PyPI project owner configures this once under [account publishing](https://pypi.org/manage/account/publishing/) for a new project, or project publishing settings after the project exists:

| Field | Value |
| --- | --- |
| PyPI project | `volna-skillcheck` |
| GitHub owner | `vladzima` |
| Repository | `volna-skillcheck` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

Use [PyPI's pending publisher flow](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/) for the first upload. No long-lived PyPI token is needed. If a release ran before setup was complete, rerun its failed publish job after configuration. The workflow also supports manual dispatch from `main` with an existing release tag.

The workflow builds the PyPI files itself. Download its `python-distributions` artifact if attaching the exact same files to the GitHub release; independently rebuilding can change archive hashes. Never replace an existing PyPI version: fix it with a new version. For a partial upload, first inspect which files are already public and their hashes; do not blindly retry or hide conflicts with `skip-existing`.

A successful smoke evaluation verifies integration, not model quality. Publish the limitations alongside any example results.

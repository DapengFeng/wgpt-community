# Genesis

A starter template for projects that want reusable quality checks and clear
GitHub issue and pull request submissions. Each repository owns its contribution
rules, toolchain choices, and review process; customize these defaults to fit.

## What this template provides

- Repository quality checks managed with `pre-commit`
- Formatting and linting defaults for common project assets
- Five issue forms for bugs, features, documentation, maintenance, and questions
- A pull request template with changelog entries, test evidence, and migration notes
- Baseline ignore rules and repository metadata

## Included tooling

Enable only the toolchains your project needs. The supplied configuration covers:

- C/C++ formatting and linting
- Python formatting and linting
- Rust formatting and static checks
- Dockerfile linting
- CMake formatting
- Makefile linting
- YAML validation and general repository hygiene checks
- Conventional commit message validation

## Quick start

1. Use this repository as a template and clone the generated repository.
2. Customize `.pre-commit-config.yaml` for your languages and install the
   prerequisites required by the enabled hooks.
3. Install `pre-commit` and both types of repository hooks:

   ```bash
   python -m pip install pre-commit
   pre-commit install --hook-type pre-commit --hook-type commit-msg
   ```

4. Run the repository checks:

   ```bash
   pre-commit run --all-files
   ```

5. Add project code, build/test commands, and contribution documentation.
   Conventional commit messages are checked by the supplied commit-msg hook;
   adjust that configuration if your project uses a different convention.

## Submitting an issue

Search existing issues and read the project's contribution or support guidance
first. Choose the form that matches the work:

| Form | Use it for | Include |
| --- | --- | --- |
| [Bug report](.github/ISSUE_TEMPLATE/bug-report.yml) | Incorrect or unexpected behavior | Minimal reproduction, exact version/environment, expected and actual results |
| [Feature request](.github/ISSUE_TEMPLATE/feature-request.yml) | A new capability or behavior change | User problem, proposed scope, observable acceptance criteria, alternatives |
| [Documentation](.github/ISSUE_TEMPLATE/documentation.yml) | Missing, incorrect, or confusing docs | Page/path and version, current problem, proposed correction, completion criteria |
| [Maintenance](.github/ISSUE_TEMPLATE/maintenance.yml) | Refactoring, dependencies, CI, or performance work | Evidence, scope, compatibility risks, measurable completion criteria |
| [Question](.github/ISSUE_TEMPLATE/question.yml) | Usage help or a request that does not fit another form | Goal, specific question, what you tried, relevant environment |

For a reproducible bug report:

1. Reduce the problem to the smallest input, configuration, or example that
   still fails. Attach it or provide an accessible link when possible.
2. Include setup steps and exact commands or UI actions, in order.
3. Separate expected behavior from actual output and include the full relevant
   error text. Note how often it happens and the last working version if known.
4. Record the project version or commit, installation method, OS, and relevant
   runtime/dependency versions. A branch name alone is not a stable version.
5. Remove secrets and personal data from logs and examples. Report security
   vulnerabilities through the project's private security reporting channel,
   not a public issue.

Form placeholders are examples, not prefilled answers. Required fields request
only the information needed to investigate or assess the proposal. Blank issues
are disabled by default; the question form provides a general entry point.

## Submitting a pull request

Use the [pull request template](.github/PULL_REQUEST_TEMPLATE.md) and follow the
project's own contribution requirements:

- Explain the problem, resulting behavior, and scope. Link related issues;
  use `Closes #123` only when the PR fully resolves the issue.
- Write short changelog entries under applicable categories: **Added**,
  **Changed**, **Fixed**, **Deprecated**, **Removed**, or **Security**.
  Use **Internal** for changes with no user-facing impact. Update the project's
  changelog or release-note files if it maintains them.
- Record the exact commands, environment, and results of automated checks, or
  reproducible manual checks. Explain skipped/failed checks and limitations.
  For this repository, run `pre-commit run --all-files` before requesting review.
- Attach screenshots or logs when useful. Explain breaking changes, migration
  steps, risks, and rollback requirements.
- Fill every section; use `None` or `Not applicable` with a reason when needed.
  Check review items only after verifying them.
- Replace every `{{PLACEHOLDER}}` in the PR template. The existing GitHub Actions
  workflow reports uppercase template tokens in new or edited issue/PR titles
  and bodies, excluding HTML comments. This check does not assess whether a
  submission is complete or correct.

Automated pre-commit update PRs use the same sections and explicitly record
which checks were not run.

## Example structured submissions

These illustrative examples show the expected level of detail. Commands and
results must be replaced with evidence from the actual change.

### Bug report example

````md
## Context / Background

- Goal: install both repository hooks using the quick-start instructions
- Impact: ordinary formatting and lint checks do not run on commit

## Reproduction Steps

1. Clone a fresh copy of the repository with no existing local hooks.
2. Install pre-commit with `python -m pip install pre-commit`.
3. Run the old documented command: `pre-commit install -t commit-msg`.
4. Check which hooks exist:

   ```bash
   test -f .git/hooks/commit-msg && echo 'commit-msg installed'
   test -f .git/hooks/pre-commit || echo 'pre-commit missing'
   ```

## Expected Behavior

The documented setup installs both pre-commit and commit-msg hooks.

## Actual Behavior

Only commit-msg is installed. Reproduces on every fresh clone.

## Environment

- Project commit: ffa8b7b
- Installation: fresh Git clone, no custom core.hooksPath
- OS: Ubuntu 24.04
- Runtime / tools: Python 3.12, pre-commit 3.6.2, Git 2.43.0

## Screenshots / Logs

```text
commit-msg installed
pre-commit missing
```
````

### Feature request example

````md
## Context / Background

Contributors have questions about setup that are neither bugs nor new features.

## Problem Statement

Blank issues are disabled and no usage-question form is available.

## Proposed Change

- Add a question form asking for the goal, question, and previous attempts.
- Keep environment details optional when they do not affect the answer.
- Leave external support destinations to each project's maintainers.

## Acceptance Criteria

- [ ] The issue chooser offers a Question entry.
- [ ] The form asks for a specific question and what the contributor tried.
- [ ] Existing bug and feature forms remain available.

## Alternatives Considered

- Enable blank issues: easier to submit, but likely to omit useful context.
- Use Discussions: suitable for projects that have enabled that feature.
````

### Pull request example

````md
## Summary of Changes

- Fix quick-start setup so both formatting checks and commit-message checks
  are installed locally.

## Related Issue

No linked issue; this corrects the documented hook installation command.

## Changelog

- Fixed: quick-start instructions now install both repository hooks.

## Testing Evidence

### Commands

```bash
pre-commit install --hook-type pre-commit --hook-type commit-msg
test -f .git/hooks/pre-commit && test -f .git/hooks/commit-msg
pre-commit run --all-files
```

### Results

```text
Environment: Ubuntu 24.04, Python 3.12, pre-commit 3.6.2; fresh Git clone.
Both hook files exist (exit 0).
Applicable pre-commit checks passed; hooks without matching files were skipped.
```

## Screenshots or Logs

Not applicable: this changes a documented shell command, with results above.

## Breaking Changes

- [x] No breaking changes
- [ ] Breaking changes described below

None. No application behavior or public interface changes.

## Risks and Rollback

The setup command installs checks that may modify files during future commits.
No deployment is needed. Revert the documentation change to restore prior text;
existing local hook installations are unaffected by reverting documentation.

## Human Review Checklist

- [x] I followed the project's applicable contribution guidelines
- [x] The changes are limited to the stated problem
- [x] The issue, motivation, and acceptance criteria are reflected in this PR
- [x] Test commands and results, or manual verification and limitations, are recorded
- [x] Documentation and changelog / release notes are updated where applicable
- [x] Breaking changes, migration steps, risks, and rollback are documented where applicable
- [x] Logs, screenshots, and examples contain no secrets or personal data
````

## Customizing for your project

**Note for coding agents:** When adapting this template, rewrite this README
for the actual repository and project. Verify its purpose, features, structure,
setup, usage, and test commands against the code and existing documentation.
Replace generic template content with project-specific information and follow
the project's own conventions.

- Replace the generic README with project documentation and, if useful, a
  `CONTRIBUTING.md` describing project-specific setup, tests, and review rules.
- Adapt form fields, required information, labels, and PR sections to your
  project's workflow. Create any labels referenced by issue forms.
- Change `.github/ISSUE_TEMPLATE/config.yml` to allow blank issues or add
  `contact_links` for your actual support, discussion, or security destinations.
- Configure a private security reporting channel and document it in your
  project's security policy.
- Add or remove toolchains in `.pre-commit-config.yaml` and extend `.gitignore`.
- Add build, test, and release workflows appropriate to your stack.
- Configure `PRE_COMMIT_PAT` if using the supplied quarterly pre-commit update
  workflow, or replace that workflow with your preferred dependency updater.
- Adapt or remove the placeholder validation workflow if your project needs to
  discuss literal template tokens in issue or PR content.
- Add any automation-specific instructions according to your own project's
  conventions; this starter does not prescribe them.

The forms use GitHub's [issue form syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
and [form field schema](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema).

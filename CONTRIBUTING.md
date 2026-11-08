# Contributing to BEA_JobRunner

Thanks for your interest. BEA_JobRunner is a small tool with a narrow job: let an AI assistant run scripts on your machine only after a human approves each one. Contributions that keep it small, auditable and safe are welcome.

## Ground rules
- **Security first.** Changes that widen what a job can do (new path access, shell use, network listeners, skipping the approval prompt) will be held to a high bar. Say plainly in your PR what the change allows and why it is safe.
- **No shell, no open ports.** Jobs run without a shell and the runner never listens on a socket. Please keep it that way.
- **No third-party dependencies.** The runner uses only the Python standard library. `pytest` is for tests only.
- **Keep it readable.** The whole codebase should stay easy for one person to review in an afternoon.

## Reporting bugs
Open an issue with your Python version, the `mode` you use, a redacted `bea_jobrunner.json`, and the steps to reproduce.

**Security vulnerabilities:** do not open a public issue. Email jeremy.jackson0@beatek.io with the details and I will respond as soon as I can.

## Submitting changes
1. Fork the repo and create a branch from `main`.
2. Make your change, with a test for any new behaviour or fixed bug. Cases to cover include path escape, symlinks, timeouts, trust changes and audit tampering.
3. Run the tests from the folder that contains `BEA_JobRunner`:
   ```
   python3 -m pytest BEA_JobRunner/tests
   ```
4. Open a pull request describing what changed and why. Keep PRs focused: one concern per PR.

## Style
- Python 3, standard library only, in the style of the existing files.
- Keep the copyright header at the top of each source file:
  ```
  # Copyright (c) 2026 Jeremy Frank Jackson dba BEATEK
  # Licensed under the MIT License.
  ```
- Update `README.md` when behaviour, config keys or commands change.

## Licensing of contributions
By submitting a contribution you agree that it is licensed under the project's [MIT License](LICENSE), and that you have the right to submit it.

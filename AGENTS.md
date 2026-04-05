# AGENTS.md

## Cursor Cloud specific instructions

This is a pure Python library (`pytimetag`) for TimeTag data processing used in physics/quantum optics. No external services, databases, or Docker are required.

### Key commands

| Action | Command |
|--------|---------|
| Install deps | `pip install -r requirements-test.txt && pip install -e .` |
| Lint | `python3 -m pylint pytimetag/` |
| Tests | `python3 -m unittest discover tests/ -v` |
| Coverage | `python3 -m coverage run -m unittest discover tests/ && python3 -m coverage report` |

### Notes

- Use `python3` not `python` (the latter is not aliased on this VM).
- Pylint is configured via `.pylintrc`; the codebase uses camelCase naming style. Pylint will report convention warnings on existing code — this is expected (score ~5/10).
- Numba JIT compilation causes a `NumbaTypeSafetyWarning` during deserialization tests — this is a known upstream warning, not a test failure.
- First test run is slower (~18s) due to Numba JIT warm-up; subsequent runs are faster.
- Coverage configuration is in `.coveragerc`.

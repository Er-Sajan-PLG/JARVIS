module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "type-enum": [2, "always", [
      "feat", "fix", "docs", "style", "refactor", "perf",
      "test", "build", "ci", "chore", "revert", "breaking"
    ]],
    "scope-enum": [2, "always", [
      "brain", "models", "memory", "adapters", "bootstrap",
      "guardrails", "events", "session", "workspace", "artifacts",
      "telemetry", "prompt", "context", "conversation", "domain",
      "integrations", "resources", "config", "api", "cli", "deps",
      "docs", "release", "security", "deps"
    ]],
    "subject-max-length": [2, "always", 72],
    "body-max-line-length": [2, "always", 100],
    "header-max-length": [2, "always", 100]
  }
};
# Claude Configuration

**Last Updated:** 2026-04-29  
**Agent Count:** 12 primary agents  
**Persona:** Software Engineer

## Core Conventions

**ALWAYS load first, before any agent:**

```
.claude/conventions/core/general.md
```

This file contains:
- System startup checklist (branch check, session management)
- Feature branch naming conventions
- General development rules
- Session management protocol
- Core conventions (repository structure, error handling, imports)

## Agent Registry

Match the user's request to **ONE** agent and load **ONLY** that file.

| Agent | Purpose | File Path |
|-------|---------|-----------|
| incident-agent | Manage incident response, triage, postmortems, and on-call processes | .claude/agents/incident-agent.md |
| review-agent | Code, performance, and accessibility reviews | .claude/agents/review-agent.md |
| security-agent | Design secure systems, threat modeling, vulnerability assessment, and compliance | .claude/agents/security-agent.md |
| product-agent | Drive product strategy, requirements, roadmap planning, and metrics | .claude/agents/product-agent.md |
| orchestrator-agent | Coordinate multi-step workflows and manage complex tasks | .claude/agents/orchestrator-agent.md |
| explain-agent | Code walkthroughs and onboarding assistance | .claude/agents/explain-agent.md |
| ask-agent | Answer questions and provide explanations | .claude/agents/ask-agent.md |
| compliance-agent | SOC 2, ISO 27001, GDPR, HIPAA, PCI-DSS compliance | .claude/agents/compliance-agent.md |
| plan-agent | Develops PRDs and works with architects to create ARDs | .claude/agents/plan-agent.md |
| document-agent | Generate documentation, READMEs, and changelogs | .claude/agents/document-agent.md |
| enforcement-agent | Reviews code against established coding standards and creates change requests | .claude/agents/enforcement-agent.md |
| debug-agent | Diagnose and fix bugs, issues, and errors | .claude/agents/debug-agent.md |

## Routing Rules

Match the user's request to the appropriate agent:

### Code Implementation
- **Keywords:** "write", "implement", "create", "build", "add feature"
- **Agent:** code-agent

### System Design
- **Keywords:** "design", "architect", "plan system", "design database"
- **Agent:** architect-agent

### Bug Fixing
- **Keywords:** "debug", "fix bug", "not working", "error", "failing"
- **Agent:** debug-agent

### Code Review
- **Keywords:** "review", "check code", "audit", "assess quality"
- **Agent:** review-agent

### Testing
- **Keywords:** "test", "write tests", "coverage", "test suite"
- **Agent:** test-agent

### Refactoring
- **Keywords:** "refactor", "improve code", "clean up", "restructure"
- **Agent:** refactor-agent

### Performance
- **Keywords:** "optimize", "performance", "slow", "speed up", "benchmark"
- **Agent:** performance-agent

### Frontend Development
- **Keywords:** "UI", "interface", "frontend", "component", "accessibility"
- **Agent:** frontend-agent

### Backend Development
- **Keywords:** "API", "backend", "microservice", "database", "server"
- **Agent:** backend-agent

### Documentation
- **Keywords:** "document", "explain", "write docs", "README"
- **Agent:** explain-agent

### Questions
- **Keywords:** "how does", "what is", "explain", "why"
- **Agent:** ask-agent

### Multi-step Workflows
- **Keywords:** "coordinate", "manage", "orchestrate", "complex task"
- **Agent:** orchestrator-agent

### Planning
- **Keywords:** "plan", "PRD", "requirements", "design document"
- **Agent:** plan-agent

### Code Standards
- **Keywords:** "enforce", "standards", "coding style", "check compliance"
- **Agent:** enforcement-agent

### Migrations
- **Keywords:** "migrate", "upgrade", "update dependencies", "framework migration"
- **Agent:** migration-agent


## Instructions

1. **Load core conventions:**
   ```
   Read: .claude/conventions/core/general.md
   ```

2. **Analyze the user's request** and match to ONE agent using the routing rules above

3. **Load that agent's file:**
   ```
   Read: .claude/agents/{selected-agent}.md
   ```

4. **Follow the agent's instructions** - The agent file will tell you:
   - What workflow to load
   - What language conventions to load
   - What subagents to load
   - What skills to load
   
5. **Do NOT load anything else** until the agent file explicitly instructs you to

## Notes

- Each agent file is self-contained with all necessary references
- Language conventions are loaded by workflows, not upfront
- Skills are loaded on-demand when workflows require them
- Subagents are loaded only when the primary agent delegates to them
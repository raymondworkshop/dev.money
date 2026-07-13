---
title: "My Homelab AI Dev Platform"
source: "https://rsgm.dev/post/ai-dev-platform/"
published: "2026-06-14"
created: "2026-06-18"
description: "Self-hosting OpenCode Web for GitOps style homelab changes."
author:
  - "[[Rsgm]]"
topics:
  - tech
  - design
---

# [My Homelab AI Dev Platform](https://rsgm.dev/post/ai-dev-platform/)

## Core View
- The author set up OpenCode Web UI with Git access to simplify homelab management through a GitOps style workflow.
- OpenCode pushes changes to Git, which are then approved via Pull Requests (PRs) before GitOps deploys them.
- The platform enables persistent coding sessions synced across devices and simplifies tasks like container updates by summarizing release notes and adding healthchecks.
- The author chose OpenCode for its vendor-agnostic nature and support for major plugins, appreciating its built-in webserver and UI.
- The setup involves a VM with OpenCode, dedicated Git user access (read/write to feature branches, not direct deploy), and limited network access to actual services for security.
- The workflow involves planning, testing, iterating with OpenCode, pushing to a feature branch, PR review, merging, and then GitOps deployment.
- Migrating services to Arcane GitOps projects improved manageability, allowing for easier updates across containers, even from a mobile device.
- A key missing piece is CI feedback integration, similar to GitHub Actions, to help diagnose failing tests and other issues, which is harder with Forgejo Actions due to API limitations.

## OpenCode
- The author explored alternatives to Claude Code due to increasing token limits and sought a vendor-agnostic solution with major plugin support.
- OpenCode was selected as a preferred coding environment.
- OpenCode features a built-in webserver and web UI, which inspired the AI Dev Platform setup.
- It provides a solid development environment with a terminal, file browser, git diffs, and git worktree support for multiple coding sessions.
- The mobile web UI offers excellent question/answer popups.

## AI Dev Platform
- A simple VM was set up on a Truenas host with basic dev tooling and OpenCode's webserver as a systemd unit.
- OpenCode has its own user on the Git server with dedicated SSH keys, allowing it to clone projects and push branches but not directly to the deploy branch.
- The workflow enforces AI changes to go through PR review before deployment.
- The VM has internet access and access to the Git server but not to the actual services, minimizing the blast radius.
- The author is comfortable giving OpenCode root access on the VM for installing build tools or testing dependencies due to the limited scope.
- This setup could be scaled into a production developer platform with ephemeral containers, preinstalled tooling, access guardrails, and audit logs.

## Workflow
- 1. Plan feature/improvement in OpenCode (spec, implementation, self-reviews).
- 2. Test or verify changes if possible.
- 3. Iterate with OpenCode on disliked aspects.
- 4. OpenCode pushes changes to a feature branch.
- 5. Author opens a PR for the feature branch.
- 6. Author merges the PR upon satisfaction.
- 7. GitOps handles deployment (Arcane for Docker, GitOps plugin for Home Assistant, Cloudflare Pages worker for blog).
- Migration to Arcane GitOps projects for Docker compose stacks improved manageability and allowed for easier network updates across containers.
- The setup enables home infrastructure changes from any device, with PR review from a phone and GitOps handling deployment.
- The main limitation is the lack of CI feedback integration, as Forgejo Actions logs are not easily accessible via the public API.

## Key Takeaways
- Self-hosting an AI Dev Platform using OpenCode and GitOps for homelab management.
- Automating container updates and service maintenance with AI assistance.
- Implementing a secure workflow with AI changes behind PR reviews.
- Leveraging GitOps for streamlined deployments and easier infrastructure management.
- Identifying limitations in CI feedback integration with Forgejo.

---
**Topics**: [[tech/_index|Tech]], [[design/_index|Design]]  
**Tags**: #AI #Homelab #GitOps #OpenCode #DevPlatform

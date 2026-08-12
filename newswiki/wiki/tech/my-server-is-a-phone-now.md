---
title: "my server is a phone now"
source: "https://seg6.space/posts/phone-server/"
published: "2026-08-04"
created: "2026-08-11"
description: "rooting a CMF Phone 1 to run my personal infrastructure at home."
topics:
  - tech
  - design
---

# [my server is a phone now](https://seg6.space/posts/phone-server/)

## Core View
- The author replaced a Hetzner VPS with a rooted CMF Phone 1 (8 cores, 8GB RAM) to host personal services, including a remote browser (Surf), a finance tracker, and a screen sharing service.
- The architecture utilizes a layered approach: [[hubs/android|Android]] as the hardware abstraction layer $\rightarrow$ [[hubs/termux|Termux]] as the host environment $\rightarrow$ `runit` for service supervision $\rightarrow$ `chroot` for Debian ARM64 application compatibility.
- Performance optimization: Transitioning from `proot-distro` to a rooted `chroot` significantly reduced syscall overhead and latency, which was critical for the Chromium-based Surf workload.
- Infrastructure management is handled via [[hubs/ansible|Ansible]], treating the phone as an immutable target where releases are pinned by OCI image digests and deployed via atomic symlinks.
- Connectivity is achieved through Cloudflare Tunnels for public HTTP ingress and [[hubs/tailscale|Tailscale]] for private administrative access, allowing the server to remain reachable across different networks.

## Key Takeaways
- Modern rootable ARM64 phones provide a low-power, battery-backed (built-in UPS) alternative to VPS for light personal infrastructure.
- For latency-sensitive workloads on Android, `chroot` is superior to `PRoot` as it avoids userspace translation of filesystem and process operations.
- Using Infrastructure-as-Code (Ansible) prevents 'pet server' syndrome and ensures the setup is reproducible on other ARM64 hardware.
- Cloudflare Tunnels enable server mobility by requiring only outbound connectivity, bypassing the need for static IPs or inbound router rules.

---
**Topics**: [[tech/_index|Tech]], [[design/_index|Design]]  
**Tags**: #tech #self-hosting #arm64 #android

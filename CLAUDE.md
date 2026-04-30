# refind-nix

## Standard
This repo follows the **Daaboulex Nix Packaging Standard v1.1**.

## Repo Config
- **Package**: `refind` (NixOS module + theme factory)
- **Upstream**: sourceforge — refind 0.14.2
- **Verify**: `nix flake check --no-build`
- **Design spec**: `../nix/.ai-context/.superpowers/specs/2026-04-30-refind-nix-design.md`

## Session Protocol
1. Read `AI-progress.json` and `AI-tasks.json`
2. Run `nix flake check --no-build`
3. Pick ONE task, complete it, verify it
4. Run `/handoff` before ending

## Hard Rules
- **Verification first**: `nix flake check --no-build` before claiming done
- **Security checks are load-bearing**: never weaken mkRefindTheme fixupPhase
- **disabledModules is required**: nixpkgs imports boot.loader.refind unconditionally
- **dont_scan_dirs EFI/nixos**: always in generated refind.conf to prevent duplicate entries

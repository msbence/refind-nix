# refind-nix

Declarative rEFInd bootloader for NixOS — typed options, first-class theming, security validation.

## Features

- **Typed NixOS options** for `refind.conf` directives (no raw `extraConfig` needed)
- **First-class theme support** — themes as Nix store derivations with `mkRefindTheme`
- **Security validation** — PE binary detection, image size limits, directive whitelist, symlink rejection
- **Bug fixes** — nixpkgs #452075 (efiRemovable path), #453812 (default_selection override)
- **Safe ESP management** — tmp→fsync→rename writes, orphan file cleanup, syncfs
- **Uses `boot.loader.external`** — the official NixOS external bootloader hook

## Quick Start

```nix
# flake.nix
inputs.refind-nix.url = "github:Daaboulex/refind-nix";

# configuration.nix
{ inputs, ... }: {
  imports = [ inputs.refind-nix.nixosModules.default ];
  nixpkgs.overlays = [ inputs.refind-nix.overlays.default ];

  boot.loader.refind = {
    enable = true;
    theme = pkgs.refind-theme-minimal;
    hideUI = [ "hints" "arrows" "label" "badges" ];
    showTools = [ "shutdown" "reboot" "firmware" ];
    timeout = 5;
    maxGenerations = 10;
  };
}
```

## Custom Themes

Package any rEFInd theme with `mkRefindTheme`:

```nix
boot.loader.refind.theme = pkgs.mkRefindTheme {
  name = "my-theme";
  src = fetchFromGitHub { owner = "..."; repo = "..."; rev = "..."; hash = "..."; };
  description = "My custom rEFInd theme";
};
```

Security checks run automatically: PE binaries, oversized images, path traversal, symlinks, and unknown directives are all rejected at build time.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable` | bool | false | Enable rEFInd boot manager |
| `package` | package | pkgs.refind | rEFInd package |
| `timeout` | int | 10 | Boot timeout in seconds |
| `maxGenerations` | int/null | 50 | Max generations in menu |
| `defaultSelection` | str/null | null | Default boot entry |
| `efiInstallAsRemovable` | bool | !canTouchEfiVariables | Install to fallback EFI path |
| `theme` | path/null | null | Theme directory (Nix store path) |
| `hideUI` | list of enum | [] | UI elements to hide |
| `showTools` | list of enum | [shutdown reboot firmware] | Second-row tools |
| `bannerScale` | enum | fillscreen | Banner scaling |
| `textOnly` | bool | false | Text-only mode |
| `extraConfig` | lines | "" | Raw config lines |
| `additionalFiles` | attrsOf path | {} | Extra files for ESP |

## License

MIT

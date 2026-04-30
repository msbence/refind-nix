# refind — declarative rEFInd bootloader module for NixOS.
{
  self,
}:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.boot.loader.refind;
  efi = config.boot.loader.efi;

  refindInstallConfig = pkgs.writeText "refind-install.json" (
    builtins.toJSON {
      nixPath = config.nix.package;
      efiBootMgrPath = pkgs.efibootmgr;
      refindPath = cfg.package;
      efiMountPoint = efi.efiSysMountPoint;
      fileSystems = config.fileSystems;
      luksDevices = config.boot.initrd.luks.devices;
      canTouchEfiVariables = efi.canTouchEfiVariables;
      efiRemovable = cfg.efiInstallAsRemovable;
      maxGenerations = if cfg.maxGenerations == null then 0 else cfg.maxGenerations;
      hostArchitecture = pkgs.stdenv.hostPlatform.parsed.cpu;
      timeout = if config.boot.loader.timeout != null then config.boot.loader.timeout else cfg.timeout;
      extraConfig = cfg.extraConfig;
      additionalFiles = cfg.additionalFiles;
      defaultSelection = cfg.defaultSelection;
      hideUI = cfg.hideUI;
      showTools = cfg.showTools;
      bannerScale = cfg.bannerScale;
      textOnly = cfg.textOnly;
      theme = if cfg.theme != null then toString cfg.theme else null;
    }
  );

  refindInstaller = pkgs.replaceVarsWith {
    src = ../installer/refind-install.py;
    isExecutable = true;
    replacements = {
      python3 = pkgs.python3.withPackages (ps: [ ps.psutil ]);
      configPath = refindInstallConfig;
    };
  };
in
{
  disabledModules = [ "system/boot/loader/refind/refind.nix" ];

  options.boot.loader.refind = {
    enable = lib.mkEnableOption "rEFInd boot manager";

    package = lib.mkPackageOption pkgs "refind" { };

    timeout = lib.mkOption {
      type = lib.types.int;
      default = 10;
      description = "Timeout in seconds before auto-boot.";
    };

    maxGenerations = lib.mkOption {
      type = lib.types.nullOr lib.types.int;
      default = 50;
      description = "Maximum generations in boot menu. null = unlimited.";
    };

    defaultSelection = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Default boot entry. null = most recent. Only written if set.";
    };

    efiInstallAsRemovable = lib.mkEnableOption null // {
      default = !efi.canTouchEfiVariables;
      defaultText = lib.literalExpression "!config.boot.loader.efi.canTouchEfiVariables";
      description = "Install to EFI/BOOT/bootx64.efi. Required when NVRAM writes fail.";
    };

    theme = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Path to rEFInd theme directory in the Nix store.";
      example = lib.literalExpression ''"''${pkgs.refind-theme-minimal}"'';
    };

    hideUI = lib.mkOption {
      type = lib.types.listOf (
        lib.types.enum [
          "banner"
          "label"
          "singleuser"
          "safemode"
          "hwtest"
          "arrows"
          "hints"
          "editor"
          "badges"
          "all"
        ]
      );
      default = [ ];
      description = "UI elements to hide.";
    };

    showTools = lib.mkOption {
      type = lib.types.listOf (
        lib.types.enum [
          "shell"
          "gptsync"
          "apple_recovery"
          "mok_tool"
          "about"
          "exit"
          "shutdown"
          "reboot"
          "firmware"
          "hidden_tags"
          "netboot"
        ]
      );
      default = [
        "shutdown"
        "reboot"
        "firmware"
      ];
      description = "Tool entries in the second row. Order controls display order.";
    };

    bannerScale = lib.mkOption {
      type = lib.types.enum [
        "noscale"
        "fillscreen"
      ];
      default = "fillscreen";
      description = "Banner scaling mode.";
    };

    textOnly = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Text-only mode. Disables all theming.";
    };

    extraConfig = lib.mkOption {
      type = lib.types.lines;
      default = "";
      description = "Raw lines prepended to refind.conf. Bypasses directive validation.";
    };

    additionalFiles = lib.mkOption {
      type = lib.types.attrsOf lib.types.path;
      default = { };
      description = "Extra files to copy to the ESP rEFInd directory.";
      example = lib.literalExpression ''{ "tools/memtest.efi" = "''${pkgs.memtest86plus.efi}/BOOTX64.efi"; }'';
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = !config.boot.loader.systemd-boot.enable;
        message = "refind-nix: rEFInd and systemd-boot cannot both be enabled.";
      }
      {
        assertion = !config.boot.loader.grub.enable;
        message = "refind-nix: rEFInd and GRUB cannot both be enabled.";
      }
      {
        assertion = pkgs.stdenv.hostPlatform.isEfi;
        message = "refind-nix: rEFInd requires a UEFI platform.";
      }
      {
        assertion = !(cfg.efiInstallAsRemovable && efi.canTouchEfiVariables);
        message = "refind-nix: efiInstallAsRemovable and canTouchEfiVariables cannot both be true.";
      }
    ];

    boot.loader.external = {
      enable = true;
      installHook = refindInstaller;
    };
  };
}

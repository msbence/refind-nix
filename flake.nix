{
  description = "Declarative rEFInd bootloader for NixOS — typed options, themes, security validation";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    git-hooks = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      git-hooks,
    }:
    let
      supportedSystems = [ "x86_64-linux" ];
      forEachSystem = nixpkgs.lib.genAttrs supportedSystems;
      pkgsFor = system: import nixpkgs { localSystem.system = system; };
    in
    {
      nixosModules.default = import ./modules/refind.nix { inherit self; };

      overlays.default = import ./overlays/default.nix { inherit self; };

      packages = forEachSystem (
        system:
        let
          pkgs = (pkgsFor system).extend self.overlays.default;
        in
        {
          refind-theme-minimal = pkgs.refind-theme-minimal;
          default = pkgs.refind-theme-minimal;
        }
      );

      formatter = forEachSystem (system: (pkgsFor system).nixfmt-rfc-style);

      checks = forEachSystem (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          pre-commit-check = git-hooks.lib.${system}.run {
            src = self;
            hooks.nixfmt-rfc-style.enable = true;
          };
        }
      );

      devShells = forEachSystem (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = pkgs.mkShell {
            inherit (self.checks.${system}.pre-commit-check) shellHook;
            buildInputs = self.checks.${system}.pre-commit-check.enabledPackages;
            packages = with pkgs; [ nil ];
          };
        }
      );
    };
}

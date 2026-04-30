# checks — eval test + pre-commit hooks.
{
  self,
  pkgs,
  lib,
  git-hooks,
  system,
}:

{
  pre-commit-check = git-hooks.lib.${system}.run {
    src = self;
    hooks.nixfmt-rfc-style.enable = true;
  };
}

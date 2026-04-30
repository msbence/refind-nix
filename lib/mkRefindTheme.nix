# mkRefindTheme — factory for rEFInd theme derivations with security validation.
{
  lib,
  stdenvNoCC,
  fetchFromGitHub,
}:

{
  name,
  src,
  version ? "unstable",
  variant ? null,
  themeDir ? ".",
  description ? "rEFInd theme",
  license ? lib.licenses.mit,
  maintainers ? [ ],
}:

stdenvNoCC.mkDerivation {
  pname = "refind-theme-${name}${lib.optionalString (variant != null) "-${variant}"}";
  inherit version src;

  dontBuild = true;
  dontFixup = false;

  installPhase = ''
    runHook preInstall

    srcDir="${themeDir}"
    ${lib.optionalString (variant != null) ''srcDir="${variant}"''}

    if [ ! -f "$srcDir/theme.conf" ]; then
      echo "ERROR: theme.conf not found in $srcDir" >&2
      exit 1
    fi

    install -d $out
    cp "$srcDir/theme.conf" $out/

    for f in background.png selection_big.png selection_small.png; do
      [ -f "$srcDir/$f" ] && cp "$srcDir/$f" $out/
    done
    [ -d "$srcDir/icons" ] && cp -r "$srcDir/icons" $out/
    [ -d "$srcDir/fonts" ] && cp -r "$srcDir/fonts" $out/

    runHook postInstall
  '';

  fixupPhase = ''
    # SECURITY 1: reject PE binaries (MZ magic 0x4d5a)
    find $out -type f | while IFS= read -r f; do
      if [ "$(head -c 2 "$f" 2>/dev/null | od -An -tx1 | tr -d ' ')" = "4d5a" ]; then
        echo "SECURITY: PE binary detected: $f" >&2
        exit 1
      fi
    done

    # SECURITY 2: reject .efi extensions
    if find $out \( -name '*.efi' -o -name '*.EFI' \) | grep -q .; then
      echo "SECURITY: EFI file extension in theme" >&2
      exit 1
    fi

    # SECURITY 3: size limits on ALL image types (LogoFAIL mitigation)
    if find $out \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.bmp' -o -name '*.icns' \) -size +5M | grep -q .; then
      echo "SECURITY: image file > 5MB detected" >&2
      exit 1
    fi

    # SECURITY 4: icons/ extension whitelist — only .png and .bmp
    if [ -d "$out/icons" ]; then
      if find "$out/icons" -type f ! \( -name '*.png' -o -name '*.bmp' \) | grep -q .; then
        echo "SECURITY: non-image file in icons/" >&2
        exit 1
      fi
    fi

    # SECURITY 5: reject symlinks
    if find $out -type l | grep -q .; then
      echo "SECURITY: symlink in theme" >&2
      exit 1
    fi

    # SECURITY 6: theme.conf directive whitelist
    ALLOWED='banner|banner_scale|icons_dir|selection_big|selection_small|font|hideui|showtools|textonly|use_graphics_for|big_icon_size|small_icon_size|icon_delay|resolution'
    if grep -vE "^\s*$|^\s*#|^\s*(''${ALLOWED})\b" "$out/theme.conf" | grep -q .; then
      echo "SECURITY: unknown directive in theme.conf:" >&2
      grep -vE "^\s*$|^\s*#|^\s*(''${ALLOWED})\b" "$out/theme.conf" >&2
      exit 1
    fi

    # SECURITY 7: reject include (path traversal)
    if grep -qiE '^\s*include\b' "$out/theme.conf"; then
      echo "SECURITY: include directive in theme.conf" >&2
      exit 1
    fi

    # SECURITY 8: reject path traversal in directive values
    if grep -E '\.\.\/' "$out/theme.conf" | grep -q .; then
      echo "SECURITY: path traversal in directive value" >&2
      exit 1
    fi
  '';

  meta = {
    inherit description license maintainers;
    platforms = lib.platforms.linux;
  };
}

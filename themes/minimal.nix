# minimal — rEFInd-minimal theme (2.2k GitHub stars).
{
  mkRefindTheme,
  fetchFromGitHub,
}:

mkRefindTheme {
  name = "minimal";
  version = "unstable-2024-01-15";
  src = fetchFromGitHub {
    owner = "EvanPurkhiser";
    repo = "rEFInd-minimal";
    rev = "2c7a4aa67707a669e5a38e8bd4456c09a5477f38";
    hash = "sha256-8FxOFSI54H5SnxoDNllofc8bJ0TiOnjbtQp/GWNQf6w=";
  };
  description = "Clean minimal rEFInd theme";
}

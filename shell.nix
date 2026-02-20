{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python3
    python3Packages.requests
    python3Packages.beautifulsoup4
    python3Packages.feedgen

    basedpyright
    black
  ];
}

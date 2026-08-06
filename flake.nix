{
  description = "GitHub Backup Deck - graphical GitHub backup manager for Wayland";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          github-backup-deck = pkgs.callPackage ./nix/package.nix { };
        in
        {
          inherit github-backup-deck;
          default = github-backup-deck;
        }
      );

      apps = forAllSystems (system: rec {
        github-backup-deck = {
          type = "app";
          program = "${self.packages.${system}.github-backup-deck}/bin/github-backup-deck";
        };
        default = github-backup-deck;
      });

      checks = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          lib = pkgs.lib;
          package = self.packages.${system}.github-backup-deck;
          source = lib.cleanSource ./.;
          python = pkgs.python3.withPackages (pythonPackages: with pythonPackages; [
            pygobject3
            pycairo
            pytest
            mypy
          ]);
          closure = pkgs.closureInfo { rootPaths = [ package ]; };
          baseChecks = {
            inherit package;

            python-tests = pkgs.runCommand "github-backup-deck-python-tests" {
              nativeBuildInputs = [
                python
                pkgs.ruff
              ];
            } ''
              cp -r ${source} source
              chmod -R u+w source
              cd source
              export HOME="$TMPDIR/home"
              export XDG_CONFIG_HOME="$TMPDIR/config"
              export XDG_STATE_HOME="$TMPDIR/state"
              export XDG_RUNTIME_DIR="$TMPDIR/runtime"
              mkdir -p "$HOME" "$XDG_RUNTIME_DIR"
              chmod 700 "$XDG_RUNTIME_DIR"
              export PYTHONPATH="$PWD/src"
              python -m compileall -q src
              pytest -q
              ruff check .
              mypy src
              touch "$out"
            '';

            cli-smoke = pkgs.runCommand "github-backup-deck-cli-smoke" {
              nativeBuildInputs = [ package ];
            } ''
              export HOME="$TMPDIR/home"
              export XDG_RUNTIME_DIR="$TMPDIR/runtime"
              export XDG_CONFIG_HOME="$TMPDIR/config"
              export XDG_STATE_HOME="$TMPDIR/state"
              export XDG_CACHE_HOME="$TMPDIR/cache"
              mkdir -p "$HOME" "$XDG_RUNTIME_DIR"
              chmod 700 "$XDG_RUNTIME_DIR"
              github-backup-deck --help >/dev/null
              github-backup-deck doctor | grep -q '"ok": true'
              github-backup-deck status | grep -q 'never-run'
              github-backup-deck probe "$TMPDIR/backup" | grep -q '"ok": true'
              touch "$out"
            '';

            runtime-closure-policy = pkgs.runCommand "github-backup-deck-runtime-closure-policy" { } ''
              if grep -E '/[^/]*(setuptools|wheel|linux-headers|gcc-wrapper|binutils-wrapper|pytest|mypy|ruff)-' \
                ${closure}/store-paths; then
                echo "forbidden build dependency in runtime closure" >&2
                exit 1
              fi
              if grep -R -E '/nix/store/[^/]+-(glib|gobject-introspection|pygobject)-[^/]+-dev' \
                ${package}/bin ${package}/libexec; then
                echo "development output leaked into launchers" >&2
                exit 1
              fi
              touch "$out"
            '';
          };
        in
        baseChecks
        // lib.optionalAttrs (system == "x86_64-linux") {
          nixos-module = import ./nix/tests/nixos-module.nix {
            inherit pkgs package;
            module = self.nixosModules.default;
          };
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python3.withPackages (pythonPackages: with pythonPackages; [
            pygobject3
            pycairo
            pytest
            mypy
            setuptools
            wheel
          ]);
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.gtk3
              pkgs.gtk-layer-shell
              pkgs.glib
              pkgs.gdk-pixbuf
              pkgs.pango
              pkgs.at-spi2-core
              pkgs.gobject-introspection
              pkgs.git
              pkgs.git-lfs
              pkgs.gh
              pkgs.sqlite
              pkgs.ruff
              pkgs.pyright
              pkgs.nixfmt-rfc-style
            ];
            shellHook = ''
              export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
              export GI_TYPELIB_PATH="${pkgs.lib.makeSearchPath "lib/girepository-1.0" [
                pkgs.gobject-introspection
                pkgs.glib
                pkgs.gtk3
                pkgs.gtk-layer-shell
                pkgs.gdk-pixbuf
                pkgs.pango
                pkgs.at-spi2-core
              ]}''${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
              echo "GitHub Backup Deck dev shell"
            '';
          };
        }
      );

      nixosModules.github-backup-deck = import ./nix/module.nix { inherit self; };
      nixosModules.default = self.nixosModules.github-backup-deck;
      homeManagerModules.github-backup-deck = import ./nix/home-manager-module.nix { inherit self; };
      homeManagerModules.default = self.homeManagerModules.github-backup-deck;
    };
}

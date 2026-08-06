{
  lib,
  stdenvNoCC,
  closureInfo,
  python3,
  gtk3,
  gtk-layer-shell,
  glib,
  gdk-pixbuf,
  pango,
  at-spi2-core,
  fontconfig,
  gsettings-desktop-schemas,
  shared-mime-info,
  hicolor-icon-theme,
  gobject-introspection,
  coreutils,
  git,
  git-lfs,
  gh,
  sqlite,
  wl-clipboard,
  xdg-utils,
  libnotify,
  dconf,
}:

let
  python = python3.withPackages (
    pythonPackages: with pythonPackages; [
      pygobject3
      pycairo
    ]
  );
  typelibSourceClosure = closureInfo {
    rootPaths = [
      python
      glib
      gdk-pixbuf
      pango
      at-spi2-core
      gtk3
      gtk-layer-shell
      gobject-introspection
    ];
  };
  runtimeTypelibs = stdenvNoCC.mkDerivation {
    pname = "github-backup-deck-runtime-typelibs";
    version = "1";
    dontUnpack = true;
    installPhase = ''
      destination="$out/lib/girepository-1.0"
      mkdir -p "$destination"
      while IFS= read -r source; do
        [ -e "$source" ] || continue
        while IFS= read -r typelib; do
          install -m644 "$typelib" "$destination/$(basename "$typelib")"
        done < <(find -L "$source" -type f -name '*.typelib' -print)
      done < ${typelibSourceClosure}/store-paths
      for required in Gtk-3.0 Gdk-3.0 GLib-2.0 Gio-2.0 GtkLayerShell-0.1; do
        test -f "$destination/$required.typelib" || {
          echo "missing runtime typelib: $required" >&2
          exit 1
        }
      done
    '';
  };
  schemaSourceClosure = closureInfo {
    rootPaths = [
      glib
      gtk3
      gsettings-desktop-schemas
    ];
  };
  runtimeSchemas = stdenvNoCC.mkDerivation {
    pname = "github-backup-deck-runtime-schemas";
    version = "1";
    dontUnpack = true;
    installPhase = ''
      destination="$out/share/glib-2.0/schemas"
      mkdir -p "$destination"
      while IFS= read -r source; do
        schema_dir="$source/share/glib-2.0/schemas"
        [ -d "$schema_dir" ] || continue
        find -L "$schema_dir" -maxdepth 1 -type f \
          \( -name '*.gschema.xml' -o -name '*.gschema.override' \) \
          -exec cp -f {} "$destination/" \;
      done < ${schemaSourceClosure}/store-paths
      test -n "$(find "$destination" -maxdepth 1 -name '*.gschema.xml' -print -quit)" || {
        echo "no GSettings schemas were collected" >&2
        exit 1
      }
      ${glib.bin}/bin/glib-compile-schemas --strict "$destination"
      test -f "$destination/gschemas.compiled"
      ${glib.bin}/bin/gsettings --schemadir "$destination" list-schemas \
        | grep -qx 'org.gtk.Settings.FileChooser'
    '';
  };
  typelibPath = lib.makeSearchPath "lib/girepository-1.0" [
    runtimeTypelibs
    glib
    gtk3
    gtk-layer-shell
    gdk-pixbuf
  ];
  dataPath = lib.makeSearchPath "share" [
    runtimeSchemas
    glib
    gtk3
    gsettings-desktop-schemas
    shared-mime-info
    hicolor-icon-theme
  ];
  runtimePath = lib.makeBinPath [
    coreutils
    git
    git-lfs
    gh
    sqlite
    wl-clipboard
    xdg-utils
    libnotify
    dconf
  ];
  pixbufLoaders = "${gdk-pixbuf}/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache";
  fontconfigFile = "${fontconfig.out}/etc/fonts/fonts.conf";
in
stdenvNoCC.mkDerivation {
  pname = "github-backup-deck";
  version = "0.3.0";
  src = lib.cleanSource ../.;
  strictDeps = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    libexec="$out/libexec/github-backup-deck"
    mkdir -p "$libexec" "$out/bin" "$out/share/applications" \
      "$out/share/icons/hicolor/scalable/apps" "$out/share/doc/github-backup-deck"
    cp -r src/github_backup_deck "$libexec/"
    find "$libexec" -type f -name '*.py' -exec sed -i '1{/^#!/d;}' {} +

    make_launcher() {
      name="$1"
      module="$2"
      cat > "$out/bin/$name" <<PY
#!${python.interpreter}
import os
import runpy
import sys

sys.dont_write_bytecode = True


def prepend(name: str, value: str) -> None:
    current = os.environ.get(name)
    os.environ[name] = value if not current else f"{value}:{current}"

prepend("GI_TYPELIB_PATH", "${typelibPath}")
prepend("XDG_DATA_DIRS", "${dataPath}")
prepend("PATH", "${runtimePath}")
os.environ.setdefault("GSETTINGS_SCHEMA_DIR", "${runtimeSchemas}/share/glib-2.0/schemas")
os.environ.setdefault("GDK_PIXBUF_MODULE_FILE", "${pixbufLoaders}")
os.environ.setdefault("FONTCONFIG_FILE", "${fontconfigFile}")
os.environ.setdefault("GH_BROWSER", "${xdg-utils}/bin/xdg-open")
os.environ.setdefault("GITHUB_BACKUP_DECK_NOOP_BROWSER", "${coreutils}/bin/true")
sys.path.insert(0, "$libexec")
runpy.run_module("$module", run_name="__main__")
PY
      chmod +x "$out/bin/$name"
    }

    make_launcher github-backup-deck github_backup_deck
    make_launcher github-backup-deck-daemon github_backup_deck.daemon
    make_launcher github-backup-deck-overview github_backup_deck.gui.overview

    install -m644 data/github-backup-deck.desktop "$out/share/applications/"
    install -m644 data/github-backup-deck-overview.desktop "$out/share/applications/"
    install -m644 data/github-backup-deck.svg \
      "$out/share/icons/hicolor/scalable/apps/github-backup-deck.svg"
    install -m644 README.md NOTICE.md LICENSE "$out/share/doc/github-backup-deck/"
    runHook postInstall
  '';

  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    export HOME="$TMPDIR/home"
    export XDG_RUNTIME_DIR="$TMPDIR/runtime"
    export XDG_CONFIG_HOME="$TMPDIR/config"
    export XDG_STATE_HOME="$TMPDIR/state"
    export XDG_CACHE_HOME="$TMPDIR/cache"
    mkdir -p "$HOME" "$XDG_RUNTIME_DIR"
    chmod 700 "$XDG_RUNTIME_DIR"

    "$out/bin/github-backup-deck" --help >/dev/null
    "$out/bin/github-backup-deck" doctor > doctor.json
    grep -q '"ok": true' doctor.json
    grep -q '"gtk_file_chooser_schema": true' doctor.json
    "$out/bin/github-backup-deck" status | grep -q '"state": "offline"'
    "$out/bin/github-backup-deck" probe "$TMPDIR/backup" | grep -q '"ok": true'
    test -x "$out/bin/github-backup-deck-daemon"
    test -x "$out/bin/github-backup-deck-overview"
    test -x "${xdg-utils}/bin/xdg-open"
    test -x "${wl-clipboard}/bin/wl-copy"
    test -x "${libnotify}/bin/notify-send"
    test -f "${runtimeSchemas}/share/glib-2.0/schemas/gschemas.compiled"
    test -f "$out/share/applications/github-backup-deck.desktop"
    test -f "$out/share/applications/github-backup-deck-overview.desktop"
    test -f "$out/share/icons/hicolor/scalable/apps/github-backup-deck.svg"

    if grep -R -E '/usr/bin/python|/usr/bin/env|/nix/store/[^/]+-(glib|gobject-introspection|pygobject)-[^/]+-dev' \
      "$out/bin" "$out/libexec/github-backup-deck"; then
      echo "non-hermetic path found in GitHub Backup Deck output" >&2
      exit 1
    fi
    runHook postInstallCheck
  '';

  meta = {
    description = "GIF Picker-family layer-shell GitHub backup manager for Wayland";
    homepage = "https://github.com/madebycli/git-backup";
    license = lib.licenses.mit;
    mainProgram = "github-backup-deck";
    platforms = lib.platforms.linux;
  };
}

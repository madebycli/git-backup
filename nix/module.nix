{ self }:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.programs.github-backup-deck;
  filteredPackage = pkgs.symlinkJoin {
    name = "github-backup-deck-configured";
    paths = [ cfg.package ];
    postBuild = ''
      ${lib.optionalString (!cfg.enableDesktopEntry) ''
        rm -f "$out/share/applications/github-backup-deck.desktop"
      ''}
      ${lib.optionalString (!cfg.enableOverviewLauncher) ''
        rm -f "$out/share/applications/github-backup-deck-overview.desktop"
      ''}
    '';
  };
in
{
  options.programs.github-backup-deck = {
    enable = lib.mkEnableOption "GitHub Backup Deck";
    package = lib.mkOption {
      type = lib.types.package;
      default = self.packages.${pkgs.system}.github-backup-deck;
      defaultText = lib.literalExpression "self.packages.${pkgs.system}.github-backup-deck";
      description = "GitHub Backup Deck package to install.";
    };
    enableDesktopEntry = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Install the main desktop launcher.";
    };
    enableOverviewLauncher = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Install the layer-shell overview launcher.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ filteredPackage ];
  };
}
